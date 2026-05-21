from __future__ import annotations

import os

API_KEY_ENV_VARS: dict[str, tuple[str, ...]] = {
    "openrouter": ("LOAIA_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
}


class SecretStore:
    """Placeholder secret store.

    The intended production implementation should use Windows Credential Manager.
    """

    def get_api_key(self, provider: str) -> str | None:
        for env_var_name in API_KEY_ENV_VARS.get(provider, ()): 
            value = os.environ.get(env_var_name, "").strip()
            if value:
                return value

        return None
