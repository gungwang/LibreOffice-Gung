"""Calc context extraction for sidebar requests."""

from __future__ import annotations

from collections.abc import Sequence

from loaia_shared.schema.messages import ContextEnvelope, SelectionContext


def extract_calc_selection(text: str) -> ContextEnvelope:
    return ContextEnvelope(selection=SelectionContext(mimeType="text/plain", text=text))


def _get_selection(controller: object) -> object | None:
    get_selection = getattr(controller, "getSelection", None)
    return get_selection() if callable(get_selection) else None


def capture_calc_selection(controller: object) -> tuple[str, str]:
    """Capture the current Calc selection text and formula.

    Returns (cell_text, formula) from the selected cell or range.
    """
    selection = _get_selection(controller)
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
    selection = _get_selection(controller)
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


def read_selection_first_column_order(controller: object) -> str | None:
    values = read_selection_first_column_values(controller)
    if values is None or not values:
        return None

    comparable = [_coerce_sort_value(value) for value in values]
    ascending = comparable == sorted(comparable)
    descending = comparable == sorted(comparable, reverse=True)
    if ascending and not descending:
        return "ascending"
    if descending and not ascending:
        return "descending"
    if ascending and descending:
        return "ascending"
    return "unsorted"


def read_selection_first_column_values(controller: object) -> list[str] | None:
    selection = _get_selection(controller)
    if selection is None:
        return None

    get_data_array = getattr(selection, "getDataArray", None)
    if callable(get_data_array):
        data = get_data_array()
        if isinstance(data, Sequence):
            values: list[str] = []
            for row in data:
                if isinstance(row, Sequence) and row:
                    values.append(str(row[0]))
            return values

    if hasattr(selection, "getString"):
        text = selection.getString()
        if isinstance(text, str):
            return [text]

    if hasattr(selection, "getCellByPosition"):
        row_count = _infer_selection_row_count(selection)
        if row_count is None:
            cell = selection.getCellByPosition(0, 0)
            if hasattr(cell, "getString"):
                text = cell.getString()
                return [text if isinstance(text, str) else str(text)]
            return None

        values = []
        for row_index in range(row_count):
            cell = selection.getCellByPosition(0, row_index)
            if hasattr(cell, "getString"):
                text = cell.getString()
                values.append(text if isinstance(text, str) else str(text))
            else:
                values.append(str(cell))
        return values

    return None


def read_active_sheet_chart_count(controller: object) -> int | None:
    sheet = _get_active_sheet(controller)
    if sheet is None:
        return None

    charts = getattr(sheet, "Charts", None)
    if charts is not None and hasattr(charts, "getCount"):
        return int(charts.getCount())

    get_charts = getattr(sheet, "getCharts", None)
    resolved_charts = get_charts() if callable(get_charts) else None
    if resolved_charts is not None and hasattr(resolved_charts, "getCount"):
        return int(resolved_charts.getCount())

    draw_page = getattr(sheet, "DrawPage", None)
    if draw_page is not None and hasattr(draw_page, "getCount"):
        return int(draw_page.getCount())

    get_draw_page = getattr(sheet, "getDrawPage", None)
    resolved_draw_page = get_draw_page() if callable(get_draw_page) else None
    if resolved_draw_page is not None and hasattr(resolved_draw_page, "getCount"):
        return int(resolved_draw_page.getCount())

    return None


def _infer_selection_row_count(selection: object) -> int | None:
    rows = getattr(selection, "Rows", None)
    if rows is not None and hasattr(rows, "getCount"):
        return int(rows.getCount())

    get_rows = getattr(selection, "getRows", None)
    resolved_rows = get_rows() if callable(get_rows) else None
    if resolved_rows is not None and hasattr(resolved_rows, "getCount"):
        return int(resolved_rows.getCount())

    range_address = getattr(selection, "RangeAddress", None)
    if range_address is None:
        get_range_address = getattr(selection, "getRangeAddress", None)
        range_address = get_range_address() if callable(get_range_address) else None
    if range_address is not None:
        start_row = getattr(range_address, "StartRow", None)
        end_row = getattr(range_address, "EndRow", None)
        if isinstance(start_row, int) and isinstance(end_row, int):
            return end_row - start_row + 1

    return None


def _get_active_sheet(controller: object) -> object | None:
    get_active_sheet = getattr(controller, "getActiveSheet", None)
    if callable(get_active_sheet):
        return get_active_sheet()

    get_model = getattr(controller, "getModel", None)
    model = get_model() if callable(get_model) else None
    if model is None:
        return None

    current_controller = getattr(model, "CurrentController", None)
    if current_controller is None:
        get_current_controller = getattr(model, "getCurrentController", None)
        current_controller = (
            get_current_controller() if callable(get_current_controller) else None
        )
    if current_controller is None:
        return None

    active_sheet = getattr(current_controller, "ActiveSheet", None)
    if active_sheet is not None:
        return active_sheet

    get_active_sheet = getattr(current_controller, "getActiveSheet", None)
    return get_active_sheet() if callable(get_active_sheet) else None


def _coerce_sort_value(value: object) -> tuple[int, object]:
    text = str(value)
    try:
        return (0, float(text))
    except ValueError:
        return (1, text.casefold())
