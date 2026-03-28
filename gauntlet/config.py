# gauntlet/config.py
#
# WHY: We use python-dotenv to load the .env file BEFORE reading any
# environment variables. Without this, running `gauntlet serve` from CMD
# would fail to find ANTHROPIC_API_KEY because Windows doesn't auto-source
# .env files. The load_dotenv() call is a no-op if the variable is already
# set (e.g. in a real production environment), so it's safe everywhere.
#
# We also delay validation to get_api_key() instead of raising at import
# time. FastAPI imports config.py when it starts — if we raise during
# import, the OpenAPI schema never builds and /openapi.json 500s.

import os
from pathlib import Path

from dotenv import load_dotenv

# Walk up from this file's location to find the .env in the project root.
# This works regardless of which directory you run the server from.
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)

# --------------------------------------------------------------------------- #
# Model config
# --------------------------------------------------------------------------- #
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
GAUNTLET_MODEL: str = os.getenv("GAUNTLET_MODEL", "claude-sonnet-4-20250514")
GAUNTLET_DB_PATH: str = os.getenv("GAUNTLET_DB_PATH", "gauntlet.db")

# --------------------------------------------------------------------------- #
# API key — validated lazily so imports never raise
# --------------------------------------------------------------------------- #

def get_api_key() -> str:
    """Return the Anthropic API key, raising a clear error if missing.

    Call this inside agent constructors or route handlers, NOT at module
    level — that way FastAPI can finish loading even without the key set.
    """
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to your .env file or export it in your shell."
        )
    return key
