import os
from dotenv import load_dotenv
load_dotenv()

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
GAUNTLET_MODEL: str    = os.environ.get("GAUNTLET_MODEL", "claude-sonnet-4-6")
GAUNTLET_DB_PATH: str  = os.environ.get("GAUNTLET_DB_PATH", "./gauntlet.db")

if not ANTHROPIC_API_KEY:
    raise EnvironmentError(
        "ANTHROPIC_API_KEY not set.\n"
        "Run: cp .env.example .env  — then add your key."
    )
