from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass(slots=True)
class ProviderRequest:
    provider: str
    model: str
    prompt: str
    context_text: str


@dataclass(slots=True)
class ProviderChunk:
    text: str


class BaseProviderAdapter(Protocol):
    name: str

    def complete(self, request: ProviderRequest) -> str:
        ...

    def stream(self, request: ProviderRequest) -> Iterable[ProviderChunk]:
        ...
