"""Append-only JSONL audit log for the LibreOffice AI Agent.

Records approvals, rejections, executed actions, and errors with
provider, model, document URL, and timestamps.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

STATE_ROOT_ENV_VAR = "LOAIA_EXTENSION_STATE_ROOT"
AUDIT_LOG_FILE_NAME = "audit.jsonl"


def _default_audit_root() -> Path:
    configured_root = os.environ.get(STATE_ROOT_ENV_VAR, "").strip()
    if configured_root:
        return Path(configured_root)

    app_data = os.environ.get("APPDATA", "").strip()
    if app_data:
        return Path(app_data) / "LibreOfficeAIAgent"

    return Path.home() / ".libreoffice-ai-agent"


class AuditLogger:
    """Append-only audit logger writing JSONL entries."""

    def __init__(self, state_root: Path | None = None) -> None:
        self.state_root = state_root or _default_audit_root()
        self._log_path = self.state_root / AUDIT_LOG_FILE_NAME

    def log_approval(
        self,
        *,
        request_id: str,
        tool_id: str,
        document_url: str,
        provider: str,
        model: str,
    ) -> None:
        self._append(
            event="approval",
            request_id=request_id,
            tool_id=tool_id,
            document_url=document_url,
            provider=provider,
            model=model,
        )

    def log_rejection(
        self,
        *,
        request_id: str,
        tool_id: str,
        document_url: str,
        provider: str,
        model: str,
    ) -> None:
        self._append(
            event="rejection",
            request_id=request_id,
            tool_id=tool_id,
            document_url=document_url,
            provider=provider,
            model=model,
        )

    def log_execution(
        self,
        *,
        request_id: str,
        tool_id: str,
        document_url: str,
        provider: str,
        model: str,
        result: str,
    ) -> None:
        self._append(
            event="execution",
            request_id=request_id,
            tool_id=tool_id,
            document_url=document_url,
            provider=provider,
            model=model,
            result=result,
        )

    def log_auto_apply(
        self,
        *,
        request_id: str,
        tool_id: str,
        document_url: str,
        provider: str,
        model: str,
    ) -> None:
        self._append(
            event="auto_apply",
            request_id=request_id,
            tool_id=tool_id,
            document_url=document_url,
            provider=provider,
            model=model,
        )

    def log_error(
        self,
        *,
        request_id: str,
        document_url: str,
        provider: str,
        model: str,
        error: str,
    ) -> None:
        self._append(
            event="error",
            request_id=request_id,
            document_url=document_url,
            provider=provider,
            model=model,
            error=error,
        )

    def _append(self, **fields: object) -> None:
        entry = {
            "timestamp": time.time(),
            **fields,
        }
        self.state_root.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")

    def read_entries(self) -> list[dict[str, object]]:
        """Read all audit entries (for testing and review)."""
        if not self._log_path.exists():
            return []

        entries = []
        with open(self._log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries
