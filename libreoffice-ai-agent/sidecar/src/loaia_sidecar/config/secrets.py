from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import sys

API_KEY_ENV_VARS: dict[str, tuple[str, ...]] = {
    "openrouter": ("LOAIA_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
}

CREDENTIAL_MANAGER_TARGETS: dict[str, str] = {
    "openrouter": "LibreOfficeAIAgent/openrouter",
}

# Windows Credential Manager constants
_CRED_TYPE_GENERIC = 1


def _read_windows_credential(target_name: str) -> str | None:
    """Read a generic credential from Windows Credential Manager via advapi32."""
    if sys.platform != "win32":
        return None

    try:
        advapi32 = ctypes.windll.advapi32  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return None

    class _CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", ctypes.wintypes.DWORD),
            ("Type", ctypes.wintypes.DWORD),
            ("TargetName", ctypes.wintypes.LPWSTR),
            ("Comment", ctypes.wintypes.LPWSTR),
            ("LastWritten", ctypes.wintypes.FILETIME),
            ("CredentialBlobSize", ctypes.wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
            ("Persist", ctypes.wintypes.DWORD),
            ("AttributeCount", ctypes.wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.wintypes.LPWSTR),
            ("UserName", ctypes.wintypes.LPWSTR),
        ]

    cred_ptr = ctypes.POINTER(_CREDENTIAL)()
    ok = advapi32.CredReadW(target_name, _CRED_TYPE_GENERIC, 0, ctypes.byref(cred_ptr))
    if not ok:
        return None

    try:
        cred = cred_ptr.contents
        blob_size = cred.CredentialBlobSize
        if blob_size == 0 or not cred.CredentialBlob:
            return None
        raw = ctypes.string_at(cred.CredentialBlob, blob_size)
        return raw.decode("utf-16-le").strip("\x00")
    finally:
        advapi32.CredFree(cred_ptr)


def save_windows_credential(target_name: str, username: str, secret: str) -> bool:
    """Save a generic credential to Windows Credential Manager."""
    if sys.platform != "win32":
        return False

    try:
        advapi32 = ctypes.windll.advapi32  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False

    _CRED_PERSIST_LOCAL_MACHINE = 2

    class _CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", ctypes.wintypes.DWORD),
            ("Type", ctypes.wintypes.DWORD),
            ("TargetName", ctypes.wintypes.LPWSTR),
            ("Comment", ctypes.wintypes.LPWSTR),
            ("LastWritten", ctypes.wintypes.FILETIME),
            ("CredentialBlobSize", ctypes.wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
            ("Persist", ctypes.wintypes.DWORD),
            ("AttributeCount", ctypes.wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.wintypes.LPWSTR),
            ("UserName", ctypes.wintypes.LPWSTR),
        ]

    encoded_secret = secret.encode("utf-16-le")
    blob = (ctypes.c_byte * len(encoded_secret))(*encoded_secret)

    cred = _CREDENTIAL()
    cred.Type = _CRED_TYPE_GENERIC
    cred.TargetName = target_name
    cred.UserName = username
    cred.CredentialBlobSize = len(encoded_secret)
    cred.CredentialBlob = blob
    cred.Persist = _CRED_PERSIST_LOCAL_MACHINE

    ok = advapi32.CredWriteW(ctypes.byref(cred), 0)
    return bool(ok)


class SecretStore:
    """Secret store using Windows Credential Manager with environment variable fallback.

    Lookup order for API keys:
    1. Environment variables (highest priority, for CI and scripting)
    2. Windows Credential Manager (for user-configured secrets)
    """

    def get_api_key(self, provider: str) -> str | None:
        # 1. Environment variable lookup.
        for env_var_name in API_KEY_ENV_VARS.get(provider, ()):
            value = os.environ.get(env_var_name, "").strip()
            if value:
                return value

        # 2. Windows Credential Manager lookup.
        target = CREDENTIAL_MANAGER_TARGETS.get(provider)
        if target is not None:
            value = _read_windows_credential(target)
            if value:
                return value

        return None

    def set_api_key(self, provider: str, api_key: str) -> bool:
        """Store an API key in Windows Credential Manager."""
        target = CREDENTIAL_MANAGER_TARGETS.get(provider)
        if target is None:
            return False
        return save_windows_credential(target, provider, api_key)
