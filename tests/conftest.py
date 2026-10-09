import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# DSPy pinned-LM session configuration (spec 003).
#
# DSPy's global settings are owned by the thread that first configures them.
# FastAPI TestClient runs the app lifespan (which calls configure_dspy) on a
# DIFFERENT thread per test module, so a second module's TestClient hits
# "dspy.settings can only be changed by the thread that initially configured
# it". Configuring once here, on the main thread, before any TestClient runs,
# makes the live-LLM security tests order-independent.
# ---------------------------------------------------------------------------
import pytest as _pytest


@_pytest.fixture(scope="session", autouse=True)
def _configure_pinned_lm_once():
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from app.ai.llm import LLMConfig, configure_dspy
        configure_dspy(LLMConfig.from_env())
    except Exception:
        # Endpoint unreachable or already configured: individual tests skip
        # or proceed as appropriate. Never fail the whole session here.
        pass
    yield
