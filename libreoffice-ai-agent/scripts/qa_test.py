#!/usr/bin/env python
"""Automated QA test for the LibreOffice AI Agent sidecar.

Usage:
    python scripts/qa_test.py

Verifies:
1. Sidecar module imports cleanly
2. Server object can be instantiated
3. Named pipe transport starts and responds to handshake
4. End-to-end chat request returns a valid streaming response from OpenRouter
5. Extension sidecar_lifecycle resolves Python and env correctly
"""

import json
import os
import subprocess
import sys
import time
from multiprocessing.connection import Client
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SIDECAR_SRC = PROJECT_ROOT / "sidecar" / "src"
SHARED_SRC = PROJECT_ROOT / "shared" / "src"
EXTENSION_SRC = PROJECT_ROOT / "extension" / "src"

# Ensure our packages are importable
for src_dir in [SIDECAR_SRC, SHARED_SRC, EXTENSION_SRC]:
    src_str = str(src_dir)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

# Load .env
env_file = PROJECT_ROOT / ".env"
if env_file.is_file():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key:
            os.environ.setdefault(key, value)

PIPE_ADDRESS = r"\\.\pipe\loaia-sidecar"
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results: list[tuple[str, bool, str]] = []


def report(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    status = PASS if passed else FAIL
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def test_import() -> bool:
    try:
        from loaia_sidecar.server import LoaiaSidecarServer  # noqa: F401
        report("Import sidecar module", True)
        return True
    except Exception as exc:
        report("Import sidecar module", False, str(exc))
        return False


def test_server_creation() -> bool:
    try:
        from loaia_sidecar.server import LoaiaSidecarServer

        server = LoaiaSidecarServer()
        providers = list(server.provider_adapters.keys())
        has_key = bool(server.secret_store.get_api_key("openrouter"))
        report("Server instantiation", True, f"providers={providers}, api_key={'set' if has_key else 'MISSING'}")
        if not has_key:
            report("API key available", False, "OPENROUTER_API_KEY not found")
            return False
        return True
    except Exception as exc:
        report("Server instantiation", False, str(exc))
        return False


def test_lifecycle_resolution() -> bool:
    try:
        from loaia.sidecar_lifecycle import _resolve_python_executable, _build_sidecar_env

        py = _resolve_python_executable()
        env = _build_sidecar_env()
        py_exists = os.path.isfile(py)
        has_pythonpath = bool(env.get("PYTHONPATH"))
        no_pythonhome = "PYTHONHOME" not in env
        no_lo_in_path = not any("LibreOffice" in p for p in env.get("PATH", "").split(os.pathsep))
        has_api_key = bool(env.get("OPENROUTER_API_KEY"))

        all_ok = py_exists and has_pythonpath and no_pythonhome and no_lo_in_path and has_api_key
        detail = f"python={py}, pythonpath={'OK' if has_pythonpath else 'MISSING'}, clean_env={no_pythonhome and no_lo_in_path}, api_key={'OK' if has_api_key else 'MISSING'}"
        report("Lifecycle env resolution", all_ok, detail)
        return all_ok
    except Exception as exc:
        report("Lifecycle env resolution", False, str(exc))
        return False


def test_pipe_handshake(server_proc: subprocess.Popen) -> bool:
    """Test handshake against a running sidecar."""
    try:
        conn = Client(PIPE_ADDRESS, family="AF_PIPE")
        msg = json.dumps({"type": "HandshakeRequest"}).encode("utf-8")
        conn.send_bytes(msg)
        resp = json.loads(conn.recv_bytes().decode("utf-8"))
        conn.close()

        is_handshake = resp.get("type") == "HandshakeResponse"
        has_providers = bool(resp.get("availableProviders"))
        ok = is_handshake and has_providers
        report("Pipe handshake", ok, f"version={resp.get('serverVersion')}, providers={resp.get('availableProviders')}")
        return ok
    except Exception as exc:
        report("Pipe handshake", False, str(exc))
        return False


def test_chat_request() -> bool:
    """Send a real chat request (question) and verify streaming DirectAnswer response."""
    try:
        conn = Client(PIPE_ADDRESS, family="AF_PIPE")
        chat_msg = json.dumps({
            "type": "ChatRequest",
            "requestId": "qa-test-001",
            "userMessage": "What is 2+2? Reply with just the number.",
            "provider": "openrouter",
            "model": os.environ.get("LOAIA_DEFAULT_MODEL", "minimax/minimax-m2.7"),
            "privacyScope": "full-document",
            "app": "writer",
            "document": {"canonicalUrl": "file:///qa-test.odt", "profileId": "qa-profile"},
            "context": {
                "selection": {"text": "Test document content.", "mimeType": "text/plain"}
            },
        }).encode("utf-8")
        conn.send_bytes(chat_msg)

        frames: list[dict] = []
        while True:
            try:
                data = conn.recv_bytes()
                frame = json.loads(data.decode("utf-8"))
                frames.append(frame)
            except EOFError:
                break
        conn.close()

        if not frames:
            report("Chat request (DirectAnswer)", False, "No frames received")
            return False

        last = frames[-1]
        last_type = last.get("type")

        if last_type == "ErrorResponse":
            report("Chat request (DirectAnswer)", False, f"Error: {last.get('message', '')[:100]}")
            return False

        if last_type == "DirectAnswer":
            text = last.get("text", "")
            stream_count = sum(1 for f in frames if f.get("type") == "StreamChunk")
            report("Chat request (DirectAnswer)", True, f"streamed={stream_count} chunks, answer={text[:60]}")
            return True

        report("Chat request (DirectAnswer)", False, f"Unexpected final type: {last_type}")
        return False
    except Exception as exc:
        report("Chat request (DirectAnswer)", False, str(exc))
        return False


def test_translate_request() -> bool:
    """Send a translate request and verify it returns a ToolProposal (replace-selection)."""
    try:
        conn = Client(PIPE_ADDRESS, family="AF_PIPE")
        chat_msg = json.dumps({
            "type": "ChatRequest",
            "requestId": "qa-test-002",
            "userMessage": "translate to chinese",
            "provider": "openrouter",
            "model": os.environ.get("LOAIA_DEFAULT_MODEL", "minimax/minimax-m2.7"),
            "privacyScope": "full-document",
            "app": "writer",
            "document": {"canonicalUrl": "file:///qa-test.odt", "profileId": "qa-profile"},
            "context": {
                "selection": {"text": "Hello world", "mimeType": "text/plain"}
            },
        }).encode("utf-8")
        conn.send_bytes(chat_msg)

        frames: list[dict] = []
        while True:
            try:
                data = conn.recv_bytes()
                frame = json.loads(data.decode("utf-8"))
                frames.append(frame)
            except EOFError:
                break
        conn.close()

        if not frames:
            report("Translate → ToolProposal", False, "No frames received")
            return False

        last = frames[-1]
        last_type = last.get("type")

        if last_type == "ErrorResponse":
            report("Translate → ToolProposal", False, f"Error: {last.get('message', '')[:100]}")
            return False

        if last_type == "ToolProposal":
            proposals = last.get("proposals", [])
            tool_id = proposals[0].get("toolId", "") if proposals else ""
            replacement = proposals[0].get("arguments", {}).get("replacementText", "") if proposals else ""
            report("Translate → ToolProposal", True, f"tool={tool_id}, replacement={replacement[:40]}")
            return True

        report("Translate → ToolProposal", False, f"Got type={last_type} instead of ToolProposal")
        return False
    except Exception as exc:
        report("Translate → ToolProposal", False, str(exc))
        return False


def test_heading_request() -> bool:
    """Send 'change to h1' and verify it returns ApplyHeading1 (safe formatting)."""
    try:
        conn = Client(PIPE_ADDRESS, family="AF_PIPE")
        chat_msg = json.dumps({
            "type": "ChatRequest",
            "requestId": "qa-test-003",
            "userMessage": "change to h1",
            "provider": "openrouter",
            "model": os.environ.get("LOAIA_DEFAULT_MODEL", "minimax/minimax-m2.7"),
            "privacyScope": "full-document",
            "app": "writer",
            "document": {"canonicalUrl": "file:///qa-test.odt", "profileId": "qa-profile"},
            "context": {
                "selection": {"text": "My Title", "mimeType": "text/plain"}
            },
        }).encode("utf-8")
        conn.send_bytes(chat_msg)

        frames: list[dict] = []
        while True:
            try:
                data = conn.recv_bytes()
                frame = json.loads(data.decode("utf-8"))
                frames.append(frame)
            except EOFError:
                break
        conn.close()

        if not frames:
            report("Heading h1 → ApplyHeading1", False, "No frames received")
            return False

        last = frames[-1]
        last_type = last.get("type")

        if last_type == "ToolProposal":
            proposals = last.get("proposals", [])
            tool_id = proposals[0].get("toolId", "") if proposals else ""
            ok = tool_id == "Writer.ApplyHeading1"
            report("Heading h1 → ApplyHeading1", ok, f"tool={tool_id}")
            return ok

        report("Heading h1 → ApplyHeading1", False, f"Got type={last_type}")
        return False
    except Exception as exc:
        report("Heading h1 → ApplyHeading1", False, str(exc))
        return False


def main() -> int:
    print(f"\n{'='*60}")
    print(f"  LibreOffice AI Agent — QA Test Suite (v0.1.5)")
    print(f"{'='*60}\n")

    # Phase 1: Static checks
    print("Phase 1: Module & Config Checks")
    if not test_import():
        print("\nCannot proceed — import failed.")
        return 1
    test_server_creation()
    test_lifecycle_resolution()

    # Phase 2: Live sidecar test
    print("\nPhase 2: Live Sidecar Integration")

    # Kill any stale sidecar that might be holding the pipe
    try:
        conn = Client(PIPE_ADDRESS, family="AF_PIPE")
        conn.close()
        print("  Killing stale sidecar on pipe...")
        if sys.platform == "win32":
            os.system('taskkill /f /fi "IMAGENAME eq python.exe" /fi "WINDOWTITLE eq loaia*" >nul 2>&1')
            # Also try via port connection to force close
            import signal
            # Just wait a moment for pipe to release
            time.sleep(1.0)
    except OSError:
        pass  # No stale process

    print("  Starting sidecar subprocess...")

    env = dict(os.environ)
    env["PYTHONPATH"] = f"{SIDECAR_SRC}{os.pathsep}{SHARED_SRC}"
    env.pop("PYTHONHOME", None)

    server_proc = subprocess.Popen(
        [sys.executable, "-c", "from loaia_sidecar.main import main; main()"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    # Wait for pipe to become available
    deadline = time.monotonic() + 5.0
    ready = False
    while time.monotonic() < deadline:
        try:
            with Client(PIPE_ADDRESS, family="AF_PIPE"):
                ready = True
                break
        except OSError:
            time.sleep(0.2)

    if not ready:
        stderr_out = server_proc.stderr.read().decode("utf-8", errors="replace") if server_proc.stderr else ""
        report("Sidecar startup", False, f"Pipe not available after 5s. stderr: {stderr_out[:200]}")
        server_proc.kill()
        server_proc.wait()
    else:
        report("Sidecar startup", True, f"PID={server_proc.pid}")
        test_pipe_handshake(server_proc)
        test_chat_request()
        test_translate_request()
        test_heading_request()

        # Cleanup
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_proc.kill()
            server_proc.wait()

    # Summary
    print(f"\n{'='*60}")
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"  Results: {passed} passed, {failed} failed, {len(results)} total")
    print(f"{'='*60}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
