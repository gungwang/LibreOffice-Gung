from dataclasses import dataclass, field

from loaia_shared.defaults import get_default_model, get_default_provider


@dataclass(slots=True)
class SidecarSettings:
    default_provider: str = field(default_factory=get_default_provider)
    default_model: str = field(default_factory=get_default_model)
    local_endpoint_url: str = "http://127.0.0.1:11434/v1"
    request_timeout_seconds: int = 120
    enabled_providers: list[str] = field(
        default_factory=lambda: ["openai-compatible", "anthropic", "gemini", "openrouter"]
    )
