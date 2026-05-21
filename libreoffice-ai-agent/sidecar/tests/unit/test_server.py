from collections.abc import Iterable

from loaia_shared.schema.messages import (
    ChatRequest,
    ContextEnvelope,
    DocumentRef,
    SelectionContext,
)
from loaia_shared.types import AppType, PrivacyScope
from loaia_sidecar.providers.base import ProviderChunk, ProviderRequest
from loaia_sidecar.server import LoaiaSidecarServer


class FakeProviderAdapter:
    name = "openrouter"

    def __init__(self, answer: str = "Remote answer") -> None:
        self.answer = answer
        self.requests: list[ProviderRequest] = []

    def complete(self, request: ProviderRequest) -> str:
        self.requests.append(request)
        return self.answer

    def stream(self, request: ProviderRequest) -> Iterable[ProviderChunk]:
        self.requests.append(request)
        return iter(())


class FailingProviderAdapter:
    name = "openrouter"

    def complete(self, request: ProviderRequest) -> str:
        raise ValueError("OpenRouter API key is not configured.")

    def stream(self, request: ProviderRequest) -> Iterable[ProviderChunk]:
        return iter(())


def make_chat_request(
    *,
    provider: str = "openrouter",
    model: str = "openai/gpt-4.1-mini",
) -> ChatRequest:
    return ChatRequest(
        requestId="req-openrouter-1",
        app=AppType.WRITER,
        document=DocumentRef(canonicalUrl="file:///example.odt", profileId="profile-1"),
        provider=provider,
        model=model,
        privacyScope=PrivacyScope.SELECTION_ONLY,
        context=ContextEnvelope(
            selection=SelectionContext(mimeType="text/plain", text="hello world")
        ),
        userMessage="Summarize this selection.",
    )


def test_handle_chat_request_uses_provider_adapter_for_direct_answers() -> None:
    adapter = FakeProviderAdapter(answer="Remote summary")
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(make_chat_request())

    assert response.type == "DirectAnswer"
    assert response.text == "Remote summary"
    assert adapter.requests == [
        ProviderRequest(
            provider="openrouter",
            model="openai/gpt-4.1-mini",
            prompt="Summarize this selection.",
            context_text="hello world",
        )
    ]


def test_handle_message_returns_error_response_for_provider_failures() -> None:
    server = LoaiaSidecarServer(provider_adapters={"openrouter": FailingProviderAdapter()})

    response = server.handle_message(
        make_chat_request().model_dump(by_alias=True, mode="json")
    )

    assert response["type"] == "ErrorResponse"
    assert response["requestId"] == "req-openrouter-1"
    assert response["message"] == "OpenRouter API key is not configured."