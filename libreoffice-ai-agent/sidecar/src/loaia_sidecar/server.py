from pydantic import ValidationError as PydanticValidationError

from loaia_shared.schema.actions import ActionPreview, SafetyClass, ToolProposal
from loaia_shared.schema.messages import (
    ChatRequest,
    DirectAnswer,
    ErrorResponse,
    HandshakeResponse,
    ToolProposalEnvelope,
)
from loaia_shared.types import AppType
from loaia_sidecar.config.secrets import SecretStore
from loaia_sidecar.config.settings import SidecarSettings
from loaia_sidecar.providers.base import BaseProviderAdapter, ProviderRequest
from loaia_sidecar.providers.openrouter import OpenRouterAdapter
from loaia_sidecar.transport.named_pipe import NamedPipeTransport


class LoaiaSidecarServer:
    """Minimal sidecar server skeleton.

    The real implementation will own the transport loop, provider dispatch,
    streaming lifecycle, and structured tool proposal generation.
    """

    def __init__(
        self,
        settings: SidecarSettings | None = None,
        secret_store: SecretStore | None = None,
        provider_adapters: dict[str, BaseProviderAdapter] | None = None,
    ) -> None:
        self.settings = settings or SidecarSettings()
        self.secret_store = secret_store or SecretStore()
        self.provider_adapters = provider_adapters or {
            OpenRouterAdapter.name: OpenRouterAdapter(
                settings=self.settings,
                secret_store=self.secret_store,
            )
        }
        self.capabilities = [
            "handshake",
            "streaming",
            "tool-proposals",
            "consent-escalation",
        ]

    def handshake(self) -> HandshakeResponse:
        return HandshakeResponse(
            serverVersion="0.1.0",
            capabilities=self.capabilities,
            availableProviders=self.settings.enabled_providers,
        )

    def handle_chat_request(self, request: ChatRequest) -> DirectAnswer | ToolProposalEnvelope:
        proposal = self._plan_writer_replace_selection(request)
        if proposal is not None:
            return ToolProposalEnvelope(requestId=request.request_id, proposals=[proposal])

        return DirectAnswer(
            requestId=request.request_id,
            text=self._complete_direct_answer(request),
        )

    def handle_message(self, payload: dict[str, object]) -> dict[str, object]:
        message_type = payload.get("type")
        request_id = payload.get("requestId") if isinstance(payload.get("requestId"), str) else ""

        if message_type == "HandshakeRequest":
            return self.handshake().model_dump(by_alias=True, mode="json")

        if message_type == "ChatRequest":
            try:
                request = ChatRequest.model_validate(payload)
            except PydanticValidationError as exc:
                return ErrorResponse(requestId=request_id, message=str(exc)).model_dump(
                    by_alias=True,
                    mode="json",
                )

            try:
                response = self.handle_chat_request(request)
            except (RuntimeError, ValueError) as exc:
                return ErrorResponse(requestId=request_id, message=str(exc)).model_dump(
                    by_alias=True,
                    mode="json",
                )

            return response.model_dump(by_alias=True, mode="json")

        return ErrorResponse(
            requestId=request_id,
            message=f"Unsupported request type: {message_type!r}",
        ).model_dump(by_alias=True, mode="json")

    def run(self) -> None:
        NamedPipeTransport(handler=self.handle_message).serve_forever()

    def _plan_writer_replace_selection(self, request: ChatRequest) -> ToolProposal | None:
        selection = request.context.selection
        if request.app is not AppType.WRITER or selection is None:
            return None

        if not selection.text.strip():
            return None

        replacement_text = self._rewrite_writer_selection(request.user_message, selection.text)
        if replacement_text is None or replacement_text == selection.text:
            return None

        return ToolProposal(
            proposalId=f"{request.request_id}-writer-replace",
            toolId="Writer.ReplaceSelection",
            safetyClass=SafetyClass.CONTENT_EDIT,
            requiresApproval=True,
            preview=ActionPreview(
                summary="Preview Writer selection replacement",
                before=selection.text,
                after=replacement_text,
            ),
            arguments={"replacementText": replacement_text},
        )

    @staticmethod
    def _rewrite_writer_selection(user_message: str, selection_text: str) -> str | None:
        normalized_message = user_message.casefold()
        if "uppercase" in normalized_message or "upper case" in normalized_message:
            return selection_text.upper()

        if "lowercase" in normalized_message or "lower case" in normalized_message:
            return selection_text.lower()

        if "title case" in normalized_message or "titlecase" in normalized_message:
            return selection_text.title()

        if "trim" in normalized_message or "strip" in normalized_message:
            return selection_text.strip()

        return None

    def _complete_direct_answer(self, request: ChatRequest) -> str:
        provider_request = ProviderRequest(
            provider=request.provider,
            model=request.model,
            prompt=request.user_message,
            context_text=request.context.selection.text if request.context.selection else "",
        )
        adapter = self.provider_adapters.get(provider_request.provider)
        if adapter is None:
            return (
                "Sidecar scaffold is running. Planner and provider execution "
                "are not implemented yet."
            )

        return adapter.complete(provider_request)
