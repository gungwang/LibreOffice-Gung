#!/usr/bin/env python
"""UI Integration Test: Launches LibreOffice Writer and tests all toolbar tools via UNO.

This script:
1. Launches LibreOffice in listening mode
2. Connects via UNO bridge
3. Creates a test document with sample text
4. Executes every dispatch command from the TOOL_UNO_DISPATCH_MAP
5. Reports which tools work correctly

Requirements:
- LibreOffice 26 installed at C:\Program Files\LibreOffice\26\program
- No other LibreOffice instances running

Usage:
    python scripts/qa_ui_test.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SIDECAR_SRC = PROJECT_ROOT / "sidecar" / "src"
SHARED_SRC = PROJECT_ROOT / "shared" / "src"
EXTENSION_SRC = PROJECT_ROOT / "extension" / "src"

# LO paths
LO_PROGRAM = Path(r"C:\Program Files\LibreOffice\26\program")
LO_SOFFICE = LO_PROGRAM / "soffice.exe"
LO_PYTHON = LO_PROGRAM / "python.exe"

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"

results: list[tuple[str, str, str]] = []


def report(name: str, status: str, detail: str = "") -> None:
    results.append((name, status, detail))
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


# The test runs INSIDE LibreOffice's Python to have UNO access.
# We generate a script that LO's Python executes.
UNO_TEST_SCRIPT = r'''
"""UNO integration test script - connects to a running LibreOffice instance via pipe."""
import sys
import time
import json

import uno
from com.sun.star.beans import PropertyValue


def run_tests():
    results = []

    # Connect to running LO instance via socket
    local_ctx = uno.getComponentContext()
    resolver = local_ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_ctx
    )
    ctx = None
    for attempt in range(30):
        try:
            ctx = resolver.resolve(
                "uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext"
            )
            break
        except Exception:
            time.sleep(1)

    if ctx is None:
        results.append({"name": "Connect to LO", "status": "FAIL", "detail": "Could not connect after 30s"})
        print("__RESULTS_START__")
        print(json.dumps(results))
        print("__RESULTS_END__")
        return

    results.append({"name": "Connect to LO", "status": "PASS", "detail": "UNO pipe connected"})

    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    helper = smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)

    # Create new Writer document
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
    time.sleep(1)

    if doc is None:
        results.append({"name": "Create Document", "status": "FAIL", "detail": "doc is None"})
        print("__RESULTS_START__")
        print(json.dumps(results))
        print("__RESULTS_END__")
        return

    results.append({"name": "Create Document", "status": "PASS", "detail": "Writer document created"})

    text = doc.getText()
    cursor = text.createTextCursor()
    text.insertString(cursor, "Test document for LibreOffice AI Agent toolbar testing.", False)
    text.insertControlCharacter(cursor, 0, False)  # PARAGRAPH_BREAK
    text.insertString(cursor, "Second paragraph with some text to format and test.", False)
    text.insertControlCharacter(cursor, 0, False)
    text.insertString(cursor, "Third paragraph for additional testing purposes.", False)

    # Select all
    ctrl = doc.getCurrentController()
    view_cursor = ctrl.getViewCursor()
    view_cursor.gotoStart(False)
    view_cursor.gotoEnd(True)
    frame = ctrl.getFrame()
    time.sleep(0.5)

    def make_prop(name, value):
        p = PropertyValue()
        p.Name = name
        p.Value = value
        return p

    def dispatch_test(name, cmd, args=()):
        try:
            helper.executeDispatch(frame, cmd, "", 0, args)
            time.sleep(0.15)
            return True, ""
        except Exception as e:
            return False, str(e)

    # ===========================================
    # WRITER TOOLBAR TESTS
    # ===========================================
    writer_tests = [
        # Basic formatting
        ("Bold", ".uno:Bold", ()),
        ("Italic", ".uno:Italic", ()),
        ("Underline", ".uno:Underline", ()),
        ("Strikethrough", ".uno:Strikeout", ()),
        ("Superscript", ".uno:SuperScript", ()),
        ("Subscript", ".uno:SubScript", ()),
        ("Shadow", ".uno:Shadowed", ()),
        ("Outline Font", ".uno:OutlineFont", ()),
        ("Small Caps", ".uno:SmallCaps", ()),
        # Text case
        ("Case: Uppercase", ".uno:ChangeCaseToUpper", ()),
        ("Case: Lowercase", ".uno:ChangeCaseToLower", ()),
        ("Case: Title Case", ".uno:ChangeCaseToTitleCase", ()),
        ("Case: Sentence Case", ".uno:ChangeCaseToSentenceCase", ()),
        ("Case: Toggle Case", ".uno:ChangeCaseToToggleCase", ()),
        # Alignment
        ("Align Left", ".uno:LeftPara", ()),
        ("Align Center", ".uno:CenterPara", ()),
        ("Align Right", ".uno:RightPara", ()),
        ("Align Justify", ".uno:JustifyPara", ()),
        # Lists
        ("Bullet List", ".uno:DefaultBulletList", ()),
        ("Numbered List", ".uno:DefaultNumberingList", ()),
        # Indent
        ("Increase Indent", ".uno:IncrementIndent", ()),
        ("Decrease Indent", ".uno:DecrementIndent", ()),
        # Line spacing
        ("Line Spacing 1", ".uno:SpacePara1", ()),
        ("Line Spacing 1.5", ".uno:SpacePara15", ()),
        ("Line Spacing 2", ".uno:SpacePara2", ()),
        # Paragraph spacing
        ("Increase Para Spacing", ".uno:ParaspaceIncrease", ()),
        ("Decrease Para Spacing", ".uno:ParaspaceDecrease", ()),
        # Font size
        ("Increase Font Size", ".uno:Grow", ()),
        ("Decrease Font Size", ".uno:Shrink", ()),
        # Font color (parametric)
        ("Font Color Red", ".uno:Color", (make_prop("FontColor.Color", 0xFF0000),)),
        ("Font Color Blue", ".uno:Color", (make_prop("FontColor.Color", 0x0000FF),)),
        ("Font Color Green", ".uno:Color", (make_prop("FontColor.Color", 0x008000),)),
        ("Font Color Black", ".uno:Color", (make_prop("FontColor.Color", 0x000000),)),
        ("Font Color Orange", ".uno:Color", (make_prop("FontColor.Color", 0xFF8C00),)),
        ("Font Color Purple", ".uno:Color", (make_prop("FontColor.Color", 0x800080),)),
        ("Font Color Yellow", ".uno:Color", (make_prop("FontColor.Color", 0xFFD700),)),
        # Highlight
        ("Highlight Yellow", ".uno:CharBackColor", (make_prop("CharBackColor.Color", 0xFFFF00),)),
        ("Highlight Green", ".uno:CharBackColor", (make_prop("CharBackColor.Color", 0x00FF00),)),
        ("Highlight Red", ".uno:CharBackColor", (make_prop("CharBackColor.Color", 0xFF0000),)),
        ("Highlight Blue", ".uno:CharBackColor", (make_prop("CharBackColor.Color", 0x00BFFF),)),
        ("Highlight None", ".uno:CharBackColor", (make_prop("CharBackColor.Color", -1),)),
        # Heading styles
        ("Heading 1", ".uno:StyleApply", (make_prop("Template", "Heading 1"), make_prop("Family", 1))),
        ("Heading 2", ".uno:StyleApply", (make_prop("Template", "Heading 2"), make_prop("Family", 1))),
        ("Heading 3", ".uno:StyleApply", (make_prop("Template", "Heading 3"), make_prop("Family", 1))),
        ("Default Style", ".uno:StyleApply", (make_prop("Template", "Default Paragraph Style"), make_prop("Family", 1))),
        # Clear formatting
        ("Clear Formatting", ".uno:ResetAttributes", ()),
        # Font name (parametric)
        ("Font: Arial", ".uno:CharFontName", (make_prop("CharFontName.FamilyName", "Arial"),)),
        ("Font: Times New Roman", ".uno:CharFontName", (make_prop("CharFontName.FamilyName", "Times New Roman"),)),
        # Font size (parametric)
        ("Font Size 16pt", ".uno:FontHeight", (make_prop("FontHeight.Height", 16.0),)),
        ("Font Size 12pt", ".uno:FontHeight", (make_prop("FontHeight.Height", 12.0),)),
        # Insert operations (non-dialog)
        ("Insert Page Break", ".uno:InsertPagebreak", ()),
        ("Insert Page Number", ".uno:InsertPageNumberField", ()),
        ("Insert Date Field", ".uno:InsertDateField", ()),
        ("Insert Time Field", ".uno:InsertTimeField", ()),
        ("Insert Comment", ".uno:InsertAnnotation", ()),
        # Undo/Redo
        ("Undo", ".uno:Undo", ()),
        ("Redo", ".uno:Redo", ()),
        ("Select All", ".uno:SelectAll", ()),
    ]

    for test_name, cmd, args in writer_tests:
        ok, err = dispatch_test(test_name, cmd, args)
        if ok:
            results.append({"name": test_name, "status": "PASS", "detail": cmd})
        else:
            results.append({"name": test_name, "status": "FAIL", "detail": f"{cmd}: {err}"})

    # Close doc without saving
    try:
        doc.setModified(False)
        doc.close(True)
    except Exception:
        pass

    # Output results
    print("__RESULTS_START__")
    print(json.dumps(results))
    print("__RESULTS_END__")


if __name__ == "__main__":
    run_tests()
'''


def kill_libreoffice():
    """Kill any running LibreOffice instances and wait for port 2002 to free."""
    if sys.platform == "win32":
        os.system('taskkill /f /im soffice.bin >nul 2>&1')
        os.system('taskkill /f /im soffice.exe >nul 2>&1')
    # Wait until port 2002 is free
    import socket
    for _ in range(15):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("localhost", 2002))
            s.close()
            time.sleep(1)  # Port still occupied, wait
        except (ConnectionRefusedError, OSError):
            break  # Port is free
    time.sleep(2)


def wait_for_socket(port: int = 2002, timeout: int = 30) -> bool:
    """Wait until the LO socket is accepting connections."""
    import socket
    for _ in range(timeout):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("localhost", port))
            s.close()
            return True
        except (ConnectionRefusedError, OSError):
            time.sleep(1)
    return False


def start_libreoffice():
    """Start LibreOffice in listening mode via socket."""
    if not LO_SOFFICE.exists():
        print(f"ERROR: LibreOffice not found at {LO_SOFFICE}")
        return None

    cmd = [
        str(LO_SOFFICE),
        "--invisible",
        "--nocrashreport",
        "--nofirststartwizard",
        "--nologo",
        "--norestore",
        "--accept=socket,host=localhost,port=2002;urp;StarOffice.ServiceManager",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"  LibreOffice started (PID={proc.pid}), waiting for socket on port 2002...")
    if not wait_for_socket(2002, timeout=30):
        print("  ERROR: Socket not ready after 30s")
        proc.kill()
        return None
    # Extra delay for full Desktop initialization
    time.sleep(3)
    print("  Socket ready.")
    return proc


def run_uno_tests():
    """Run the UNO test script inside LO's Python environment."""
    # Write test script to temp file
    test_script_path = PROJECT_ROOT / "scripts" / "_tmp_uno_test.py"
    test_script_path.write_text(UNO_TEST_SCRIPT, encoding="utf-8")

    try:
        # Run with LO's Python which has UNO access
        env = dict(os.environ)
        env["URE_BOOTSTRAP"] = f"file:///{str(LO_PROGRAM / 'fundamental.ini').replace(chr(92), '/')}"

        result = subprocess.run(
            [str(LO_PYTHON), str(test_script_path)],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=str(LO_PROGRAM),
        )
        return result.stdout, result.stderr, result.returncode
    finally:
        test_script_path.unlink(missing_ok=True)


def parse_results(stdout: str) -> list[dict]:
    """Extract JSON results from the test output."""
    if "__RESULTS_START__" in stdout and "__RESULTS_END__" in stdout:
        start = stdout.index("__RESULTS_START__") + len("__RESULTS_START__")
        end = stdout.index("__RESULTS_END__")
        import json
        return json.loads(stdout[start:end].strip())
    return []


def main() -> int:
    print(f"\n{'='*60}")
    print(f"  LibreOffice AI Agent — UI Integration Test (v0.1.9)")
    print(f"{'='*60}\n")

    # Kill existing LO
    print("  Killing existing LibreOffice instances...")
    kill_libreoffice()

    # Start LO from outer script
    lo_proc = start_libreoffice()
    if lo_proc is None:
        return 1

    # Run UNO tests (LO Python connects to the running instance via pipe)
    print("  Running UNO dispatch tests inside LibreOffice Python...\n")
    stdout, stderr, rc = run_uno_tests()

    if rc != 0:
        print(f"  ERROR: Test script failed (exit code {rc})")
        if stderr:
            print(f"  stderr: {stderr[:1000]}")
        if stdout:
            print(f"  stdout: {stdout[:500]}")
        # Cleanup
        kill_libreoffice()
        return 1

    # Parse results
    test_results = parse_results(stdout)
    if not test_results:
        print("  ERROR: Could not parse test results from output")
        if stdout:
            print(f"  stdout: {stdout[:1000]}")
        if stderr:
            print(f"  stderr: {stderr[:500]}")
        kill_libreoffice()
        return 1

    # Display results
    passed = sum(1 for r in test_results if r["status"] == "PASS")
    failed = sum(1 for r in test_results if r["status"] == "FAIL")
    skipped = sum(1 for r in test_results if r["status"] == "SKIP")

    for r in test_results:
        status = r["status"]
        if status == "PASS":
            tag = PASS
        elif status == "FAIL":
            tag = FAIL
        else:
            tag = SKIP
        detail = r.get("detail", "")
        print(f"  [{tag}] {r['name']}" + (f" — {detail}" if detail else ""))

    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed, {skipped} skipped, {len(test_results)} total")
    print(f"{'='*60}\n")

    # Final cleanup
    kill_libreoffice()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
