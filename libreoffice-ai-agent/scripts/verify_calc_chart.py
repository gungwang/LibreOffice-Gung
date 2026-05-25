from __future__ import annotations

import sys

from verification_probe_common import (
    close_document_session,
    connect,
    load_document_with_controller,
    make_property,
    make_url,
    wait_for_uno_result,
)


def flatten_text(text: str) -> str:
    return text.replace("\r", "\\r").replace("\n", "\\n")


def extract_section(summary_text: str, header: str, next_header: str | None = None) -> str:
    header_marker = f"{header}:\n"
    start_index = summary_text.find(header_marker)
    if start_index < 0:
        return ""

    content_start = start_index + len(header_marker)
    if next_header is None:
        return summary_text[content_start:].strip()

    next_marker = f"\n\n{next_header}:\n"
    end_index = summary_text.find(next_marker, content_start)
    if end_index < 0:
        return summary_text[content_start:].strip()

    return summary_text[content_start:end_index].strip()


def extract_labeled_value(section_text: str, label: str) -> str:
    prefix = f"{label}: "
    for line in section_text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()

    return ""


def canonical_chart_type(chart_type: str) -> str:
    normalized = chart_type.strip().casefold()
    chart_type_map = {
        "pie": "Pie",
        "line": "Line",
        "scatter": "Scatter",
        "area": "Area",
        "column": "Column",
        "bar": "Bar",
    }
    return chart_type_map.get(normalized, chart_type.strip())


def get_sheet_charts(sheet: object) -> object:
    charts = getattr(sheet, "Charts", None)
    if charts is not None:
        return charts

    get_charts = getattr(sheet, "getCharts", None)
    if callable(get_charts):
        charts = get_charts()
        if charts is not None:
            return charts

    raise RuntimeError("Calc sheet does not expose Charts.")


def get_chart_count(sheet: object) -> int:
    charts = get_sheet_charts(sheet)
    get_count = getattr(charts, "getCount", None)
    if callable(get_count):
        return int(get_count())

    raise RuntimeError("Calc chart collection does not expose getCount().")


def get_chart_by_index(sheet: object, index: int) -> object:
    charts = get_sheet_charts(sheet)
    get_by_index = getattr(charts, "getByIndex", None)
    if callable(get_by_index):
        return get_by_index(index)

    return charts[index]


def get_last_chart_type(sheet: object) -> str | None:
    chart_count = get_chart_count(sheet)
    if chart_count < 1:
        return None

    chart = get_chart_by_index(sheet, chart_count - 1)
    chart_document = getattr(chart, "EmbeddedObject", None)
    if chart_document is None:
        get_embedded_object = getattr(chart, "getEmbeddedObject", None)
        if callable(get_embedded_object):
            chart_document = get_embedded_object()
    if chart_document is None:
        return None

    diagram = getattr(chart_document, "Diagram", None)
    if diagram is None:
        get_diagram = getattr(chart_document, "getDiagram", None)
        if callable(get_diagram):
            diagram = get_diagram()
    if diagram is None:
        get_first_diagram = getattr(chart_document, "getFirstDiagram", None)
        if callable(get_first_diagram):
            diagram = get_first_diagram()
    if diagram is None:
        return None

    get_diagram_type = getattr(diagram, "getDiagramType", None)
    if not callable(get_diagram_type):
        return None

    diagram_type = get_diagram_type()
    if diagram_type == "com.sun.star.chart.BarDiagram":
        vertical = getattr(diagram, "Vertical", None)
        if isinstance(vertical, bool):
            return "Bar" if vertical else "Column"
        return "Bar"

    diagram_type_map = {
        "com.sun.star.chart.PieDiagram": "Pie",
        "com.sun.star.chart.LineDiagram": "Line",
        "com.sun.star.chart.XYDiagram": "Scatter",
        "com.sun.star.chart.AreaDiagram": "Area",
    }
    return diagram_type_map.get(diagram_type)


def populate_chart_data(sheet: object) -> object:
    values: tuple[tuple[object, ...], ...] = (
        ("Month", "Revenue"),
        ("Jan", 12.0),
        ("Feb", 18.0),
        ("Mar", 9.0),
        ("Apr", 21.0),
    )

    for row_index, row in enumerate(values):
        for column_index, value in enumerate(row):
            cell = sheet.getCellByPosition(column_index, row_index)
            if isinstance(value, str):
                cell.setString(value)
            else:
                cell.setValue(float(value))

    return sheet.getCellRangeByName("A1:B5")


def verify(
    context: object,
    prompt: str,
    expected_chart_type: str,
) -> int:
    desktop = None
    document = None
    stage = "load-document"
    try:
        stage = "load-document"
        desktop, document, controller = load_document_with_controller(
            context,
            "private:factory/scalc",
        )
        stage = "get-controller"
        frame = controller.getFrame()

        stage = "populate-sheet-data"
        sheet = document.getSheets().getByIndex(0)
        selected_range = populate_chart_data(sheet)
        controller.select(selected_range)
        charts_before = get_chart_count(sheet)

        stage = "resolve-dispatches"
        preview_url = make_url("preview-selection")
        approve_url = make_url("approve-pending")
        preview_dispatch = frame.queryDispatch(preview_url, "_self", 0)
        approve_dispatch = frame.queryDispatch(approve_url, "_self", 0)

        results: dict[str, str] = {
            "PREVIEW_DISPATCH_PRESENT": str(preview_dispatch is not None),
            "APPROVE_DISPATCH_PRESENT": str(approve_dispatch is not None),
            "CHART_COUNT_BEFORE": str(charts_before),
        }

        if preview_dispatch is None or approve_dispatch is None:
            for key, value in results.items():
                print(f"{key}={value}")
            print("VALIDATION_PASSED=False")
            print("FAILURE=Protocol dispatch is not available for one or more commands.")
            return 1

        stage = "dispatch-preview"
        preview_dispatch.dispatch(
            preview_url,
            (make_property("Prompt", prompt),),
        )

        charts_after_preview = get_chart_count(sheet)
        results["CHART_COUNT_AFTER_PREVIEW"] = str(charts_after_preview)
        results["PREVIEW_LEFT_DOCUMENT_UNCHANGED"] = str(
            charts_after_preview == charts_before
        )

        stage = "dispatch-approve"
        approve_dispatch.dispatch(approve_url, ())

        stage = "wait-chart-type"
        applied_chart_type = wait_for_uno_result(
            lambda: (
                get_last_chart_type(sheet)
                if get_chart_count(sheet) > charts_before and get_last_chart_type(sheet) is not None
                else None
            ),
            "Calc chart type after approval",
            attempts=30,
            delay_seconds=0.5,
        )

        charts_after = get_chart_count(sheet)

        results["CHART_COUNT_AFTER"] = str(charts_after)
        results["APPROVE_CREATED_CHART"] = str(charts_after > charts_before)
        results["LAST_CHART_TYPE"] = str(applied_chart_type)
        results["CHART_TYPE_MATCHES"] = str(
            applied_chart_type == canonical_chart_type(expected_chart_type)
        )

        failures: list[str] = []
        if results["PREVIEW_LEFT_DOCUMENT_UNCHANGED"] != "True":
            failures.append(
                "Preview dispatch changed the sheet before approval; "
                "chart creation should stay gated behind approve."
            )
        if results["APPROVE_CREATED_CHART"] != "True":
            failures.append("Approving the chart proposal did not create a new chart on the sheet.")
        if results["CHART_TYPE_MATCHES"] != "True":
            failures.append(
                "The newest Calc chart did not report the expected applied chart type."
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
    except Exception:
        print(f"FAILED_STAGE={stage}")
        raise
    finally:
        close_document_session(document=document, desktop=desktop)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "Usage: verify_calc_chart.py <pipe_name> <prompt> <expected_chart_type>",
            file=sys.stderr,
        )
        return 2

    pipe_name = argv[0]
    prompt = argv[1]
    expected_chart_type = argv[2]

    try:
        context = connect(pipe_name)
    except Exception as exc:
        print(f"UNHANDLED_EXCEPTION={type(exc).__name__}: {exc}")
        return 1

    try:
        return verify(context, prompt, expected_chart_type)
    except Exception as exc:
        print(f"UNHANDLED_EXCEPTION={type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))