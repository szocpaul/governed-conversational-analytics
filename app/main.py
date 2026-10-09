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
        import dspy
        if getattr(dspy.settings, "lm", None) is None:
            # Not yet configured (e.g. production run): configure now.
            configure_dspy(config)
        # else: already configured (e.g. test session fixture on the main
        # thread); reusing it avoids DSPy's cross-thread configure lock.
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

    # Demo UI (spec 004, T008): serve the static interface at / and its
    # assets at /static. Minimal wiring; the query path is unchanged.
    import os as _os

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    web_dir = _os.path.join(_os.path.dirname(__file__), "web")
    if _os.path.isdir(web_dir):
        app.mount("/static", StaticFiles(directory=web_dir), name="static")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(_os.path.join(web_dir, "index.html"))

    return app


app = create_app()
