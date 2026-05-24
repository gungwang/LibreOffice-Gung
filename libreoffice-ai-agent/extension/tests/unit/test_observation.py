from types import SimpleNamespace

from loaia.context.calc import _apply_chart_type_to_last_chart, read_active_sheet_last_chart_type
from loaia.observation import build_observation_results, capture_observation_state


class FakeCalcCharts:
    def __init__(self, *charts: object) -> None:
        self._charts = list(charts)

    def getCount(self) -> int:
        return len(self._charts)

    def getByIndex(self, index: int) -> object:
        return self._charts[index]


class FakeChartDiagram:
    def __init__(self, diagram_type: str, *, vertical: bool | None = None) -> None:
        self._diagram_type = diagram_type
        if vertical is not None:
            self.Vertical = vertical

    def getDiagramType(self) -> str:
        return self._diagram_type


class FakeChartDocument:
    def __init__(self, diagram: FakeChartDiagram) -> None:
        self.Diagram = diagram

    def createInstance(self, service_name: str) -> FakeChartDiagram:
        vertical = None
        if service_name == "com.sun.star.chart.BarDiagram":
            vertical = True
        return FakeChartDiagram(service_name, vertical=vertical)


class FakeTableChart:
    def __init__(self, diagram: FakeChartDiagram) -> None:
        self.EmbeddedObject = FakeChartDocument(diagram)


class FakeCalcSheet:
    def __init__(self, *charts: FakeTableChart) -> None:
        self.Charts = FakeCalcCharts(*charts)


class FakeCalcSelection:
    def __init__(self, rows: list[list[object]]) -> None:
        self._rows = rows

    def getDataArray(self) -> tuple[tuple[object, ...], ...]:
        return tuple(tuple(row) for row in self._rows)


class FakeCalcController:
    def __init__(self, rows: list[list[object]], *charts: FakeTableChart) -> None:
        self._selection = FakeCalcSelection(rows)
        self._sheet = FakeCalcSheet(*charts)

    def getSelection(self) -> FakeCalcSelection:
        return self._selection

    def getActiveSheet(self) -> FakeCalcSheet:
        return self._sheet


class FakeImpressShape:
    def __init__(self, text: str) -> None:
        self._text = text

    def getString(self) -> str:
        return self._text


class FakeImpressPage:
    def __init__(self, layout: int = 0, shape_text: str = "") -> None:
        self.Layout = layout
        self._shape = FakeImpressShape(shape_text)

    def getCount(self) -> int:
        return 1

    def getByIndex(self, index: int) -> FakeImpressShape:
        if index != 0:
            raise IndexError(index)
        return self._shape


class FakeDrawPages:
    def __init__(self, *pages: FakeImpressPage) -> None:
        self._pages = list(pages)

    def getCount(self) -> int:
        return len(self._pages)

    def getByIndex(self, index: int) -> FakeImpressPage:
        return self._pages[index]


class FakeImpressModel:
    def __init__(self, *pages: FakeImpressPage) -> None:
        self._draw_pages = FakeDrawPages(*pages)

    def getDrawPages(self) -> FakeDrawPages:
        return self._draw_pages


class FakeImpressController:
    def __init__(self, current_page: FakeImpressPage, *pages: FakeImpressPage) -> None:
        self._current_page = current_page
        self._model = FakeImpressModel(*pages)

    def getCurrentPage(self) -> FakeImpressPage:
        return self._current_page

    def getModel(self) -> FakeImpressModel:
        return self._model


def test_build_observation_results_parses_calc_chart_summary_probe() -> None:
    after_controller = FakeCalcController(
        [[1, 2], [3, 4]],
        FakeTableChart(FakeChartDiagram("com.sun.star.chart.PieDiagram")),
    )
    proposal = SimpleNamespace(
        tool_id="Calc.CreateChartFromSelection",
        preview=None,
        arguments={"chartType": "Pie"},
    )

    preconditions, postconditions, outcome = build_observation_results(
        proposal,
        selection_before="A1:B10",
        selection_after="A1:B10",
        summary="Inserted chart (type hint: Pie) from selection.",
        controller=after_controller,
        state_after=capture_observation_state(proposal, after_controller),
    )

    assert preconditions[0].status == "passed"
    assert postconditions[0].probe == "calc.active_sheet_last_chart_type.equals_argument.chartType"
    assert postconditions[0].actual == "Pie"
    assert postconditions[0].expected == "Pie"
    assert outcome == "satisfied"


def test_apply_chart_type_to_last_chart_sets_requested_diagram() -> None:
    controller = FakeCalcController(
        [[1, 2], [3, 4]],
        FakeTableChart(FakeChartDiagram("com.sun.star.chart.BarDiagram", vertical=True)),
    )

    _apply_chart_type_to_last_chart(controller, "Pie")

    assert read_active_sheet_last_chart_type(controller) == "Pie"


def test_read_active_sheet_last_chart_type_distinguishes_column_from_bar() -> None:
    column_controller = FakeCalcController(
        [[1, 2], [3, 4]],
        FakeTableChart(FakeChartDiagram("com.sun.star.chart.BarDiagram", vertical=False)),
    )
    bar_controller = FakeCalcController(
        [[1, 2], [3, 4]],
        FakeTableChart(FakeChartDiagram("com.sun.star.chart.BarDiagram", vertical=True)),
    )

    assert read_active_sheet_last_chart_type(column_controller) == "Column"
    assert read_active_sheet_last_chart_type(bar_controller) == "Bar"


def test_build_observation_results_parses_calc_sort_summary_probe() -> None:
    controller = FakeCalcController([[9], [5], [1]])
    proposal = SimpleNamespace(
        tool_id="Calc.SortSelectedRange",
        preview=None,
        arguments={"ascending": False, "sortDirection": "descending"},
    )

    _, postconditions, outcome = build_observation_results(
        proposal,
        selection_before="A1:B10",
        selection_after="A1:B10",
        summary="Sorted selected range (descending).",
        controller=controller,
        state_after=capture_observation_state(proposal, controller),
    )

    assert postconditions[0].probe == "calc.selection_first_column_order.equals_argument.sortDirection"
    assert postconditions[0].actual == "descending"
    assert postconditions[0].expected == "descending"
    assert outcome == "satisfied"


def test_build_observation_results_parses_impress_outline_length_probe() -> None:
    controller = FakeImpressController(
        FakeImpressPage(layout=1, shape_text="Current slide"),
        FakeImpressPage(layout=1, shape_text="Existing slide"),
        FakeImpressPage(layout=1, shape_text="Project Status Update"),
    )
    proposal = SimpleNamespace(
        tool_id="Impress.CreateSlideFromOutline",
        preview=None,
        arguments={"outline": "Project Status Update", "outlineLength": 21},
    )

    _, postconditions, outcome = build_observation_results(
        proposal,
        selection_before="",
        selection_after="",
        summary="Created new slide with outline (21 chars).",
        controller=controller,
    )

    assert postconditions[0].probe == "impress.last_slide_text.equals_argument.outline"
    assert postconditions[0].actual == "Project Status Update"
    assert postconditions[0].expected == "Project Status Update"
    assert outcome == "satisfied"


def test_build_observation_results_parses_impress_layout_probe() -> None:
    current_page = FakeImpressPage(layout=0, shape_text="Current slide")
    controller = FakeImpressController(current_page, current_page)
    proposal = SimpleNamespace(
        tool_id="Impress.ApplyLayoutToCurrentSlide",
        preview=None,
        arguments={"layout": 0},
    )

    _, postconditions, outcome = build_observation_results(
        proposal,
        selection_before="",
        selection_after="",
        summary="Applied layout 0 to current slide.",
        controller=controller,
    )

    assert postconditions[0].probe == "impress.current_slide_layout.equals_argument.layout"
    assert postconditions[0].actual == 0
    assert postconditions[0].expected == 0
    assert outcome == "satisfied"