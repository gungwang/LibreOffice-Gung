from loaia.actions.base import ActionDefinition

APP_ACTIONS = [
    ActionDefinition(
        "App.ExecuteUnoCommand",
        "app",
        safe_formatting=False,
        requires_approval=True,
    ),
]
