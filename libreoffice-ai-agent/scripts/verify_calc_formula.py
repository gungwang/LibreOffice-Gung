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
            return line[len(prefix):].strip()

    return ""


def verify(
    context: object,
    prompt: str,
    initial_value: str,
    expected_provider: str | None = None,
    expected_model: str | None = None,
) -> int:
    desktop = None
    document = None
    try:
        desktop, document = load_document(context, "private:factory/scalc")
        controller = document.getCurrentController()
        frame = controller.getFrame()
        panel_window = get_sidebar_panel_window(context, frame)

        # Put content in cell A1 and select it.
        sheet = document.getSheets().getByIndex(0)
        cell = sheet.getCellByPosition(0, 0)
        cell.setString(initial_value)
        controller.select(cell)

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

        approve_button = panel_window.getControl("ApproveButton")
        results["APPROVE_ENABLED_BEFORE"] = str(approve_button.isEnabled())

        preview_dispatch.dispatch(
            preview_url,
            (make_property("Prompt", prompt),),
        )

        status_after_preview = model_text(panel_window.getControl("Status"))
        summary_after_preview = model_text(panel_window.getControl("Summary"))
        pending_preview = extract_section(
            summary_after_preview, "Pending preview", "Last result"
        )
        preview_after = extract_labeled_value(pending_preview, "After")
        results["RAW_STATUS_AFTER_PREVIEW"] = flatten_text(status_after_preview)
        results["RAW_SUMMARY_AFTER_PREVIEW"] = flatten_text(summary_after_preview)
        results["PENDING_PREVIEW_TEXT"] = flatten_text(pending_preview)
        results["PREVIEW_AFTER_TEXT"] = flatten_text(preview_after)
        results["HAS_PENDING_PREVIEW"] = str(
            pending_preview not in ("", "No pending proposal.")
            and "Insert formula" in pending_preview
        )
        results["HAS_PREVIEW_RESULT"] = str(
            "Last result:\nPreview Calc formula insertion" in summary_after_preview
            or "Insert formula" in summary_after_preview
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

        # The formula proposed should look like a formula (starts with =).
        results["PROPOSED_FORMULA_VALID"] = str(
            preview_after.startswith("=") or preview_after.startswith("'=")
        )

        # Now approve.
        approve_dispatch.dispatch(approve_url, ())

        summary_after_approve = model_text(panel_window.getControl("Summary"))
        cell_formula = cell.getFormula()
        results["CELL_FORMULA_AFTER"] = cell_formula
        results["HAS_APPLIED_RESULT"] = str(
            "Applied Calc.InsertFormulaInSelection" in summary_after_approve
        )
        results["APPROVE_ENABLED_AFTER_APPROVE"] = str(approve_button.isEnabled())
        # After approval, cell should contain a formula.
        results["CELL_HAS_FORMULA"] = str(
            cell_formula.startswith("=") if cell_formula else False
        )

        failures: list[str] = []
        if results["HAS_PENDING_PREVIEW"] != "True":
            failures.append("Preview dispatch did not produce a formula proposal.")
        if results["APPROVE_ENABLED_AFTER_PREVIEW"] != "True":
            failures.append("Approve was not enabled after preview dispatch.")
        if expected_provider and results.get("HAS_EXPECTED_PROVIDER") != "True":
            failures.append("Sidebar status did not show the expected provider.")
        if expected_model and results.get("HAS_EXPECTED_MODEL") != "True":
            failures.append("Sidebar status did not show the expected model.")
        if results["PROPOSED_FORMULA_VALID"] != "True":
            failures.append(
                f"Proposed formula does not start with '=': '{preview_after}'"
            )
        if results["HAS_APPLIED_RESULT"] != "True":
            failures.append("Sidebar summary did not record the applied formula result.")
        if results["APPROVE_ENABLED_AFTER_APPROVE"] != "False":
            failures.append("Approve did not return to disabled state after apply.")
        if results["CELL_HAS_FORMULA"] != "True":
            failures.append(
                f"Cell does not contain a formula after approval: '{cell_formula}'"
            )

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
    if len(argv) not in (3, 5):
        print(
            "Usage: verify_calc_formula.py <pipe_name> <prompt> "
            "<initial_value> [<expected_provider> <expected_model>]",
            file=sys.stderr,
        )
        return 2

    pipe_name = argv[0]
    prompt = argv[1]
    initial_value = argv[2]
    expected_provider = argv[3] if len(argv) > 3 else None
    expected_model = argv[4] if len(argv) > 4 else None

    try:
        context = connect(pipe_name)
    except Exception as exc:
        print(f"UNHANDLED_EXCEPTION={type(exc).__name__}: {exc}")
        return 1

    try:
        return verify(
            context,
            prompt,
            initial_value,
            expected_provider,
            expected_model,
        )
    except Exception as exc:
        print(f"UNHANDLED_EXCEPTION={type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
