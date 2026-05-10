import sqlite3
import time
from pathlib import Path
from threading import Lock

DB_PATH = Path(__file__).parent / "sessions.db"
_lock = Lock()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key TEXT,
                model TEXT,
                track TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                created_at REAL
            )
            """
        )
        conn.commit()


def log_request(api_key: str, model: str, track: str, input_tokens: int, output_tokens: int):
    with _lock:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO requests (api_key, model, track, input_tokens, output_tokens, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (api_key, model, track, input_tokens, output_tokens, time.time()),
            )
            conn.commit()


# DB init on module load
init_db()
