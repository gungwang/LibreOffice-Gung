from collections.abc import Callable, Iterable

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

    def __init__(
        self,
        answer: str = "Remote answer",
        complete_impl: Callable[[ProviderRequest], str] | None = None,
    ) -> None:
        self.answer = answer
        self.complete_impl = complete_impl
        self.requests: list[ProviderRequest] = []

    def complete(self, request: ProviderRequest) -> str:
        self.requests.append(request)
        if self.complete_impl is not None:
            return self.complete_impl(request)
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
    app: AppType = AppType.WRITER,
    selection_text: str | None = "hello world",
    user_message: str = "Summarize this selection.",
) -> ChatRequest:
    context = ContextEnvelope()
    if selection_text is not None:
        context = ContextEnvelope(
            selection=SelectionContext(mimeType="text/plain", text=selection_text)
        )

    return ChatRequest(
        requestId="req-openrouter-1",
        app=app,
        document=DocumentRef(canonicalUrl="file:///example.odt", profileId="profile-1"),
        provider=provider,
        model=model,
        privacyScope=PrivacyScope.SELECTION_ONLY,
        context=context,
        userMessage=user_message,
    )


def test_handle_chat_request_uses_provider_adapter_for_direct_answers() -> None:
    adapter = FakeProviderAdapter(answer="Remote summary")
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(make_chat_request(selection_text=None))

    assert response.type == "DirectAnswer"
    assert response.text == "Remote summary"
    assert adapter.requests == [
        ProviderRequest(
            provider="openrouter",
            model="openai/gpt-4.1-mini",
            prompt="Summarize this selection.",
            context_text="",
        )
    ]


def test_handle_chat_request_uses_provider_adapter_for_writer_proposals() -> None:
    adapter = FakeProviderAdapter(answer="Greetings from the revised draft.")
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(user_message="Rewrite this selection in a more formal tone.")
    )

    assert response.type == "ToolProposal"
    assert len(response.proposals) == 1
    proposal = response.proposals[0]
    assert proposal.tool_id == "Writer.ReplaceSelection"
    assert proposal.preview is not None
    assert proposal.preview.before == "hello world"
    assert proposal.preview.after == "Greetings from the revised draft."
    assert proposal.arguments == {"replacementText": "Greetings from the revised draft."}
    assert len(adapter.requests) == 1
    assert adapter.requests[0].context_text == "hello world"
    assert "NO_REPLACEMENT" in adapter.requests[0].prompt
    assert "Rewrite this selection in a more formal tone." in adapter.requests[0].prompt


def test_handle_chat_request_falls_back_to_direct_answer_when_provider_declines_rewrite() -> None:
    def complete_impl(request: ProviderRequest) -> str:
        if "NO_REPLACEMENT" in request.prompt:
            return "NO_REPLACEMENT"

        return "Remote summary"

    adapter = FakeProviderAdapter(complete_impl=complete_impl)
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(make_chat_request())

    assert response.type == "DirectAnswer"
    assert response.text == "Remote summary"
    assert len(adapter.requests) == 2
    assert "NO_REPLACEMENT" in adapter.requests[0].prompt
    assert adapter.requests[0].context_text == "hello world"
    assert adapter.requests[1] == ProviderRequest(
        provider="openrouter",
        model="openai/gpt-4.1-mini",
        prompt="Summarize this selection.",
        context_text="hello world",
    )


def test_handle_message_returns_error_response_for_provider_failures() -> None:
    server = LoaiaSidecarServer(provider_adapters={"openrouter": FailingProviderAdapter()})

    response = server.handle_message(
        make_chat_request().model_dump(by_alias=True, mode="json")
    )

    assert response["type"] == "ErrorResponse"
    assert response["requestId"] == "req-openrouter-1"
    assert response["message"] == "OpenRouter API key is not configured."