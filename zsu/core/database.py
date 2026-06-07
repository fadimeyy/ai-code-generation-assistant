import os
import sqlite3
from datetime import datetime

# ── SQLite Database ──────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "codesense.db")


def init_db():
    """Create the metrics table if it doesn't exist."""
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT    NOT NULL,
            mode      TEXT    NOT NULL,
            ruff      INTEGER NOT NULL,
            bandit    INTEGER NOT NULL,
            llm_found INTEGER NOT NULL
        )
    """)
    con.commit()
    con.close()


def save_metric_db(mode: str, ruff: int, bandit: int, llm_found: bool):
    """Insert one metric row into the database."""
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO metrics (timestamp, mode, ruff, bandit, llm_found) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), mode, ruff, bandit, int(llm_found)),
    )
    con.commit()
    con.close()


def load_metrics_db() -> list:
    """Return all rows from metrics table as a list of dicts."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT timestamp, mode, ruff, bandit, llm_found FROM metrics ORDER BY id"
    ).fetchall()
    con.close()
    return [
        {
            "timestamp": r["timestamp"],
            "mode":      r["mode"],
            "ruff":      r["ruff"],
            "bandit":    r["bandit"],
            "llm_found": bool(r["llm_found"]),
        }
        for r in rows
    ]


def clear_metrics_db():
    """Delete all metric rows from the database."""
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM metrics")
    con.commit()
    con.close()

def save_chat_db(session_id: str, role: str, content: str, intent: str = "chat"):
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            intent TEXT,
            timestamp TEXT
        )
    """)
    con.execute(
        "INSERT INTO chat_history (session_id, role, content, intent, timestamp) VALUES (?,?,?,?,?)",
        (session_id, role, content, intent, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    con.commit()
    con.close()

def load_chat_sessions_db():
    """Son 20 session'ı döndür"""
    con = sqlite3.connect(DB_PATH)
    try:
        rows = con.execute("""
            SELECT session_id, MIN(timestamp) as started, COUNT(*) as msg_count
            FROM chat_history
            GROUP BY session_id
            ORDER BY started DESC
            LIMIT 20
        """).fetchall()
        return [{"session_id": r[0], "started": r[1], "msg_count": r[2]} for r in rows]
    except:
        return []
    finally:
        con.close()

def load_chat_history_db(session_id: str):
    """Belirli session'ın mesajlarını döndür"""
    con = sqlite3.connect(DB_PATH)
    try:
        rows = con.execute(
            "SELECT role, content, intent FROM chat_history WHERE session_id=? ORDER BY id",
            (session_id,)
        ).fetchall()
        return [{"role": r[0], "content": r[1], "intent": r[2]} for r in rows]
    except:
        return []
    finally:
        con.close()
# Initialise DB on startup
init_db()
