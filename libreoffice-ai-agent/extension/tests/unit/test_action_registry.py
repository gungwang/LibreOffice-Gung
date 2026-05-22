from loaia.actions.executor import (
    SAFE_FORMATTING_TOOL_IDS,
    TOOL_UNO_DISPATCH_MAP,
    is_safe_formatting_action,
)
from loaia.actions.registry import ACTION_REGISTRY


def test_writer_toggle_bold_is_registered() -> None:
    assert "Writer.ToggleBold" in ACTION_REGISTRY


def test_all_mvp_writer_actions_registered() -> None:
    expected = [
        "Writer.GetSelection",
        "Writer.ToggleBold",
        "Writer.ToggleItalic",
        "Writer.ToggleUnderline",
        "Writer.ApplyHeading1",
        "Writer.ApplyHeading2",
        "Writer.ApplyHeading3",
        "Writer.ApplyBullets",
        "Writer.AlignLeft",
        "Writer.AlignCenter",
        "Writer.AlignRight",
        "Writer.ReplaceSelection",
        "Writer.InsertBelowSelection",
    ]
    for tool_id in expected:
        assert tool_id in ACTION_REGISTRY, f"Missing: {tool_id}"


def test_all_mvp_calc_actions_registered() -> None:
    expected = [
        "Calc.GetSelectedRange",
        "Calc.GetSelectedFormula",
        "Calc.ToggleBold",
        "Calc.ToggleItalic",
        "Calc.AlignLeft",
        "Calc.AlignCenter",
        "Calc.AlignRight",
        "Calc.ApplyNumberFormatCurrency",
        "Calc.ApplyNumberFormatPercent",
        "Calc.ApplyNumberFormatDate",
        "Calc.InsertFormulaInSelection",
        "Calc.CreateChartFromSelection",
        "Calc.SortSelectedRange",
    ]
    for tool_id in expected:
        assert tool_id in ACTION_REGISTRY, f"Missing: {tool_id}"


def test_all_mvp_impress_actions_registered() -> None:
    expected = [
        "Impress.GetSelectedText",
        "Impress.ToggleBold",
        "Impress.ToggleItalic",
        "Impress.ApplyBullets",
        "Impress.AlignLeft",
        "Impress.AlignCenter",
        "Impress.AlignRight",
        "Impress.ReplaceSelectedText",
        "Impress.CreateSlideFromOutline",
        "Impress.ApplyLayoutToCurrentSlide",
    ]
    for tool_id in expected:
        assert tool_id in ACTION_REGISTRY, f"Missing: {tool_id}"


def test_all_mvp_draw_actions_registered() -> None:
    expected = [
        "Draw.GetSelectedText",
        "Draw.ToggleBold",
        "Draw.ToggleItalic",
        "Draw.ToggleUnderline",
        "Draw.AlignLeft",
        "Draw.AlignCenter",
        "Draw.AlignRight",
        "Draw.ReplaceSelectedText",
    ]
    for tool_id in expected:
        assert tool_id in ACTION_REGISTRY, f"Missing: {tool_id}"


def test_all_mvp_math_actions_registered() -> None:
    expected = [
        "Math.GetFormula",
        "Math.ReplaceFormula",
    ]
    for tool_id in expected:
        assert tool_id in ACTION_REGISTRY, f"Missing: {tool_id}"


def test_all_mvp_base_actions_registered() -> None:
    expected = [
        "Base.GetContext",
        "Base.ExplainQuery",
    ]
    for tool_id in expected:
        assert tool_id in ACTION_REGISTRY, f"Missing: {tool_id}"


def test_safe_formatting_registry_actions_match_executor() -> None:
    for tool_id, action_def in ACTION_REGISTRY.items():
        if action_def.safe_formatting:
            assert is_safe_formatting_action(tool_id), (
                f"{tool_id} is marked safe_formatting in registry but not in executor"
            )


def test_all_safe_formatting_tools_have_uno_dispatch() -> None:
    for tool_id in SAFE_FORMATTING_TOOL_IDS:
        assert tool_id in TOOL_UNO_DISPATCH_MAP, (
            f"{tool_id} is safe-formatting but has no UNO dispatch mapping"
        )
