"""Persistentes Gedächtnis von HOPE (SQLite).

Enthält Gespräche, Nachrichten, Gedächtniseinträge, Aufgaben, Notizen,
Einstellungen, das Aktionsprotokoll und bestätigungspflichtige Aktionen.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DEFAULT_SETTINGS: dict[str, Any] = {
    "language": "de-DE",
    "model": "gemini-2.5-flash",
    "tts_enabled": True,
    "stt_enabled": True,
    "continuous_mode": True,
    "wake_word": False,
    "voice_profile": "hope-standard",
    "voice_name": "",
    "voice_rate": 1.0,
    "voice_pitch": 1.05,
    "search_enabled": True,
    "tools_enabled": True,
    "memory_enabled": True,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'notiz',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    due_at TEXT,
    priority TEXT NOT NULL DEFAULT 'mittel',
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    remind_at TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ok',
    sensitive INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_actions (
    id TEXT PRIMARY KEY,
    conversation_id INTEGER,
    tool TEXT NOT NULL,
    args TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'offen',
    created_at TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class HopeMemory:
    """Schlanker SQLite-Store; jede Operation nutzt eine eigene Verbindung."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.db_path, timeout=20)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
            con.commit()
        finally:
            con.close()

    # ---------------------------------------------------------------- Setup
    def init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_SCHEMA)
            for key, value in DEFAULT_SETTINGS.items():
                con.execute(
                    "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                    (key, json.dumps(value)),
                )

    # ---------------------------------------------------------- Gespräche
    def create_conversation(self, title: str = "Neue Unterhaltung") -> int:
        now = utc_now()
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO conversations(title, created_at, updated_at) VALUES (?, ?, ?)",
                (title[:90], now, now),
            )
            return int(cur.lastrowid)

    def list_conversations(self, limit: int = 40) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                """SELECT c.id, c.title, c.created_at, c.updated_at,
                          (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
                   FROM conversations c ORDER BY c.updated_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(self, conversation_id: int) -> dict | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return dict(row) if row else None

    def touch_conversation(self, conversation_id: int) -> None:
        with self._connect() as con:
            con.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (utc_now(), conversation_id))

    def rename_conversation(self, conversation_id: int, title: str) -> None:
        with self._connect() as con:
            con.execute("UPDATE conversations SET title = ? WHERE id = ?", (title[:90], conversation_id))

    def delete_conversation(self, conversation_id: int) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

    # --------------------------------------------------------- Nachrichten
    def add_message(self, conversation_id: int, role: str, content: str) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, utc_now()),
            )
            con.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (utc_now(), conversation_id))
            return int(cur.lastrowid)

    def list_messages(self, conversation_id: int, limit: int | None = None) -> list[dict]:
        with self._connect() as con:
            if limit:
                rows = con.execute(
                    """SELECT * FROM (
                           SELECT * FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?
                       ) ORDER BY id ASC""",
                    (conversation_id, limit),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC",
                    (conversation_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def count_messages(self, conversation_id: int) -> int:
        with self._connect() as con:
            row = con.execute(
                "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?", (conversation_id,)
            ).fetchone()
        return int(row["n"])

    # ----------------------------------------------------------- Gedächtnis
    def add_memory(self, content: str, category: str = "notiz") -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO memories(content, category, created_at) VALUES (?, ?, ?)",
                (content, category, utc_now()),
            )
            return int(cur.lastrowid)

    def list_memories(self, limit: int = 200) -> list[dict]:
        with self._connect() as con:
            rows = con.execute("SELECT * FROM memories ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def delete_memory(self, memory_id: int) -> bool:
        with self._connect() as con:
            cur = con.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cur.rowcount > 0

    # ------------------------------------------------------------- Aufgaben
    def add_task(self, title: str, notes: str = "", due_at: str | None = None, priority: str = "mittel") -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO tasks(title, notes, due_at, priority, created_at) VALUES (?, ?, ?, ?, ?)",
                (title, notes, due_at, priority, utc_now()),
            )
            return int(cur.lastrowid)

    def list_tasks(self, status: str = "open", limit: int = 200) -> list[dict]:
        query = "SELECT * FROM tasks"
        if status == "open":
            query += " WHERE done = 0"
        elif status == "done":
            query += " WHERE done = 1"
        query += " ORDER BY done ASC, CASE priority WHEN 'hoch' THEN 0 WHEN 'mittel' THEN 1 ELSE 2 END, id DESC LIMIT ?"
        with self._connect() as con:
            rows = con.execute(query, (limit,)).fetchall()
        return [dict(row) for row in rows]

    def get_task(self, task_id: int) -> dict | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None

    def complete_task(self, task_id: int) -> bool:
        with self._connect() as con:
            cur = con.execute(
                "UPDATE tasks SET done = 1, completed_at = ? WHERE id = ?", (utc_now(), task_id)
            )
            return cur.rowcount > 0

    def delete_task(self, task_id: int) -> bool:
        with self._connect() as con:
            cur = con.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cur.rowcount > 0

    # -------------------------------------------------------------- Notizen
    def add_note(self, title: str, body: str = "") -> int:
        now = utc_now()
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO notes(title, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (title, body, now, now),
            )
            return int(cur.lastrowid)

    def list_notes(self, query: str = "", limit: int = 100) -> list[dict]:
        with self._connect() as con:
            if query:
                like = f"%{query}%"
                rows = con.execute(
                    "SELECT * FROM notes WHERE title LIKE ? OR body LIKE ? ORDER BY updated_at DESC LIMIT ?",
                    (like, like, limit),
                ).fetchall()
            else:
                rows = con.execute("SELECT * FROM notes ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def delete_note(self, note_id: int) -> bool:
        with self._connect() as con:
            cur = con.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            return cur.rowcount > 0

    # ---------------------------------------------------------- Erinnerungen
    def add_reminder(self, text: str, remind_at: str) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO reminders(text, remind_at, created_at) VALUES (?, ?, ?)",
                (text, remind_at, utc_now()),
            )
            return int(cur.lastrowid)

    def list_reminders(self, only_open: bool = True) -> list[dict]:
        query = "SELECT * FROM reminders"
        if only_open:
            query += " WHERE done = 0"
        query += " ORDER BY remind_at ASC LIMIT 100"
        with self._connect() as con:
            rows = con.execute(query).fetchall()
        return [dict(row) for row in rows]

    def delete_reminder(self, reminder_id: int) -> bool:
        with self._connect() as con:
            cur = con.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            return cur.rowcount > 0

    # --------------------------------------------------------- Einstellungen
    def get_settings(self) -> dict[str, Any]:
        with self._connect() as con:
            rows = con.execute("SELECT key, value FROM settings").fetchall()
        settings = dict(DEFAULT_SETTINGS)
        for row in rows:
            try:
                settings[row["key"]] = json.loads(row["value"])
            except json.JSONDecodeError:
                settings[row["key"]] = row["value"]
        return settings

    def update_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        clean = {key: value for key, value in patch.items() if key in DEFAULT_SETTINGS}
        with self._connect() as con:
            for key, value in clean.items():
                con.execute(
                    "INSERT INTO settings(key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, json.dumps(value)),
                )
        return self.get_settings()

    # ---------------------------------------------------------- Protokoll
    def log_action(self, action: str, detail: str = "", status: str = "ok", sensitive: bool = False) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO action_log(action, detail, status, sensitive, created_at) VALUES (?, ?, ?, ?, ?)",
                (action, detail[:2000], status, int(sensitive), utc_now()),
            )
            return int(cur.lastrowid)

    def list_actions(self, limit: int = 60) -> list[dict]:
        with self._connect() as con:
            rows = con.execute("SELECT * FROM action_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------- Bestätigungspflichtige Aktionen
    def create_pending(self, tool: str, args: dict, summary: str, conversation_id: int | None = None) -> str:
        pending_id = uuid.uuid4().hex[:12]
        with self._connect() as con:
            con.execute(
                "INSERT INTO pending_actions(id, conversation_id, tool, args, summary, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (pending_id, conversation_id, tool, json.dumps(args, ensure_ascii=False), summary, utc_now()),
            )
        return pending_id

    def get_pending(self, pending_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM pending_actions WHERE id = ?", (pending_id,)).fetchone()
        if not row:
            return None
        action = dict(row)
        action["args"] = json.loads(action["args"])
        return action

    def set_pending_status(self, pending_id: str, status: str) -> None:
        with self._connect() as con:
            con.execute("UPDATE pending_actions SET status = ? WHERE id = ?", (status, pending_id))
