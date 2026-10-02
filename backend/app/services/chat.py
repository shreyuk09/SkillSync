"""The RAG chatbot.

Every message follows the same path, and it is the clearest demonstration of
RAG in the whole project:

    question
      -> embed the question
      -> search the vector store (resume quota + JD quota)
      -> build a CONTEXT block with [S1], [S2] labels
      -> the LLM answers using only that context
      -> map the [S#] labels back to real chunks
      -> return answer + clickable sources

Nothing is answered from the model's own knowledge of the candidate, because
it has none: the only facts it ever sees are the retrieved chunks.
"""

from typing import Any, Dict, List

from app.core.config import Settings
from app.core.errors import JobDescriptionMissing, ResumeMissing
from app.core.logging import get_logger
from app.models.store import Store
from app.rag.generation import format_history, generate_grounded
from app.rag.llm import get_llm
from app.rag.prompts import CHAT_SCHEMA, CHAT_SYSTEM
from app.rag.retriever import get_retriever

logger = get_logger(__name__)

SUGGESTED_QUESTIONS = [
    "Why am I not a strong match for this job?",
    "Which of my projects is most relevant to this role?",
    "What skills am I missing?",
    "Does my resume mention all the required technologies?",
    "Which of my experiences matches their responsibilities?",
    "What should I improve first?",
    "What does this job actually require?",
    "How should I describe my strongest project in an interview?",
]


def ask(
    session_id: str,
    question: str,
    settings: Settings,
    store: Store,
    *,
    remember: bool = True,
) -> Dict[str, Any]:
    """Answer one question with retrieval-augmented generation."""
    question = question.strip()
    if not question:
        return {
            "answer": "Ask me something about your resume or this job description.",
            "found_answer": False,
            "sources": [],
            "follow_ups": SUGGESTED_QUESTIONS[:3],
            "retrieval": [],
        }

    resume = store.get_document(session_id, "resume")
    if not resume:
        raise ResumeMissing()
    jd = store.get_document(session_id, "jd")
    if not jd:
        raise JobDescriptionMissing()

    retriever = get_retriever(settings)
    llm = get_llm(settings)

    # --- RETRIEVE -------------------------------------------------------
    chunks = retriever.retrieve_pair(
        session_id, question, resume_k=6, jd_k=5
    )

    history = store.get_chat_history(session_id, limit=6) if remember else []
    history_block = format_history(history)

    # --- GENERATE -------------------------------------------------------
    # Nothing cleared the relevance floor. Answer from general knowledge rather
    # than refusing -- but say up front that the documents are silent, so the
    # user never mistakes advice for something their resume actually says.
    if not chunks:
        task = (
            f"The candidate asks:\n\n{question}\n\n"
            "Nothing in the uploaded resume or job description is relevant to this "
            "question. Do NOT refuse. Open by stating plainly that the documents "
            "don't cover it, then answer from general career knowledge with every "
            "such sentence prefixed 'General guidance:'. Cite no [S#] labels, and "
            "assert nothing about this candidate or this employer."
        )
    else:
        task = f"The candidate asks:\n\n{question}"

    result = generate_grounded(
        llm,
        system=CHAT_SYSTEM,
        task=task,
        chunks=chunks,
        schema=CHAT_SCHEMA,
        effort=settings.llm_effort,
        max_tokens=4000,
        extra_context=history_block,
        explicit_refs_key="used_refs",
        include_all_sources=False,
    )

    answer = result.data.get("answer", "").strip()
    found = bool(result.data.get("found_answer", True))
    general = bool(result.data.get("used_general_knowledge", not chunks))
    follow_ups = result.data.get("follow_ups") or []

    if remember:
        store.add_chat_message(session_id, "user", question)
        store.add_chat_message(session_id, "assistant", answer, result.sources)

    return {
        "answer": answer,
        "found_answer": found,
        "used_general_knowledge": general,
        "sources": result.sources,
        "follow_ups": follow_ups[:3],
        "retrieval": result.retrieval_trace,
    }


def history(session_id: str, store: Store) -> List[Dict[str, Any]]:
    return [
        {
            "role": message["role"],
            "content": message["content"],
            "sources": message["sources"],
            "created_at": message["created_at"],
        }
        for message in store.get_chat_history(session_id, limit=100)
    ]
