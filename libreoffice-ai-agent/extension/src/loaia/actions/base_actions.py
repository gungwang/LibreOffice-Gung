from loaia.actions.base import ActionDefinition

BASE_ACTIONS = [
    ActionDefinition(
        "Base.GetContext",
        "base",
        safe_formatting=False,
        requires_approval=False,
    ),
    ActionDefinition(
        "Base.ExplainQuery",
        "base",
        safe_formatting=False,
        requires_approval=False,
    ),
]
