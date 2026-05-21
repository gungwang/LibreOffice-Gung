from loaia.actions.base import ActionDefinition

WRITER_ACTIONS = [
    ActionDefinition(
        "Writer.GetSelection",
        "writer",
        safe_formatting=False,
        requires_approval=False,
    ),
    ActionDefinition(
        "Writer.ToggleBold",
        "writer",
        safe_formatting=True,
        requires_approval=False,
    ),
    ActionDefinition(
        "Writer.ApplyHeading1",
        "writer",
        safe_formatting=True,
        requires_approval=False,
    ),
    ActionDefinition(
        "Writer.ApplyHeading2",
        "writer",
        safe_formatting=True,
        requires_approval=False,
    ),
    ActionDefinition(
        "Writer.ReplaceSelection",
        "writer",
        safe_formatting=False,
        requires_approval=True,
    ),
]
