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

CHANGED_TEXT_SENTINEL = "__CHANGED_TEXT__"
SCAFFOLD_DIRECT_ANSWER = (
    "Sidecar scaffold is running. Planner and provider execution are not implemented yet."
)
NO_REPLACEMENT_SENTINEL = "NO_REPLACEMENT"


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


def extract_labeled_value(section_text: str, label: str) -> str:
    prefix = f"{label}: "
    for line in section_text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()

    return ""


def verify(
    context: object,
    prompt: str,
    initial_selection: str,
    expected_text: str,
    expected_provider: str | None = None,
    expected_model: str | None = None,
) -> int:
    desktop = None
    document = None
    try:
        desktop, document = load_document(context, "private:factory/swriter")
        controller = document.getCurrentController()
        frame = controller.getFrame()
        panel_window = get_sidebar_panel_window(context, frame)

        text = document.Text
        cursor = text.createTextCursor()
        text.insertString(cursor, initial_selection, False)
        cursor.gotoStart(False)
        cursor.goRight(len(initial_selection), True)
        controller.select(cursor)

        preview_url = make_url("preview-selection")
        approve_url = make_url("approve-pending")
        preview_dispatch = frame.queryDispatch(preview_url, "_self", 0)
        approve_dispatch = frame.queryDispatch(approve_url, "_self", 0)

        results: dict[str, str] = {
            "PREVIEW_DISPATCH_PRESENT": str(preview_dispatch is not None),
            "APPROVE_DISPATCH_PRESENT": str(approve_dispatch is not None),
        }

        if preview_dispatch is None or approve_dispatch is None:
            for key, value in results.items():
                print(f"{key}={value}")
            print("VALIDATION_PASSED=False")
            print("FAILURE=Protocol dispatch is not available for one or more commands.")
            return 1

        preview_dispatch.dispatch(
            preview_url,
            (make_property("Prompt", prompt),),
        )

        status_after_preview = model_text(panel_window.getControl("Status"))
        summary_after_preview = model_text(panel_window.getControl("Summary"))
        pending_preview = extract_section(summary_after_preview, "Pending preview", "Last result")
        preview_after = extract_labeled_value(pending_preview, "After")
        approve_button = panel_window.getControl("ApproveButton")
        results["HAS_PENDING_PREVIEW"] = str(
            pending_preview not in ("", "No pending proposal.")
            and "Preview Writer selection replacement" in pending_preview
        )
        results["HAS_PREVIEW_RESULT"] = str(
            "Last result:\nPreview Writer selection replacement" in summary_after_preview
        )
        results["APPROVE_ENABLED_AFTER_PREVIEW"] = str(approve_button.isEnabled())
        if expected_provider is not None:
            results["HAS_EXPECTED_PROVIDER"] = str(
                f"Provider: {expected_provider}" in status_after_preview
            )
        if expected_model is not None:
            results["HAS_EXPECTED_MODEL"] = str(
                f"Model: {expected_model}" in status_after_preview
            )
        if expected_text == CHANGED_TEXT_SENTINEL:
            results["PROPOSED_TEXT_CHANGED"] = str(
                preview_after
                not in (
                    "",
                    initial_selection,
                    SCAFFOLD_DIRECT_ANSWER,
                    NO_REPLACEMENT_SENTINEL,
                )
            )

        approve_dispatch.dispatch(approve_url, ())

        summary_after_approve = model_text(panel_window.getControl("Summary"))
        document_text = document.Text.getString()
        results["DOC_TEXT"] = document_text
        results["HAS_APPLIED_RESULT"] = str(
            "Applied Writer.ReplaceSelection" in summary_after_approve
        )
        results["APPROVE_ENABLED_AFTER_APPROVE"] = str(approve_button.isEnabled())
        if expected_text == CHANGED_TEXT_SENTINEL:
            results["DOC_TEXT_CHANGED"] = str(
                document_text.strip()
                and document_text
                not in (
                    initial_selection,
                    SCAFFOLD_DIRECT_ANSWER,
                    NO_REPLACEMENT_SENTINEL,
                )
            )

        failures: list[str] = []
        if results["HAS_PENDING_PREVIEW"] != "True":
            failures.append("Preview dispatch did not populate a pending proposal.")
        if results["HAS_PREVIEW_RESULT"] != "True":
            failures.append("Sidebar summary did not record the preview result.")
        if results["APPROVE_ENABLED_AFTER_PREVIEW"] != "True":
            failures.append("Approve was not enabled after preview dispatch.")
        if expected_provider is not None and results["HAS_EXPECTED_PROVIDER"] != "True":
            failures.append("Sidebar status did not show the expected provider.")
        if expected_model is not None and results["HAS_EXPECTED_MODEL"] != "True":
            failures.append("Sidebar status did not show the expected model.")
        if expected_text == CHANGED_TEXT_SENTINEL:
            if results["PROPOSED_TEXT_CHANGED"] != "True":
                failures.append("Pending preview did not expose a changed replacement text.")
            if results["DOC_TEXT_CHANGED"] != "True":
                failures.append(
                    "Approval did not update the Writer document to a changed replacement."
                )
        elif results["DOC_TEXT"] != expected_text:
            failures.append(
                "Approval did not update the Writer document to the expected text."
            )
        if results["HAS_APPLIED_RESULT"] != "True":
            failures.append("Sidebar summary did not record the applied result.")
        if results["APPROVE_ENABLED_AFTER_APPROVE"] != "False":
            failures.append("Approve did not return to the disabled state after apply.")

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
            "Usage: verify_protocol_actions.py <pipe_name> <prompt> "
            "<initial_selection> <expected_text|__CHANGED_TEXT__> "
            "[<expected_provider> <expected_model>]",
            file=sys.stderr,
        )
        return 2

    pipe_name, prompt, initial_selection, expected_text, *extra = argv
    expected_provider = extra[0] if len(extra) == 2 else None
    expected_model = extra[1] if len(extra) == 2 else None
    context = connect(pipe_name)
    return verify(
        context=context,
        prompt=prompt,
        initial_selection=initial_selection,
        expected_text=expected_text,
        expected_provider=expected_provider,
        expected_model=expected_model,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))