from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

from loaia.context.calc import create_chart_from_selection, read_active_sheet_last_chart_type


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
        vertical = True if service_name == "com.sun.star.chart.BarDiagram" else None
        return FakeChartDiagram(service_name, vertical=vertical)


class FakeTableChart:
    def __init__(self, diagram: FakeChartDiagram) -> None:
        self.EmbeddedObject = FakeChartDocument(diagram)


class FakeCharts:
    def __init__(self) -> None:
        self.items: list[FakeTableChart] = []
        self.last_added_name: str | None = None
        self.last_added_ranges: tuple[object, ...] | None = None

    def addNewByName(
        self,
        name: str,
        rectangle: object,
        ranges: tuple[object, ...],
        column_headers: bool,
        row_headers: bool,
    ) -> None:
        self.last_added_name = name
        self.last_added_ranges = ranges
        self.last_added_rectangle = rectangle
        self.last_column_headers = column_headers
        self.last_row_headers = row_headers
        self.items.append(
            FakeTableChart(
                FakeChartDiagram("com.sun.star.chart.BarDiagram", vertical=True)
            )
        )

    def getCount(self) -> int:
        return len(self.items)

    def getByIndex(self, index: int) -> FakeTableChart:
        return self.items[index]


class FakeSheet:
    def __init__(self) -> None:
        self.Charts = FakeCharts()


class FakeSelection:
    def __init__(self) -> None:
        self.RangeAddress = SimpleNamespace(StartRow=0, EndRow=4, StartColumn=0, EndColumn=1)


class FakeController:
    def __init__(self) -> None:
        self.sheet = FakeSheet()
        self.selection = FakeSelection()

    def getSelection(self) -> FakeSelection:
        return self.selection

    def getActiveSheet(self) -> FakeSheet:
        return self.sheet


def test_create_chart_from_selection_adds_chart_and_applies_requested_type() -> None:
    controller = FakeController()
    fake_uno = SimpleNamespace(createUnoStruct=lambda _name: SimpleNamespace())

    with patch.dict(sys.modules, {"uno": fake_uno}):
        result = create_chart_from_selection(controller, chart_type="Pie")

    assert result == "Inserted chart (type hint: Pie) from selection."
    assert controller.sheet.Charts.last_added_name == "LoaiaChart1"
    assert controller.sheet.Charts.last_added_ranges == (controller.selection.RangeAddress,)
    assert controller.sheet.Charts.last_column_headers is True
    assert controller.sheet.Charts.last_row_headers is True
    assert read_active_sheet_last_chart_type(controller) == "Pie"