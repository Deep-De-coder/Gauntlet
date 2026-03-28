"""SQLite storage — zero-config, auto-creates gauntlet.db on first run."""
import json, sqlite3
from pathlib import Path
from gauntlet.config import GAUNTLET_DB_PATH
from gauntlet.core.models import EvalReport


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(Path(GAUNTLET_DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS eval_reports (
        eval_id TEXT PRIMARY KEY, data TEXT NOT NULL, created_at REAL NOT NULL
    )""")
    conn.commit()
    return conn


async def save_report(report: EvalReport) -> None:
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO eval_reports VALUES (?, ?, ?)",
        (report.eval_id, report.model_dump_json(), report.created_at),
    )
    conn.commit(); conn.close()


async def get_report(eval_id: str) -> EvalReport | None:
    conn = _conn()
    row = conn.execute("SELECT data FROM eval_reports WHERE eval_id = ?", (eval_id,)).fetchone()
    conn.close()
    return EvalReport.model_validate_json(row[0]) if row else None


async def list_reports(limit: int = 20) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT eval_id, created_at FROM eval_reports ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [{"eval_id": r[0], "created_at": r[1]} for r in rows]
