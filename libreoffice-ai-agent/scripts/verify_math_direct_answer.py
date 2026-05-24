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

SCAFFOLD_DIRECT_ANSWER = (
    "Sidecar scaffold is running. Planner and provider execution are not implemented yet."
)


def read_formula(document: object) -> str:
    if hasattr(document, "getFormula"):
        return str(document.getFormula())
    if hasattr(document, "Formula"):
        return str(document.Formula)

    raise RuntimeError("Cannot read formula from Math document model")


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

        # Set the formula in the Math document.
        if hasattr(document, "setFormula"):
            document.setFormula(initial_formula)
        elif hasattr(document, "Formula"):
            document.Formula = initial_formula
        else:
            print("UNHANDLED_EXCEPTION=Cannot set formula on Math document model")
            return 1

        formula_before = read_formula(document)

        preview_url = make_url("preview-selection")
        preview_dispatch = frame.queryDispatch(preview_url, "_self", 0)

        results: dict[str, str] = {
            "PREVIEW_DISPATCH_PRESENT": str(preview_dispatch is not None),
            "FORMULA_BEFORE": formula_before,
        }

        if preview_dispatch is None:
            for key, value in results.items():
                print(f"{key}={value}")
            print("VALIDATION_PASSED=False")
            print("FAILURE=Protocol dispatch is not available for preview-selection.")
            return 1

        preview_dispatch.dispatch(
            preview_url,
            (make_property("Prompt", prompt),),
        )

        _state_data, session_payload = wait_for_uno_result(
            lambda: find_sidebar_session(last_prompt=prompt, require_result=True),
            "Math direct-answer session state",
        )
        messages = coerce_sidebar_messages(session_payload)
        user_message = next((message for message in reversed(messages) if message["role"] == "user"), None)
        assistant_message = next(
            (message for message in reversed(messages) if message["role"] == "assistant"),
            None,
        )
        formula_after = read_formula(document)

        results["FORMULA_AFTER"] = formula_after
        results["FORMULA_UNCHANGED"] = str(formula_after == formula_before)
        results["LAST_RESULT"] = str(session_payload.get("lastResult") or "")
        results["HAS_USER_MESSAGE"] = str(
            user_message is not None and user_message.get("text") == prompt
        )
        results["HAS_ASSISTANT_MESSAGE"] = str(assistant_message is not None)

        if expected_provider is not None:
            results["HAS_EXPECTED_PROVIDER"] = str(
                assistant_message is not None
                and assistant_message.get("provider") == expected_provider
            )
        if expected_model is not None:
            results["HAS_EXPECTED_MODEL"] = str(
                assistant_message is not None
                and assistant_message.get("model") == expected_model
            )
        results["HAS_EXPECTED_ANSWER"] = str(
            assistant_message is not None
            and assistant_message.get("text") not in ("", SCAFFOLD_DIRECT_ANSWER)
        )

        failures: list[str] = []
        if results["FORMULA_UNCHANGED"] != "True":
            failures.append("Math direct-answer flow unexpectedly changed the formula.")
        if results["HAS_USER_MESSAGE"] != "True":
            failures.append("Session history did not record the Math prompt.")
        if results["HAS_ASSISTANT_MESSAGE"] != "True":
            failures.append("Session history did not record the Math direct answer.")
        if expected_provider and results.get("HAS_EXPECTED_PROVIDER") != "True":
            failures.append("Session history did not show the expected provider.")
        if expected_model and results.get("HAS_EXPECTED_MODEL") != "True":
            failures.append("Session history did not show the expected model.")
        if results["HAS_EXPECTED_ANSWER"] != "True":
            failures.append("No real direct answer was recorded for the Math formula.")

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
