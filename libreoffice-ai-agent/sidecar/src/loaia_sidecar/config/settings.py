from dataclasses import dataclass, field


@dataclass(slots=True)
class SidecarSettings:
    default_provider: str = "openai-compatible"
    default_model: str = "local-default"
    local_endpoint_url: str = "http://127.0.0.1:11434/v1"
    request_timeout_seconds: int = 120
    enabled_providers: list[str] = field(
        default_factory=lambda: ["openai-compatible", "anthropic", "gemini", "openrouter"]
    )
