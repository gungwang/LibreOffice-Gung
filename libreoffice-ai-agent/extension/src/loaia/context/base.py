"""Base context extraction for sidebar requests."""

from __future__ import annotations

from loaia_shared.schema.messages import ContextEnvelope, SelectionContext


def extract_base_context(text: str) -> ContextEnvelope:
    return ContextEnvelope(selection=SelectionContext(mimeType="text/plain", text=text))


def capture_base_context(controller: object) -> str:
    """Capture context from the current Base document.

    Returns the SQL query text if a query is open, or the table/form name.
    """
    model = None
    if hasattr(controller, "getModel"):
        model = controller.getModel()
    elif hasattr(controller, "Model"):
        model = controller.Model

    if model is None:
        return ""

    # Try to get the current SQL command from the active query/view.
    if hasattr(controller, "getSelection"):
        selection = controller.getSelection()
        if selection is not None and hasattr(selection, "getString"):
            text = selection.getString()
            if text:
                return text

    # Try to get database name and connection info.
    if hasattr(model, "DataSource"):
        ds = model.DataSource
        if hasattr(ds, "Name"):
            return f"Database: {ds.Name}"

    return ""
