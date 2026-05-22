from __future__ import annotations

import sys

from verification_probe_common import (
    close_document_session,
    connect,
    get_sidebar_panel_window,
    load_document,
    make_property,
    make_url,
    model_text,
)

INVALID_SELECTION = "invalid-selection"
UNSUPPORTED_DOCUMENT = "unsupported-document"
TRANSPORT_ERROR = "transport-error"


def shorten_text(text: str, limit: int = 90) -> str:
    normalized = text.strip()
    if len(normalized) <= limit:
        return normalized

    return f"{normalized[: limit - 3].rstrip()}..."


def verify(
    context: object,
    prompt: str,
    initial_text: str,
    scenario: str = INVALID_SELECTION,
    pipe_address: str | None = None,
) -> int:
    if scenario == INVALID_SELECTION:
        expected_error = "Select text in Writer before sending a request."
        expected_status_error = expected_error
        expected_recent_activity = expected_error
        document_url = "private:factory/swriter"
        value_key = "DOC_TEXT"
        waiting_failure = (
            "Connection state did not remain in the waiting state after invalid selection."
        )
        expected_error_failure = (
            "Sidebar status did not show the expected invalid-selection error."
        )
        recent_activity_failure = (
            "Sidebar recent activity did not include the invalid-selection error."
        )
        unchanged_value_failure = (
            "Invalid-selection flow unexpectedly changed the Writer document."
        )
        approve_failure = "Approve should stay disabled after invalid selection."
        expected_selection_summary = "Selection:\nNo captured selection yet."
    elif scenario == UNSUPPORTED_DOCUMENT:
        expected_error = "Sidebar actions currently support Writer documents only."
        expected_status_error = expected_error
        expected_recent_activity = expected_error
        document_url = "private:factory/scalc"
        value_key = "CELL_TEXT"
        waiting_failure = (
            "Connection state did not remain in the waiting state after unsupported "
            "document validation."
        )
        expected_error_failure = (
            "Sidebar status did not show the expected Writer-only error."
        )
        recent_activity_failure = (
            "Sidebar recent activity did not include the Writer-only error."
        )
        unchanged_value_failure = (
            "Unsupported-document flow unexpectedly changed the Calc cell value."
        )
        approve_failure = (
            "Approve should stay disabled after unsupported document validation."
        )
        expected_selection_summary = "Selection:\nNo captured selection yet."
    elif scenario == TRANSPORT_ERROR:
        if not pipe_address:
            print("Missing pipe address for transport-error scenario.", file=sys.stderr)
            return 2

        expected_error = f"Could not connect to sidecar pipe at {pipe_address}"
        expected_status_error = shorten_text(expected_error, limit=90)
        expected_recent_activity = expected_status_error
        document_url = "private:factory/swriter"
        value_key = "DOC_TEXT"
        waiting_failure = (
            "Connection state did not remain in the waiting state after transport error."
        )
        expected_error_failure = (
            "Sidebar status did not show the expected sidecar transport error."
        )
        recent_activity_failure = (
            "Sidebar recent activity did not include the transport error."
        )
        unchanged_value_failure = (
            "Transport error flow unexpectedly changed the Writer document."
        )
        approve_failure = "Approve should stay disabled after a transport error."
        expected_selection_summary = f"Selection:\n{initial_text}"
    else:
        print(f"Unsupported scenario: {scenario}", file=sys.stderr)
        return 2

    desktop = None
    document = None
    try:
        desktop, document = load_document(context, document_url)
        controller = document.getCurrentController()
        frame = controller.getFrame()

        open_sidebar_url = make_url("open-sidebar")
        preview_url = make_url("preview-selection")
        open_dispatch = frame.queryDispatch(open_sidebar_url, "_self", 0)
        preview_dispatch = frame.queryDispatch(preview_url, "_self", 0)
        results: dict[str, str] = {
            "OPEN_SIDEBAR_DISPATCH_PRESENT": str(open_dispatch is not None),
            "PREVIEW_DISPATCH_PRESENT": str(preview_dispatch is not None),
        }

        if open_dispatch is None or preview_dispatch is None:
            for key, value in results.items():
                print(f"{key}={value}")
            print("VALIDATION_PASSED=False")
            print("FAILURE=Protocol dispatch is not available for one or more commands.")
            return 1

        open_dispatch.dispatch(open_sidebar_url, ())

        panel_window = get_sidebar_panel_window(context, frame)

        status_after_open = model_text(panel_window.getControl("Status"))
        approve_button = panel_window.getControl("ApproveButton")
        results["OPEN_STATUS_HAS_COMMAND"] = str(
            "Last command: open-sidebar" in status_after_open
        )
        results["APPROVE_ENABLED_AFTER_OPEN"] = str(approve_button.isEnabled())

        if scenario in (INVALID_SELECTION, TRANSPORT_ERROR):
            text = document.Text
            cursor = text.createTextCursor()
            text.insertString(cursor, initial_text, False)
            if scenario == TRANSPORT_ERROR:
                cursor.gotoStart(False)
                cursor.goRight(len(initial_text), True)
                controller.select(cursor)
            current_value = document.Text.getString()
        else:
            sheet = document.getSheets().getByIndex(0)
            cell = sheet.getCellByPosition(0, 0)
            cell.setString(initial_text)
            current_value = cell.getString()

        dispatch_properties = [make_property("Prompt", prompt)]
        if scenario == TRANSPORT_ERROR:
            dispatch_properties.append(make_property("PipeAddress", pipe_address))

        preview_dispatch.dispatch(preview_url, tuple(dispatch_properties))

        status_after_error = model_text(panel_window.getControl("Status"))
        summary_after_error = model_text(panel_window.getControl("Summary"))
        results["STILL_WAITING_AFTER_ERROR"] = str(
            "Connection: waiting for first sidecar response" in status_after_error
        )
        results["LAST_COMMAND_AFTER_ERROR"] = str(
            "Last command: preview-selection" in status_after_error
        )
        results["HAS_EXPECTED_ERROR_IN_STATUS"] = str(
            f"Last error: {expected_status_error}" in status_after_error
        )
        results["HAS_PROMPT_IN_SUMMARY"] = str(f"Prompt:\n{prompt}" in summary_after_error)
        results["HAS_EXPECTED_SELECTION_IN_SUMMARY"] = str(
            expected_selection_summary in summary_after_error
        )
        results["HAS_NO_PENDING_PREVIEW"] = str(
            "Pending preview:\nNo pending proposal." in summary_after_error
        )
        results["HAS_NO_RESULT"] = str(
            "Last result:\nNo completed result yet." in summary_after_error
        )
        results["HAS_RECENT_ERROR_ACTIVITY"] = str(
            f"Recent activity:\n- {expected_recent_activity}" in summary_after_error
        )
        results[value_key] = current_value
        results["APPROVE_ENABLED_AFTER_ERROR"] = str(approve_button.isEnabled())

        failures: list[str] = []
        if results["OPEN_STATUS_HAS_COMMAND"] != "True":
            failures.append("Sidebar status did not reflect the open-sidebar command.")
        if results["APPROVE_ENABLED_AFTER_OPEN"] != "False":
            failures.append("Approve should start disabled after opening the sidebar.")
        if results["STILL_WAITING_AFTER_ERROR"] != "True":
            failures.append(waiting_failure)
        if results["LAST_COMMAND_AFTER_ERROR"] != "True":
            failures.append("Sidebar status did not reflect the preview-selection command.")
        if results["HAS_EXPECTED_ERROR_IN_STATUS"] != "True":
            failures.append(expected_error_failure)
        if results["HAS_PROMPT_IN_SUMMARY"] != "True":
            failures.append("Sidebar summary did not retain the submitted prompt.")
        if results["HAS_EXPECTED_SELECTION_IN_SUMMARY"] != "True":
            failures.append("Sidebar summary did not show the expected selection state.")
        if results["HAS_NO_PENDING_PREVIEW"] != "True":
            failures.append("Sidebar summary did not show the empty pending-preview state.")
        if results["HAS_NO_RESULT"] != "True":
            failures.append("Sidebar summary did not keep the empty last-result state.")
        if results["HAS_RECENT_ERROR_ACTIVITY"] != "True":
            failures.append(recent_activity_failure)
        if results[value_key] != initial_text:
            failures.append(unchanged_value_failure)
        if results["APPROVE_ENABLED_AFTER_ERROR"] != "False":
            failures.append(approve_failure)

        for key, value in results.items():
            print(f"{key}={value}")

        if failures:
            print("VALIDATION_PASSED=False")
            for failure in failures:
                print(f"FAILURE={failure}")
            return 1

        print("VALIDATION_PASSED=True")
        return 0
    finally:
        close_document_session(document=document, desktop=desktop)


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4, 5):
        print(
            "Usage: verify_sidebar_invalid_selection.py <pipe_name> <prompt> "
            "<initial_text> [<scenario> [<pipe_address>]]",
            file=sys.stderr,
        )
        return 2

    pipe_name, prompt, initial_text, *extra = argv
    scenario = extra[0] if extra else INVALID_SELECTION
    pipe_address = extra[1] if len(extra) > 1 else None
    context = connect(pipe_name)
    return verify(
        context=context,
        prompt=prompt,
        initial_text=initial_text,
        scenario=scenario,
        pipe_address=pipe_address,
    )


def cli(argv: list[str]) -> int:
    try:
        return main(argv)
    except Exception as error:
        print(
            f"UNHANDLED_EXCEPTION={error.__class__.__name__}: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))