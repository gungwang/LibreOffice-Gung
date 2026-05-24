from loaia.actions.base import ActionDefinition
from loaia_shared.capabilities.compiler import get_compiled_capabilities
from loaia_shared.schema.actions import SafetyClass

ACTION_REGISTRY = {
    tool_id: ActionDefinition(
        tool_id=tool_id,
        app=compiled.descriptor.app,
        safe_formatting=compiled.descriptor.safety_class == SafetyClass.SAFE_FORMATTING,
        requires_approval=compiled.descriptor.requires_approval,
    )
    for tool_id, compiled in get_compiled_capabilities().items()
}
