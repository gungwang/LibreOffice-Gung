from __future__ import annotations

import sys

from verification_probe_common import (
    close_document_session,
    connect,
    load_document,
    make_property,
    make_url,
)

CHANGED_TEXT_SENTINEL = "__CHANGED_TEXT__"
SCAFFOLD_DIRECT_ANSWER = (
    "Sidecar scaffold is running. Planner and provider execution are not implemented yet."
)
NO_REPLACEMENT_SENTINEL = "NO_REPLACEMENT"


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

        preview_text = document.Text.getString()
        results["DOC_TEXT_AFTER_PREVIEW"] = preview_text
        results["PREVIEW_LEFT_DOCUMENT_UNCHANGED"] = str(
            preview_text == initial_selection
        )
        if expected_provider is not None:
            results["EXPECTED_PROVIDER_CHECK_SKIPPED"] = expected_provider
        if expected_model is not None:
            results["EXPECTED_MODEL_CHECK_SKIPPED"] = expected_model
        if expected_text == CHANGED_TEXT_SENTINEL:
            results["EXPECTED_CHANGED_RESULT"] = "True"

        approve_dispatch.dispatch(approve_url, ())

        document_text = document.Text.getString()
        results["DOC_TEXT"] = document_text
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
        if results["PREVIEW_LEFT_DOCUMENT_UNCHANGED"] != "True":
            failures.append("Preview dispatch changed the Writer document before approval.")
        if expected_text == CHANGED_TEXT_SENTINEL:
            if results["DOC_TEXT_CHANGED"] != "True":
                failures.append(
                    "Approval did not update the Writer document to a changed replacement."
                )
        elif results["DOC_TEXT"] != expected_text:
            failures.append(
                "Approval did not update the Writer document to the expected text."
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