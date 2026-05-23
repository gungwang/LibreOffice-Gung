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

NON_SCAFFOLD_SENTINEL = "__NON_SCAFFOLD__"
SCAFFOLD_DIRECT_ANSWER = (
    "Sidecar scaffold is running. Planner and provider execution are not implemented yet."
)


def flatten_text(text: str) -> str:
    return text.replace("\r", "\\r").replace("\n", "\\n")


def extract_section(summary_text: str, header: str, next_header: str | None = None) -> str:
    header_marker = f"{header}:\n"
    start_index = summary_text.find(header_marker)
    if start_index < 0:
        return ""

    content_start = start_index + len(header_marker)
    if next_header is None:
        return summary_text[content_start:].strip()

    next_marker = f"\n\n{next_header}:\n"
    end_index = summary_text.find(next_marker, content_start)
    if end_index < 0:
        return summary_text[content_start:].strip()

    return summary_text[content_start:end_index].strip()


def verify(
    context: object,
    prompt: str,
    initial_selection: str,
    expected_answer: str,
    expected_provider: str | None = None,
    expected_model: str | None = None,
) -> int:
    desktop = None
    document = None
    try:
        desktop, document = load_document(context, "private:factory/swriter")
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
        provider_input = panel_window.getControl("ProviderInput")
        model_input = panel_window.getControl("ModelInput")
        save_settings_button = panel_window.getControl("SaveSettingsButton")
        settings_status_control = panel_window.getControl("SettingsStatus")

        status_after_open = model_text(panel_window.getControl("Status"))
        settings_after_open = model_text(settings_status_control)
        approve_button = panel_window.getControl("ApproveButton")
        results["SETTINGS_CONTROLS_RENDERED"] = str(
            all(
                control is not None
                for control in (
                    provider_input,
                    model_input,
                    save_settings_button,
                    settings_status_control,
                )
            )
        )
        results["PROVIDER_INPUT_HAS_VALUE"] = str(bool(model_text(provider_input).strip()))
        results["MODEL_INPUT_HAS_VALUE"] = str(bool(model_text(model_input).strip()))
        results["SETTINGS_STATUS_HAS_HEADER"] = str(
            "Writer-first settings:" in settings_after_open
        )
        results["OPEN_STATUS_HAS_COMMAND"] = str(
            "Last command: open-sidebar" in status_after_open
        )
        results["APPROVE_ENABLED_AFTER_OPEN"] = str(approve_button.isEnabled())

        text = document.Text
        cursor = text.createTextCursor()
        text.insertString(cursor, initial_selection, False)
        cursor.gotoStart(False)
        cursor.goRight(len(initial_selection), True)
        controller.select(cursor)

        preview_dispatch.dispatch(
            preview_url,
            (make_property("Prompt", prompt),),
        )

        status_after_answer = model_text(panel_window.getControl("Status"))
        summary_after_answer = model_text(panel_window.getControl("Summary"))
        rendered_result = extract_section(summary_after_answer, "Last result", "Recent activity")
        rendered_recent_activity = extract_section(summary_after_answer, "Recent activity")
        results["RAW_STATUS_AFTER_ANSWER"] = flatten_text(status_after_answer)
        results["RAW_SUMMARY_AFTER_ANSWER"] = flatten_text(summary_after_answer)
        results["RENDERED_RESULT"] = flatten_text(rendered_result)
        results["CONNECTED_AFTER_ANSWER"] = str(
            "Connection: connected to sidecar" in status_after_answer
        )
        results["LAST_COMMAND_AFTER_ANSWER"] = str(
            "Last command: preview-selection" in status_after_answer
        )
        if expected_provider is not None:
            results["HAS_EXPECTED_PROVIDER"] = str(
                f"Provider: {expected_provider}" in status_after_answer
            )
        if expected_model is not None:
            results["HAS_EXPECTED_MODEL"] = str(
                f"Model: {expected_model}" in status_after_answer
            )
        results["HAS_PROMPT_IN_SUMMARY"] = str(f"Prompt:\n{prompt}" in summary_after_answer)
        results["HAS_SELECTION_IN_SUMMARY"] = str(
            f"Selection:\n{initial_selection}" in summary_after_answer
        )
        results["HAS_NO_PENDING_PREVIEW"] = str(
            "Pending preview:\nNo pending proposal." in summary_after_answer
        )
        if expected_answer == NON_SCAFFOLD_SENTINEL:
            results["HAS_EXPECTED_ANSWER"] = str(
                rendered_result not in ("", "No completed result yet.", SCAFFOLD_DIRECT_ANSWER)
            )
            results["HAS_RECENT_ACTIVITY"] = str(
                bool(rendered_recent_activity)
                and rendered_recent_activity != "No chat activity yet."
                and SCAFFOLD_DIRECT_ANSWER not in rendered_recent_activity
            )
        else:
            results["HAS_EXPECTED_ANSWER"] = str(
                f"Last result:\n{expected_answer}" in summary_after_answer
            )
            results["HAS_RECENT_ACTIVITY"] = str(
                f"Recent activity:\n- {expected_answer}" in summary_after_answer
            )
        results["DOC_TEXT"] = document.Text.getString()
        results["APPROVE_ENABLED_AFTER_ANSWER"] = str(approve_button.isEnabled())

        failures: list[str] = []
        if results["SETTINGS_CONTROLS_RENDERED"] != "True":
            failures.append("Sidebar settings controls did not render after opening the panel.")
        if results["PROVIDER_INPUT_HAS_VALUE"] != "True":
            failures.append("Provider input did not render with an initial value.")
        if results["MODEL_INPUT_HAS_VALUE"] != "True":
            failures.append("Model input did not render with an initial value.")
        if results["SETTINGS_STATUS_HAS_HEADER"] != "True":
            failures.append("Settings section did not render its Writer-first header.")
        if results["OPEN_STATUS_HAS_COMMAND"] != "True":
            failures.append("Sidebar status did not reflect the open-sidebar command.")
        if results["APPROVE_ENABLED_AFTER_OPEN"] != "False":
            failures.append("Approve should start disabled after opening the sidebar.")
        if results["CONNECTED_AFTER_ANSWER"] != "True":
            failures.append("Sidebar did not report a connected sidecar after direct answer.")
        if results["LAST_COMMAND_AFTER_ANSWER"] != "True":
            failures.append("Sidebar status did not reflect the preview-selection command.")
        if expected_provider is not None and results["HAS_EXPECTED_PROVIDER"] != "True":
            failures.append("Sidebar status did not show the expected provider.")
        if expected_model is not None and results["HAS_EXPECTED_MODEL"] != "True":
            failures.append("Sidebar status did not show the expected model.")
        if results["HAS_PROMPT_IN_SUMMARY"] != "True":
            failures.append("Sidebar summary did not retain the submitted prompt.")
        if results["HAS_SELECTION_IN_SUMMARY"] != "True":
            failures.append("Sidebar summary did not retain the selected text.")
        if results["HAS_NO_PENDING_PREVIEW"] != "True":
            failures.append("Sidebar summary did not show the empty pending-preview state.")
        if results["HAS_EXPECTED_ANSWER"] != "True":
            failures.append("Sidebar summary did not record the direct answer result.")
        if results["HAS_RECENT_ACTIVITY"] != "True":
            failures.append("Sidebar recent activity did not include the direct answer.")
        if results["DOC_TEXT"] != initial_selection:
            failures.append("Direct answer flow unexpectedly changed the Writer document.")
        if results["APPROVE_ENABLED_AFTER_ANSWER"] != "False":
            failures.append("Approve should stay disabled after a direct answer.")

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
    if len(argv) not in (4, 6):
        print(
            "Usage: verify_sidebar_direct_answer.py <pipe_name> <prompt> "
            "<initial_selection> <expected_answer> "
            "[<expected_provider> <expected_model>]",
            file=sys.stderr,
        )
        return 2

    pipe_name, prompt, initial_selection, expected_answer, *extra = argv
    expected_provider = extra[0] if len(extra) == 2 else None
    expected_model = extra[1] if len(extra) == 2 else None
    context = connect(pipe_name)
    return verify(
        context=context,
        prompt=prompt,
        initial_selection=initial_selection,
        expected_answer=expected_answer,
        expected_provider=expected_provider,
        expected_model=expected_model,
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