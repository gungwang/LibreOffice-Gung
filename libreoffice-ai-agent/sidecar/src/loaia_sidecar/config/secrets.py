class SecretStore:
    """Placeholder secret store.

    The intended production implementation should use Windows Credential Manager.
    """

    def get_api_key(self, provider: str) -> str | None:
        return None
