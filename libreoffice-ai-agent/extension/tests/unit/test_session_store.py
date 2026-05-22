from pathlib import Path

from loaia.document_session import DocumentSessionKey
from loaia.session_store import SqliteSidebarSessionStore
from loaia_shared.types import AppType


def _make_key() -> DocumentSessionKey:
    return DocumentSessionKey(
        profile_id="test-profile",
        canonical_document_url="file:///test.odt",
        app_type=AppType.WRITER,
    )


def test_sqlite_store_round_trip(tmp_path: Path) -> None:
    store = SqliteSidebarSessionStore(state_root=tmp_path)
    key = _make_key()

    # Initially empty.
    snapshot = store.load_session(key)
    assert snapshot.last_prompt is None
    assert snapshot.message_texts == []

    # Record a request.
    store.record_request(key, "Summarize this.", "openrouter", "gpt-4.1-mini")
    snapshot = store.load_session(key)
    assert snapshot.last_prompt == "Summarize this."
    assert len(snapshot.message_texts) == 1
    assert "Summarize this." in snapshot.message_texts[0]

    # Record a result.
    store.record_result(key, "This is a summary.", "openrouter", "gpt-4.1-mini")
    snapshot = store.load_session(key)
    assert snapshot.last_result == "This is a summary."
    assert len(snapshot.message_texts) == 2

    # Record an error.
    store.record_error(key, "Connection timeout.")
    snapshot = store.load_session(key)
    assert snapshot.last_error == "Connection timeout."
    assert len(snapshot.message_texts) == 3

    store.close()


def test_sqlite_store_settings_round_trip(tmp_path: Path) -> None:
    store = SqliteSidebarSessionStore(state_root=tmp_path)

    settings = store.load_settings()
    assert settings.provider  # has a default

    saved = store.save_settings("openrouter", "gpt-4.1-mini")
    assert saved.provider == "openrouter"
    assert saved.model == "gpt-4.1-mini"

    reloaded = store.load_settings()
    assert reloaded.provider == "openrouter"
    assert reloaded.model == "gpt-4.1-mini"

    store.close()


def test_sqlite_store_trims_messages(tmp_path: Path) -> None:
    store = SqliteSidebarSessionStore(state_root=tmp_path)
    key = _make_key()

    for i in range(20):
        store.record_request(key, f"Message {i}", "openrouter", "gpt-4.1-mini")

    snapshot = store.load_session(key)
    assert len(snapshot.message_texts) <= 12  # MAX_HISTORY_MESSAGES

    store.close()


def test_sqlite_store_none_session_key(tmp_path: Path) -> None:
    store = SqliteSidebarSessionStore(state_root=tmp_path)

    # Should not raise.
    snapshot = store.load_session(None)
    assert snapshot.last_prompt is None

    store.record_request(None, "test", "p", "m")  # no-op
    store.record_result(None, "test", "p", "m")  # no-op
    store.record_error(None, "test")  # no-op

    store.close()
