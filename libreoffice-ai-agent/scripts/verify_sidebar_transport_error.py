from __future__ import annotations

import sys

from verify_protocol_actions import connect, make_property, make_url, model_text


def shorten_text(text: str, limit: int = 90) -> str:
    normalized = text.strip()
    if len(normalized) <= limit:
        return normalized

    return f"{normalized[: limit - 3].rstrip()}..."


def verify(
    context: object,
    prompt: str,
    initial_selection: str,
    pipe_address: str,
) -> int:
    expected_error = f"Could not connect to sidecar pipe at {pipe_address}"
    expected_short_error = shorten_text(expected_error, limit=90)
    service_manager = context.ServiceManager
    desktop = service_manager.createInstanceWithContext(
        "com.sun.star.frame.Desktop",
        context,
    )
    document = None
    try:
        document = desktop.loadComponentFromURL(
            "private:factory/swriter",
            "_blank",
            0,
            (make_property("Hidden", False),),
        )
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

        factory_manager = context.getValueByName(
            "/singletons/com.sun.star.ui.theUIElementFactoryManager"
        )
        ui_element = factory_manager.createUIElement(
            "private:resource/toolpanel/LoaiaPanelFactory/LoaiaPanel",
            (
                make_property("Frame", frame),
                make_property("ParentWindow", frame.getContainerWindow()),
            ),
        )
        panel_window = ui_element.getRealInterface().Window

        status_after_open = model_text(panel_window.getControl("Status"))
        approve_button = panel_window.getControl("ApproveButton")
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
            (
                make_property("Prompt", prompt),
                make_property("PipeAddress", pipe_address),
            ),
        )

        status_after_error = model_text(panel_window.getControl("Status"))
        summary_after_error = model_text(panel_window.getControl("Summary"))
        results["STILL_WAITING_AFTER_ERROR"] = str(
            "Connection: waiting for first sidecar response" in status_after_error
        )
        results["LAST_COMMAND_AFTER_ERROR"] = str(
            "Last command: preview-selection" in status_after_error
        )
        results["HAS_EXPECTED_ERROR_IN_STATUS"] = str(
            f"Last error: {expected_short_error}" in status_after_error
        )
        results["HAS_PROMPT_IN_SUMMARY"] = str(f"Prompt:\n{prompt}" in summary_after_error)
        results["HAS_SELECTION_IN_SUMMARY"] = str(
            f"Selection:\n{initial_selection}" in summary_after_error
        )
        results["HAS_NO_PENDING_PREVIEW"] = str(
            "Pending preview:\nNo pending proposal." in summary_after_error
        )
        results["HAS_NO_RESULT"] = str(
            "Last result:\nNo completed result yet." in summary_after_error
        )
        results["HAS_RECENT_ERROR_ACTIVITY"] = str(
            f"Recent activity:\n- {expected_short_error}" in summary_after_error
        )
        results["DOC_TEXT"] = document.Text.getString()
        results["APPROVE_ENABLED_AFTER_ERROR"] = str(approve_button.isEnabled())

        failures: list[str] = []
        if results["OPEN_STATUS_HAS_COMMAND"] != "True":
            failures.append("Sidebar status did not reflect the open-sidebar command.")
        if results["APPROVE_ENABLED_AFTER_OPEN"] != "False":
            failures.append("Approve should start disabled after opening the sidebar.")
        if results["STILL_WAITING_AFTER_ERROR"] != "True":
            failures.append("Connection state did not remain in the waiting state after error.")
        if results["LAST_COMMAND_AFTER_ERROR"] != "True":
            failures.append("Sidebar status did not reflect the preview-selection command.")
        if results["HAS_EXPECTED_ERROR_IN_STATUS"] != "True":
            failures.append("Sidebar status did not show the expected sidecar transport error.")
        if results["HAS_PROMPT_IN_SUMMARY"] != "True":
            failures.append("Sidebar summary did not retain the submitted prompt.")
        if results["HAS_SELECTION_IN_SUMMARY"] != "True":
            failures.append("Sidebar summary did not retain the selected text.")
        if results["HAS_NO_PENDING_PREVIEW"] != "True":
            failures.append("Sidebar summary did not show the empty pending-preview state.")
        if results["HAS_NO_RESULT"] != "True":
            failures.append("Sidebar summary did not keep the empty last-result state.")
        if results["HAS_RECENT_ERROR_ACTIVITY"] != "True":
            failures.append("Sidebar recent activity did not include the transport error.")
        if results["DOC_TEXT"] != initial_selection:
            failures.append("Transport error flow unexpectedly changed the Writer document.")
        if results["APPROVE_ENABLED_AFTER_ERROR"] != "False":
            failures.append("Approve should stay disabled after a transport error.")

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
        if document is not None:
            try:
                document.close(True)
            except Exception:
                pass
        try:
            desktop.terminate()
        except Exception:
            pass


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(
            "Usage: verify_sidebar_transport_error.py <pipe_name> <prompt> "
            "<initial_selection> <pipe_address>",
            file=sys.stderr,
        )
        return 2

    pipe_name, prompt, initial_selection, pipe_address = argv
    context = connect(pipe_name)
    return verify(
        context=context,
        prompt=prompt,
        initial_selection=initial_selection,
        pipe_address=pipe_address,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))