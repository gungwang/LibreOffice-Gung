from dataclasses import dataclass

from loaia_sidecar.models.capabilities import ModelCapabilities


@dataclass(slots=True)
class ModelEntry:
    provider: str
    model: str
    capabilities: ModelCapabilities


DEFAULT_CATALOG = [
    ModelEntry(
        provider="openai-compatible",
        model="local-default",
        capabilities=ModelCapabilities(),
    )
]
