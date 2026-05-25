from __future__ import annotations

import sys

from verification_probe_common import (
    close_document_session,
    connect,
    load_document_with_controller,
    make_property,
    make_url,
)


def read_char_weight(target: object) -> float | None:
    get_property_value = getattr(target, "getPropertyValue", None)
    if callable(get_property_value):
        weight = get_property_value("CharWeight")
        if isinstance(weight, (int, float)):
            return float(weight)

    weight = getattr(target, "CharWeight", None)
    if isinstance(weight, (int, float)):
        return float(weight)

    return None


def set_char_weight(target: object, value: float) -> None:
    set_property_value = getattr(target, "setPropertyValue", None)
    if callable(set_property_value):
        set_property_value("CharWeight", float(value))
        return

    setattr(target, "CharWeight", float(value))


def read_shape_text_weight(shape: object) -> float | None:
    create_text_cursor = getattr(shape, "createTextCursor", None)
    if callable(create_text_cursor):
        cursor = create_text_cursor()
        weight = read_char_weight(cursor)
        if weight is not None:
            return weight

    return read_char_weight(shape)


def set_shape_text_weight(shape: object, value: float) -> None:
    set_char_weight(shape, value)

    create_text_cursor = getattr(shape, "createTextCursor", None)
    if callable(create_text_cursor):
        set_char_weight(create_text_cursor(), value)


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
        desktop, document, controller = load_document_with_controller(
            context,
            "private:factory/sdraw",
        )
        frame = controller.getFrame()

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
        set_shape_text_weight(shape, 100.0)
        controller.select(shape)

        preview_url = make_url("preview-selection")
        preview_dispatch = frame.queryDispatch(preview_url, "_self", 0)
        weight_before = read_shape_text_weight(shape)

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

        weight_after = read_shape_text_weight(shape)
        shape_text = shape.getString()

        results["CHAR_WEIGHT_AFTER"] = str(weight_after)
        results["SHAPE_TEXT"] = shape_text
        results["BOLD_APPLIED"] = str(
            weight_before is not None
            and weight_after is not None
            and weight_after > weight_before
        )

        # Shape text should be unchanged (formatting doesn't change content).
        results["SHAPE_TEXT_UNCHANGED"] = str(shape_text == initial_text)
        if expected_provider is not None:
            results["EXPECTED_PROVIDER_CHECK_SKIPPED"] = expected_provider
        if expected_model is not None:
            results["EXPECTED_MODEL_CHECK_SKIPPED"] = expected_model

        failures: list[str] = []
        if results["BOLD_APPLIED"] != "True":
            failures.append("Safe formatting did not apply bold formatting to the Draw text shape.")
        if results["SHAPE_TEXT_UNCHANGED"] != "True":
            failures.append("Shape text was changed; formatting should not alter text content.")

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
