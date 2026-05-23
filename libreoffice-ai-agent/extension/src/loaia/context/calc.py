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


def create_chart_from_selection(controller: object, chart_type: str = "Bar") -> str:
    """Create a chart from the currently selected Calc range.

    Uses UNO dispatch to insert a chart. *chart_type* is informational metadata;
    the dispatch creates the default chart which the user can customise.
    """
    try:
        import uno  # type: ignore[import]

        ctx = uno.getComponentContext()
        smgr = ctx.ServiceManager
        dispatcher = smgr.createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", ctx
        )
    except ImportError:
        raise ValueError("UNO runtime is not available for chart creation.") from None

    frame = controller.getFrame() if hasattr(controller, "getFrame") else None
    if frame is None:
        raise ValueError("Controller does not expose a frame for dispatch.")

    dispatcher.executeDispatch(frame, ".uno:InsertObjectChart", "", 0, ())
    return f"Inserted chart (type hint: {chart_type}) from selection."


def sort_selected_range(controller: object, *, ascending: bool = True) -> str:
    """Sort the currently selected Calc range by the first column.

    Uses UNO dispatch with SortAscending / SortDescending.
    """
    try:
        import uno  # type: ignore[import]

        ctx = uno.getComponentContext()
        smgr = ctx.ServiceManager
        dispatcher = smgr.createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", ctx
        )
    except ImportError:
        raise ValueError("UNO runtime is not available for sorting.") from None

    frame = controller.getFrame() if hasattr(controller, "getFrame") else None
    if frame is None:
        raise ValueError("Controller does not expose a frame for dispatch.")

    cmd = ".uno:SortAscending" if ascending else ".uno:SortDescending"
    dispatcher.executeDispatch(frame, cmd, "", 0, ())
    direction = "ascending" if ascending else "descending"
    return f"Sorted selected range ({direction})."
