from __future__ import annotations

import sys

from verification_probe_common import (
    close_document_session,
    connect,
    load_document,
    make_property,
    make_url,
)


def read_char_weight(cell: object) -> float | None:
    get_property_value = getattr(cell, "getPropertyValue", None)
    if callable(get_property_value):
        weight = get_property_value("CharWeight")
        if isinstance(weight, (int, float)):
            return float(weight)

    weight = getattr(cell, "CharWeight", None)
    if isinstance(weight, (int, float)):
        return float(weight)

    return None


def set_char_weight(cell: object, value: float) -> None:
    set_property_value = getattr(cell, "setPropertyValue", None)
    if callable(set_property_value):
        set_property_value("CharWeight", float(value))
        return

    setattr(cell, "CharWeight", float(value))


def verify(
    context: object,
    prompt: str,
    initial_value: str,
    expected_tool_id: str,
    expected_provider: str | None = None,
    expected_model: str | None = None,
) -> int:
    desktop = None
    document = None
    try:
        desktop, document = load_document(context, "private:factory/scalc")
        controller = document.getCurrentController()
        frame = controller.getFrame()

        # Put content in cell A1 and select it.
        sheet = document.getSheets().getByIndex(0)
        cell = sheet.getCellByPosition(0, 0)
        cell.setString(initial_value)
        set_char_weight(cell, 100.0)
        controller.select(cell)

        preview_url = make_url("preview-selection")
        preview_dispatch = frame.queryDispatch(preview_url, "_self", 0)

        weight_before = read_char_weight(cell)

        results: dict[str, str] = {
            "PREVIEW_DISPATCH_PRESENT": str(preview_dispatch is not None),
            "EXPECTED_TOOL_ID": expected_tool_id,
            "CHAR_WEIGHT_BEFORE": str(weight_before),
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

        weight_after = read_char_weight(cell)
        cell_value = cell.getString()

        results["CHAR_WEIGHT_AFTER"] = str(weight_after)
        results["CELL_VALUE"] = cell_value
        results["BOLD_APPLIED"] = str(
            weight_before is not None
            and weight_after is not None
            and weight_after > weight_before
        )

        # Cell value should be unchanged (formatting doesn't change content).
        results["CELL_VALUE_UNCHANGED"] = str(cell_value == initial_value)
        if expected_provider is not None:
            results["EXPECTED_PROVIDER_CHECK_SKIPPED"] = expected_provider
        if expected_model is not None:
            results["EXPECTED_MODEL_CHECK_SKIPPED"] = expected_model

        failures: list[str] = []
        if results["BOLD_APPLIED"] != "True":
            failures.append("Safe formatting did not apply bold formatting to the Calc cell.")
        if results["CELL_VALUE_UNCHANGED"] != "True":
            failures.append("Cell value was changed; formatting should not alter cell content.")

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
            "Usage: verify_calc_safe_formatting.py <pipe_name> <prompt> "
            "<initial_value> <expected_tool_id> "
            "[<expected_provider> <expected_model>]",
            file=sys.stderr,
        )
        return 2

    pipe_name = argv[0]
    prompt = argv[1]
    initial_value = argv[2]
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
            initial_value,
            expected_tool_id,
            expected_provider,
            expected_model,
        )
    except Exception as exc:
        print(f"UNHANDLED_EXCEPTION={type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
