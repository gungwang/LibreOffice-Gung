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


def flatten_text(text: str) -> str:
    return text.replace("\r", "\\r").replace("\n", "\\n")


def verify(
    context: object,
    prompt: str,
    initial_text: str,
    expected_tool_id: str,
    expected_provider: str | None = None,
    expected_model: str | None = None,
) -> int:
    desktop = None
    document = None
    try:
        desktop, document = load_document(context, "private:factory/sdraw")
        controller = document.getCurrentController()
        frame = controller.getFrame()
        panel_window = get_sidebar_panel_window(context, frame)

        # Insert a text shape with content and select it.
        draw_page = document.getDrawPages().getByIndex(0)
        import uno  # type: ignore[import]

        size = uno.createUnoStruct("com.sun.star.awt.Size")
        size.Width = 10000
        size.Height = 5000
        position = uno.createUnoStruct("com.sun.star.awt.Point")
        position.X = 1000
        position.Y = 1000

        shape = document.createInstance("com.sun.star.drawing.TextShape")
        shape.Size = size
        shape.Position = position
        draw_page.add(shape)
        shape.setString(initial_text)
        controller.select(shape)

        preview_url = make_url("preview-selection")
        preview_dispatch = frame.queryDispatch(preview_url, "_self", 0)

        results: dict[str, str] = {
            "PREVIEW_DISPATCH_PRESENT": str(preview_dispatch is not None),
        }

        if preview_dispatch is None:
            for key, value in results.items():
                print(f"{key}={value}")
            print("VALIDATION_PASSED=False")
            print("FAILURE=Protocol dispatch is not available for preview-selection.")
            return 1

        approve_button = panel_window.getControl("ApproveButton")
        results["APPROVE_ENABLED_BEFORE"] = str(approve_button.isEnabled())

        preview_dispatch.dispatch(
            preview_url,
            (make_property("Prompt", prompt),),
        )

        status_after = model_text(panel_window.getControl("Status"))
        summary_after = model_text(panel_window.getControl("Summary"))
        shape_text = shape.getString()

        results["RAW_STATUS_AFTER"] = flatten_text(status_after)
        results["RAW_SUMMARY_AFTER"] = flatten_text(summary_after)
        results["SHAPE_TEXT"] = shape_text

        # Safe formatting should not create a pending proposal.
        results["HAS_NO_PENDING_PREVIEW"] = str(
            "No pending proposal." in summary_after
        )

        # Should show "Applied Draw.ToggleBold" (or similar) in last result.
        expected_result = f"Applied {expected_tool_id}"
        results["HAS_EXPECTED_RESULT"] = str(expected_result in summary_after)

        # Shape text should be unchanged (formatting doesn't change content).
        results["SHAPE_TEXT_UNCHANGED"] = str(shape_text == initial_text)

        # Approve should remain disabled (no pending proposal).
        results["APPROVE_DISABLED_AFTER"] = str(not approve_button.isEnabled())

        if expected_provider is not None:
            results["HAS_EXPECTED_PROVIDER"] = str(
                f"Provider: {expected_provider}" in status_after
            )
        if expected_model is not None:
            results["HAS_EXPECTED_MODEL"] = str(
                f"Model: {expected_model}" in status_after
            )

        failures: list[str] = []
        if results["HAS_NO_PENDING_PREVIEW"] != "True":
            failures.append("Safe formatting left a pending proposal instead of auto-applying.")
        if results["HAS_EXPECTED_RESULT"] != "True":
            failures.append(
                f"Sidebar summary did not contain expected result '{expected_result}'."
            )
        if results["SHAPE_TEXT_UNCHANGED"] != "True":
            failures.append("Shape text was changed; formatting should not alter text content.")
        if results["APPROVE_DISABLED_AFTER"] != "True":
            failures.append("Approve button was enabled after safe formatting auto-apply.")
        if expected_provider and results.get("HAS_EXPECTED_PROVIDER") != "True":
            failures.append("Sidebar status did not show the expected provider.")
        if expected_model and results.get("HAS_EXPECTED_MODEL") != "True":
            failures.append("Sidebar status did not show the expected model.")

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
            "Usage: verify_draw_safe_formatting.py <pipe_name> <prompt> "
            "<initial_text> <expected_tool_id> "
            "[<expected_provider> <expected_model>]",
            file=sys.stderr,
        )
        return 2

    pipe_name = argv[0]
    prompt = argv[1]
    initial_text = argv[2]
    expected_tool_id = argv[3]
    expected_provider = argv[4] if len(argv) > 4 else None
    expected_model = argv[5] if len(argv) > 5 else None

    try:
        context = connect(pipe_name)
    except Exception as exc:
        print(f"UNHANDLED_EXCEPTION={type(exc).__name__}: {exc}")
        return 1

    try:
        return verify(
            context,
            prompt,
            initial_text,
            expected_tool_id,
            expected_provider,
            expected_model,
        )
    except Exception as exc:
        print(f"UNHANDLED_EXCEPTION={type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
