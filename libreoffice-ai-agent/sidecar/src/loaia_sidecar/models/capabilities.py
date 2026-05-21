from dataclasses import dataclass


@dataclass(slots=True)
class ModelCapabilities:
    supports_streaming: bool = True
    supports_tool_planning: bool = True
    supports_long_context: bool = False
