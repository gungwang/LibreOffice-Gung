class HistoryStore:
    """Placeholder per-document history store.

    Phase 1 should implement SQLite-backed storage in the LibreOffice profile.
    """

    def append_message(self, session_key: str, role: str, text: str) -> None:
        del session_key, role, text

    def get_messages(self, session_key: str) -> list[dict[str, str]]:
        del session_key
        return []
