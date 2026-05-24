from __future__ import annotations

import sys

from verification_probe_common import (
    coerce_sidebar_messages,
    close_document_session,
    connect,
    find_sidebar_session,
    load_document,
    make_property,
    make_url,
    wait_for_uno_result,
)

INVALID_SELECTION = "invalid-selection"
UNSUPPORTED_DOCUMENT = "unsupported-document"
TRANSPORT_ERROR = "transport-error"


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
        expected_error = "Select a shape with text in Draw before sending a request."
        expected_status_error = expected_error
        expected_recent_activity = expected_error
        document_url = "private:factory/sdraw"
        value_key = "DOC_TEXT"
        waiting_failure = (
            "Connection state did not remain in the waiting state after empty "
            "Draw document validation."
        )
        expected_error_failure = (
            "Sidebar status did not show the expected Draw empty-selection error."
        )
        recent_activity_failure = (
            "Sidebar recent activity did not include the Draw empty-selection error."
        )
        unchanged_value_failure = (
            "Draw empty-selection flow unexpectedly changed the document."
        )
        approve_failure = (
            "Approve should stay disabled after Draw empty-selection validation."
        )
        expected_selection_summary = "Selection:\nNo captured selection yet."
    elif scenario == TRANSPORT_ERROR:
        if not pipe_address:
            print("Missing pipe address for transport-error scenario.", file=sys.stderr)
            return 2

        expected_error = f"Could not connect to sidecar pipe at {pipe_address}"
        document_url = "private:factory/swriter"
    else:
        print(f"Unsupported scenario: {scenario}", file=sys.stderr)
        return 2

    desktop = None
    document = None
    stage = "load_document"
    try:
        stage = "load_document"
        desktop, document = load_document(context, document_url)
        stage = "get_controller"
        controller = document.getCurrentController()
        frame = controller.getFrame()

        stage = "query_dispatch"
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

        stage = "open_sidebar"
        open_dispatch.dispatch(open_sidebar_url, ())

        current_value = initial_text
        shape_count_before: int | None = None
        stage = "prepare_document"
        if scenario in (INVALID_SELECTION, TRANSPORT_ERROR):
            text = document.Text
            cursor = text.createTextCursor()
            text.insertString(cursor, initial_text, False)
            if scenario == TRANSPORT_ERROR:
                cursor.gotoStart(False)
                cursor.goRight(len(initial_text), True)
                controller.select(cursor)
            current_value = document.Text.getString()
        elif scenario == UNSUPPORTED_DOCUMENT:
            draw_page = document.getDrawPages().getByIndex(0)
            shape_count_before = draw_page.getCount()

        dispatch_properties = [make_property("Prompt", prompt)]
        if scenario == TRANSPORT_ERROR:
            dispatch_properties.append(make_property("PipeAddress", pipe_address))

        stage = "dispatch_preview"
        preview_dispatch.dispatch(preview_url, tuple(dispatch_properties))
        stage = "wait_for_session_error"
        _state_data, session_payload = wait_for_uno_result(
            lambda: find_sidebar_session(last_prompt=prompt, require_error=True),
            f"{scenario} session error state",
        )
        messages = coerce_sidebar_messages(session_payload)
        user_message = next((message for message in reversed(messages) if message["role"] == "user"), None)
        system_message = next((message for message in reversed(messages) if message["role"] == "system"), None)

        results["LAST_ERROR_MATCHES"] = str(session_payload.get("lastError") == expected_error)
        results["HAS_USER_MESSAGE"] = str(
            user_message is not None and user_message.get("text") == prompt
        )
        results["HAS_SYSTEM_MESSAGE"] = str(
            system_message is not None and system_message.get("text") == expected_error
        )

        if scenario == UNSUPPORTED_DOCUMENT:
            draw_page = document.getDrawPages().getByIndex(0)
            results["DRAW_SHAPE_COUNT_BEFORE"] = str(shape_count_before)
            results["DRAW_SHAPE_COUNT_AFTER"] = str(draw_page.getCount())
            results["DOCUMENT_UNCHANGED"] = str(draw_page.getCount() == shape_count_before)
        else:
            results["DOC_TEXT"] = document.Text.getString()
            results["DOCUMENT_UNCHANGED"] = str(document.Text.getString() == current_value)

        failures: list[str] = []
        if results["LAST_ERROR_MATCHES"] != "True":
            failures.append(f"{scenario} flow did not record the expected error.")
        if results["HAS_USER_MESSAGE"] != "True":
            failures.append(f"{scenario} flow did not record the submitted prompt.")
        if results["HAS_SYSTEM_MESSAGE"] != "True":
            failures.append(f"{scenario} flow did not record the expected error activity.")
        if results["DOCUMENT_UNCHANGED"] != "True":
            failures.append(f"{scenario} flow unexpectedly changed the document.")

        for key, value in results.items():
            print(f"{key}={value}")

        if failures:
            print("VALIDATION_PASSED=False")
            for failure in failures:
                print(f"FAILURE={failure}")
            return 1

        print("VALIDATION_PASSED=True")
        return 0
    except Exception:
        print(f"FAILED_STAGE={stage}", file=sys.stderr)
        raise
    finally:
        try:
            close_document_session(document=document, desktop=desktop)
        except Exception:
            print("FAILED_STAGE=close_document_session", file=sys.stderr)
            raise


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