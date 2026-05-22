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
    initial_formula: str,
    expected_provider: str | None = None,
    expected_model: str | None = None,
) -> int:
    desktop = None
    document = None
    try:
        desktop, document = load_document(context, "private:factory/smath")
        controller = document.getCurrentController()
        frame = controller.getFrame()
        panel_window = get_sidebar_panel_window(context, frame)

        # Set the formula in the Math document.
        if hasattr(document, "setFormula"):
            document.setFormula(initial_formula)
        elif hasattr(document, "Formula"):
            document.Formula = initial_formula
        else:
            print("UNHANDLED_EXCEPTION=Cannot set formula on Math document model")
            return 1

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

        results["RAW_STATUS_AFTER"] = flatten_text(status_after)
        results["RAW_SUMMARY_AFTER"] = flatten_text(summary_after)

        # Direct answer flow: Math explanations don't modify formula.
        # Check that a result was generated (not an error).
        results["HAS_NO_ERROR"] = str("Last error:" not in status_after)
        results["CONNECTED"] = str("connected to sidecar" in status_after)

        if expected_provider is not None:
            results["HAS_EXPECTED_PROVIDER"] = str(
                f"Provider: {expected_provider}" in status_after
            )
        if expected_model is not None:
            results["HAS_EXPECTED_MODEL"] = str(
                f"Model: {expected_model}" in status_after
            )

        # Check the formula was captured in the selection.
        results["HAS_FORMULA_IN_SELECTION"] = str(
            initial_formula in summary_after
        )

        # Either a direct answer was given or a proposal was created.
        results["HAS_RESULT_OR_PROPOSAL"] = str(
            "Last result:" in summary_after
            and "No completed result yet." not in summary_after
        )

        failures: list[str] = []
        if results["CONNECTED"] != "True":
            failures.append("Sidecar connection was not established.")
        if results["HAS_NO_ERROR"] != "True":
            failures.append("An error was reported in status after preview.")
        if expected_provider and results.get("HAS_EXPECTED_PROVIDER") != "True":
            failures.append("Sidebar status did not show the expected provider.")
        if expected_model and results.get("HAS_EXPECTED_MODEL") != "True":
            failures.append("Sidebar status did not show the expected model.")
        if results["HAS_FORMULA_IN_SELECTION"] != "True":
            failures.append("Math formula was not captured in sidebar selection.")
        if results["HAS_RESULT_OR_PROPOSAL"] != "True":
            failures.append("No result or proposal generated for the Math formula.")

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
            "Usage: verify_math_direct_answer.py <pipe_name> <prompt> "
            "<initial_formula> [<expected_provider> <expected_model>]",
            file=sys.stderr,
        )
        return 2

    pipe_name = argv[0]
    prompt = argv[1]
    initial_formula = argv[2]
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
            initial_formula,
            expected_provider,
            expected_model,
        )
    except Exception as exc:
        print(f"UNHANDLED_EXCEPTION={type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
