from pathlib import Path

from loaia.audit import AuditLogger


def test_audit_logger_round_trip(tmp_path: Path) -> None:
    logger = AuditLogger(state_root=tmp_path)

    logger.log_approval(
        request_id="req-1",
        tool_id="Writer.ReplaceSelection",
        document_url="file:///test.odt",
        provider="openrouter",
        model="gpt-4.1-mini",
    )
    logger.log_execution(
        request_id="req-1",
        tool_id="Writer.ReplaceSelection",
        document_url="file:///test.odt",
        provider="openrouter",
        model="gpt-4.1-mini",
        result="Applied Writer.ReplaceSelection",
    )
    logger.log_auto_apply(
        request_id="req-2",
        tool_id="Writer.ToggleBold",
        document_url="file:///test.odt",
        provider="openrouter",
        model="gpt-4.1-mini",
    )
    logger.log_error(
        request_id="req-3",
        document_url="file:///test.odt",
        provider="openrouter",
        model="gpt-4.1-mini",
        error="Connection timeout",
    )

    entries = logger.read_entries()
    assert len(entries) == 4

    assert entries[0]["event"] == "approval"
    assert entries[0]["tool_id"] == "Writer.ReplaceSelection"
    assert entries[0]["request_id"] == "req-1"
    assert "timestamp" in entries[0]

    assert entries[1]["event"] == "execution"
    assert entries[1]["result"] == "Applied Writer.ReplaceSelection"

    assert entries[2]["event"] == "auto_apply"
    assert entries[2]["tool_id"] == "Writer.ToggleBold"

    assert entries[3]["event"] == "error"
    assert entries[3]["error"] == "Connection timeout"


def test_audit_logger_rejection(tmp_path: Path) -> None:
    logger = AuditLogger(state_root=tmp_path)

    logger.log_rejection(
        request_id="req-5",
        tool_id="Writer.ReplaceSelection",
        document_url="file:///test.odt",
        provider="openrouter",
        model="gpt-4.1-mini",
    )

    entries = logger.read_entries()
    assert len(entries) == 1
    assert entries[0]["event"] == "rejection"


def test_audit_logger_empty(tmp_path: Path) -> None:
    logger = AuditLogger(state_root=tmp_path)
    assert logger.read_entries() == []
