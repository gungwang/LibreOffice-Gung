from __future__ import annotations

import sys

from verification_probe_common import (
    close_document_session,
    connect,
    load_document_with_controller,
    make_property,
    make_url,
)


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
        desktop, document, controller = load_document_with_controller(
            context,
            "private:factory/scalc",
        )
        frame = controller.getFrame()

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
            "FORMULA_BEFORE": cell.getFormula(),
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

        formula_after_preview = cell.getFormula()
        results["FORMULA_AFTER_PREVIEW"] = formula_after_preview
        results["PREVIEW_LEFT_FORMULA_UNCHANGED"] = str(
            formula_after_preview == results["FORMULA_BEFORE"]
        )
        if expected_provider is not None:
            results["EXPECTED_PROVIDER_CHECK_SKIPPED"] = expected_provider
        if expected_model is not None:
            results["EXPECTED_MODEL_CHECK_SKIPPED"] = expected_model

        # Now approve.
        approve_dispatch.dispatch(approve_url, ())

        cell_formula = cell.getFormula()
        results["CELL_FORMULA_AFTER"] = cell_formula
        results["CELL_HAS_FORMULA"] = str(
            bool(cell_formula)
            and cell_formula != results["FORMULA_BEFORE"]
            and cell_formula.startswith("=")
        )

        failures: list[str] = []
        if results["PREVIEW_LEFT_FORMULA_UNCHANGED"] != "True":
            failures.append("Preview dispatch changed the Calc formula before approval.")
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
