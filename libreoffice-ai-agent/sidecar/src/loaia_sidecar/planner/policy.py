from loaia_shared.capabilities.compiler import get_safe_formatting_tool_ids


SAFE_FORMATTING_TOOL_IDS = get_safe_formatting_tool_ids()


def is_safe_formatting_tool(tool_id: str) -> bool:
    return tool_id in SAFE_FORMATTING_TOOL_IDS
