import json
import threading

from pydantic import ValidationError as PydanticValidationError

from loaia_shared.capabilities.compiler import get_capability_descriptor, get_descriptor_hash
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
from loaia_shared.schema.plans import ExecutionPlan, ObservationReport, PlanRevision, PlanStep
from loaia_shared.types import AppType, PrivacyScope
from loaia_sidecar.planner.evaluator import evaluate_observation
from loaia_sidecar.planner.retriever import CapabilityRetriever
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
            "execution-plans",
            "observation-reports",
            "replanning",
            "consent-escalation",
            "cancellation",
        ]
        self.capability_retriever = CapabilityRetriever()
        self._plan_sessions: dict[str, ExecutionPlan] = {}
        self._cancelled_requests: set[str] = set()
        self._cancel_lock = threading.Lock()

    def handshake(self) -> HandshakeResponse:
        return HandshakeResponse(
            serverVersion="0.1.9",
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

        if message_type == "ObservationReport":
            try:
                report = ObservationReport.model_validate(payload)
            except PydanticValidationError as exc:
                return ErrorResponse(requestId=request_id, message=str(exc)).model_dump(
                    by_alias=True,
                    mode="json",
                )

            response = self._handle_observation_report(report)
            return response.model_dump(by_alias=True, mode="json")

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

        if message_type == "ObservationReport":
            try:
                report = ObservationReport.model_validate(payload)
            except PydanticValidationError as exc:
                return ErrorResponse(requestId=request_id, message=str(exc)).model_dump(
                    by_alias=True, mode="json"
                )

            response = self._handle_observation_report(report)
            return response.model_dump(by_alias=True, mode="json")

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

        return self._proposal_from_capability(
            request,
            "Writer.InsertBelowSelection",
            preview=ActionPreview(
                summary="Insert text below current selection",
                before="",
                after=text,
            ),
            arguments={"replacementText": text},
        )

    def _plan_writer_insert_table(self, request: ChatRequest) -> ToolProposal:
        """Plan a Writer.InsertTable action by parsing rows/columns from user message."""
        import re

        normalized = request.user_message.casefold()
        # Try to extract dimensions like "3x5", "3 x 5", "3 by 5", "3 columns 5 rows", etc.
        # Pattern: NxM or N by M
        match = re.search(r"(\d+)\s*[x×by]\s*(\d+)", normalized)
        if match:
            num1, num2 = int(match.group(1)), int(match.group(2))
            # Heuristic: if user says "3x5", interpret as 3 columns x 5 rows
            cols, rows = num1, num2
        else:
            # Try "N rows" and "M columns" separately
            row_match = re.search(r"(\d+)\s*rows?", normalized)
            col_match = re.search(r"(\d+)\s*col(?:umn)?s?", normalized)
            rows = int(row_match.group(1)) if row_match else 3
            cols = int(col_match.group(1)) if col_match else 3

        # Clamp to reasonable limits
        rows = max(1, min(rows, 50))
        cols = max(1, min(cols, 20))

        return self._proposal_from_capability(
            request,
            "Writer.InsertTable",
            preview=ActionPreview(
                summary=f"Insert {cols}x{rows} table",
                before="",
                after=f"[Table: {cols} columns × {rows} rows]",
            ),
            arguments={"rows": rows, "columns": cols},
        )

    def _plan_writer_convert_to_table(self, request: ChatRequest) -> ToolProposal | None:
        """Convert selected text into a table (Copilot: 'Visualize as Table').

        Sends the selection to the LLM to parse into rows/columns, then inserts
        a table with that data.
        """
        selection = request.context.selection
        if selection is None or not selection.text.strip():
            return None

        adapter = self.provider_adapters.get(request.provider)
        if adapter is None:
            return None

        prompt = "\n".join(
            [
                "You are a LibreOffice Writer table assistant.",
                "Convert the selected text into a tab-separated table.",
                "Reply with ONLY TSV content using tabs between columns and newlines between rows.",
                "Do not add markdown fences, explanations, or commentary.",
                "If the selection cannot be converted into a meaningful table, reply with: NO_TABLE",
                f"User request: {request.user_message.strip()}",
            ]
        )
        provider_request = ProviderRequest(
            provider=request.provider,
            model=request.model,
            prompt=prompt,
            context_text=selection.text,
        )
        tsv_data = adapter.complete(provider_request).strip()
        if not tsv_data or tsv_data.casefold() == "no_table":
            return None

        rows = [row for row in tsv_data.splitlines() if row.strip()]
        if not rows:
            return None

        columns = max(len(row.split("\t")) for row in rows)
        return self._proposal_from_capability(
            request,
            "Writer.ConvertToTable",
            preview=ActionPreview(
                summary="Convert selected text into a table",
                before=selection.text,
                after=f"[Table: {columns} columns x {len(rows)} rows]",
            ),
            arguments={
                "tsvData": tsv_data,
                "rows": len(rows),
                "columns": columns,
            },
        )

    def _build_impress_replace_proposal(self, request: ChatRequest) -> ToolProposal | None:
        selection = request.context.selection
        if selection is None or not selection.text.strip():
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
        replacement = adapter.complete(provider_request).strip()
        if not replacement or replacement == selection.text:
            return None

        return self._proposal_from_capability(
            request,
            "Impress.ReplaceSelectedText",
            preview=ActionPreview(
                summary="Replace selected Impress text",
                before=selection.text,
                after=replacement,
            ),
            arguments={"replacementText": replacement},
        )

    def _build_draw_replace_proposal(self, request: ChatRequest) -> ToolProposal | None:
        selection = request.context.selection
        if selection is None or not selection.text.strip():
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
        replacement = adapter.complete(provider_request).strip()
        if not replacement or replacement == selection.text:
            return None

        return self._proposal_from_capability(
            request,
            "Draw.ReplaceSelectedText",
            preview=ActionPreview(
                summary="Replace selected Draw text",
                before=selection.text,
                after=replacement,
            ),
            arguments={"replacementText": replacement},
        )

    def _build_math_replace_proposal(self, request: ChatRequest) -> ToolProposal | None:
        selection = request.context.selection
        if selection is None or not selection.text.strip():
            return None

        adapter = self.provider_adapters.get(request.provider)
        if adapter is None:
            return None

        provider_request = ProviderRequest(
            provider=request.provider,
            model=request.model,
            prompt=self._build_math_rewrite_prompt(request.user_message),
            context_text=selection.text,
        )
        formula = adapter.complete(provider_request).strip()
        if not formula or formula == selection.text:
            return None

        return self._proposal_from_capability(
            request,
            "Math.ReplaceFormula",
            preview=ActionPreview(
                summary="Replace Math formula",
                before=selection.text,
                after=formula,
            ),
            arguments={"formula": formula},
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
        return user_message.strip()

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

    def _should_use_direct_answer(self, request: ChatRequest) -> bool:
        normalized = request.user_message.casefold().strip()
        if not normalized:
            return True

        return (
            normalized.endswith("?")
            or any(normalized.startswith(q) for q in self._QUESTION_STARTERS)
            or any(keyword in normalized for keyword in self._ANALYSIS_KEYWORDS)
            or normalized.startswith(("explain ", "summarize", "summarise", "describe "))
        )

    def _plan_tool_proposal(self, request: ChatRequest) -> ToolProposal | None:
        if self._should_use_direct_answer(request):
            return None

        normalized = request.user_message.casefold()
        writer_rewrite_intent = request.app == AppType.WRITER and any(
            keyword in normalized
            for keyword in (
                "rewrite",
                "rephrase",
                "formal",
                "grammar",
                "simplify",
                "shorten",
                "uppercase",
                "lowercase",
                "title case",
                "sentence case",
                "fix",
                "improve",
            )
        )

        specialized = self._build_specialized_proposal(request)
        if specialized is not None:
            self._plan_sessions[request.request_id] = self._build_execution_plan(request, specialized)
            return specialized
        if writer_rewrite_intent:
            return None

        candidates = self.capability_retriever.search(
            app=request.app,
            query=request.user_message,
            limit=8,
        )
        for candidate in candidates:
            tool_id = candidate.descriptor.tool_id
            if tool_id == "App.ExecuteUnoCommand":
                continue

            proposal = self._compose_candidate_proposal(request, tool_id)
            if proposal is None:
                if tool_id == "Writer.ReplaceSelection":
                    return None
                continue

            self._plan_sessions[request.request_id] = self._build_execution_plan(request, proposal)
            return proposal

        return None

    def _build_specialized_proposal(self, request: ChatRequest) -> ToolProposal | None:
        normalized = request.user_message.casefold()

        if request.app == AppType.WRITER:
            if any(
                keyword in normalized
                for keyword in (
                    "convert to table",
                    "convert this text to a table",
                    "visualize this as a table",
                )
            ):
                return self._plan_writer_convert_to_table(request)
            if any(
                keyword in normalized
                for keyword in (
                    "insert a table",
                    "insert table",
                    "create a table",
                    "add a table",
                )
            ):
                return self._plan_writer_insert_table(request)
            if any(
                keyword in normalized
                for keyword in (
                    "insert below",
                    "add below",
                    "append",
                    "draft",
                    "write below",
                )
            ):
                return self._plan_writer_insert_below(request)
            if any(
                keyword in normalized
                for keyword in (
                    "rewrite",
                    "rephrase",
                    "formal",
                    "grammar",
                    "simplify",
                    "shorten",
                    "uppercase",
                    "lowercase",
                    "title case",
                    "sentence case",
                    "fix",
                    "improve",
                )
            ):
                return self._build_writer_replace_proposal(request)

        if request.app == AppType.CALC:
            if any(keyword in normalized for keyword in ("sort", "order", "arrange")):
                return self._build_calc_sort_proposal(request)
            if any(keyword in normalized for keyword in ("chart", "graph", "plot", "visualize", "visualization")):
                return self._build_calc_chart_proposal(request)
            if any(keyword in normalized for keyword in ("formula", "insert formula", "calculate", "sum", "average", "count")):
                return self._build_calc_formula_proposal(request)

        if request.app == AppType.IMPRESS:
            if any(keyword in normalized for keyword in ("new slide", "create slide", "add slide", "insert slide")):
                return self._build_impress_create_slide_proposal(request)
            if any(keyword in normalized for keyword in ("layout", "apply layout", "change layout", "slide layout")):
                return self._build_impress_layout_proposal(request)

        return None

    def _compose_candidate_proposal(
        self,
        request: ChatRequest,
        tool_id: str,
    ) -> ToolProposal | None:
        if tool_id == "Writer.ReplaceSelection":
            return self._build_writer_replace_proposal(request)
        if tool_id == "Writer.InsertBelowSelection":
            return self._plan_writer_insert_below(request)
        if tool_id == "Writer.InsertTable":
            return self._plan_writer_insert_table(request)
        if tool_id == "Writer.ConvertToTable":
            return self._plan_writer_convert_to_table(request)
        if tool_id == "Calc.InsertFormulaInSelection":
            return self._build_calc_formula_proposal(request)
        if tool_id == "Calc.CreateChartFromSelection":
            return self._build_calc_chart_proposal(request)
        if tool_id == "Calc.SortSelectedRange":
            return self._build_calc_sort_proposal(request)
        if tool_id == "Impress.ReplaceSelectedText":
            return self._build_impress_replace_proposal(request)
        if tool_id == "Impress.CreateSlideFromOutline":
            return self._build_impress_create_slide_proposal(request)
        if tool_id == "Impress.ApplyLayoutToCurrentSlide":
            return self._build_impress_layout_proposal(request)
        if tool_id == "Draw.ReplaceSelectedText":
            return self._build_draw_replace_proposal(request)
        if tool_id == "Math.ReplaceFormula":
            return self._build_math_replace_proposal(request)

        descriptor = get_capability_descriptor(tool_id)
        if descriptor is None:
            return None

        if descriptor.safety_class == SafetyClass.SAFE_FORMATTING:
            return self._proposal_from_capability(request, tool_id)

        if descriptor.binding.kind == "uno-dispatch":
            return self._proposal_from_capability(request, tool_id, wrap_dispatch=True)

        return self._proposal_from_capability(request, tool_id)

    def _build_writer_replace_proposal(self, request: ChatRequest) -> ToolProposal | None:
        selection = request.context.selection
        if selection is None or not selection.text.strip():
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
        replacement = self._normalize_writer_rewrite_response(adapter.complete(provider_request))
        if replacement is None or replacement == selection.text:
            return None

        return self._proposal_from_capability(
            request,
            "Writer.ReplaceSelection",
            preview=ActionPreview(
                summary="Preview Writer selection replacement",
                before=selection.text,
                after=replacement,
            ),
            arguments={"replacementText": replacement},
        )

    def _build_calc_formula_proposal(self, request: ChatRequest) -> ToolProposal | None:
        selection = request.context.selection
        if selection is None or not selection.text.strip():
            return None

        adapter = self.provider_adapters.get(request.provider)
        if adapter is None:
            return None

        provider_request = ProviderRequest(
            provider=request.provider,
            model=request.model,
            prompt=self._build_calc_formula_prompt(request.user_message),
            context_text=selection.text,
        )
        formula = self._normalize_calc_formula_response(adapter.complete(provider_request))
        if formula is None:
            return None

        return self._proposal_from_capability(
            request,
            "Calc.InsertFormulaInSelection",
            preview=ActionPreview(
                summary=f"Insert formula: {formula}",
                before=selection.text,
                after=formula,
            ),
            arguments={"formula": formula},
        )

    def _build_calc_chart_proposal(self, request: ChatRequest) -> ToolProposal | None:
        normalized = request.user_message.casefold()
        chart_type = "Bar"
        for candidate in ("pie", "line", "scatter", "area", "column", "bar"):
            if candidate in normalized:
                chart_type = candidate.capitalize()
                break

        return self._proposal_from_capability(
            request,
            "Calc.CreateChartFromSelection",
            preview=ActionPreview(
                summary=f"Create {chart_type} chart from selection",
                before="",
                after=f"[{chart_type} chart]",
            ),
            arguments={"chartType": chart_type},
        )

    def _build_calc_sort_proposal(self, request: ChatRequest) -> ToolProposal | None:
        ascending = "descend" not in request.user_message.casefold()
        direction = "ascending" if ascending else "descending"
        return self._proposal_from_capability(
            request,
            "Calc.SortSelectedRange",
            preview=ActionPreview(
                summary=f"Sort selected range ({direction})",
                before="",
                after=f"[sorted {direction}]",
            ),
            arguments={"ascending": ascending},
        )

    def _build_impress_create_slide_proposal(self, request: ChatRequest) -> ToolProposal | None:
        adapter = self.provider_adapters.get(request.provider)
        outline = request.user_message.strip()
        if adapter is not None:
            provider_request = ProviderRequest(
                provider=request.provider,
                model=request.model,
                prompt=self._build_impress_outline_prompt(request.user_message),
                context_text=request.context.selection.text if request.context.selection else "",
            )
            outline = adapter.complete(provider_request).strip() or outline

        return self._proposal_from_capability(
            request,
            "Impress.CreateSlideFromOutline",
            preview=ActionPreview(
                summary="Create new slide from outline",
                before="",
                after=outline,
            ),
            arguments={"outline": outline},
        )

    def _build_impress_layout_proposal(self, request: ChatRequest) -> ToolProposal | None:
        normalized = request.user_message.casefold()
        layout = 0
        layout_map = {"blank": 0, "title": 1, "content": 1, "two column": 3}
        for name, value in layout_map.items():
            if name in normalized:
                layout = value
                break

        return self._proposal_from_capability(
            request,
            "Impress.ApplyLayoutToCurrentSlide",
            preview=ActionPreview(
                summary=f"Apply layout {layout} to current slide",
                before="",
                after=f"[layout {layout}]",
            ),
            arguments={"layout": layout},
        )

    def _proposal_from_capability(
        self,
        request: ChatRequest,
        capability_id: str,
        *,
        preview: ActionPreview | None = None,
        arguments: dict[str, object] | None = None,
        wrap_dispatch: bool = False,
    ) -> ToolProposal:
        descriptor = get_capability_descriptor(capability_id)
        if descriptor is None:
            raise ValueError(f"Unknown capability: {capability_id}")

        proposal_tool_id = capability_id
        proposal_arguments = dict(arguments or {})
        if wrap_dispatch:
            proposal_tool_id = "App.ExecuteUnoCommand"
            proposal_arguments = {"targetToolId": capability_id, **proposal_arguments}

        return ToolProposal(
            proposalId=f"{request.request_id}-{capability_id.casefold().replace('.', '-').replace('_', '-')}",
            toolId=proposal_tool_id,
            safetyClass=descriptor.safety_class,
            requiresApproval=descriptor.requires_approval,
            preview=preview
            or ActionPreview(
                summary=f"Apply {capability_id}",
                before="",
                after="",
            ),
            arguments=proposal_arguments,
        )

    def _build_execution_plan(self, request: ChatRequest, proposal: ToolProposal) -> ExecutionPlan:
        descriptor_hash = get_descriptor_hash(proposal.tool_id) or ""
        approval_mode = "explicit" if proposal.requires_approval else "auto"
        return ExecutionPlan(
            sessionId=request.request_id,
            goal=request.user_message,
            steps=[
                PlanStep(
                    stepId=f"{request.request_id}-step-1",
                    capabilityId=proposal.tool_id,
                    descriptorHash=descriptor_hash,
                    arguments=proposal.arguments,
                    targetScope=str(request.privacy_scope),
                    approvalMode=approval_mode,
                    onFailure="replan",
                )
            ],
        )

    def _handle_observation_report(self, report: ObservationReport) -> PlanRevision:
        plan = self._plan_sessions.get(report.session_id)
        if plan is None:
            return PlanRevision(
                sessionId=report.session_id,
                action="stop",
                reason="No matching execution plan was found for this session.",
            )

        decision = evaluate_observation(plan, report)
        if decision.action == "complete":
            self._plan_sessions.pop(report.session_id, None)

        return PlanRevision(
            sessionId=report.session_id,
            action=decision.action,
            reason=decision.reason,
            nextStepId=decision.next_step_id,
        )

    @staticmethod
    def _build_writer_insert_below_prompt(user_message: str) -> str:
        return "\n".join(
            [
                "You are a LibreOffice Writer drafting assistant.",
                "Write text that should be inserted below the current selection.",
                "Reply with ONLY the inserted text. No markdown fences or commentary.",
                f"User request: {user_message.strip()}",
            ]
        )

    @staticmethod
    def _build_writer_rewrite_prompt(user_message: str) -> str:
        return "\n".join(
            [
                "You are a LibreOffice Writer rewrite assistant.",
                "Rewrite the selected text according to the user request.",
                "Reply with ONLY valid JSON.",
                'If a rewrite is appropriate, reply with: {"action":"replace-selection","replacementText":"<full replacement text>"}',
                'If no rewrite is needed, reply with: {"action":"no-replacement"}',
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

        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError:
            return normalized or None

        if not isinstance(payload, dict):
            return None

        action = str(payload.get("action", "")).casefold()
        if action == "no-replacement":
            return None
        replacement = payload.get("replacementText")
        if action == "replace-selection" and isinstance(replacement, str) and replacement:
            return replacement
        return None
