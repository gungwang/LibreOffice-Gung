from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path
from typing import TYPE_CHECKING

from loaia.document_session import DocumentSessionKey
from loaia_shared.defaults import get_default_model, get_default_provider

if TYPE_CHECKING:
    import sqlite3

OPENROUTER_API_KEY_ENV_VARS = ("LOAIA_OPENROUTER_API_KEY", "OPENROUTER_API_KEY")
STATE_ROOT_ENV_VAR = "LOAIA_EXTENSION_STATE_ROOT"
STATE_FILE_NAME = "sidebar-state.json"
MAX_HISTORY_MESSAGES = 12


def _check_credential_manager(target: str) -> bool:
    """Check if a credential exists in Windows Credential Manager."""
    try:
        from loaia_sidecar.config.secrets import _read_windows_credential

        value = _read_windows_credential(target)
        return bool(value)
    except Exception:
        return False


def describe_api_key_status(provider: str) -> str:
    normalized_provider = provider.strip().casefold()
    if normalized_provider == "openrouter":
        for env_var in OPENROUTER_API_KEY_ENV_VARS:
            if os.environ.get(env_var, "").strip():
                return "configured"

        if _check_credential_manager("LibreOfficeAIAgent/openrouter"):
            return "configured"

        return "missing"

    return "not required"


def _default_state_root() -> Path:
    configured_root = os.environ.get(STATE_ROOT_ENV_VAR, "").strip()
    if configured_root:
        return Path(configured_root)

    app_data = os.environ.get("APPDATA", "").strip()
    if app_data:
        return Path(app_data) / "LibreOfficeAIAgent"

    return Path.home() / ".libreoffice-ai-agent"


def _make_session_id(session_key: DocumentSessionKey) -> str:
    payload = json.dumps(
        {
            "profileId": session_key.profile_id,
            "canonicalDocumentUrl": session_key.canonical_document_url,
            "appType": str(session_key.app_type),
        },
        sort_keys=True,
    )
    return sha1(payload.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class SidebarSettingsSnapshot:
    provider: str
    model: str
    api_key_status: str


@dataclass(slots=True)
class SidebarSessionSnapshot:
    last_prompt: str | None = None
    last_result: str | None = None
    last_error: str | None = None
    message_texts: list[str] = field(default_factory=list)
    history_summary: list[dict[str, object]] = field(default_factory=list)


class JsonSidebarSessionStore:
    def __init__(self, state_root: Path | None = None) -> None:
        self.state_root = state_root or _default_state_root()
        self.state_file = self.state_root / STATE_FILE_NAME

    def load_settings(self) -> SidebarSettingsSnapshot:
        data = self._read_data()
        settings = data.get("settings", {})
        provider = str(settings.get("provider") or get_default_provider())
        model = str(settings.get("model") or get_default_model())
        return SidebarSettingsSnapshot(
            provider=provider,
            model=model,
            api_key_status=describe_api_key_status(provider),
        )

    def save_settings(self, provider: str, model: str) -> SidebarSettingsSnapshot:
        data = self._read_data()
        data["settings"] = {
            "provider": provider,
            "model": model,
        }
        self._write_data(data)
        return SidebarSettingsSnapshot(
            provider=provider,
            model=model,
            api_key_status=describe_api_key_status(provider),
        )

    def load_session(self, session_key: DocumentSessionKey | None) -> SidebarSessionSnapshot:
        if session_key is None:
            return SidebarSessionSnapshot()

        data = self._read_data()
        sessions = data.get("sessions", {})
        session_payload = sessions.get(_make_session_id(session_key), {})
        messages = [
            message
            for message in (
                self._coerce_history_message(message)
                for message in session_payload.get("messages", [])
            )
            if message is not None
        ]
        return SidebarSessionSnapshot(
            last_prompt=self._coerce_optional_str(session_payload.get("lastPrompt")),
            last_result=self._coerce_optional_str(session_payload.get("lastResult")),
            last_error=self._coerce_optional_str(session_payload.get("lastError")),
            message_texts=[str(message["text"]) for message in messages],
            history_summary=[dict(message) for message in messages[-6:]],
        )

    def record_request(
        self,
        session_key: DocumentSessionKey | None,
        prompt: str,
        provider: str,
        model: str,
    ) -> None:
        if session_key is None:
            return

        data = self._read_data()
        session_payload = self._get_session_payload(data, session_key)
        session_payload["lastPrompt"] = prompt
        session_payload["lastError"] = None
        self._append_message(
            session_payload,
            self._make_history_message(
                role="user",
                text=prompt,
                provider=provider,
                model=model,
            ),
        )
        self._write_data(data)

    def record_result(
        self,
        session_key: DocumentSessionKey | None,
        text: str,
        provider: str,
        model: str,
        role: str = "assistant",
    ) -> None:
        if session_key is None:
            return

        data = self._read_data()
        session_payload = self._get_session_payload(data, session_key)
        session_payload["lastResult"] = text
        session_payload["lastError"] = None
        self._append_message(
            session_payload,
            self._make_history_message(
                role=role,
                text=text,
                provider=provider,
                model=model,
            ),
        )
        self._write_data(data)

    def record_error(self, session_key: DocumentSessionKey | None, error_message: str) -> None:
        if session_key is None:
            return

        data = self._read_data()
        session_payload = self._get_session_payload(data, session_key)
        session_payload["lastError"] = error_message
        self._append_message(
            session_payload,
            self._make_history_message(role="system", text=error_message),
        )
        self._write_data(data)

    def _read_data(self) -> dict[str, object]:
        if not self.state_file.exists():
            return {"settings": {}, "sessions": {}}

        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"settings": {}, "sessions": {}}

    def _write_data(self, data: dict[str, object]) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @staticmethod
    def _coerce_optional_str(value: object) -> str | None:
        return value if isinstance(value, str) else None

    @staticmethod
    def _append_message(
        session_payload: dict[str, object],
        message: dict[str, object],
    ) -> None:
        raw_messages = session_payload.setdefault("messages", [])
        if not isinstance(raw_messages, list):
            raw_messages = []
            session_payload["messages"] = raw_messages

        raw_messages.append(message)
        if len(raw_messages) > MAX_HISTORY_MESSAGES:
            del raw_messages[:-MAX_HISTORY_MESSAGES]

    @staticmethod
    def _get_session_payload(
        data: dict[str, object],
        session_key: DocumentSessionKey,
    ) -> dict[str, object]:
        sessions = data.setdefault("sessions", {})
        if not isinstance(sessions, dict):
            sessions = {}
            data["sessions"] = sessions

        session_id = _make_session_id(session_key)
        session_payload = sessions.setdefault(
            session_id,
            {
                "key": {
                    "profileId": session_key.profile_id,
                    "canonicalDocumentUrl": session_key.canonical_document_url,
                    "appType": str(session_key.app_type),
                },
                "messages": [],
            },
        )
        if not isinstance(session_payload, dict):
            session_payload = {
                "key": {
                    "profileId": session_key.profile_id,
                    "canonicalDocumentUrl": session_key.canonical_document_url,
                    "appType": str(session_key.app_type),
                },
                "messages": [],
            }
            sessions[session_id] = session_payload

        return session_payload

    @staticmethod
    def _make_history_message(
        *,
        role: str,
        text: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, object]:
        message: dict[str, object] = {
            "role": role,
            "text": text,
        }
        if provider is not None:
            message["provider"] = provider
        if model is not None:
            message["model"] = model

        return message

    @staticmethod
    def _coerce_history_message(message: object) -> dict[str, object] | None:
        if not isinstance(message, dict):
            return None

        role = message.get("role")
        text = message.get("text")
        if not isinstance(role, str) or not isinstance(text, str):
            return None

        normalized: dict[str, object] = {
            "role": role,
            "text": text,
        }
        provider = message.get("provider")
        if isinstance(provider, str):
            normalized["provider"] = provider
        model = message.get("model")
        if isinstance(model, str):
            normalized["model"] = model

        return normalized


class InMemorySidebarSessionStore(JsonSidebarSessionStore):
    def __init__(self) -> None:
        super().__init__(state_root=Path("."))
        self._data: dict[str, object] = {"settings": {}, "sessions": {}}

    def _read_data(self) -> dict[str, object]:
        return deepcopy(self._data)

    def _write_data(self, data: dict[str, object]) -> None:
        self._data = deepcopy(data)


_SQLITE_DB_NAME = "history.sqlite3"
_SQLITE_SETTINGS_FILE = "settings.json"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    canonical_document_url TEXT NOT NULL,
    app_type TEXT NOT NULL,
    last_prompt TEXT,
    last_result TEXT,
    last_error TEXT,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
"""


class SqliteSidebarSessionStore:
    """SQLite-backed session store for conversation history.

    Settings are still stored in a JSON file alongside the database
    to keep the settings path consistent with the JSON store.
    """

    def __init__(self, state_root: Path | None = None) -> None:
        self.state_root = state_root or _default_state_root()
        self._db_path = self.state_root / _SQLITE_DB_NAME
        self._settings_file = self.state_root / _SQLITE_SETTINGS_FILE
        self._conn: "sqlite3.Connection | None" = None

    def _get_connection(self) -> "sqlite3.Connection":
        import sqlite3

        if self._conn is not None:
            return self._conn

        self.state_root.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA_SQL)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- Settings (JSON file, same as JsonSidebarSessionStore) --

    def load_settings(self) -> SidebarSettingsSnapshot:
        data = self._read_settings_data()
        provider = str(data.get("provider") or get_default_provider())
        model = str(data.get("model") or get_default_model())
        return SidebarSettingsSnapshot(
            provider=provider,
            model=model,
            api_key_status=describe_api_key_status(provider),
        )

    def save_settings(self, provider: str, model: str) -> SidebarSettingsSnapshot:
        self.state_root.mkdir(parents=True, exist_ok=True)
        self._settings_file.write_text(
            json.dumps({"provider": provider, "model": model}, indent=2),
            encoding="utf-8",
        )
        return SidebarSettingsSnapshot(
            provider=provider,
            model=model,
            api_key_status=describe_api_key_status(provider),
        )

    def _read_settings_data(self) -> dict[str, object]:
        if not self._settings_file.exists():
            return {}
        try:
            return json.loads(self._settings_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    # -- Session history (SQLite) --

    def load_session(self, session_key: DocumentSessionKey | None) -> SidebarSessionSnapshot:
        if session_key is None:
            return SidebarSessionSnapshot()

        conn = self._get_connection()
        session_id = _make_session_id(session_key)

        row = conn.execute(
            "SELECT last_prompt, last_result, last_error FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        if row is None:
            return SidebarSessionSnapshot()

        last_prompt, last_result, last_error = row

        messages = conn.execute(
            "SELECT role, text, provider, model FROM messages "
            "WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()

        message_texts = [text for _, text, _, _ in messages]
        history_summary = [
            self._row_to_history_entry(role, text, provider, model)
            for role, text, provider, model in messages[-6:]
        ]

        return SidebarSessionSnapshot(
            last_prompt=last_prompt,
            last_result=last_result,
            last_error=last_error,
            message_texts=message_texts[-MAX_HISTORY_MESSAGES:],
            history_summary=history_summary,
        )

    def record_request(
        self,
        session_key: DocumentSessionKey | None,
        prompt: str,
        provider: str,
        model: str,
    ) -> None:
        if session_key is None:
            return

        conn = self._get_connection()
        session_id = _make_session_id(session_key)
        now = time.time()

        self._ensure_session(conn, session_id, session_key, now)
        conn.execute(
            "UPDATE sessions SET last_prompt = ?, last_error = NULL, updated_at = ? "
            "WHERE session_id = ?",
            (prompt, now, session_id),
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, text, provider, model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, "user", prompt, provider, model, now),
        )
        self._trim_messages(conn, session_id)
        conn.commit()

    def record_result(
        self,
        session_key: DocumentSessionKey | None,
        text: str,
        provider: str,
        model: str,
        role: str = "assistant",
    ) -> None:
        if session_key is None:
            return

        conn = self._get_connection()
        session_id = _make_session_id(session_key)
        now = time.time()

        self._ensure_session(conn, session_id, session_key, now)
        conn.execute(
            "UPDATE sessions SET last_result = ?, last_error = NULL, updated_at = ? "
            "WHERE session_id = ?",
            (text, now, session_id),
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, text, provider, model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, role, text, provider, model, now),
        )
        self._trim_messages(conn, session_id)
        conn.commit()

    def record_error(self, session_key: DocumentSessionKey | None, error_message: str) -> None:
        if session_key is None:
            return

        conn = self._get_connection()
        session_id = _make_session_id(session_key)
        now = time.time()

        self._ensure_session(conn, session_id, session_key, now)
        conn.execute(
            "UPDATE sessions SET last_error = ?, updated_at = ? WHERE session_id = ?",
            (error_message, now, session_id),
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, text, provider, model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, "system", error_message, None, None, now),
        )
        self._trim_messages(conn, session_id)
        conn.commit()

    @staticmethod
    def _ensure_session(
        conn: "sqlite3.Connection",
        session_id: str,
        session_key: DocumentSessionKey,
        now: float,
    ) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO sessions "
            "(session_id, profile_id, canonical_document_url, app_type, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                session_id,
                session_key.profile_id,
                session_key.canonical_document_url,
                str(session_key.app_type),
                now,
            ),
        )

    @staticmethod
    def _trim_messages(conn: "sqlite3.Connection", session_id: str) -> None:
        conn.execute(
            "DELETE FROM messages WHERE session_id = ? AND id NOT IN "
            "(SELECT id FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?)",
            (session_id, session_id, MAX_HISTORY_MESSAGES),
        )

    @staticmethod
    def _row_to_history_entry(
        role: str, text: str, provider: str | None, model: str | None
    ) -> dict[str, object]:
        entry: dict[str, object] = {"role": role, "text": text}
        if provider is not None:
            entry["provider"] = provider
        if model is not None:
            entry["model"] = model
        return entry