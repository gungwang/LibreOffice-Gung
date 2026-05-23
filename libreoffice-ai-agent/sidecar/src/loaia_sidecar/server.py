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
        """Plan a Writer content-edit using intent classification.

        Implements Copilot-like behavior:
        - Questions/summaries → DirectAnswer (return None)
        - Rewrite/edit/translate/tone → ReplaceSelection
        - Draft new content / insert below → InsertBelowSelection
        - Insert table → InsertTable
        - Convert text to table → ConvertToTable
        - Formatting (bold/heading/etc.) → handled by _plan_safe_formatting (called before this)
        """
        normalized = request.user_message.casefold().strip()

        # --- Questions and analysis → DirectAnswer ---
        if (
            normalized.endswith("?")
            or any(normalized.startswith(q) for q in self._QUESTION_STARTERS)
            or any(kw in normalized for kw in self._ANALYSIS_KEYWORDS)
        ):
            return None

        # --- Table insertion (new empty table) ---
        table_insert_keywords = (
            "insert a table", "insert table", "create a table", "create table",
            "add a table", "add table", "make a table",
        )
        if any(kw in normalized for kw in table_insert_keywords):
            return self._plan_writer_insert_table(request)

        # --- Convert text to table (Copilot: "Visualize as Table") ---
        table_convert_keywords = (
            "convert to table", "convert to a table", "make into table",
            "make into a table", "visualize as table", "visualize as a table",
            "turn into table", "turn into a table", "format as table",
            "format as a table", "text to table",
        )
        if any(kw in normalized for kw in table_convert_keywords):
            return self._plan_writer_convert_to_table(request)

        # --- Insert below / draft new content ---
        insert_keywords = (
            "insert below", "add below", "append", "add after",
            "insert after", "write below", "add paragraph",
            "draft", "write a", "write an", "generate",
            "compose", "create a paragraph", "create content",
        )
        if any(kw in normalized for kw in insert_keywords):
            return self._plan_writer_insert_below(request)

        # --- Rewrite / edit / translate / tone (operates on selection) ---
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

        return ToolProposal(
            proposalId=f"{request.request_id}-writer-table",
            toolId="Writer.InsertTable",
            safetyClass=SafetyClass.CONTENT_EDIT,
            requiresApproval=False,
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

        prompt = "\n".join([
            "Convert the following text into a table format.",
            "Output ONLY tab-separated values (TSV). Each line is a row, columns separated by TAB.",
            "First line should be the header row if headers can be inferred.",
            "Do NOT add any explanation, markdown, or formatting. Just TSV data.",
            "",
            "Text to convert:",
            selection.text.strip(),
        ])

        provider_request = ProviderRequest(
            provider=request.provider,
            model=request.model,
            prompt=prompt,
            context_text="",
        )
        tsv_text = adapter.complete(provider_request).strip()
        if not tsv_text:
            return None

        # Parse TSV to determine dimensions
        lines = [line for line in tsv_text.splitlines() if line.strip()]
        if not lines:
            return None
        rows = len(lines)
        cols = max(len(line.split("\t")) for line in lines)
        cols = max(cols, 1)

        return ToolProposal(
            proposalId=f"{request.request_id}-writer-convert-table",
            toolId="Writer.ConvertToTable",
            safetyClass=SafetyClass.CONTENT_EDIT,
            requiresApproval=False,
            preview=ActionPreview(
                summary=f"Convert text to {cols}x{rows} table",
                before=selection.text[:100],
                after=tsv_text[:200],
            ),
            arguments={"rows": rows, "columns": cols, "tsvData": tsv_text},
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
                "You are a document editing assistant. The user wants to MODIFY their selected text.",
                "",
                "RULES:",
                "1. Reply with ONLY the replacement text. No explanations, no JSON, no markdown fences.",
                "2. Return the COMPLETE replacement text that should replace the user's selection.",
                "3. For translation: return the fully translated text.",
                "4. For rewrite/rephrase: return the rewritten version.",
                "5. For tone change (formal, casual, professional): return the adjusted text.",
                "6. For make shorter/longer: return condensed or expanded version.",
                "7. For fix grammar/spelling: return the corrected text.",
                "8. NEVER explain what you did. NEVER add notes. Just output the replacement text.",
                "",
                f"User instruction: {user_message.strip()}",
            ]
        )

    @staticmethod
    def _normalize_writer_rewrite_response(response_text: str) -> str | None:
        """Normalize the LLM response for a rewrite action.

        The prompt asks for raw replacement text, but some models may still
        wrap in markdown fences or quotes. Strip those.
        """
        normalized = response_text.strip()
        if not normalized:
            return None

        # Strip markdown code fences
        if normalized.startswith("```") and normalized.endswith("```"):
            lines = normalized.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            normalized = "\n".join(lines).strip()

        # Legacy sentinel
        if normalized.casefold() == WRITER_NO_REPLACEMENT_SENTINEL.casefold():
            return None

        # Some models still return JSON despite instructions — handle gracefully
        if normalized.startswith("{") and normalized.endswith("}"):
            try:
                payload = json.loads(normalized)
                if isinstance(payload, dict):
                    if payload.get("action") == "no-replacement":
                        return None
                    replacement = payload.get("replacementText")
                    if isinstance(replacement, str) and replacement.strip():
                        return replacement.strip()
            except json.JSONDecodeError:
                pass

        # Strip wrapping quotes
        if (
            len(normalized) >= 2
            and normalized[0] == normalized[-1]
            and normalized[0] in {'"', "'"}
        ):
            inner = normalized[1:-1].strip()
            if inner:
                normalized = inner

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
        # --- Bold ---
        "bold": {
            "writer": "Writer.ToggleBold",
            "calc": "Calc.ToggleBold",
            "impress": "Impress.ToggleBold",
            "draw": "Draw.ToggleBold",
        },
        "make bold": {"writer": "Writer.ToggleBold", "calc": "Calc.ToggleBold"},
        "to bold": {"writer": "Writer.ToggleBold", "calc": "Calc.ToggleBold"},
        # --- Italic ---
        "italic": {
            "writer": "Writer.ToggleItalic",
            "calc": "Calc.ToggleItalic",
            "impress": "Impress.ToggleItalic",
            "draw": "Draw.ToggleItalic",
        },
        "italicize": {"writer": "Writer.ToggleItalic"},
        "make italic": {"writer": "Writer.ToggleItalic"},
        # --- Underline ---
        "underline": {
            "writer": "Writer.ToggleUnderline",
            "draw": "Draw.ToggleUnderline",
        },
        # --- Strikethrough ---
        "strikethrough": {"writer": "Writer.ToggleStrikethrough", "calc": "Calc.ToggleStrikethrough", "impress": "Impress.ToggleStrikethrough", "draw": "Draw.ToggleStrikethrough"},
        "strike through": {"writer": "Writer.ToggleStrikethrough"},
        "strikeout": {"writer": "Writer.ToggleStrikethrough"},
        "cross out": {"writer": "Writer.ToggleStrikethrough"},
        "line through": {"writer": "Writer.ToggleStrikethrough"},
        # --- Superscript / Subscript ---
        "superscript": {"writer": "Writer.ToggleSuperscript"},
        "super script": {"writer": "Writer.ToggleSuperscript"},
        "subscript": {"writer": "Writer.ToggleSubscript"},
        "sub script": {"writer": "Writer.ToggleSubscript"},
        # --- Shadow / Outline / Small Caps ---
        "shadow": {"writer": "Writer.ToggleShadow"},
        "shadow text": {"writer": "Writer.ToggleShadow"},
        "outline font": {"writer": "Writer.ToggleOutline"},
        "outline text": {"writer": "Writer.ToggleOutline"},
        "small caps": {"writer": "Writer.ToggleSmallCaps"},
        "smallcaps": {"writer": "Writer.ToggleSmallCaps"},
        # --- Text case ---
        "uppercase": {"writer": "Writer.CaseUpper"},
        "upper case": {"writer": "Writer.CaseUpper"},
        "all caps": {"writer": "Writer.CaseUpper"},
        "to uppercase": {"writer": "Writer.CaseUpper"},
        "make uppercase": {"writer": "Writer.CaseUpper"},
        "lowercase": {"writer": "Writer.CaseLower"},
        "lower case": {"writer": "Writer.CaseLower"},
        "to lowercase": {"writer": "Writer.CaseLower"},
        "make lowercase": {"writer": "Writer.CaseLower"},
        "title case": {"writer": "Writer.CaseTitle"},
        "titlecase": {"writer": "Writer.CaseTitle"},
        "capitalize": {"writer": "Writer.CaseTitle"},
        "capitalize each word": {"writer": "Writer.CaseTitle"},
        "sentence case": {"writer": "Writer.CaseSentence"},
        "toggle case": {"writer": "Writer.CaseToggle"},
        # --- Headings ---
        "heading 1": {"writer": "Writer.ApplyHeading1"},
        "heading1": {"writer": "Writer.ApplyHeading1"},
        "h1": {"writer": "Writer.ApplyHeading1"},
        "heading 2": {"writer": "Writer.ApplyHeading2"},
        "heading2": {"writer": "Writer.ApplyHeading2"},
        "h2": {"writer": "Writer.ApplyHeading2"},
        "heading 3": {"writer": "Writer.ApplyHeading3"},
        "heading3": {"writer": "Writer.ApplyHeading3"},
        "h3": {"writer": "Writer.ApplyHeading3"},
        "normal style": {"writer": "Writer.ApplyDefaultStyle"},
        "default style": {"writer": "Writer.ApplyDefaultStyle"},
        "remove heading": {"writer": "Writer.ApplyDefaultStyle"},
        "clear heading": {"writer": "Writer.ApplyDefaultStyle"},
        # --- Alignment ---
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
        "text to left": {"writer": "Writer.AlignLeft"},
        "align to left": {"writer": "Writer.AlignLeft"},
        "move to left": {"writer": "Writer.AlignLeft"},
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
        "center align": {"writer": "Writer.AlignCenter"},
        "center text": {"writer": "Writer.AlignCenter"},
        "text to center": {"writer": "Writer.AlignCenter"},
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
        "text to right": {"writer": "Writer.AlignRight"},
        "align to right": {"writer": "Writer.AlignRight"},
        "move to right": {"writer": "Writer.AlignRight"},
        "justify": {"writer": "Writer.AlignJustify"},
        "justify text": {"writer": "Writer.AlignJustify"},
        "full justify": {"writer": "Writer.AlignJustify"},
        "align justify": {"writer": "Writer.AlignJustify"},
        # --- Bullet / Number list ---
        "bullet": {
            "writer": "Writer.ApplyBullets",
            "impress": "Impress.ApplyBullets",
        },
        "bullets": {
            "writer": "Writer.ApplyBullets",
            "impress": "Impress.ApplyBullets",
        },
        "bullet list": {"writer": "Writer.ApplyBullets"},
        "bulleted list": {"writer": "Writer.ApplyBullets"},
        "unordered list": {"writer": "Writer.ApplyBullets"},
        "numbered list": {"writer": "Writer.ApplyNumbering"},
        "number list": {"writer": "Writer.ApplyNumbering"},
        "numbering": {"writer": "Writer.ApplyNumbering"},
        "ordered list": {"writer": "Writer.ApplyNumbering"},
        # --- Indent ---
        "increase indent": {"writer": "Writer.IncreaseIndent"},
        "indent more": {"writer": "Writer.IncreaseIndent"},
        "indent": {"writer": "Writer.IncreaseIndent"},
        "tab in": {"writer": "Writer.IncreaseIndent"},
        "decrease indent": {"writer": "Writer.DecreaseIndent"},
        "indent less": {"writer": "Writer.DecreaseIndent"},
        "outdent": {"writer": "Writer.DecreaseIndent"},
        "tab out": {"writer": "Writer.DecreaseIndent"},
        # --- Line spacing ---
        "single spacing": {"writer": "Writer.LineSpacingSingle"},
        "single space": {"writer": "Writer.LineSpacingSingle"},
        "line spacing 1": {"writer": "Writer.LineSpacingSingle"},
        "1.5 spacing": {"writer": "Writer.LineSpacing1_5"},
        "one and a half spacing": {"writer": "Writer.LineSpacing1_5"},
        "line spacing 1.5": {"writer": "Writer.LineSpacing1_5"},
        "double spacing": {"writer": "Writer.LineSpacingDouble"},
        "double space": {"writer": "Writer.LineSpacingDouble"},
        "line spacing 2": {"writer": "Writer.LineSpacingDouble"},
        # --- Font size ---
        "increase font": {"writer": "Writer.IncreaseFontSize"},
        "increase font size": {"writer": "Writer.IncreaseFontSize"},
        "bigger font": {"writer": "Writer.IncreaseFontSize"},
        "larger font": {"writer": "Writer.IncreaseFontSize"},
        "make bigger": {"writer": "Writer.IncreaseFontSize"},
        "font bigger": {"writer": "Writer.IncreaseFontSize"},
        "decrease font": {"writer": "Writer.DecreaseFontSize"},
        "decrease font size": {"writer": "Writer.DecreaseFontSize"},
        "smaller font": {"writer": "Writer.DecreaseFontSize"},
        "make smaller": {"writer": "Writer.DecreaseFontSize"},
        "font smaller": {"writer": "Writer.DecreaseFontSize"},
        # --- Font color ---
        "red color": {"writer": "Writer.FontColorRed"},
        "color red": {"writer": "Writer.FontColorRed"},
        "font red": {"writer": "Writer.FontColorRed"},
        "red font": {"writer": "Writer.FontColorRed"},
        "text red": {"writer": "Writer.FontColorRed"},
        "red text": {"writer": "Writer.FontColorRed"},
        "make red": {"writer": "Writer.FontColorRed"},
        "change to red": {"writer": "Writer.FontColorRed"},
        "color to red": {"writer": "Writer.FontColorRed"},
        "font color red": {"writer": "Writer.FontColorRed"},
        "blue color": {"writer": "Writer.FontColorBlue"},
        "color blue": {"writer": "Writer.FontColorBlue"},
        "font blue": {"writer": "Writer.FontColorBlue"},
        "blue font": {"writer": "Writer.FontColorBlue"},
        "text blue": {"writer": "Writer.FontColorBlue"},
        "blue text": {"writer": "Writer.FontColorBlue"},
        "make blue": {"writer": "Writer.FontColorBlue"},
        "change to blue": {"writer": "Writer.FontColorBlue"},
        "color to blue": {"writer": "Writer.FontColorBlue"},
        "font color blue": {"writer": "Writer.FontColorBlue"},
        "green color": {"writer": "Writer.FontColorGreen"},
        "color green": {"writer": "Writer.FontColorGreen"},
        "font green": {"writer": "Writer.FontColorGreen"},
        "green font": {"writer": "Writer.FontColorGreen"},
        "text green": {"writer": "Writer.FontColorGreen"},
        "green text": {"writer": "Writer.FontColorGreen"},
        "make green": {"writer": "Writer.FontColorGreen"},
        "change to green": {"writer": "Writer.FontColorGreen"},
        "font color green": {"writer": "Writer.FontColorGreen"},
        "black color": {"writer": "Writer.FontColorBlack"},
        "color black": {"writer": "Writer.FontColorBlack"},
        "font black": {"writer": "Writer.FontColorBlack"},
        "black font": {"writer": "Writer.FontColorBlack"},
        "make black": {"writer": "Writer.FontColorBlack"},
        "font color black": {"writer": "Writer.FontColorBlack"},
        "white color": {"writer": "Writer.FontColorWhite"},
        "color white": {"writer": "Writer.FontColorWhite"},
        "font white": {"writer": "Writer.FontColorWhite"},
        "white font": {"writer": "Writer.FontColorWhite"},
        "make white": {"writer": "Writer.FontColorWhite"},
        "font color white": {"writer": "Writer.FontColorWhite"},
        "orange color": {"writer": "Writer.FontColorOrange"},
        "color orange": {"writer": "Writer.FontColorOrange"},
        "font orange": {"writer": "Writer.FontColorOrange"},
        "orange font": {"writer": "Writer.FontColorOrange"},
        "make orange": {"writer": "Writer.FontColorOrange"},
        "font color orange": {"writer": "Writer.FontColorOrange"},
        "purple color": {"writer": "Writer.FontColorPurple"},
        "color purple": {"writer": "Writer.FontColorPurple"},
        "font purple": {"writer": "Writer.FontColorPurple"},
        "purple font": {"writer": "Writer.FontColorPurple"},
        "make purple": {"writer": "Writer.FontColorPurple"},
        "font color purple": {"writer": "Writer.FontColorPurple"},
        "yellow color": {"writer": "Writer.FontColorYellow"},
        "color yellow": {"writer": "Writer.FontColorYellow"},
        "font yellow": {"writer": "Writer.FontColorYellow"},
        "yellow font": {"writer": "Writer.FontColorYellow"},
        "make yellow": {"writer": "Writer.FontColorYellow"},
        "font color yellow": {"writer": "Writer.FontColorYellow"},
        # --- Highlight / background color ---
        "highlight yellow": {"writer": "Writer.HighlightYellow"},
        "yellow highlight": {"writer": "Writer.HighlightYellow"},
        "highlight green": {"writer": "Writer.HighlightGreen"},
        "green highlight": {"writer": "Writer.HighlightGreen"},
        "highlight red": {"writer": "Writer.HighlightRed"},
        "red highlight": {"writer": "Writer.HighlightRed"},
        "highlight blue": {"writer": "Writer.HighlightBlue"},
        "blue highlight": {"writer": "Writer.HighlightBlue"},
        "remove highlight": {"writer": "Writer.HighlightNone"},
        "clear highlight": {"writer": "Writer.HighlightNone"},
        "no highlight": {"writer": "Writer.HighlightNone"},
        # --- Clear formatting ---
        "clear formatting": {"writer": "Writer.ClearFormatting", "impress": "Impress.ClearFormatting", "draw": "Draw.ClearFormatting"},
        "remove formatting": {"writer": "Writer.ClearFormatting", "impress": "Impress.ClearFormatting", "draw": "Draw.ClearFormatting"},
        "clear format": {"writer": "Writer.ClearFormatting"},
        "reset formatting": {"writer": "Writer.ClearFormatting"},
        "plain text": {"writer": "Writer.ClearFormatting"},
        # --- Paragraph spacing ---
        "increase paragraph spacing": {"writer": "Writer.IncreaseParaSpacing"},
        "increase para spacing": {"writer": "Writer.IncreaseParaSpacing"},
        "more paragraph space": {"writer": "Writer.IncreaseParaSpacing"},
        "decrease paragraph spacing": {"writer": "Writer.DecreaseParaSpacing"},
        "decrease para spacing": {"writer": "Writer.DecreaseParaSpacing"},
        "less paragraph space": {"writer": "Writer.DecreaseParaSpacing"},
        # --- Insert operations (Writer) ---
        "insert page break": {"writer": "Writer.InsertPageBreak"},
        "page break": {"writer": "Writer.InsertPageBreak"},
        "new page": {"writer": "Writer.InsertPageBreak"},
        "insert column break": {"writer": "Writer.InsertColumnBreak"},
        "column break": {"writer": "Writer.InsertColumnBreak"},
        "insert special character": {"writer": "Writer.InsertSpecialChar"},
        "special character": {"writer": "Writer.InsertSpecialChar"},
        "insert symbol": {"writer": "Writer.InsertSpecialChar"},
        "insert hyperlink": {"writer": "Writer.InsertHyperlink"},
        "hyperlink": {"writer": "Writer.InsertHyperlink"},
        "add link": {"writer": "Writer.InsertHyperlink"},
        "insert link": {"writer": "Writer.InsertHyperlink"},
        "insert comment": {"writer": "Writer.InsertComment", "calc": "Calc.InsertComment", "impress": "Impress.InsertComment"},
        "add comment": {"writer": "Writer.InsertComment", "calc": "Calc.InsertComment"},
        "insert image": {"writer": "Writer.InsertImage", "calc": "Calc.InsertImage", "impress": "Impress.InsertImage", "draw": "Draw.InsertImage"},
        "insert picture": {"writer": "Writer.InsertImage", "calc": "Calc.InsertImage", "impress": "Impress.InsertImage"},
        "add image": {"writer": "Writer.InsertImage", "calc": "Calc.InsertImage"},
        "insert photo": {"writer": "Writer.InsertImage"},
        "insert bookmark": {"writer": "Writer.InsertBookmark"},
        "add bookmark": {"writer": "Writer.InsertBookmark"},
        "insert footnote": {"writer": "Writer.InsertFootnote"},
        "add footnote": {"writer": "Writer.InsertFootnote"},
        "insert endnote": {"writer": "Writer.InsertEndnote"},
        "add endnote": {"writer": "Writer.InsertEndnote"},
        "insert header": {"writer": "Writer.InsertHeader"},
        "add header": {"writer": "Writer.InsertHeader"},
        "insert footer": {"writer": "Writer.InsertFooter"},
        "add footer": {"writer": "Writer.InsertFooter"},
        "insert page number": {"writer": "Writer.InsertPageNumber"},
        "page number": {"writer": "Writer.InsertPageNumber"},
        "insert date": {"writer": "Writer.InsertDateField"},
        "insert date field": {"writer": "Writer.InsertDateField"},
        "insert time": {"writer": "Writer.InsertTimeField"},
        "insert time field": {"writer": "Writer.InsertTimeField"},
        # --- Edit / Utility ---
        "format paintbrush": {"writer": "Writer.FormatPaintbrush"},
        "clone formatting": {"writer": "Writer.FormatPaintbrush"},
        "copy formatting": {"writer": "Writer.FormatPaintbrush"},
        "select all": {"writer": "Writer.SelectAll"},
        "undo": {"writer": "Writer.Undo"},
        "redo": {"writer": "Writer.Redo"},
        "find and replace": {"writer": "Writer.FindReplace"},
        "search and replace": {"writer": "Writer.FindReplace"},
        "word count": {"writer": "Writer.WordCount"},
        "spell check": {"writer": "Writer.SpellCheck"},
        "check spelling": {"writer": "Writer.SpellCheck"},
        # --- Calc number formats ---
        "currency": {"calc": "Calc.ApplyNumberFormatCurrency"},
        "currency format": {"calc": "Calc.ApplyNumberFormatCurrency"},
        "percent": {"calc": "Calc.ApplyNumberFormatPercent"},
        "percent format": {"calc": "Calc.ApplyNumberFormatPercent"},
        "date format": {"calc": "Calc.ApplyNumberFormatDate"},
        "number format": {"calc": "Calc.ApplyNumberFormatDecimal"},
        "scientific format": {"calc": "Calc.ApplyNumberFormatScientific"},
        "increase decimals": {"calc": "Calc.IncreaseDecimals"},
        "add decimal": {"calc": "Calc.IncreaseDecimals"},
        "more decimals": {"calc": "Calc.IncreaseDecimals"},
        "decrease decimals": {"calc": "Calc.DecreaseDecimals"},
        "less decimals": {"calc": "Calc.DecreaseDecimals"},
        "fewer decimals": {"calc": "Calc.DecreaseDecimals"},
        # --- Calc cells/rows ---
        "merge cells": {"calc": "Calc.MergeCells"},
        "merge": {"calc": "Calc.MergeCells"},
        "insert row above": {"calc": "Calc.InsertRowAbove"},
        "insert row below": {"calc": "Calc.InsertRowBelow"},
        "add row": {"calc": "Calc.InsertRowBelow"},
        "insert column before": {"calc": "Calc.InsertColumnBefore"},
        "insert column after": {"calc": "Calc.InsertColumnAfter"},
        "add column": {"calc": "Calc.InsertColumnAfter"},
        "delete row": {"calc": "Calc.DeleteRows"},
        "delete rows": {"calc": "Calc.DeleteRows"},
        "delete column": {"calc": "Calc.DeleteColumns"},
        "delete columns": {"calc": "Calc.DeleteColumns"},
        "wrap text": {"calc": "Calc.WrapText"},
        "text wrap": {"calc": "Calc.WrapText"},
        # --- Calc sort/filter ---
        "sort ascending": {"calc": "Calc.SortAscending"},
        "sort a to z": {"calc": "Calc.SortAscending"},
        "sort descending": {"calc": "Calc.SortDescending"},
        "sort z to a": {"calc": "Calc.SortDescending"},
        "autofilter": {"calc": "Calc.AutoFilter"},
        "auto filter": {"calc": "Calc.AutoFilter"},
        "filter": {"calc": "Calc.AutoFilter"},
        # --- Calc other ---
        "freeze panes": {"calc": "Calc.FreezePanes"},
        "freeze": {"calc": "Calc.FreezePanes"},
        "autosum": {"calc": "Calc.AutoSum"},
        "auto sum": {"calc": "Calc.AutoSum"},
        "sum": {"calc": "Calc.AutoSum"},
        "insert chart": {"calc": "Calc.InsertChart", "impress": "Impress.InsertChart"},
        # --- Impress slides ---
        "new slide": {"impress": "Impress.InsertSlide"},
        "insert slide": {"impress": "Impress.InsertSlide"},
        "add slide": {"impress": "Impress.InsertSlide"},
        "duplicate slide": {"impress": "Impress.DuplicateSlide"},
        "delete slide": {"impress": "Impress.DeleteSlide"},
        "remove slide": {"impress": "Impress.DeleteSlide"},
        "start presentation": {"impress": "Impress.StartPresentation"},
        "play presentation": {"impress": "Impress.StartPresentation"},
        "start slideshow": {"impress": "Impress.StartPresentation"},
        "start from current": {"impress": "Impress.StartFromCurrent"},
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
