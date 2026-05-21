from loaia.actions.base import ActionDefinition

CALC_ACTIONS = [
    ActionDefinition(
        "Calc.GetSelectedRange",
        "calc",
        safe_formatting=False,
        requires_approval=False,
    ),
    ActionDefinition(
        "Calc.ToggleBold",
        "calc",
        safe_formatting=True,
        requires_approval=False,
    ),
    ActionDefinition(
        "Calc.ApplyNumberFormatCurrency",
        "calc",
        safe_formatting=True,
        requires_approval=False,
    ),
    ActionDefinition(
        "Calc.InsertFormulaInSelection",
        "calc",
        safe_formatting=False,
        requires_approval=True,
    ),
    ActionDefinition(
        "Calc.CreateChartFromSelection",
        "calc",
        safe_formatting=False,
        requires_approval=True,
    ),
]
