"""Impress context extraction for sidebar requests."""

from __future__ import annotations

from loaia_shared.schema.messages import ContextEnvelope, SelectionContext


def extract_impress_selection(text: str) -> ContextEnvelope:
    return ContextEnvelope(selection=SelectionContext(mimeType="text/plain", text=text))


def capture_impress_selection(controller: object) -> str:
    """Capture the current Impress selection text.

    Returns the text content of the selected text frame or shape.
    """
    selection = controller.getSelection() if hasattr(controller, "getSelection") else None
    if selection is None:
        return ""

    # Single shape with text
    if hasattr(selection, "getString"):
        return selection.getString() or ""

    # Shape collection — get text from the first shape
    if hasattr(selection, "getCount") and hasattr(selection, "getByIndex"):
        count = selection.getCount()
        if count > 0:
            shape = selection.getByIndex(0)
            if hasattr(shape, "getString"):
                return shape.getString() or ""

    return ""


def apply_impress_text_replacement(controller: object, replacement_text: str) -> str:
    """Replace the text in the currently selected Impress shape.

    Returns a result message.
    """
    selection = controller.getSelection() if hasattr(controller, "getSelection") else None
    if selection is None:
        raise ValueError("No Impress shape is selected.")

    # Single shape with text
    if hasattr(selection, "setString"):
        selection.setString(replacement_text)
        return "Replaced selected Impress text."

    # Shape collection — replace text in the first shape
    if hasattr(selection, "getCount") and hasattr(selection, "getByIndex"):
        count = selection.getCount()
        if count > 0:
            shape = selection.getByIndex(0)
            if hasattr(shape, "setString"):
                shape.setString(replacement_text)
                return "Replaced text in first selected Impress shape."

    raise ValueError("Selected Impress object does not support text replacement.")
