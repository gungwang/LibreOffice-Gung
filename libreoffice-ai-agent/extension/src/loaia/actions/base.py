from dataclasses import dataclass


@dataclass(slots=True)
class ActionDefinition:
    tool_id: str
    app: str
    safe_formatting: bool = False
    requires_approval: bool = True
