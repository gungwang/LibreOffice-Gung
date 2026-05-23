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


def create_slide_from_outline(controller: object, outline: str) -> str:
    """Create a new slide at the end of the presentation with *outline* as its text.

    Uses the document's DrawPages API to append a page and set its text.
    """
    model = controller.getModel() if hasattr(controller, "getModel") else None
    draw_pages = model.getDrawPages() if model and hasattr(model, "getDrawPages") else None
    if draw_pages is None:
        raise ValueError("Impress document does not expose DrawPages.")

    new_page = draw_pages.insertNewByIndex(draw_pages.getCount())

    # Set the title/outline text on the first text shape if available.
    if new_page.getCount() > 0:
        shape = new_page.getByIndex(0)
        if hasattr(shape, "setString"):
            shape.setString(outline)

    return f"Created new slide with outline ({len(outline)} chars)."


def apply_layout_to_current_slide(controller: object, layout: int = 0) -> str:
    """Apply a standard layout to the current Impress slide.

    *layout* is the numeric layout index (0 = blank, 1 = title/content, etc.).
    """
    current_page = (
        controller.getCurrentPage()
        if hasattr(controller, "getCurrentPage")
        else None
    )
    if current_page is None:
        raise ValueError("Cannot determine the current Impress slide.")

    if not hasattr(current_page, "Layout"):
        raise ValueError("Current slide does not expose a Layout property.")

    current_page.Layout = layout
    return f"Applied layout {layout} to current slide."
