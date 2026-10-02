"""STAGE 9 -- LLM generation.

Every call to a language model in this project goes through this module.
Keeping it in one place means:

* the API key is read once, on the server, and never leaves it;
* every failure mode maps to a friendly `AppError` instead of a stack trace;
* structured extraction (resume parsing, match explanations, interview
  questions) uses **structured outputs** -- we hand the model a JSON Schema and
  the API guarantees the response validates against it, so there is no fragile
  "please respond with JSON" prompt parsing.

**Two providers, one interface.** The same pluggable pattern the embedder and
the vector store already use:

    GroqLLM       -- open models on Groq's fast inference. Generous free tier.
    AnthropicLLM  -- optional paid alternative.

Everything above this module (`generation.py`, every service) calls
`complete()` / `complete_json()` and never knows which one is running.

The retrieval half of RAG uses no LLM at all -- the model only ever sees the
chunks the retriever selected.
"""

import json
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import Settings
from app.core.errors import LLMError, LLMNotConfigured
from app.core.logging import get_logger

logger = get_logger(__name__)

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

# Effort maps onto each provider's own control. Groq's open models take
# OpenAI-style reasoning effort, which has only three levels.
#
# Deliberately mapped one step DOWN from the Anthropic scale: reasoning tokens
# come out of the same per-minute budget as the answer, so "high" everywhere
# starves the response on the free tier. Medium reasoning on gpt-oss-120b still
# produces good analysis.
_GROQ_EFFORT = {
    "low": "low",
    "medium": "low",
    "high": "medium",
    "xhigh": "high",
    "max": "high",
}


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------
def looks_like_real_key(value: Optional[str]) -> bool:
    """Is this an actual key, or the placeholder from .env.example?

    Copying `.env.example` to `.env` and forgetting to edit it is the single
    most common setup mistake. Without this check the placeholder gets sent to
    the API and the user sees a confusing rejection instead of "you haven't
    added your key yet".
    """
    if not value:
        return False
    value = value.strip().strip("\"'")
    if not value or value.endswith("...") or "your-api-key" in value.lower():
        return False
    return len(value) > 20


# Kept as a private alias so older imports keep working.
_looks_like_real_key = looks_like_real_key


def _parse_json(raw: str) -> Dict[str, Any]:
    """Parse a JSON response, tolerating code fences and stray prose."""
    raw = (raw or "").strip()
    if not raw:
        raise LLMError("The AI returned an empty response.", hint="Try again.")

    fenced = _JSON_FENCE.search(raw)
    if fenced:
        raw = fenced.group(1).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Last resort: grab the outermost {...} block.
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    logger.error("Could not parse JSON from model output: %s", raw[:400])
    raise LLMError(
        "The AI returned a response we couldn't read.",
        hint="Try running the analysis again.",
    )


def _billing_error(detail: str, code: str = "") -> Optional[LLMError]:
    """Out-of-credit errors deserve their own message.

    "The request was rejected" sends people hunting for a bug in their
    documents when the actual fix is a billing page.

    Note the `code` check comes first and can veto. Groq's *rate limit* message
    ends with "Upgrade to Dev Tier today at https://console.groq.com/settings/
    billing" -- so a naive substring search for "billing" classifies a
    rate limit as an empty wallet, which is a confusing and wrong thing to tell
    someone. The provider's own error code is the reliable signal.
    """
    if code and "rate_limit" in code:
        return None

    lowered = detail.lower()
    if any(
        marker in lowered
        for marker in ("credit balance", "insufficient_quota", "billing to upgrade")
    ):
        return LLMError(
            "Your account has no credits left for this provider.",
            hint=(
                "Add credits with your provider, or switch provider by setting "
                "LLM_PROVIDER in backend/.env. Upload, indexing and the RAG "
                "Inspector keep working without credits."
            ),
            code="llm_out_of_credits",
            status_code=402,
        )
    return None


def _groq_error_parts(exc: Exception) -> Tuple[str, str]:
    """Return `(message, code)` from a Groq API error body."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        error = body["error"]
        return str(error.get("message", "") or ""), str(error.get("code", "") or "")
    return "", ""


_WAIT_HINT = re.compile(r"try again in ([\d.]+)\s*s", re.IGNORECASE)


def _groq_retry_after(exc: Exception) -> Optional[float]:
    """How long to wait before retrying, or None if this isn't retryable.

    Groq puts the exact wait in the `retry-after` header, and sometimes in the
    message text. Both are capped so a request can't hang for minutes.
    """
    status = getattr(exc, "status_code", None)
    detail, code = _groq_error_parts(exc)
    if status not in (413, 429) and "rate_limit" not in code:
        return None

    response = getattr(exc, "response", None)
    header = None
    if response is not None:
        try:
            header = response.headers.get("retry-after")
        except Exception:
            header = None

    for candidate in (header, (_WAIT_HINT.search(detail) or [None, None])[1]):
        try:
            if candidate is not None:
                return max(1.0, min(float(candidate) + 1.0, 30.0))
        except (TypeError, ValueError):
            continue

    # No explicit hint: the per-minute bucket refills continuously, so a short
    # wait is usually enough.
    return 12.0


# --------------------------------------------------------------------------
# Provider interface
# --------------------------------------------------------------------------
class BaseLLM:
    """What every provider must offer. Callers only ever see this."""

    provider = "base"
    display_name = "Base"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def compact_output(self) -> bool:
        """Should callers ask for fewer items than they otherwise would?

        A provider with a small per-minute token budget can't return twenty
        interview questions with sample answers in one response -- the JSON is
        cut off mid-object and the whole call fails. Services that generate a
        *list* consult this and scale their request down, which is far better
        than an error.
        """
        return False

    @property
    def model(self) -> str:
        raise NotImplementedError

    def complete(
        self,
        *,
        system: str,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        effort: Optional[str] = None,
    ) -> str:
        raise NotImplementedError

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: Dict[str, Any],
        max_tokens: Optional[int] = None,
        effort: Optional[str] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def info(self) -> dict:
        return {"provider": self.provider, "name": self.display_name, "model": self.model}


# --------------------------------------------------------------------------
# Provider 2: Anthropic (optional, paid)
# --------------------------------------------------------------------------
class AnthropicLLM(BaseLLM):
    provider = "anthropic"
    display_name = "Anthropic"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        try:
            import anthropic
        except ImportError as exc:
            raise LLMNotConfigured(
                "The `anthropic` package isn't installed on the server.",
                hint="Run `pip install anthropic` in the backend environment.",
            ) from exc

        key = _resolve_key(settings, "anthropic")
        if not key:
            raise LLMNotConfigured(
                "No Anthropic API key is configured.",
                hint="Add ANTHROPIC_API_KEY to backend/.env and restart the backend.",
            )
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=key)

    @property
    def model(self) -> str:
        return self._settings.llm_model

    # -- error mapping -----------------------------------------------------
    def _provider_message(self, exc: Exception) -> str:
        """Pull the human sentence out of an API error, never the raw JSON.

        The SDK's `.message` is the whole wire payload -- dumping that into the
        UI is exactly the stack-trace-in-the-browser problem this app avoids.
        """
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                return error["message"]
            if isinstance(body.get("message"), str):
                return body["message"]
        return ""

    def _map_error(self, exc: Exception) -> LLMError:
        anthropic = self._anthropic

        if isinstance(exc, anthropic.AuthenticationError):
            return LLMError(
                "The Anthropic API key was rejected.",
                hint="Check ANTHROPIC_API_KEY in backend/.env, then restart the backend.",
                code="llm_auth_failed",
                status_code=401,
            )
        if isinstance(exc, anthropic.PermissionDeniedError):
            return LLMError(
                "This API key isn't allowed to use that model.",
                hint="Check your Anthropic console permissions.",
                code="llm_permission_denied",
                status_code=403,
            )
        if isinstance(exc, anthropic.RateLimitError):
            return LLMError(
                "Too many requests to the AI model right now.",
                hint="Wait about a minute and try again.",
                code="llm_rate_limited",
                status_code=429,
            )
        if isinstance(exc, anthropic.NotFoundError):
            return LLMError(
                "The configured model doesn't exist.",
                hint="Check LLM_MODEL in backend/.env.",
                code="llm_model_not_found",
                status_code=404,
            )
        if isinstance(exc, anthropic.APIConnectionError):
            return LLMError(
                "Couldn't reach the AI model -- the network request failed.",
                hint="Check your internet connection and try again.",
                code="llm_unreachable",
            )
        if isinstance(exc, anthropic.APIStatusError):
            if exc.status_code >= 500:
                return LLMError(
                    "The AI service is having trouble right now.",
                    hint="Try again in a few seconds.",
                    code="llm_server_error",
                )
            detail = self._provider_message(exc)
            billing = _billing_error(detail)
            if billing:
                return billing
            return LLMError(
                "The AI request was rejected.",
                hint=detail or "Try shortening your documents and running it again.",
                code="llm_bad_request",
                status_code=400,
            )
        return LLMError()

    @staticmethod
    def _text_from(response) -> str:
        parts = [b.text for b in response.content if getattr(b, "type", "") == "text"]
        return "\n".join(parts).strip()

    def _guard(self, response) -> None:
        if getattr(response, "stop_reason", None) == "refusal":
            raise LLMError(
                "The AI declined to answer that request.",
                hint="Rephrase your question and try again.",
                code="llm_refusal",
            )
        if getattr(response, "stop_reason", None) == "max_tokens":
            logger.warning("Response hit max_tokens; output may be truncated.")

    # -- calls -------------------------------------------------------------
    def complete(self, *, system, messages, max_tokens=None, effort=None) -> str:
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self._settings.llm_max_tokens,
                system=system,
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": effort or self._settings.llm_effort},
            )
        except TypeError:
            # An older anthropic SDK without output_config / adaptive thinking.
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self._settings.llm_max_tokens,
                system=system,
                messages=messages,
            )
        except Exception as exc:
            logger.exception("Anthropic text call failed")
            raise self._map_error(exc) from exc

        self._guard(response)
        return self._text_from(response)

    def complete_json(self, *, system, user, schema, max_tokens=None, effort=None):
        messages = [{"role": "user", "content": user}]
        output_config = {
            "effort": effort or self._settings.llm_extraction_effort,
            "format": {"type": "json_schema", "schema": schema},
        }
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self._settings.llm_max_tokens,
                system=system,
                messages=messages,
                thinking={"type": "adaptive"},
                output_config=output_config,
            )
        except TypeError:
            logger.warning(
                "Installed anthropic SDK doesn't support output_config; "
                "falling back to prompt-instructed JSON."
            )
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self._settings.llm_max_tokens,
                system=system
                + "\n\nRespond with a single JSON object and nothing else. "
                "It must match this JSON Schema:\n" + json.dumps(schema),
                messages=messages,
            )
        except Exception as exc:
            logger.exception("Anthropic JSON call failed")
            raise self._map_error(exc) from exc

        self._guard(response)
        return _parse_json(self._text_from(response))


# --------------------------------------------------------------------------
# Provider 1: Groq (default; open models, OpenAI-compatible surface)
# --------------------------------------------------------------------------
class GroqLLM(BaseLLM):
    """Groq's OpenAI-compatible chat completions API.

    Two differences from Anthropic worth knowing:

    * The system prompt is the first message rather than a separate field.
    * Structured output is `response_format={"type": "json_schema", ...}` with
      the schema nested one level deeper, and `strict: true` requires that
      every property appear in `required` with `additionalProperties: false`
      -- which the schemas in `prompts.py` already satisfy.
    """

    provider = "groq"
    display_name = "Groq"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        try:
            import groq
        except ImportError as exc:
            raise LLMNotConfigured(
                "The `groq` package isn't installed on the server.",
                hint="Run `pip install groq` in the backend environment.",
            ) from exc

        key = _resolve_key(settings, "groq")
        if not key:
            raise LLMNotConfigured(
                "No Groq API key is configured.",
                hint="Add GROQ_API_KEY to backend/.env and restart the backend.",
            )
        self._groq = groq
        self._client = groq.Groq(api_key=key)

    @property
    def model(self) -> str:
        return self._settings.groq_model

    @property
    def compact_output(self) -> bool:
        # Anything at or below the free tier's 8k/min needs smaller responses.
        return self._settings.groq_tpm_budget <= 12000

    def _map_error(self, exc: Exception) -> LLMError:
        groq = self._groq

        if isinstance(exc, groq.AuthenticationError):
            return LLMError(
                "The Groq API key was rejected.",
                hint="Check GROQ_API_KEY in backend/.env, then restart the backend.",
                code="llm_auth_failed",
                status_code=401,
            )
        if isinstance(exc, groq.RateLimitError):
            return LLMError(
                "Groq is rate-limiting this key right now.",
                hint="Wait about a minute and try again. The free tier has per-minute limits.",
                code="llm_rate_limited",
                status_code=429,
            )
        if isinstance(exc, groq.NotFoundError):
            return LLMError(
                f"The model '{self.model}' isn't available on Groq.",
                hint="Check GROQ_MODEL in backend/.env against console.groq.com.",
                code="llm_model_not_found",
                status_code=404,
            )
        if isinstance(exc, groq.APIConnectionError):
            return LLMError(
                "Couldn't reach Groq -- the network request failed.",
                hint="Check your internet connection and try again.",
                code="llm_unreachable",
            )
        if isinstance(exc, groq.APIStatusError):
            if exc.status_code >= 500:
                return LLMError(
                    "Groq is having trouble right now.",
                    hint="Try again in a few seconds.",
                    code="llm_server_error",
                )

            detail, code = _groq_error_parts(exc)

            # 413 "Request too large" is a *rate limit*, not a bad request:
            # Groq counts input + reserved output against a tokens-per-minute
            # budget, and the free tier's is small.
            if exc.status_code == 413 or "rate_limit" in code:
                return LLMError(
                    "Groq's free-tier rate limit was hit.",
                    hint=(
                        "The free tier allows 8,000 tokens per minute. Wait about a "
                        "minute and press Try again -- or upgrade at "
                        "console.groq.com/settings/billing, or switch to Anthropic by "
                        "setting LLM_PROVIDER=anthropic in backend/.env."
                    ),
                    code="llm_rate_limited",
                    status_code=429,
                )

            billing = _billing_error(detail, code)
            if billing:
                return billing
            return LLMError(
                "The AI request was rejected.",
                hint=detail or "Try shortening your documents and running it again.",
                code="llm_bad_request",
                status_code=400,
            )
        return LLMError()

    def _call(self, messages, *, max_tokens, effort, response_format=None) -> str:
        # Two constraints have to be satisfied at once here:
        #
        # 1. Groq counts input tokens PLUS the reserved output tokens against a
        #    per-minute budget (8,000 on the free tier), so asking for the
        #    Anthropic default of 8,000 output tokens fails before a single
        #    token is generated.
        # 2. gpt-oss models spend output tokens on internal reasoning *before*
        #    writing the answer. Reserve too little and the model reasons until
        #    the cap, emits nothing, and the API rejects the empty result with
        #    `json_validate_failed` -- a confusing error whose real cause is a
        #    budget that was too small, not a bad schema.
        #
        # So: give the response as much room as the per-minute budget allows
        # after the prompt is accounted for, rather than a fixed number.
        estimated_input = sum(len(str(m.get("content", ""))) for m in messages) // 3
        headroom = self._settings.groq_tpm_budget - estimated_input - 400
        budget = min(
            max_tokens or self._settings.llm_max_tokens,
            self._settings.groq_max_tokens,
            max(1024, headroom),
        )

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": budget,
            "reasoning_effort": _GROQ_EFFORT.get(
                effort or self._settings.llm_effort, "medium"
            ),
        }
        if response_format:
            kwargs["response_format"] = response_format

        attempts = max(1, self._settings.groq_rate_limit_retries + 1)
        schema_retries = 2
        for attempt in range(attempts + schema_retries):
            try:
                response = self._client.chat.completions.create(**kwargs)
                break
            except TypeError:
                # Older SDK without reasoning_effort / max_completion_tokens.
                kwargs.pop("reasoning_effort", None)
                kwargs["max_tokens"] = kwargs.pop("max_completion_tokens", budget)
                response = self._client.chat.completions.create(**kwargs)
                break
            except Exception as exc:
                _, code = _groq_error_parts(exc)

                # Open models occasionally break a strict schema -- usually by
                # writing an enum value that isn't in the allowed set, or by
                # running out of room mid-object. Groq rejects the whole call
                # rather than returning partial JSON. A plain retry fixes it
                # most of the time, so try again before giving up.
                if "json_validate" in code and attempt < attempts + schema_retries - 1:
                    logger.info("Groq returned schema-invalid JSON; retrying.")
                    continue

                wait = _groq_retry_after(exc)
                if wait is not None and attempt < attempts - 1:
                    # The free tier's per-minute budget refills continuously, so
                    # waiting really does fix this. Better than handing the user
                    # an error they can only resolve by waiting anyway.
                    logger.info(
                        "Groq rate limit hit; waiting %.1fs then retrying (%d/%d).",
                        wait, attempt + 1, attempts - 1,
                    )
                    time.sleep(wait)
                    continue
                logger.exception("Groq call failed")
                raise self._map_error(exc) from exc

        choice = response.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            logger.warning(
                "Groq response hit the %d-token cap; output may be truncated.", budget
            )
        return (choice.message.content or "").strip()

    @staticmethod
    def _as_chat(system: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Groq has no separate system field -- it's the first message."""
        chat: List[Dict[str, Any]] = [{"role": "system", "content": system}]
        for message in messages:
            content = message["content"]
            if not isinstance(content, str):
                # Flatten any structured content down to its text parts.
                content = "\n".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            chat.append({"role": message["role"], "content": content})
        return chat

    def complete(self, *, system, messages, max_tokens=None, effort=None) -> str:
        return self._call(
            self._as_chat(system, messages), max_tokens=max_tokens, effort=effort
        )

    def complete_json(self, *, system, user, schema, max_tokens=None, effort=None):
        raw = self._call(
            self._as_chat(system, [{"role": "user", "content": user}]),
            max_tokens=max_tokens,
            effort=effort or self._settings.llm_extraction_effort,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "response", "strict": True, "schema": schema},
            },
        )
        return _parse_json(raw)


# --------------------------------------------------------------------------
# Provider selection
# --------------------------------------------------------------------------
PROVIDERS = {"anthropic": AnthropicLLM, "groq": GroqLLM}


def _resolve_key(settings: Settings, provider: str) -> Optional[str]:
    """Find a usable key for `provider`, checking .env then the process env.

    Also handles the very easy mistake of pasting a Groq key (`gsk_...`) into
    ANTHROPIC_API_KEY, or vice versa -- the key's own prefix says which service
    it belongs to, so we trust that over which box it was typed into.
    """
    import os

    candidates = [
        settings.groq_api_key,
        settings.anthropic_api_key,
        os.environ.get("GROQ_API_KEY"),
        os.environ.get("ANTHROPIC_API_KEY"),
    ]

    for value in candidates:
        if not looks_like_real_key(value):
            continue
        value = value.strip().strip("\"'")
        detected = "groq" if value.startswith("gsk_") else "anthropic"
        if detected == provider:
            return value
    return None


def detect_provider(settings: Settings) -> Optional[str]:
    """Which provider can we actually run with right now?"""
    configured = (settings.llm_provider or "auto").lower()

    if configured in PROVIDERS:
        return configured if _resolve_key(settings, configured) else None

    # auto: prefer whichever key is present, Groq first.
    for provider in ("groq", "anthropic"):
        if _resolve_key(settings, provider):
            return provider
    return None


def is_configured(settings: Settings) -> bool:
    return detect_provider(settings) is not None


def active_model(settings: Settings) -> str:
    provider = detect_provider(settings)
    if provider == "groq":
        return settings.groq_model
    if provider == "anthropic":
        return settings.llm_model
    # Nothing configured -- report whatever the settings say it would use.
    configured = (settings.llm_provider or "auto").lower()
    return settings.groq_model if configured == "groq" else settings.llm_model


_llm: Optional[BaseLLM] = None
_lock = threading.Lock()


def get_llm(settings: Settings) -> BaseLLM:
    """Return the process-wide LLM client, building it on first use."""
    global _llm
    if _llm is not None:
        return _llm

    with _lock:
        if _llm is not None:
            return _llm

        provider = detect_provider(settings)
        if provider is None:
            configured = (settings.llm_provider or "auto").lower()
            if configured == "groq":
                raise LLMNotConfigured(
                    "No Groq API key is configured.",
                    hint="Add GROQ_API_KEY to backend/.env and restart the backend.",
                )
            if configured == "anthropic":
                raise LLMNotConfigured(
                    "No Anthropic API key is configured.",
                    hint="Add ANTHROPIC_API_KEY to backend/.env and restart the backend.",
                )
            raise LLMNotConfigured(
                "No API key is configured on the server.",
                hint=(
                    "Add GROQ_API_KEY (free tier) or ANTHROPIC_API_KEY to "
                    "backend/.env and restart the backend."
                ),
            )

        _llm = PROVIDERS[provider](settings)
        logger.info("LLM provider: %s (%s)", _llm.display_name, _llm.model)
        return _llm


def reset_llm() -> None:
    """Test hook -- drop the cached client."""
    global _llm
    _llm = None
