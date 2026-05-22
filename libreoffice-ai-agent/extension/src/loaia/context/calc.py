"""Calc context extraction for sidebar requests."""

from __future__ import annotations

from loaia_shared.schema.messages import ContextEnvelope, SelectionContext


def extract_calc_selection(text: str) -> ContextEnvelope:
    return ContextEnvelope(selection=SelectionContext(mimeType="text/plain", text=text))


def capture_calc_selection(controller: object) -> tuple[str, str]:
    """Capture the current Calc selection text and formula.

    Returns (cell_text, formula) from the selected cell or range.
    """
    selection = controller.getSelection() if hasattr(controller, "getSelection") else None
    if selection is None:
        return ("", "")

    # Single cell
    if hasattr(selection, "getString") and hasattr(selection, "getFormula"):
        return (selection.getString() or "", selection.getFormula() or "")

    # Cell range — get the first cell
    if hasattr(selection, "getCellByPosition"):
        try:
            cell = selection.getCellByPosition(0, 0)
            return (cell.getString() or "", cell.getFormula() or "")
        except Exception:
            pass

    return ("", "")


def apply_calc_formula(controller: object, formula: str) -> str:
    """Insert a formula into the currently selected Calc cell.

    Returns a result message.
    """
    selection = controller.getSelection() if hasattr(controller, "getSelection") else None
    if selection is None:
        raise ValueError("No Calc cell is selected.")

    # Single cell
    if hasattr(selection, "setFormula"):
        selection.setFormula(formula)
        return f"Inserted formula: {formula}"

    # Range — apply to first cell
    if hasattr(selection, "getCellByPosition"):
        try:
            cell = selection.getCellByPosition(0, 0)
            cell.setFormula(formula)
            return f"Inserted formula into first cell: {formula}"
        except Exception as exc:
            raise ValueError(f"Could not insert formula: {exc}") from exc

    raise ValueError("Selected Calc object does not support formula insertion.")
