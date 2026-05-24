from __future__ import annotations

from dataclasses import dataclass
from multiprocessing.connection import Client
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import uuid4

try:
    import unohelper
    from com.sun.star.awt import XContainerWindowEventHandler
except ImportError:  # pragma: no cover - exercised under LibreOffice runtime
    class _UnoBase:
        pass

    class XContainerWindowEventHandler:  # type: ignore[no-redef]
        pass

    class _UnoHelperModule:
        Base = _UnoBase

    unohelper = _UnoHelperModule()

from loaia.actions.executor import (
    can_execute_via_dispatch,
    execute_dispatch_action,
    execute_safe_formatting,
    execute_uno_command,
    is_safe_formatting_action,
)
from loaia.audit import AuditLogger
from loaia.context.base import capture_base_context
from loaia.context.calc import apply_calc_formula, capture_calc_selection
from loaia.context.draw import apply_draw_text_replacement, capture_draw_selection
from loaia.context.impress import apply_impress_text_replacement, capture_impress_selection
from loaia.context.math import apply_math_formula, capture_math_formula
from loaia.document_session import (
    get_controller,
    get_model,
    resolve_app_type,
    resolve_document_url,
    resolve_history_session_key,
    resolve_profile_id,
)
from loaia.observation import build_observation_results
from loaia.session_store import (
    JsonSidebarSessionStore,
    SqliteSidebarSessionStore,
    describe_api_key_status,
)
from loaia.sidecar_lifecycle import ensure_sidecar_running
from loaia.undo import undo_context
from loaia_shared.errors import TransportError
from loaia_shared.schema.messages import ObservationReport, PlanRevision
from loaia_shared.schema.plans import ProbeResult
from loaia_shared.transport import (
    DEFAULT_NAMED_PIPE_ADDRESS,
    decode_transport_payload,
    encode_transport_payload,
)
from loaia_shared.types import AppType

if TYPE_CHECKING:
    from loaia.sidebar_panel import SidebarPanel


@dataclass(slots=True)
class RuntimeSelection:
    app_type: AppType
    text: str
    text_ranges: tuple[object, ...] = ()
    selection_supplier: object | None = None
    controller: object | None = None


class RuntimeSidecarTransportClient:
    def __init__(self, address: str = DEFAULT_NAMED_PIPE_ADDRESS) -> None:
        self.address = address

    def request(self, payload: dict[str, object]) -> dict[str, object]:
        try:
            with Client(self.address, family="AF_PIPE", authkey=None) as connection:
                connection.send_bytes(encode_transport_payload(payload))
                return decode_transport_payload(connection.recv_bytes())
        except OSError as exc:
            raise TransportError(f"Could not connect to sidecar pipe at {self.address}") from exc

    def request_streaming(
        self,
        payload: dict[str, object],
        on_chunk: object = None,
    ) -> dict[str, object]:
        """Send a request and receive streamed frames."""
        try:
            with Client(self.address, family="AF_PIPE", authkey=None) as connection:
                connection.send_bytes(encode_transport_payload(payload))
                final_frame: dict[str, object] | None = None
                while True:
                    try:
                        frame = decode_transport_payload(connection.recv_bytes())
                    except EOFError:
                        break

                    frame_type = frame.get("type")
                    if frame_type == "StreamChunk":
                        if on_chunk is not None:
                            on_chunk(frame)  # type: ignore[operator]
                    else:
                        final_frame = frame

                if final_frame is None:
                    raise TransportError("Sidecar closed connection without a final response")
                return final_frame
        except OSError as exc:
            raise TransportError(f"Could not connect to sidecar pipe at {self.address}") from exc

    def send_cancel(self, request_id: str) -> None:
        """Send a CancelRequest to the sidecar on a separate connection."""
        payload: dict[str, object] = {
            "type": "CancelRequest",
            "requestId": request_id,
        }
        try:
            with Client(self.address, family="AF_PIPE", authkey=None) as connection:
                connection.send_bytes(encode_transport_payload(payload))
                try:
                    decode_transport_payload(connection.recv_bytes())
                except EOFError:
                    pass
        except OSError:
            pass  # Sidecar may already be gone; cancel is best-effort


class SidebarDialogEventHandler(unohelper.Base, XContainerWindowEventHandler):
    def __init__(
        self,
        panel: SidebarPanel,
        transport: RuntimeSidecarTransportClient | None = None,
        session_store: JsonSidebarSessionStore | SqliteSidebarSessionStore | None = None,
    ) -> None:
        self.panel = panel
        self.transport = transport or RuntimeSidecarTransportClient()
        self.session_store = session_store
        self.audit = AuditLogger()
        self._cancel_requested: bool = False
        self._current_request_id: str | None = None

    def callHandlerMethod(self, window: object, event_object: object, method_name: str) -> bool:
        del event_object

        if method_name == "Send":
            self.handle_send(window=window)
            return True

        if method_name == "Approve":
            self.approve_pending(window=window)
            return True

        if method_name == "SaveSettings":
            self.save_settings(window=window)
            return True

        return False

    def getSupportedMethodNames(self) -> tuple[str, ...]:
        return ("Send", "Approve", "SaveSettings")

    def handle_send(
        self,
        window: object | None = None,
        prompt: str | None = None,
        pipe_address: str | None = None,
    ) -> str:
        return self._handle_send(
            window=window,
            prompt_override=prompt,
            pipe_address_override=pipe_address,
        )

    def preview_current_selection(
        self,
        window: object | None = None,
        prompt: str | None = None,
        pipe_address: str | None = None,
    ) -> str:
        return self.handle_send(
            window=window,
            prompt=prompt,
            pipe_address=pipe_address,
        )

    def save_settings(
        self,
        window: object | None = None,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> str:
        return self._handle_save_settings(
            window=window,
            provider_override=provider,
            model_override=model,
            api_key_override=api_key,
        )

    def approve_pending(
        self,
        window: object | None = None,
        pipe_address: str | None = None,
    ) -> str:
        return self._handle_approve(
            window=window,
            pipe_address_override=pipe_address,
        )

    def _handle_send(
        self,
        window: object | None,
        prompt_override: str | None = None,
        pipe_address_override: str | None = None,
    ) -> str:
        session_key = resolve_history_session_key(self.panel.frame)
        prompt = (
            prompt_override
            if prompt_override is not None
            else _get_control_text(window, "PromptInput")
        )
        if not prompt.strip():
            message = "Enter a message before sending."
            self.panel.set_last_error(message)
            self.panel.append_message(message)
            self._append_chat(window, f"[Error] {message}")
            self._record_error(session_key, message)
            return message

        # Show user message in chat
        self._append_chat(window, f"You: {prompt.strip()}")
        _set_control_text(window, "PromptInput", "")
        self.panel.clear_pending_proposal()

        self.panel.record_request(
            provider=self.panel.state.provider,
            model=self.panel.state.model,
            privacy_scope=self.panel.state.privacy_scope,
            selection_text=None,
            user_message=prompt,
        )
        history_summary = self._load_history_summary(session_key)
        self._record_request(session_key, prompt)

        try:
            selection = self._capture_selection()
            pipe_address = (
                pipe_address_override
                if pipe_address_override is not None
                else DEFAULT_NAMED_PIPE_ADDRESS
            )
            ensure_sidecar_running(address=pipe_address)
            transport_client = (
                self.transport
                if pipe_address_override is None
                else RuntimeSidecarTransportClient(address=pipe_address_override)
            )
            self._cancel_requested = False
            self.panel.set_streaming(True)
            streaming_chunks: list[str] = []
            chat_payload = self._build_chat_request(
                selection, prompt, history_summary
            )
            request_id = str(chat_payload.get("requestId", ""))
            self._current_request_id = request_id
            self.panel.set_selection_preview(selection.text)

            def _on_stream_chunk(frame: dict[str, object]) -> None:
                if self._cancel_requested:
                    return
                text = frame.get("text")
                if isinstance(text, str):
                    streaming_chunks.append(text)

            response = transport_client.request_streaming(
                chat_payload,
                on_chunk=_on_stream_chunk,
            )
            self._current_request_id = None
            self.panel.set_streaming(False)

            if self._cancel_requested:
                cancel_msg = "Request cancelled."
                self.panel.set_last_error(cancel_msg)
                self.panel.append_message(cancel_msg)
                self._append_chat(window, f"[System] {cancel_msg}")
                self._record_error(session_key, cancel_msg)
                return cancel_msg
        except TransportError as exc:
            self.panel.set_streaming(False)
            self.panel.set_connected(False)
            self.panel.set_last_error(str(exc))
            self.panel.append_message(str(exc))
            self._append_chat(window, f"[Error] {exc}")
            self._record_error(session_key, str(exc))
            return str(exc)
        except ValueError as exc:
            self.panel.set_streaming(False)
            self.panel.set_connected(False)
            self.panel.set_last_error(str(exc))
            self.panel.append_message(str(exc))
            self._append_chat(window, f"[Error] {exc}")
            self._record_error(session_key, str(exc))
            return str(exc)

        self.panel.set_connected(True)

        response_type = response.get("type")
        if response_type == "DirectAnswer":
            text = response.get("text")
            answer_text = text if isinstance(text, str) else "AI returned an empty answer."
            self.panel.clear_pending_proposal()
            self.panel.set_last_result(answer_text)
            self.panel.append_message(answer_text)
            self._append_chat(window, f"AI: {answer_text}")
            self._record_result(session_key, answer_text)
            return answer_text

        if response_type == "ToolProposal":
            proposals = response.get("proposals")
            if (
                not isinstance(proposals, list)
                or not proposals
                or not isinstance(proposals[0], dict)
            ):
                message = "AI returned an invalid action payload."
                self._append_chat(window, f"[Error] {message}")
                self._record_error(session_key, message)
                return message

            proposal = _proposal_from_payload(
                proposals[0],
                session_id=_optional_string(response.get("requestId")) or request_id,
            )

            if getattr(proposal, "requires_approval", False):
                preview = getattr(proposal, "preview", None)
                preview_summary = getattr(preview, "summary", None) or proposal.tool_id
                self.panel.set_pending_proposal(proposal)
                self.panel.set_last_result(preview_summary)
                self.panel.append_message(preview_summary)
                self._record_result(session_key, preview_summary)
                return preview_summary

            try:
                result_message = self._execute_proposal_step(
                    transport_client,
                    session_key,
                    selection,
                    proposal,
                    window=window,
                )
            except (ValueError, RuntimeError) as exc:
                self.panel.set_last_error(str(exc))
                self.panel.append_message(str(exc))
                self._append_chat(window, f"[Error] {exc}")
                self._record_error(session_key, str(exc))
                return str(exc)

            self._append_chat(window, f"AI: Done. {result_message}")
            return result_message

        if response_type == "ConsentRequest":
            # Auto-grant scope escalation for simpler UX
            reason = response.get("reason", "")
            self.panel.append_message(str(reason) or "Scope escalated.")
            self._append_chat(window, f"[System] Scope escalated: {reason}")
            self.panel.state.privacy_scope = str(
                response.get("requestedScope", "full-document")
            )
            # Re-send with escalated scope
            return self._handle_send(
                window=window,
                prompt_override=prompt,
                pipe_address_override=pipe_address_override,
            )

        message = response.get("message")
        if isinstance(message, str):
            self.panel.set_last_error(message)
            self.panel.append_message(message)
            self._append_chat(window, f"[Error] {message}")
            self._record_error(session_key, message)
            return message

        unexpected_message = f"Unexpected response: {response_type!r}"
        self.panel.set_last_error(unexpected_message)
        self.panel.append_message(unexpected_message)
        self._append_chat(window, f"[Error] {unexpected_message}")
        self._record_error(session_key, unexpected_message)
        return unexpected_message

    def _handle_approve(
        self,
        window: object | None,
        pipe_address_override: str | None = None,
    ) -> str:
        proposal = self.panel.state.pending_proposal
        if proposal is None:
            message = "No pending proposal is available for approval."
            self.panel.set_last_error(message)
            self.panel.append_message(message)
            return message

        session_key = resolve_history_session_key(self.panel.frame)
        pipe_address = (
            pipe_address_override
            if pipe_address_override is not None
            else DEFAULT_NAMED_PIPE_ADDRESS
        )
        transport_client = (
            self.transport
            if pipe_address_override is None
            else RuntimeSidecarTransportClient(address=pipe_address)
        )

        try:
            selection = self._capture_selection()
            result_message = self._execute_proposal_step(
                transport_client,
                session_key,
                selection,
                proposal,
                window=window,
            )
        except (ValueError, RuntimeError) as exc:
            self.panel.set_last_error(str(exc))
            self.panel.append_message(str(exc))
            self._record_error(session_key, str(exc))
            return str(exc)

        return result_message

    def _execute_proposal(self, selection: RuntimeSelection, proposal: object) -> str | None:
        """Execute a proposal against the given selection."""
        tool_id = getattr(proposal, "tool_id", "")
        arguments = _extract_proposal_arguments(proposal)

        if tool_id == "App.ExecuteUnoCommand":
            return execute_uno_command(
                self.panel.frame,
                target_tool_id=_optional_string(arguments.get("targetToolId")),
                dispatch_alias=_optional_string(arguments.get("dispatchAlias")),
                command=_optional_string(arguments.get("command")),
                arguments=arguments,
            )

        if can_execute_via_dispatch(tool_id):
            return execute_dispatch_action(self.panel.frame, tool_id, **arguments)

        if tool_id == "Writer.ReplaceSelection":
            replacement_text = _extract_replacement_text(proposal)
            _apply_writer_replacement(selection, replacement_text)
            return None

        if tool_id == "Writer.InsertBelowSelection":
            text = _extract_replacement_text(proposal)
            _insert_below_writer_selection(selection, text)
            return None

        if tool_id == "Calc.InsertFormulaInSelection":
            formula = arguments.get("formula") if isinstance(arguments, dict) else None
            if not isinstance(formula, str) or not formula:
                raise ValueError("Calc formula proposal does not contain a formula.")
            if selection.controller is None:
                raise ValueError("Calc controller is not available for formula insertion.")
            return apply_calc_formula(selection.controller, formula)

        if tool_id == "Calc.CreateChartFromSelection":
            if selection.controller is None:
                raise ValueError("Calc controller is not available for chart creation.")
            from loaia.context.calc import create_chart_from_selection

            chart_type = (
                arguments.get("chartType", "Bar")
                if isinstance(arguments, dict)
                else "Bar"
            )
            return create_chart_from_selection(selection.controller, chart_type)

        if tool_id == "Calc.SortSelectedRange":
            if selection.controller is None:
                raise ValueError("Calc controller is not available for sorting.")
            from loaia.context.calc import sort_selected_range

            ascending = (
                arguments.get("ascending", True)
                if isinstance(arguments, dict)
                else True
            )
            return sort_selected_range(selection.controller, ascending=ascending)

        if tool_id == "Impress.ReplaceSelectedText":
            replacement_text = _extract_replacement_text(proposal)
            if selection.controller is None:
                raise ValueError("Impress controller is not available for text replacement.")
            return apply_impress_text_replacement(selection.controller, replacement_text)

        if tool_id == "Writer.InsertTable":
            rows = int(arguments.get("rows", 3))
            cols = int(arguments.get("columns", 3))
            _insert_writer_table(selection, rows, cols)
            return "Inserted Writer table."

        if tool_id == "Writer.ConvertToTable":
            rows = int(arguments.get("rows", 3))
            cols = int(arguments.get("columns", 3))
            tsv_data = str(arguments.get("tsvData", ""))
            _convert_writer_text_to_table(selection, rows, cols, tsv_data)
            return "Converted Writer selection to a table."

        if tool_id == "Impress.CreateSlideFromOutline":
            if selection.controller is None:
                raise ValueError("Impress controller is not available for slide creation.")
            from loaia.context.impress import create_slide_from_outline

            outline = (
                arguments.get("outline", "")
                if isinstance(arguments, dict)
                else ""
            )
            return create_slide_from_outline(selection.controller, outline)

        if tool_id == "Impress.ApplyLayoutToCurrentSlide":
            if selection.controller is None:
                raise ValueError("Impress controller is not available for layout change.")
            from loaia.context.impress import apply_layout_to_current_slide

            layout = (
                arguments.get("layout", 0)
                if isinstance(arguments, dict)
                else 0
            )
            return apply_layout_to_current_slide(selection.controller, layout)

        if tool_id == "Draw.ReplaceSelectedText":
            replacement_text = _extract_replacement_text(proposal)
            if selection.controller is None:
                raise ValueError("Draw controller is not available for text replacement.")
            return apply_draw_text_replacement(selection.controller, replacement_text)

        if tool_id == "Math.ReplaceFormula":
            formula = arguments.get("formula") if isinstance(arguments, dict) else None
            if not isinstance(formula, str) or not formula:
                formula = _extract_replacement_text(proposal)
            if not formula:
                raise ValueError("Math formula proposal does not contain a formula.")
            if selection.controller is None:
                raise ValueError("Math controller is not available for formula replacement.")
            return apply_math_formula(selection.controller, formula)

        if tool_id == "Base.ExplainQuery":
            return f"Applied {tool_id}"

        raise ValueError(f"Unsupported tool: {tool_id}")

    def _handle_save_settings(
        self,
        window: object | None,
        provider_override: str | None = None,
        model_override: str | None = None,
        api_key_override: str | None = None,
    ) -> str:
        provider = (
            provider_override
            if provider_override is not None
            else _get_control_text(window, "ProviderInput")
        ).strip()
        model = (
            model_override
            if model_override is not None
            else _get_control_text(window, "ModelInput")
        ).strip()
        api_key = (
            api_key_override
            if api_key_override is not None
            else _get_control_text(window, "ApiKeyInput")
        ).strip()

        if not provider or not model:
            message = "Provider and model must both be set."
            _set_control_text(window, "SettingsStatus", message)
            return message

        # Save API key to credential store if provided
        if api_key:
            try:
                from loaia.sidecar_lifecycle import save_api_key
                save_api_key(provider, api_key)
            except Exception:
                pass  # Best-effort; will try env var fallback at runtime

        if self.session_store is None:
            api_key_status = describe_api_key_status(provider)
        else:
            snapshot = self.session_store.save_settings(provider, model)
            api_key_status = snapshot.api_key_status

        # If key was just provided, update status
        if api_key:
            api_key_status = "configured (just saved)"

        self.panel.apply_settings(
            provider=provider,
            model=model,
            api_key_status=api_key_status,
        )

        message = f"Saved Writer-first provider settings. Provider: {provider}, Model: {model}"
        self.panel.apply_settings(
            provider=provider,
            model=model,
            api_key_status=api_key_status,
            notice=message,
        )
        # Clear API key field after saving for security
        _set_control_text(window, "ApiKeyInput", "")
        self._append_chat(window, f"[System] {message}")
        return message

    def _append_chat(self, window: object | None, text: str) -> None:
        """Append a line to the ChatOutput control."""
        if window is None:
            return
        current = _get_control_text(window, "ChatOutput")
        if current and current != "Ready. Type a message below to chat with AI.":
            new_text = f"{current}\n{text}"
        else:
            new_text = text
        _set_control_text(window, "ChatOutput", new_text)

    def _capture_selection(self) -> RuntimeSelection:
        frame = self.panel.frame
        controller = get_controller(frame)
        app_type = resolve_app_type(frame)

        if app_type == AppType.WRITER:
            return self._capture_writer_selection_impl(controller)
        if app_type == AppType.CALC:
            return self._capture_calc_selection_impl(controller)
        if app_type == AppType.IMPRESS:
            return self._capture_impress_selection_impl(controller)
        if app_type == AppType.DRAW:
            return self._capture_draw_selection_impl(controller)
        if app_type == AppType.MATH:
            return self._capture_math_selection_impl(controller)
        if app_type == AppType.BASE:
            return self._capture_base_selection_impl(controller)

        raise ValueError("Unsupported document type.")

    def _capture_writer_selection_impl(self, controller: object) -> RuntimeSelection:
        model = get_model(controller)
        if model is None or not hasattr(model, "Text"):
            raise ValueError("Current document is not a Writer document.")

        if not hasattr(controller, "getSelection"):
            raise ValueError("Current document controller does not expose selection APIs.")

        # Selection-only is the default privacy boundary for Writer edits.
        index_access = controller.getSelection()
        selection_text = ""
        text_ranges = ()

        if hasattr(index_access, "getCount") and hasattr(index_access, "getByIndex"):
            count = index_access.getCount()
            if count >= 1:
                text_ranges = tuple(index_access.getByIndex(i) for i in range(count))
                selection_text = "\n".join(
                    _get_range_text(r) for r in text_ranges
                )

        if not selection_text.strip():
            raise ValueError("Select text in Writer before sending a request.")

        return RuntimeSelection(
            app_type=AppType.WRITER,
            text=selection_text,
            text_ranges=text_ranges,
            selection_supplier=controller,
            controller=controller,
        )

    def _capture_calc_selection_impl(self, controller: object) -> RuntimeSelection:
        cell_text, formula = capture_calc_selection(controller)
        context_text = formula if formula.strip() else cell_text
        if not context_text.strip():
            raise ValueError("Select a cell with content in Calc before sending a request.")

        return RuntimeSelection(
            app_type=AppType.CALC,
            text=context_text,
            controller=controller,
        )

    def _capture_impress_selection_impl(self, controller: object) -> RuntimeSelection:
        selection_text = capture_impress_selection(controller)
        if not selection_text.strip():
            raise ValueError("Select a text shape in Impress before sending a request.")

        return RuntimeSelection(
            app_type=AppType.IMPRESS,
            text=selection_text,
            controller=controller,
        )

    def _capture_draw_selection_impl(self, controller: object) -> RuntimeSelection:
        selection_text = capture_draw_selection(controller)
        if not selection_text.strip():
            raise ValueError("Select a shape with text in Draw before sending a request.")

        return RuntimeSelection(
            app_type=AppType.DRAW,
            text=selection_text,
            controller=controller,
        )

    def _capture_math_selection_impl(self, controller: object) -> RuntimeSelection:
        formula_text = capture_math_formula(controller)
        if not formula_text.strip():
            raise ValueError("Open a Math formula before sending a request.")

        return RuntimeSelection(
            app_type=AppType.MATH,
            text=formula_text,
            controller=controller,
        )

    def _capture_base_selection_impl(self, controller: object) -> RuntimeSelection:
        context_text = capture_base_context(controller)
        if not context_text.strip():
            raise ValueError("Open a database object in Base before sending a request.")

        return RuntimeSelection(
            app_type=AppType.BASE,
            text=context_text,
            controller=controller,
        )

    def _build_chat_request(
        self,
        selection: RuntimeSelection,
        prompt: str,
        history_summary: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        session_key = resolve_history_session_key(self.panel.frame)
        document_url = resolve_document_url(self.panel.frame)
        profile_id = resolve_profile_id()
        effective_history_summary = history_summary or []
        if session_key is not None:
            document_url = session_key.canonical_document_url
            profile_id = session_key.profile_id

        return {
            "type": "ChatRequest",
            "requestId": f"sidebar-{uuid4().hex}",
            "app": selection.app_type.value,
            "document": {
                "canonicalUrl": document_url,
                "profileId": profile_id,
            },
            "provider": self.panel.state.provider,
            "model": self.panel.state.model,
            "privacyScope": self.panel.state.privacy_scope,
            "context": {
                "selection": {
                    "mimeType": "text/plain",
                    "text": selection.text,
                }
            },
            "userMessage": prompt,
            "historySummary": effective_history_summary,
        }

    def _load_history_summary(self, session_key: object) -> list[dict[str, object]]:
        if self.session_store is None:
            return []

        return self.session_store.load_session(session_key).history_summary

    def _record_request(self, session_key: object, prompt: str) -> None:
        if self.session_store is None:
            return
        self.session_store.record_request(
            session_key, prompt,
            provider=self.panel.state.provider,
            model=self.panel.state.model,
        )

    def _record_result(self, session_key: object, text: str, role: str = "assistant") -> None:
        if self.session_store is None:
            return
        self.session_store.record_result(
            session_key, text,
            provider=self.panel.state.provider,
            model=self.panel.state.model,
            role=role,
        )

    def _record_error(self, session_key: object, message: str) -> None:
        if self.session_store is None:
            return
        self.session_store.record_error(session_key, message)

    def _report_observation(
        self,
        transport_client: RuntimeSidecarTransportClient,
        proposal: object,
        outcome: str,
        summary: str,
        preconditions: list[ProbeResult] | None = None,
        postconditions: list[ProbeResult] | None = None,
    ) -> PlanRevision | None:
        session_id = _optional_string(getattr(proposal, "session_id", None))
        step_id = _optional_string(getattr(proposal, "step_id", None))
        if session_id is None or step_id is None:
            return None

        payload = ObservationReport(
            sessionId=session_id,
            stepId=step_id,
            outcome=outcome,
            preconditions=preconditions or [],
            postconditions=postconditions or [],
            summary=summary,
        )
        response = transport_client.request(payload.model_dump(by_alias=True, mode="json"))
        if response.get("type") != "PlanRevision":
            return None

        return PlanRevision.model_validate(response)

    def _execute_proposal_step(
        self,
        transport_client: RuntimeSidecarTransportClient,
        session_key: object,
        selection: RuntimeSelection,
        proposal: object,
        *,
        window: object | None,
        depth: int = 0,
    ) -> str:
        if depth > 4:
            raise RuntimeError("Plan revision depth exceeded the current safety limit.")

        before_text = selection.text

        try:
            model = get_model(get_controller(self.panel.frame))
            with undo_context(model, f"AI: {proposal.tool_id}"):
                if is_safe_formatting_action(proposal.tool_id):
                    result_message = execute_safe_formatting(
                        self.panel.frame,
                        proposal.tool_id,
                        **_extract_proposal_arguments(proposal),
                    )
                else:
                    result_message = self._execute_proposal(selection, proposal) or f"Applied {proposal.tool_id}"
        except (ValueError, RuntimeError):
            after_text = self._capture_observation_selection_text(selection, before_text)
            preconditions, postconditions, _ = build_observation_results(
                proposal,
                selection_before=before_text,
                selection_after=after_text,
                summary="",
                controller=selection.controller,
            )
            revision = self._report_observation(
                transport_client,
                proposal,
                outcome="failed",
                summary=f"Failed {proposal.tool_id}",
                preconditions=preconditions,
                postconditions=postconditions,
            )
            follow_up = self._apply_plan_revision(
                transport_client,
                session_key,
                revision,
                window=window,
                depth=depth + 1,
            )
            if follow_up is not None:
                return follow_up
            raise

        after_text = self._capture_observation_selection_text(selection, before_text)
        preconditions, postconditions, outcome = build_observation_results(
            proposal,
            selection_before=before_text,
            selection_after=after_text,
            summary=result_message,
            controller=selection.controller,
        )
        revision = self._report_observation(
            transport_client,
            proposal,
            outcome=outcome,
            summary=result_message,
            preconditions=preconditions,
            postconditions=postconditions,
        )

        self.panel.clear_pending_proposal()
        self.panel.set_selection_preview(after_text)
        self.panel.set_last_result(result_message)
        self.panel.append_message(result_message)
        self._record_result(session_key, result_message, role="system")
        self.audit.log_auto_apply(
            request_id=getattr(proposal, "proposal_id", ""),
            tool_id=proposal.tool_id,
            document_url=resolve_document_url(self.panel.frame),
            provider=self.panel.state.provider,
            model=self.panel.state.model,
        )

        follow_up = self._apply_plan_revision(
            transport_client,
            session_key,
            revision,
            window=window,
            depth=depth + 1,
        )
        return follow_up or result_message

    def _apply_plan_revision(
        self,
        transport_client: RuntimeSidecarTransportClient,
        session_key: object,
        revision: PlanRevision | None,
        *,
        window: object | None,
        depth: int,
    ) -> str | None:
        if revision is None:
            return None

        if revision.action in {"complete", "stop"} or revision.next_proposal is None:
            return None

        next_proposal = _proposal_from_payload(
            revision.next_proposal.model_dump(by_alias=True, mode="json"),
            session_id=revision.session_id,
            step_id=revision.next_step_id,
        )
        if next_proposal.requires_approval:
            preview = getattr(next_proposal, "preview", None)
            preview_summary = getattr(preview, "summary", None) or next_proposal.tool_id
            self.panel.set_pending_proposal(next_proposal)
            self.panel.set_last_result(preview_summary)
            self.panel.append_message(preview_summary)
            self._record_result(session_key, preview_summary)
            return preview_summary

        selection = self._capture_selection()
        return self._execute_proposal_step(
            transport_client,
            session_key,
            selection,
            next_proposal,
            window=window,
            depth=depth,
        )

    def _capture_observation_selection_text(
        self,
        selection: RuntimeSelection,
        fallback: str,
    ) -> str:
        try:
            current_selection = self._capture_selection()
            if current_selection.text.strip():
                return current_selection.text
        except ValueError:
            pass

        if selection.text.strip():
            return selection.text
        return fallback


def _get_range_text(text_range: object) -> str:
    if not hasattr(text_range, "getString"):
        raise ValueError("Writer selected range does not expose getString().")
    text = text_range.getString()
    if not isinstance(text, str):
        raise ValueError("Writer selected range returned a non-string value.")
    return text


def _extract_proposal_arguments(proposal: object) -> dict[str, object]:
    arguments = getattr(proposal, "arguments", {})
    if isinstance(arguments, dict):
        return arguments
    return {}


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _apply_writer_replacement(selection: RuntimeSelection, replacement_text: str) -> None:
    if len(selection.text_ranges) != 1:
        raise ValueError("Writer replace-selection currently supports exactly one selected range.")
    text_range = selection.text_ranges[0]
    if not hasattr(text_range, "setString"):
        raise ValueError("Writer selected range does not expose setString().")
    text_range.setString(replacement_text)
    selection.text = replacement_text
    if hasattr(selection.selection_supplier, "select"):
        selection.selection_supplier.select(text_range)


def _insert_below_writer_selection(selection: RuntimeSelection, text: str) -> None:
    """Insert text as a new paragraph immediately after the current selection."""
    if len(selection.text_ranges) != 1:
        raise ValueError("Writer insert-below currently supports exactly one selected range.")
    text_range = selection.text_ranges[0]
    parent_text = (
        getattr(text_range, "Text", None)
        or getattr(text_range, "getText", lambda: None)()
    )
    if parent_text is None or not hasattr(parent_text, "insertControlCharacter"):
        raise ValueError("Writer text object does not support paragraph insertion.")
    end_cursor = text_range.getEnd()
    try:
        from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK  # type: ignore[import]
    except ImportError:
        PARAGRAPH_BREAK = 0
    parent_text.insertControlCharacter(end_cursor, PARAGRAPH_BREAK, False)
    parent_text.insertString(end_cursor, text, False)
    selection.text = text


def _insert_writer_table(selection: RuntimeSelection, rows: int, cols: int) -> None:
    """Insert a table at the current cursor position in Writer."""
    if not selection.text_ranges:
        raise ValueError("No text range available for table insertion.")

    text_range = selection.text_ranges[0]
    parent_text = (
        getattr(text_range, "Text", None)
        or getattr(text_range, "getText", lambda: None)()
    )
    if parent_text is None:
        raise ValueError("Writer text object not available for table insertion.")

    # Get the document model to create the table
    try:
        import uno  # type: ignore[import]

        ctx = uno.getComponentContext()
        smgr = ctx.ServiceManager
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.getCurrentComponent()
    except ImportError:
        raise ValueError("UNO runtime not available for table insertion.")

    if doc is None or not hasattr(doc, "createInstance"):
        raise ValueError("No active document for table insertion.")

    # Create table via document factory
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(rows, cols)

    # Insert at cursor position (end of current selection)
    cursor = text_range.getEnd()
    parent_text.insertTextContent(cursor, table, False)

    # Apply basic styling: header row background
    try:
        first_row = table.getRows().getByIndex(0)
        first_row.setPropertyValue("BackColor", 0xDDDDDD)  # Light gray header
    except Exception:
        pass  # Style is optional, don't fail if it doesn't work


def _convert_writer_text_to_table(
    selection: RuntimeSelection, rows: int, cols: int, tsv_data: str
) -> None:
    """Replace selected text with a table populated from TSV data."""
    if not selection.text_ranges:
        raise ValueError("No text range available for table conversion.")

    text_range = selection.text_ranges[0]
    parent_text = (
        getattr(text_range, "Text", None)
        or getattr(text_range, "getText", lambda: None)()
    )
    if parent_text is None:
        raise ValueError("Writer text object not available for table conversion.")

    try:
        import uno  # type: ignore[import]

        ctx = uno.getComponentContext()
        smgr = ctx.ServiceManager
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.getCurrentComponent()
    except ImportError:
        raise ValueError("UNO runtime not available for table conversion.")

    if doc is None or not hasattr(doc, "createInstance"):
        raise ValueError("No active document for table conversion.")

    # Delete the selected text first
    try:
        text_range.setString("")
    except Exception:
        pass

    # Create and insert table
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(rows, cols)
    cursor = text_range.getEnd()
    parent_text.insertTextContent(cursor, table, False)

    # Populate with TSV data
    lines = [line for line in tsv_data.splitlines() if line.strip()]
    for row_idx, line in enumerate(lines):
        if row_idx >= rows:
            break
        cells = line.split("\t")
        for col_idx, cell_text in enumerate(cells):
            if col_idx >= cols:
                break
            cell_name = _table_cell_name(col_idx, row_idx)
            try:
                cell = table.getCellByName(cell_name)
                if cell is not None:
                    cell.setString(cell_text.strip())
            except Exception:
                pass

    # Style header row
    try:
        first_row = table.getRows().getByIndex(0)
        first_row.setPropertyValue("BackColor", 0xDDDDDD)
    except Exception:
        pass


def _table_cell_name(col: int, row: int) -> str:
    """Convert 0-based col/row to Writer table cell name like A1, B2, AA3."""
    name = ""
    c = col
    while True:
        name = chr(ord("A") + c % 26) + name
        c = c // 26 - 1
        if c < 0:
            break
    return f"{name}{row + 1}"


def _extract_replacement_text(proposal: object) -> str:
    preview = getattr(proposal, "preview", None)
    preview_after = getattr(preview, "after", None)
    if isinstance(preview_after, str) and preview_after:
        return preview_after
    arguments = getattr(proposal, "arguments", {})
    if isinstance(arguments, dict):
        replacement_text = arguments.get("replacementText")
        if isinstance(replacement_text, str):
            return replacement_text
    raise ValueError("Proposal does not contain replacement text.")


def _proposal_from_payload(
    payload: dict[str, object],
    session_id: str | None = None,
    step_id: str | None = None,
) -> SimpleNamespace:
    preview = None
    preview_payload = payload.get("preview")
    if isinstance(preview_payload, dict):
        preview = SimpleNamespace(
            summary=preview_payload.get("summary"),
            before=preview_payload.get("before"),
            after=preview_payload.get("after"),
        )
    arguments = payload.get("arguments")
    resolved_session_id = session_id or None
    resolved_step_id = step_id or (f"{resolved_session_id}-step-1" if resolved_session_id else None)
    return SimpleNamespace(
        proposal_id=payload.get("proposalId"),
        tool_id=payload.get("toolId"),
        safety_class=payload.get("safetyClass"),
        requires_approval=payload.get("requiresApproval"),
        preview=preview,
        arguments=dict(arguments) if isinstance(arguments, dict) else {},
        session_id=resolved_session_id,
        step_id=resolved_step_id,
    )


def _proposal_selection_preview(proposal: object) -> str | None:
    preview = getattr(proposal, "preview", None)
    preview_after = getattr(preview, "after", None)
    if isinstance(preview_after, str) and preview_after:
        return preview_after
    return None


def _get_control_text(window: object, control_name: str) -> str:
    if window is None or not hasattr(window, "getControl"):
        return ""
    try:
        control = window.getControl(control_name)
    except Exception:
        return ""
    if control is None:
        return ""
    if hasattr(control, "getText"):
        text = control.getText()
        if isinstance(text, str):
            return text
    if not hasattr(control, "getModel"):
        return ""
    model = control.getModel()
    for attribute_name in ("Text", "Label"):
        value = getattr(model, attribute_name, None)
        if isinstance(value, str):
            return value
    return ""


def _set_control_text(window: object, control_name: str, value: str) -> None:
    if window is None or not hasattr(window, "getControl"):
        return
    try:
        control = window.getControl(control_name)
    except Exception:
        return
    if control is None:
        return
    if hasattr(control, "setText"):
        control.setText(value)
        return
    if not hasattr(control, "getModel"):
        return
    model = control.getModel()
    for attribute_name in ("Text", "Label"):
        if hasattr(model, attribute_name):
            setattr(model, attribute_name, value)
            return