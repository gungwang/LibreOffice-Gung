from loaia.actions.base import ActionDefinition

MATH_ACTIONS = [
    ActionDefinition(
        "Math.GetFormula",
        "math",
        safe_formatting=False,
        requires_approval=False,
    ),
    ActionDefinition(
        "Math.ReplaceFormula",
        "math",
        safe_formatting=False,
        requires_approval=True,
    ),
]
