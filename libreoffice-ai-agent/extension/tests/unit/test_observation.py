from types import SimpleNamespace

from loaia.observation import build_observation_results


def test_build_observation_results_parses_calc_chart_summary_probe() -> None:
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
    )

    assert preconditions[0].status == "passed"
    assert postconditions[0].probe == "summary.matches_argument.chartType"
    assert postconditions[0].actual == "Pie"
    assert postconditions[0].expected == "Pie"
    assert outcome == "satisfied"


def test_build_observation_results_parses_calc_sort_summary_probe() -> None:
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
    )

    assert postconditions[0].probe == "summary.matches_argument.sortDirection"
    assert postconditions[0].actual == "descending"
    assert postconditions[0].expected == "descending"
    assert outcome == "satisfied"


def test_build_observation_results_parses_impress_outline_length_probe() -> None:
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
    )

    assert postconditions[0].probe == "summary.matches_argument.outlineLength"
    assert postconditions[0].actual == 21
    assert postconditions[0].expected == 21
    assert outcome == "satisfied"


def test_build_observation_results_parses_impress_layout_probe() -> None:
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
    )

    assert postconditions[0].probe == "summary.matches_argument.layout"
    assert postconditions[0].actual == 0
    assert postconditions[0].expected == 0
    assert outcome == "satisfied"