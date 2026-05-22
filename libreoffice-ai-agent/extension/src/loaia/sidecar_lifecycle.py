"""Sidecar process lifecycle management.

Detects whether the sidecar is listening and starts it as a subprocess if not.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from multiprocessing.connection import Client
from pathlib import Path

from loaia_shared.transport import DEFAULT_NAMED_PIPE_ADDRESS

_SIDECAR_MODULE = "loaia_sidecar.main"
_MAX_STARTUP_WAIT_SECONDS = 5.0
_POLL_INTERVAL_SECONDS = 0.25

_sidecar_process: subprocess.Popen[bytes] | None = None


def is_sidecar_running(address: str = DEFAULT_NAMED_PIPE_ADDRESS) -> bool:
    """Check if the sidecar is listening on the named pipe."""
    try:
        with Client(address, family="AF_PIPE", authkey=None):
            return True
    except OSError:
        return False


def ensure_sidecar_running(address: str = DEFAULT_NAMED_PIPE_ADDRESS) -> bool:
    """Start the sidecar if not already running. Returns True if sidecar is reachable."""
    global _sidecar_process  # noqa: PLW0603

    if is_sidecar_running(address):
        return True

    # If we previously launched a process that died, clear it.
    if _sidecar_process is not None:
        if _sidecar_process.poll() is not None:
            _sidecar_process = None

    # Only launch if we don't already have a live child.
    if _sidecar_process is None:
        python_exe = _resolve_python_executable()
        env = _build_sidecar_env()
        try:
            _sidecar_process = subprocess.Popen(
                [python_exe, "-m", _SIDECAR_MODULE],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except OSError:
            return False

    # Wait for sidecar to start listening.
    deadline = time.monotonic() + _MAX_STARTUP_WAIT_SECONDS
    while time.monotonic() < deadline:
        if is_sidecar_running(address):
            return True
        if _sidecar_process is not None and _sidecar_process.poll() is not None:
            _sidecar_process = None
            return False
        time.sleep(_POLL_INTERVAL_SECONDS)

    return is_sidecar_running(address)


def stop_sidecar() -> None:
    """Terminate the managed sidecar process if we started one."""
    global _sidecar_process  # noqa: PLW0603

    if _sidecar_process is None:
        return

    try:
        _sidecar_process.terminate()
        _sidecar_process.wait(timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        try:
            _sidecar_process.kill()
        except OSError:
            pass

    _sidecar_process = None


def _resolve_python_executable() -> str:
    """Find the Python executable to use for the sidecar subprocess."""
    return sys.executable or "python"


def _build_sidecar_env() -> dict[str, str]:
    """Build the environment for the sidecar subprocess.

    Inherits current environment and adds PYTHONPATH entries for sidecar and shared sources.
    """
    env = dict(os.environ)

    # Determine the project root (libreoffice-ai-agent/).
    extension_src = Path(__file__).resolve().parent.parent
    project_root = extension_src.parent

    sidecar_src = project_root / "sidecar" / "src"
    shared_src = project_root / "shared" / "src"

    python_path_entries = []
    if sidecar_src.is_dir():
        python_path_entries.append(str(sidecar_src))
    if shared_src.is_dir():
        python_path_entries.append(str(shared_src))

    existing_pythonpath = env.get("PYTHONPATH", "")
    if existing_pythonpath:
        python_path_entries.append(existing_pythonpath)

    env["PYTHONPATH"] = os.pathsep.join(python_path_entries)
    return env


def save_api_key(provider: str, api_key: str) -> bool:
    """Save an API key to the environment variable for the current session.

    Also attempts to save via Windows Credential Manager if available.
    """
    # Set in current process environment so the sidecar inherits it.
    env_var_map = {
        "openrouter": "OPENROUTER_API_KEY",
        "openai-compatible": "OPENAI_API_KEY",
    }
    env_var = env_var_map.get(provider)
    if env_var:
        os.environ[env_var] = api_key

    # Try Windows Credential Manager
    if sys.platform == "win32":
        try:
            import ctypes
            import ctypes.wintypes

            _CRED_TYPE_GENERIC = 1
            _CRED_PERSIST_LOCAL_MACHINE = 2

            target_map = {
                "openrouter": "LibreOfficeAIAgent/openrouter",
                "openai-compatible": "LibreOfficeAIAgent/openai-compatible",
            }
            target = target_map.get(provider)
            if target is None:
                target = f"LibreOfficeAIAgent/{provider}"

            advapi32 = ctypes.windll.advapi32  # type: ignore[attr-defined]

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

            encoded = api_key.encode("utf-16-le")
            blob = (ctypes.c_byte * len(encoded))(*encoded)

            cred = _CREDENTIAL()
            cred.Type = _CRED_TYPE_GENERIC
            cred.TargetName = target
            cred.UserName = provider
            cred.CredentialBlobSize = len(encoded)
            cred.CredentialBlob = blob
            cred.Persist = _CRED_PERSIST_LOCAL_MACHINE

            return bool(advapi32.CredWriteW(ctypes.byref(cred), 0))
        except Exception:
            pass

    return bool(env_var)
