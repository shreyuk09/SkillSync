"""FastAPI application entry point.

    uvicorn app.main:app --reload --port 8000

Responsibilities kept here and nowhere else: app construction, CORS, global
error handling, and startup/shutdown housekeeping.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.routes import analysis, chat, demo, documents, health, prep, sessions, skillsync
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger, setup_logging
from app.models.store import get_store
from app.rag.vector_store import get_vector_store

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.debug)

    logger.info("%s v%s starting", settings.app_name, __version__)
    logger.info("Data directory: %s", settings.storage_dir)

    store = get_store(settings)

    # Privacy housekeeping: drop sessions (and their vectors) past their TTL.
    expired = store.expired_session_ids()
    if expired:
        vector_store = get_vector_store(settings)
        for session_id in expired:
            vector_store.delete_session(session_id)
            store.delete_session(session_id)
        logger.info("Purged %d expired session(s).", len(expired))

    from app.rag.llm import active_model, detect_provider, is_configured

    provider = detect_provider(settings)
    if is_configured(settings):
        logger.info("LLM: %s via %s", active_model(settings), provider)
    else:
        logger.warning(
            "No LLM API key set. Upload, chunking, embedding and vector search "
            "all work; analysis and chat return a clear error until a key is "
            "added (GROQ_API_KEY or ANTHROPIC_API_KEY in backend/.env)."
        )

    # Load the embedding model and SkillSync indexes off the request path.
    from app.skillsync.rag import warmup

    warmup()

    yield

    logger.info("Shutting down.")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.debug)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Retrieval-Augmented Generation over a resume and a job description. "
            "Documents are extracted, cleaned, sectioned, chunked, embedded and "
            "indexed; questions are answered from retrieved chunks with citations."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # ---- error handling: never leak a stack trace to the browser --------
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        logger.info("Handled error [%s] %s", exc.code, exc.message)
        return JSONResponse(status_code=exc.status_code, content={"error": exc.to_dict()})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(part) for part in first.get("loc", [])[1:]) or "input"
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": f"There's a problem with '{field}': {first.get('msg', 'invalid value')}",
                    "hint": "Check the form and try again.",
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"http_{exc.status_code}",
                    "message": str(exc.detail),
                    "hint": None,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Something went wrong while processing that request.",
                    "hint": "Try again. If it keeps happening, check the backend logs.",
                }
            },
        )

    # ---- routes ---------------------------------------------------------
    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(sessions.router, prefix=api_prefix)
    app.include_router(documents.router, prefix=api_prefix)
    app.include_router(analysis.router, prefix=api_prefix)
    app.include_router(chat.router, prefix=api_prefix)
    app.include_router(prep.router, prefix=api_prefix)
    app.include_router(demo.router, prefix=api_prefix)
    app.include_router(skillsync.router, prefix=api_prefix)

    @app.get("/", include_in_schema=False)
    def root():
        return {
            "name": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
