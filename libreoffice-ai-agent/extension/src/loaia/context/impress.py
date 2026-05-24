"""Impress context extraction for sidebar requests."""

from __future__ import annotations

from loaia_shared.schema.messages import ContextEnvelope, SelectionContext


def extract_impress_selection(text: str) -> ContextEnvelope:
    return ContextEnvelope(selection=SelectionContext(mimeType="text/plain", text=text))


def capture_impress_selection(controller: object) -> str:
    """Capture the current Impress selection text.

    Returns the text content of the selected text frame or shape.
    """
    get_selection = getattr(controller, "getSelection", None)
    selection = get_selection() if callable(get_selection) else None
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
    get_selection = getattr(controller, "getSelection", None)
    selection = get_selection() if callable(get_selection) else None
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
    get_model = getattr(controller, "getModel", None)
    model = get_model() if callable(get_model) else None
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
    get_current_page = getattr(controller, "getCurrentPage", None)
    current_page = get_current_page() if callable(get_current_page) else None
    if current_page is None:
        raise ValueError("Cannot determine the current Impress slide.")

    if not hasattr(current_page, "Layout"):
        raise ValueError("Current slide does not expose a Layout property.")

    current_page.Layout = layout
    return f"Applied layout {layout} to current slide."


def read_current_slide_layout(controller: object) -> int | None:
    get_current_page = getattr(controller, "getCurrentPage", None)
    current_page = get_current_page() if callable(get_current_page) else None
    if current_page is None or not hasattr(current_page, "Layout"):
        return None

    return int(current_page.Layout)


def read_last_slide_text(controller: object) -> str | None:
    get_model = getattr(controller, "getModel", None)
    model = get_model() if callable(get_model) else None
    draw_pages = model.getDrawPages() if model and hasattr(model, "getDrawPages") else None
    if draw_pages is None or not hasattr(draw_pages, "getCount") or draw_pages.getCount() < 1:
        return None

    page = draw_pages.getByIndex(draw_pages.getCount() - 1)
    if page is None or not hasattr(page, "getCount") or page.getCount() < 1:
        return None

    shape = page.getByIndex(0)
    if shape is None or not hasattr(shape, "getString"):
        return None

    text = shape.getString()
    return text if isinstance(text, str) else None
