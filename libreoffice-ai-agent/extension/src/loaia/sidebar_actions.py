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

from loaia.actions.executor import execute_safe_formatting, is_safe_formatting_action
from loaia.document_session import (
    DEFAULT_PROFILE_ID,
    get_controller,
    get_model,
    resolve_document_url,
    resolve_history_session_key,
)
from loaia.session_store import JsonSidebarSessionStore, describe_api_key_status
from loaia_shared.errors import TransportError
from loaia_shared.transport import (
    DEFAULT_NAMED_PIPE_ADDRESS,
    decode_transport_payload,
    encode_transport_payload,
)

if TYPE_CHECKING:
    from loaia.sidebar_panel import SidebarPanel


@dataclass(slots=True)
class RuntimeWriterSelection:
    text: str
    text_ranges: tuple[object, ...]
    selection_supplier: object


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


class SidebarDialogEventHandler(unohelper.Base, XContainerWindowEventHandler):
    def __init__(
        self,
        panel: SidebarPanel,
        transport: RuntimeSidecarTransportClient | None = None,
        session_store: JsonSidebarSessionStore | None = None,
    ) -> None:
        self.panel = panel
        self.transport = transport or RuntimeSidecarTransportClient()
        self.session_store = session_store
        self._pending_selection: RuntimeWriterSelection | None = None

    def callHandlerMethod(self, window: object, event_object: object, method_name: str) -> bool:
        del event_object

        if method_name == "Send":
            self.preview_current_selection(window=window)
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

    def preview_current_selection(
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

    def approve_pending(self, window: object | None = None) -> str:
        return self._handle_approve(window=window)

    def save_settings(
        self,
        window: object | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> str:
        return self._handle_save_settings(
            window=window,
            provider_override=provider,
            model_override=model,
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
            message = "Enter a prompt before sending."
            self.panel.set_last_error(message)
            self.panel.append_message(message)
            self._record_error(session_key, message)
            return message

        if prompt_override is not None:
            _set_control_text(window, "PromptInput", prompt)

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
            selection = self._capture_writer_selection()
            self.panel.set_selection_preview(selection.text)
            transport_client = (
                self.transport
                if pipe_address_override is None
                else RuntimeSidecarTransportClient(address=pipe_address_override)
            )
            response = transport_client.request(
                self._build_chat_request(selection, prompt, history_summary)
            )
        except TransportError as exc:
            self.panel.set_connected(False)
            self.panel.set_last_error(str(exc))
            self.panel.append_message(str(exc))
            self._record_error(session_key, str(exc))
            return str(exc)
        except ValueError as exc:
            self.panel.set_last_error(str(exc))
            self.panel.append_message(str(exc))
            self._record_error(session_key, str(exc))
            return str(exc)

        self.panel.set_connected(True)

        response_type = response.get("type")
        if response_type == "DirectAnswer":
            text = response.get("text")
            answer_text = text if isinstance(text, str) else "Sidecar returned an empty answer."
            self._pending_selection = None
            self.panel.clear_pending_proposal()
            self.panel.set_last_result(answer_text)
            self.panel.append_message(answer_text)
            self._record_result(session_key, answer_text)
            return answer_text

        if response_type == "ToolProposal":
            proposals = response.get("proposals")
            if (
                not isinstance(proposals, list)
                or not proposals
                or not isinstance(proposals[0], dict)
            ):
                message = "Sidecar returned an invalid tool proposal payload."
                self.panel.set_last_error(message)
                self.panel.append_message(message)
                self._record_error(session_key, message)
                return message

            proposal = _proposal_from_payload(proposals[0])

            # Auto-apply safe formatting actions without preview/approval.
            if is_safe_formatting_action(proposal.tool_id):
                try:
                    result_message = execute_safe_formatting(
                        self.panel.frame, proposal.tool_id
                    )
                except (ValueError, RuntimeError) as exc:
                    self.panel.set_last_error(str(exc))
                    self.panel.append_message(str(exc))
                    self._record_error(session_key, str(exc))
                    return str(exc)

                self._pending_selection = None
                self.panel.clear_pending_proposal()
                self.panel.set_last_result(result_message)
                self.panel.append_message(result_message)
                self._record_result(session_key, result_message, role="system")
                return result_message

            preview = proposal.preview
            summary = preview.summary if preview is not None else proposal.tool_id
            self._pending_selection = selection
            self.panel.set_pending_proposal(proposal)
            self.panel.set_last_result(summary)
            self.panel.append_message(summary)
            self._record_result(session_key, summary)
            return summary

        message = response.get("message")
        if isinstance(message, str):
            self.panel.set_last_error(message)
            self.panel.append_message(f"Error: {message}")
            self._record_error(session_key, message)
            return message

        unexpected_message = f"Unexpected response type from sidecar: {response_type!r}"
        self.panel.set_last_error(unexpected_message)
        self.panel.append_message(unexpected_message)
        self._record_error(session_key, unexpected_message)
        return unexpected_message

    def _handle_approve(self, window: object | None) -> str:
        session_key = resolve_history_session_key(self.panel.frame)
        proposal = self.panel.state.pending_proposal
        if proposal is None or self._pending_selection is None:
            message = "No pending Writer proposal is available for approval."
            self.panel.set_last_error(message)
            self.panel.append_message(message)
            self._record_error(session_key, message)
            return message

        try:
            replacement_text = _extract_replacement_text(proposal)
            _apply_writer_replacement(self._pending_selection, replacement_text)
        except ValueError as exc:
            self.panel.set_last_error(str(exc))
            self.panel.append_message(str(exc))
            self._record_error(session_key, str(exc))
            return str(exc)

        applied_message = f"Applied {proposal.tool_id}"
        self.panel.set_selection_preview(replacement_text)
        self.panel.set_last_result(applied_message)
        self.panel.append_message(applied_message)
        self._record_result(session_key, applied_message, role="system")
        self.panel.clear_pending_proposal()
        self._pending_selection = None
        _set_control_text(window, "PromptInput", "")
        return applied_message

    def _handle_save_settings(
        self,
        window: object | None,
        provider_override: str | None = None,
        model_override: str | None = None,
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
        if not provider or not model:
            message = "Provider and model must both be set before saving settings."
            self.panel.apply_settings(
                provider=self.panel.state.provider,
                model=self.panel.state.model,
                api_key_status=self.panel.state.api_key_status,
                notice=message,
            )
            return message

        if self.session_store is None:
            api_key_status = describe_api_key_status(provider)
        else:
            snapshot = self.session_store.save_settings(provider, model)
            api_key_status = snapshot.api_key_status

        message = "Saved Writer-first provider settings."
        if provider_override is not None:
            _set_control_text(window, "ProviderInput", provider)
        if model_override is not None:
            _set_control_text(window, "ModelInput", model)
        self.panel.apply_settings(
            provider=provider,
            model=model,
            api_key_status=api_key_status,
            notice=message,
        )
        return message

    def _capture_writer_selection(self) -> RuntimeWriterSelection:
        frame = self.panel.frame
        controller = get_controller(frame)
        model = get_model(controller)
        if model is None or not hasattr(model, "Text"):
            raise ValueError("Sidebar actions currently support Writer documents only.")

        if not hasattr(controller, "getSelection"):
            raise ValueError("Current document controller does not expose selection APIs.")

        index_access = controller.getSelection()
        if not hasattr(index_access, "getCount") or not hasattr(index_access, "getByIndex"):
            raise ValueError("Current Writer selection is not accessible.")

        count = index_access.getCount()
        if count < 1:
            raise ValueError("Select text in Writer before sending a request.")

        text_ranges = tuple(index_access.getByIndex(index) for index in range(count))
        selection_text = "\n".join(_get_range_text(text_range) for text_range in text_ranges)
        if not selection_text.strip():
            raise ValueError("Select text in Writer before sending a request.")

        return RuntimeWriterSelection(
            text=selection_text,
            text_ranges=text_ranges,
            selection_supplier=controller,
        )

    def _build_chat_request(
        self,
        selection: RuntimeWriterSelection,
        prompt: str,
        history_summary: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        session_key = resolve_history_session_key(self.panel.frame)
        document_url = resolve_document_url(self.panel.frame)
        profile_id = DEFAULT_PROFILE_ID
        effective_history_summary = history_summary or []
        if session_key is not None:
            document_url = session_key.canonical_document_url
            profile_id = session_key.profile_id

        return {
            "type": "ChatRequest",
            "requestId": f"sidebar-{uuid4().hex}",
            "app": "writer",
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

    def _record_request(
        self,
        session_key: object,
        prompt: str,
    ) -> None:
        if self.session_store is None:
            return

        self.session_store.record_request(
            session_key,
            prompt,
            provider=self.panel.state.provider,
            model=self.panel.state.model,
        )

    def _record_result(
        self,
        session_key: object,
        text: str,
        role: str = "assistant",
    ) -> None:
        if self.session_store is None:
            return

        self.session_store.record_result(
            session_key,
            text,
            provider=self.panel.state.provider,
            model=self.panel.state.model,
            role=role,
        )

    def _record_error(self, session_key: object, message: str) -> None:
        if self.session_store is None:
            return

        self.session_store.record_error(session_key, message)


def _get_range_text(text_range: object) -> str:
    if not hasattr(text_range, "getString"):
        raise ValueError("Writer selected range does not expose getString().")

    text = text_range.getString()
    if not isinstance(text, str):
        raise ValueError("Writer selected range returned a non-string value.")

    return text


def _apply_writer_replacement(selection: RuntimeWriterSelection, replacement_text: str) -> None:
    if len(selection.text_ranges) != 1:
        raise ValueError("Writer replace-selection currently supports exactly one selected range.")

    text_range = selection.text_ranges[0]
    if not hasattr(text_range, "setString"):
        raise ValueError("Writer selected range does not expose setString().")

    text_range.setString(replacement_text)
    selection.text = replacement_text

    if hasattr(selection.selection_supplier, "select"):
        selection.selection_supplier.select(text_range)


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

    raise ValueError("Writer replacement proposal does not contain replacement text.")


def _proposal_from_payload(payload: dict[str, object]) -> SimpleNamespace:
    preview = None
    preview_payload = payload.get("preview")
    if isinstance(preview_payload, dict):
        preview = SimpleNamespace(
            summary=preview_payload.get("summary"),
            before=preview_payload.get("before"),
            after=preview_payload.get("after"),
        )

    arguments = payload.get("arguments")
    return SimpleNamespace(
        proposal_id=payload.get("proposalId"),
        tool_id=payload.get("toolId"),
        safety_class=payload.get("safetyClass"),
        requires_approval=payload.get("requiresApproval"),
        preview=preview,
        arguments=dict(arguments) if isinstance(arguments, dict) else {},
    )


def _get_control_text(window: object, control_name: str) -> str:
    if window is None or not hasattr(window, "getControl"):
        return ""

    control = window.getControl(control_name)
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

    control = window.getControl(control_name)
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