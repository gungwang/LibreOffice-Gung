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
