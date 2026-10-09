"""FastAPI application entrypoint for the conversational query pipeline."""
from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

# Load .env (if present) before any config is read from the environment.
load_dotenv()

from app.ai.llm import LLMConfig, LLMEndpointError, configure_dspy
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure the pinned local LM at startup. No fallback is allowed.

    If the endpoint or exact model cannot be verified, the app still starts
    so /health works, but the query path reports a stable dependency_error.
    """
    config = LLMConfig.from_env()
    try:
        configure_dspy(config)
        app.state.llm_ready = True
        app.state.llm_error = None
    except LLMEndpointError as exc:
        app.state.llm_ready = False
        app.state.llm_error = str(exc)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Governed Conversational Analytics",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.include_router(router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
