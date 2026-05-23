import json
import threading

from pydantic import ValidationError as PydanticValidationError

from loaia_shared.schema.actions import ActionPreview, SafetyClass, ToolProposal
from loaia_shared.schema.messages import (
    ChatRequest,
    ConsentRequest,
    DirectAnswer,
    ErrorResponse,
    HandshakeResponse,
    StreamChunk,
    ToolProposalEnvelope,
)
from loaia_shared.types import AppType, PrivacyScope
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
            "cancellation",
        ]
        self._cancelled_requests: set[str] = set()
        self._cancel_lock = threading.Lock()

    def handshake(self) -> HandshakeResponse:
        return HandshakeResponse(
            serverVersion="0.1.0",
            capabilities=self.capabilities,
            availableProviders=self.settings.enabled_providers,
        )

    def handle_chat_request(
        self, request: ChatRequest
    ) -> DirectAnswer | ToolProposalEnvelope | ConsentRequest:
        # Check if consent escalation is needed.
        consent = self._check_consent_escalation(request)
        if consent is not None:
            return consent

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

        if message_type == "CancelRequest":
            cancel_id = request_id
            with self._cancel_lock:
                self._cancelled_requests.add(cancel_id)
            return {"type": "CancelAck", "requestId": cancel_id}

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
        NamedPipeTransport(handler=self.handle_message_streaming).serve_forever()

    def handle_message_streaming(
        self, payload: dict[str, object]
    ) -> dict[str, object] | list[dict[str, object]]:
        """Handle a message, returning streamed chunks + final response when applicable."""
        message_type = payload.get("type")
        request_id = payload.get("requestId") if isinstance(payload.get("requestId"), str) else ""

        if message_type == "HandshakeRequest":
            return self.handshake().model_dump(by_alias=True, mode="json")

        if message_type == "CancelRequest":
            cancel_id = request_id
            with self._cancel_lock:
                self._cancelled_requests.add(cancel_id)
            return {"type": "CancelAck", "requestId": cancel_id}

        if message_type == "ChatRequest":
            try:
                request = ChatRequest.model_validate(payload)
            except PydanticValidationError as exc:
                return ErrorResponse(requestId=request_id, message=str(exc)).model_dump(
                    by_alias=True, mode="json"
                )

            try:
                # Check consent escalation first.
                consent = self._check_consent_escalation(request)
                if consent is not None:
                    return consent.model_dump(by_alias=True, mode="json")

                # Non-streaming path for tool proposals
                proposal = self._plan_tool_proposal(request)
                if proposal is not None:
                    response = ToolProposalEnvelope(
                        requestId=request.request_id, proposals=[proposal]
                    )
                    return response.model_dump(by_alias=True, mode="json")

                # Streaming path for direct answers
                return self._stream_direct_answer(request)
            except (RuntimeError, ValueError) as exc:
                return ErrorResponse(requestId=request_id, message=str(exc)).model_dump(
                    by_alias=True, mode="json"
                )

        return ErrorResponse(
            requestId=request_id,
            message=f"Unsupported request type: {message_type!r}",
        ).model_dump(by_alias=True, mode="json")

    # ------------------------------------------------------------------
    # Consent escalation
    # ------------------------------------------------------------------

    _DOCUMENT_SCOPE_KEYWORDS = (
        "whole document", "entire document", "full document",
        "whole page", "entire page", "full page",
        "all text", "the document", "this document",
        "summarize everything", "review everything",
    )

    def _check_consent_escalation(
        self, request: ChatRequest
    ) -> ConsentRequest | None:
        """Return a ConsentRequest if the user's message implies broader
        context but the current scope is selection-only with no/empty selection.
        """
        if request.privacy_scope != PrivacyScope.SELECTION_ONLY:
            return None

        has_selection = (
            request.context.selection is not None
            and request.context.selection.text.strip()
        )
        if has_selection:
            return None

        normalized = request.user_message.casefold()
        if not any(kw in normalized for kw in self._DOCUMENT_SCOPE_KEYWORDS):
            return None

        return ConsentRequest(
            requestId=request.request_id,
            requestedScope=PrivacyScope.FULL_DOCUMENT.value,
            reason=(
                "Your request appears to need the full document, but the "
                "current privacy scope is selection-only. Please approve "
                "escalation to full-document scope."
            ),
        )

    def _stream_direct_answer(
        self, request: ChatRequest
    ) -> dict[str, object] | list[dict[str, object]]:
        """Stream a direct answer, returning chunks + final DirectAnswer."""
        adapter = self.provider_adapters.get(request.provider)
        if adapter is None:
            raise ValueError(f"Provider {request.provider!r} is not available.")

        provider_request = ProviderRequest(
            provider=request.provider,
            model=request.model,
            prompt=self._build_direct_answer_prompt(request.user_message),
            context_text=(request.context.selection.text if request.context.selection else ""),
        )

        frames: list[dict[str, object]] = []
        collected_text: list[str] = []

        try:
            for chunk in adapter.stream(provider_request):
                if self._is_cancelled(request.request_id):
                    break
                collected_text.append(chunk.text)
                frames.append(
                    StreamChunk(
                        requestId=request.request_id, text=chunk.text
                    ).model_dump(by_alias=True, mode="json")
                )
        except NotImplementedError:
            # Fallback to non-streaming complete()
            text = adapter.complete(provider_request)
            return DirectAnswer(
                requestId=request.request_id, text=text
            ).model_dump(by_alias=True, mode="json")

        full_text = "".join(collected_text).strip()
        if not full_text:
            raise RuntimeError("Provider returned an empty response.")

        frames.append(
            DirectAnswer(
                requestId=request.request_id, text=full_text
            ).model_dump(by_alias=True, mode="json")
        )
        # Clean up cancellation entry now that the request is done.
        with self._cancel_lock:
            self._cancelled_requests.discard(request.request_id)
        return frames

    def _is_cancelled(self, request_id: str) -> bool:
        with self._cancel_lock:
            return request_id in self._cancelled_requests

    _QUESTION_STARTERS: tuple[str, ...] = (
        "what does", "what is", "what are", "what was", "what were",
        "who is", "who are", "who was", "who were",
        "where is", "where are", "where was",
        "when is", "when was", "when did",
        "why is", "why are", "why does", "why did",
        "how is", "how are", "how does", "how did", "how many", "how much",
        "tell me about", "tell me what", "tell me why", "tell me how",
        "is this", "is it", "are there", "does this", "do these",
        "can you explain", "can you tell",
    )

    _ANALYSIS_KEYWORDS: tuple[str, ...] = (
        "summarize this", "summarise this", "summarize the",
        "summarise the", "give a summary", "provide a summary",
        "explain this", "explain the", "analyze this", "analyse this",
        "describe this", "describe the", "list the key",
        "answer this question",
        "please summarize", "please summarise",
        "please explain", "please describe",
    )

    def _plan_writer_proposal(self, request: ChatRequest) -> ToolProposal | None:
        """Plan a Writer content-edit: either insert-below or replace-selection."""
        normalized = request.user_message.casefold().strip()

        # Questions about the text should be direct answers, not edits.
        if (
            normalized.endswith("?")
            or any(normalized.startswith(q) for q in self._QUESTION_STARTERS)
            or any(kw in normalized for kw in self._ANALYSIS_KEYWORDS)
        ):
            return None

        insert_keywords = (
            "insert below", "add below", "append", "add after",
            "insert after", "write below", "add paragraph",
        )
        if any(kw in normalized for kw in insert_keywords):
            return self._plan_writer_insert_below(request)
        return self._plan_writer_replace_selection(request)

    def _plan_writer_insert_below(self, request: ChatRequest) -> ToolProposal | None:
        """Plan Writer.InsertBelowSelection via the provider."""
        adapter = self.provider_adapters.get(request.provider)
        if adapter is None:
            return None

        provider_request = ProviderRequest(
            provider=request.provider,
            model=request.model,
            prompt=self._build_writer_insert_below_prompt(request.user_message),
            context_text=(
                request.context.selection.text
                if request.context.selection
                else ""
            ),
        )
        text = adapter.complete(provider_request).strip()
        if not text:
            return None

        return ToolProposal(
            proposalId=f"{request.request_id}-writer-insert-below",
            toolId="Writer.InsertBelowSelection",
            safetyClass=SafetyClass.CONTENT_EDIT,
            requiresApproval=False,
            preview=ActionPreview(
                summary="Insert text below current selection",
                before="",
                after=text,
            ),
            arguments={"replacementText": text},
        )

    @staticmethod
    def _build_writer_insert_below_prompt(user_message: str) -> str:
        return "\n".join(
            [
                "You are a LibreOffice Writer assistant.",
                "The user wants to insert new text below their current selection.",
                "Reply with ONLY the text to insert. No explanation, no markdown fences.",
                f"User request: {user_message.strip()}",
            ]
        )

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
            requiresApproval=False,
            preview=ActionPreview(
                summary="Replace selection",
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
                    "For a rewrite/edit/transform request, return exactly: "
                    '{"action":"replace-selection","replacementText":"<full replacement text>"}'
                ),
                (
                    "Translation IS a replace-selection action. When the user asks to translate "
                    "the text to another language, return the translated text as replacementText."
                ),
                (
                    "If the user is asking a QUESTION about the text (e.g. summarize, "
                    "explain, analyze, or answer a question) WITHOUT wanting to change "
                    "the document, return exactly: "
                    '{"action":"no-replacement"}'
                ),
                (
                    "Use replace-selection when the user wants to CHANGE the document text "
                    "(rewrite, fix grammar, shorten, expand, translate, convert, etc.)."
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
        # Try safe-formatting first (applies across all apps).
        safe_proposal = self._plan_safe_formatting(request)
        if safe_proposal is not None:
            return safe_proposal

        if request.app is AppType.WRITER:
            return self._plan_writer_proposal(request)
        if request.app is AppType.CALC:
            return self._plan_calc_proposal(request)
        if request.app is AppType.IMPRESS:
            return self._plan_impress_proposal(request)
        if request.app is AppType.DRAW:
            return self._plan_draw_proposal(request)
        if request.app is AppType.MATH:
            return self._plan_math_proposal(request)
        if request.app is AppType.BASE:
            return self._plan_base_proposal(request)
        return None

    # ------------------------------------------------------------------
    # Safe-formatting planner
    # ------------------------------------------------------------------

    _SAFE_FORMATTING_KEYWORDS: dict[str, dict[str, str]] = {
        "bold": {
            "writer": "Writer.ToggleBold",
            "calc": "Calc.ToggleBold",
            "impress": "Impress.ToggleBold",
            "draw": "Draw.ToggleBold",
        },
        "italic": {
            "writer": "Writer.ToggleItalic",
            "calc": "Calc.ToggleItalic",
            "impress": "Impress.ToggleItalic",
            "draw": "Draw.ToggleItalic",
        },
        "underline": {
            "writer": "Writer.ToggleUnderline",
            "draw": "Draw.ToggleUnderline",
        },
        "heading 1": {"writer": "Writer.ApplyHeading1"},
        "heading1": {"writer": "Writer.ApplyHeading1"},
        "h1": {"writer": "Writer.ApplyHeading1"},
        "heading 2": {"writer": "Writer.ApplyHeading2"},
        "heading2": {"writer": "Writer.ApplyHeading2"},
        "h2": {"writer": "Writer.ApplyHeading2"},
        "heading 3": {"writer": "Writer.ApplyHeading3"},
        "heading3": {"writer": "Writer.ApplyHeading3"},
        "h3": {"writer": "Writer.ApplyHeading3"},
        "bullet": {
            "writer": "Writer.ApplyBullets",
            "impress": "Impress.ApplyBullets",
        },
        "bullets": {
            "writer": "Writer.ApplyBullets",
            "impress": "Impress.ApplyBullets",
        },
        "align left": {
            "writer": "Writer.AlignLeft",
            "calc": "Calc.AlignLeft",
            "impress": "Impress.AlignLeft",
            "draw": "Draw.AlignLeft",
        },
        "left align": {
            "writer": "Writer.AlignLeft",
            "calc": "Calc.AlignLeft",
            "impress": "Impress.AlignLeft",
            "draw": "Draw.AlignLeft",
        },
        "center": {
            "writer": "Writer.AlignCenter",
            "calc": "Calc.AlignCenter",
            "impress": "Impress.AlignCenter",
            "draw": "Draw.AlignCenter",
        },
        "align center": {
            "writer": "Writer.AlignCenter",
            "calc": "Calc.AlignCenter",
            "impress": "Impress.AlignCenter",
            "draw": "Draw.AlignCenter",
        },
        "align right": {
            "writer": "Writer.AlignRight",
            "calc": "Calc.AlignRight",
            "impress": "Impress.AlignRight",
            "draw": "Draw.AlignRight",
        },
        "right align": {
            "writer": "Writer.AlignRight",
            "calc": "Calc.AlignRight",
            "impress": "Impress.AlignRight",
            "draw": "Draw.AlignRight",
        },
        "currency": {"calc": "Calc.ApplyNumberFormatCurrency"},
        "currency format": {"calc": "Calc.ApplyNumberFormatCurrency"},
        "percent": {"calc": "Calc.ApplyNumberFormatPercent"},
        "percent format": {"calc": "Calc.ApplyNumberFormatPercent"},
        "date format": {"calc": "Calc.ApplyNumberFormatDate"},
    }

    def _plan_safe_formatting(self, request: ChatRequest) -> ToolProposal | None:
        """Match user message against known formatting keywords and return a proposal."""
        normalized = request.user_message.casefold().strip()
        app_key = {
            AppType.WRITER: "writer",
            AppType.CALC: "calc",
            AppType.IMPRESS: "impress",
            AppType.DRAW: "draw",
        }.get(request.app)
        if app_key is None:
            return None

        for keyword, app_map in self._SAFE_FORMATTING_KEYWORDS.items():
            if keyword in normalized:
                tool_id = app_map.get(app_key)
                if tool_id is not None:
                    return ToolProposal(
                        proposalId=f"{request.request_id}-safe-fmt",
                        toolId=tool_id,
                        safetyClass=SafetyClass.SAFE_FORMATTING,
                        requiresApproval=False,
                        preview=ActionPreview(
                            summary=f"Apply {tool_id}",
                            before="",
                            after="",
                        ),
                        arguments={},
                    )
        return None

    def _plan_calc_proposal(self, request: ChatRequest) -> ToolProposal | None:
        """Plan a Calc action proposal: formula, chart, or sort."""
        normalized_message = request.user_message.casefold()

        # Chart creation
        chart_keywords = ("chart", "graph", "plot", "visualize", "visualization")
        if any(kw in normalized_message for kw in chart_keywords):
            chart_type = "Bar"
            for ct in ("pie", "line", "scatter", "area", "column", "bar"):
                if ct in normalized_message:
                    chart_type = ct.capitalize()
                    break
            return ToolProposal(
                proposalId=f"{request.request_id}-calc-chart",
                toolId="Calc.CreateChartFromSelection",
                safetyClass=SafetyClass.CONTENT_EDIT,
                requiresApproval=False,
                preview=ActionPreview(
                    summary=f"Create {chart_type} chart from selection",
                    before="",
                    after=f"[{chart_type} chart]",
                ),
                arguments={"chartType": chart_type},
            )

        # Sort
        sort_keywords = ("sort", "order", "arrange")
        if any(kw in normalized_message for kw in sort_keywords):
            ascending = "descend" not in normalized_message
            direction = "ascending" if ascending else "descending"
            return ToolProposal(
                proposalId=f"{request.request_id}-calc-sort",
                toolId="Calc.SortSelectedRange",
                safetyClass=SafetyClass.CONTENT_EDIT,
                requiresApproval=False,
                preview=ActionPreview(
                    summary=f"Sort selected range ({direction})",
                    before="",
                    after=f"[sorted {direction}]",
                ),
                arguments={"ascending": ascending},
            )

        # Formula insertion
        selection = request.context.selection
        if selection is None or not selection.text.strip():
            return None

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
            requiresApproval=False,
            preview=ActionPreview(
                summary=f"Insert formula: {formula}",
                before=selection.text,
                after=formula,
            ),
            arguments={"formula": formula},
        )

    def _plan_impress_proposal(self, request: ChatRequest) -> ToolProposal | None:
        """Plan an Impress action: slide creation, layout change, or text replacement."""
        normalized_message = request.user_message.casefold()

        # Slide creation from outline
        slide_keywords = ("new slide", "create slide", "add slide", "insert slide")
        if any(kw in normalized_message for kw in slide_keywords):
            adapter = self.provider_adapters.get(request.provider)
            if adapter is not None:
                provider_request = ProviderRequest(
                    provider=request.provider,
                    model=request.model,
                    prompt=self._build_impress_outline_prompt(request.user_message),
                    context_text=(
                        request.context.selection.text
                        if request.context.selection
                        else ""
                    ),
                )
                outline = adapter.complete(provider_request).strip()
            else:
                outline = request.user_message.strip()

            return ToolProposal(
                proposalId=f"{request.request_id}-impress-slide",
                toolId="Impress.CreateSlideFromOutline",
                safetyClass=SafetyClass.CONTENT_EDIT,
                requiresApproval=False,
                preview=ActionPreview(
                    summary="Create new slide from outline",
                    before="",
                    after=outline,
                ),
                arguments={"outline": outline},
            )

        # Layout change
        layout_keywords = ("layout", "apply layout", "change layout", "slide layout")
        if any(kw in normalized_message for kw in layout_keywords):
            layout = 0  # default blank
            layout_map = {"blank": 0, "title": 1, "content": 1, "two column": 3}
            for name, idx in layout_map.items():
                if name in normalized_message:
                    layout = idx
                    break
            return ToolProposal(
                proposalId=f"{request.request_id}-impress-layout",
                toolId="Impress.ApplyLayoutToCurrentSlide",
                safetyClass=SafetyClass.CONTENT_EDIT,
                requiresApproval=False,
                preview=ActionPreview(
                    summary=f"Apply layout {layout} to current slide",
                    before="",
                    after=f"[layout {layout}]",
                ),
                arguments={"layout": layout},
            )

        # Text replacement (existing)
        selection = request.context.selection
        if selection is None or not selection.text.strip():
            return None

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
            requiresApproval=False,
            preview=ActionPreview(
                summary="Replace selected Impress text",
                before=selection.text,
                after=replacement,
            ),
            arguments={"replacementText": replacement},
        )

    def _plan_draw_proposal(self, request: ChatRequest) -> ToolProposal | None:
        """Plan a Draw action: text replacement in selected shapes."""
        selection = request.context.selection
        if selection is None or not selection.text.strip():
            return None

        normalized_message = request.user_message.casefold()
        rewrite_keywords = ("rewrite", "rephrase", "improve", "reword", "simplify", "shorten")
        if not any(keyword in normalized_message for keyword in rewrite_keywords):
            return None

        adapter = self.provider_adapters.get(request.provider)
        if adapter is None:
            return None

        provider_request = ProviderRequest(
            provider=request.provider,
            model=request.model,
            prompt=self._build_draw_rewrite_prompt(request.user_message),
            context_text=selection.text,
        )
        response_text = adapter.complete(provider_request)
        replacement = response_text.strip()
        if not replacement or replacement == selection.text:
            return None

        return ToolProposal(
            proposalId=f"{request.request_id}-draw-replace",
            toolId="Draw.ReplaceSelectedText",
            safetyClass=SafetyClass.CONTENT_EDIT,
            requiresApproval=False,
            preview=ActionPreview(
                summary="Replace selected Draw text",
                before=selection.text,
                after=replacement,
            ),
            arguments={"replacementText": replacement},
        )

    def _plan_math_proposal(self, request: ChatRequest) -> ToolProposal | None:
        """Plan a Math action: formula rewrite or explanation."""
        selection = request.context.selection
        if selection is None or not selection.text.strip():
            return None

        normalized_message = request.user_message.casefold()

        # Formula rewrite
        rewrite_keywords = (
            "rewrite", "simplify", "expand", "factor", "convert", "fix", "correct",
        )
        if any(keyword in normalized_message for keyword in rewrite_keywords):
            adapter = self.provider_adapters.get(request.provider)
            if adapter is None:
                return None

            provider_request = ProviderRequest(
                provider=request.provider,
                model=request.model,
                prompt=self._build_math_rewrite_prompt(request.user_message),
                context_text=selection.text,
            )
            response_text = adapter.complete(provider_request)
            formula = response_text.strip()
            if not formula or formula == selection.text:
                return None

            return ToolProposal(
                proposalId=f"{request.request_id}-math-replace",
                toolId="Math.ReplaceFormula",
                safetyClass=SafetyClass.CONTENT_EDIT,
                requiresApproval=False,
                preview=ActionPreview(
                    summary="Replace Math formula",
                    before=selection.text,
                    after=formula,
                ),
                arguments={"formula": formula},
            )

        # Default: return None (will fall through to direct answer)
        return None

    def _plan_base_proposal(self, request: ChatRequest) -> ToolProposal | None:
        """Plan a Base action: SQL query generation or explanation.

        Base actions are informational only — they don't modify the database.
        """
        # Base is primarily informational; return None to trigger direct answer.
        return None

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

    @staticmethod
    def _build_impress_outline_prompt(user_message: str) -> str:
        return "\n".join(
            [
                "You are a LibreOffice Impress slide creator.",
                "Generate slide outline text based on the user request.",
                "Reply with ONLY the slide text content. No explanation, no markdown fences.",
                f"User request: {user_message.strip()}",
            ]
        )

    @staticmethod
    def _build_draw_rewrite_prompt(user_message: str) -> str:
        return "\n".join(
            [
                "You are a LibreOffice Draw text editor.",
                "Rewrite the selected shape text according to the user request.",
                "Reply with ONLY the rewritten text. No explanation, no markdown fences.",
                f"User request: {user_message.strip()}",
            ]
        )

    @staticmethod
    def _build_math_rewrite_prompt(user_message: str) -> str:
        return "\n".join(
            [
                "You are a LibreOffice Math formula editor.",
                "The formula uses StarMath markup notation.",
                "Rewrite the formula according to the user request.",
                "Reply with ONLY the StarMath formula. No explanation, no markdown fences.",
                f"User request: {user_message.strip()}",
            ]
        )

    @staticmethod
    def _build_direct_answer_prompt(user_message: str) -> str:
        return "\n".join([
            "You are a concise AI assistant embedded in LibreOffice.",
            "Answer the user's question briefly and directly.",
            "Do NOT generate setup guides, tutorials, or unrelated content.",
            "Keep answers short (1-3 paragraphs max) unless the user explicitly asks for detail.",
            "If the user provides document text as context, answer about THAT text specifically.",
            f"User: {user_message.strip()}",
        ])

    def _complete_direct_answer(self, request: ChatRequest) -> str:
        prompt = self._build_direct_answer_prompt(request.user_message)
        provider_request = ProviderRequest(
            provider=request.provider,
            model=request.model,
            prompt=prompt,
            context_text=request.context.selection.text if request.context.selection else "",
        )
        adapter = self.provider_adapters.get(provider_request.provider)
        if adapter is None:
            return (
                "Sidecar scaffold is running. Planner and provider execution "
                "are not implemented yet."
            )

        return adapter.complete(provider_request)
