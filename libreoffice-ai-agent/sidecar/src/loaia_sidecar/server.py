import json

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
from loaia_sidecar.providers.openai_compatible import OpenAICompatibleAdapter
from loaia_sidecar.providers.openrouter import OpenRouterAdapter
from loaia_sidecar.transport.named_pipe import NamedPipeTransport

WRITER_NO_REPLACEMENT_SENTINEL = "NO_REPLACEMENT"


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
            ),
            OpenAICompatibleAdapter.name: OpenAICompatibleAdapter(
                settings=self.settings,
            ),
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
        # Try app-specific planning first.
        proposal = self._plan_tool_proposal(request)
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
        if replacement_text is None:
            replacement_text = self._plan_writer_replace_selection_via_provider(request)

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

    def _plan_writer_replace_selection_via_provider(self, request: ChatRequest) -> str | None:
        selection = request.context.selection
        if selection is None:
            return None

        adapter = self.provider_adapters.get(request.provider)
        if adapter is None:
            return None

        provider_request = ProviderRequest(
            provider=request.provider,
            model=request.model,
            prompt=self._build_writer_rewrite_prompt(request.user_message),
            context_text=selection.text,
        )
        response_text = adapter.complete(provider_request)
        return self._normalize_writer_rewrite_response(response_text)

    @staticmethod
    def _build_writer_rewrite_prompt(user_message: str) -> str:
        return "\n".join(
            [
                "You are planning a LibreOffice Writer ReplaceSelection action.",
                (
                    "Reply with JSON only. Do not add markdown fences, commentary, or extra text."
                ),
                (
                    "For a rewrite, return exactly: "
                    '{"action":"replace-selection","replacementText":"<full replacement text>"}'
                ),
                (
                    "If the request should stay a direct answer instead of replacing the "
                    "selection, return exactly: "
                    '{"action":"no-replacement"}'
                ),
                (
                    f"Legacy fallback remains {WRITER_NO_REPLACEMENT_SENTINEL}, "
                    "but prefer the JSON contract above."
                ),
                f"User request: {user_message.strip()}",
            ]
        )

    @staticmethod
    def _normalize_writer_rewrite_response(response_text: str) -> str | None:
        normalized = response_text.strip()
        if not normalized:
            return None

        if normalized.startswith("```") and normalized.endswith("```"):
            lines = normalized.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            normalized = "\n".join(lines).strip()

        if normalized.casefold() == WRITER_NO_REPLACEMENT_SENTINEL.casefold():
            return None

        if normalized.startswith("{") and normalized.endswith("}"):
            try:
                payload = json.loads(normalized)
            except json.JSONDecodeError:
                payload = None

            if isinstance(payload, dict):
                action = str(payload.get("action") or "").strip().casefold()
                if action == "no-replacement":
                    return None

                if action == "replace-selection":
                    replacement_text = payload.get("replacementText")
                    if isinstance(replacement_text, str):
                        replacement_text = replacement_text.strip()
                        return replacement_text or None

                    return None

        if (
            len(normalized) >= 2
            and normalized[0] == normalized[-1]
            and normalized[0] in {'"', "'"}
        ):
            normalized = normalized[1:-1].strip()

        return normalized or None

    def _plan_tool_proposal(self, request: ChatRequest) -> ToolProposal | None:
        """Route planning to the appropriate app-specific planner."""
        if request.app is AppType.WRITER:
            return self._plan_writer_replace_selection(request)
        if request.app is AppType.CALC:
            return self._plan_calc_proposal(request)
        if request.app is AppType.IMPRESS:
            return self._plan_impress_proposal(request)
        return None

    def _plan_calc_proposal(self, request: ChatRequest) -> ToolProposal | None:
        """Plan a Calc action proposal if the user message implies formula insertion."""
        selection = request.context.selection
        if selection is None or not selection.text.strip():
            return None

        normalized_message = request.user_message.casefold()
        # Only propose formula insertion for explicit formula-related requests.
        formula_keywords = ("formula", "insert formula", "calculate", "sum", "average", "count")
        if not any(keyword in normalized_message for keyword in formula_keywords):
            return None

        # Use the provider to generate a formula suggestion.
        adapter = self.provider_adapters.get(request.provider)
        if adapter is None:
            return None

        provider_request = ProviderRequest(
            provider=request.provider,
            model=request.model,
            prompt=self._build_calc_formula_prompt(request.user_message),
            context_text=selection.text,
        )
        response_text = adapter.complete(provider_request)
        formula = self._normalize_calc_formula_response(response_text)
        if formula is None:
            return None

        return ToolProposal(
            proposalId=f"{request.request_id}-calc-formula",
            toolId="Calc.InsertFormulaInSelection",
            safetyClass=SafetyClass.CONTENT_EDIT,
            requiresApproval=True,
            preview=ActionPreview(
                summary=f"Insert formula: {formula}",
                before=selection.text,
                after=formula,
            ),
            arguments={"formula": formula},
        )

    def _plan_impress_proposal(self, request: ChatRequest) -> ToolProposal | None:
        """Plan an Impress text replacement proposal."""
        selection = request.context.selection
        if selection is None or not selection.text.strip():
            return None

        normalized_message = request.user_message.casefold()
        # Only propose text replacement for explicit rewrite requests.
        rewrite_keywords = ("rewrite", "rephrase", "improve", "reword", "simplify", "shorten")
        if not any(keyword in normalized_message for keyword in rewrite_keywords):
            return None

        adapter = self.provider_adapters.get(request.provider)
        if adapter is None:
            return None

        provider_request = ProviderRequest(
            provider=request.provider,
            model=request.model,
            prompt=self._build_impress_rewrite_prompt(request.user_message),
            context_text=selection.text,
        )
        response_text = adapter.complete(provider_request)
        replacement = response_text.strip()
        if not replacement or replacement == selection.text:
            return None

        return ToolProposal(
            proposalId=f"{request.request_id}-impress-replace",
            toolId="Impress.ReplaceSelectedText",
            safetyClass=SafetyClass.CONTENT_EDIT,
            requiresApproval=True,
            preview=ActionPreview(
                summary="Replace selected Impress text",
                before=selection.text,
                after=replacement,
            ),
            arguments={"replacementText": replacement},
        )

    @staticmethod
    def _build_calc_formula_prompt(user_message: str) -> str:
        return "\n".join(
            [
                "You are a LibreOffice Calc formula assistant.",
                "Given the user request and the selected cell context, suggest a formula.",
                "Reply with ONLY the formula (starting with =). No explanation, no commentary.",
                "If you cannot suggest a formula, reply with: NO_FORMULA",
                f"User request: {user_message.strip()}",
            ]
        )

    @staticmethod
    def _normalize_calc_formula_response(response_text: str) -> str | None:
        normalized = response_text.strip()
        if not normalized or normalized.casefold() == "no_formula":
            return None
        # Strip markdown fences if present.
        if normalized.startswith("```") and normalized.endswith("```"):
            lines = normalized.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            normalized = "\n".join(lines).strip()
        # Must look like a formula.
        if normalized.startswith("="):
            return normalized
        return None

    @staticmethod
    def _build_impress_rewrite_prompt(user_message: str) -> str:
        return "\n".join(
            [
                "You are a LibreOffice Impress text editor.",
                "Rewrite the selected slide text according to the user request.",
                "Reply with ONLY the rewritten text. No explanation, no markdown fences.",
                f"User request: {user_message.strip()}",
            ]
        )

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
