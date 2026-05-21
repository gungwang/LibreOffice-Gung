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
    ) -> None:
        self.panel = panel
        self.transport = transport or RuntimeSidecarTransportClient()
        self._pending_selection: RuntimeWriterSelection | None = None

    def callHandlerMethod(self, window: object, event_object: object, method_name: str) -> bool:
        del event_object

        if method_name == "Send":
            self._handle_send(window)
            return True

        if method_name == "Approve":
            self._handle_approve(window)
            return True

        return False

    def getSupportedMethodNames(self) -> tuple[str, ...]:
        return ("Send", "Approve")

    def _handle_send(self, window: object) -> None:
        prompt = _get_control_text(window, "PromptInput")
        if not prompt.strip():
            self.panel.append_message("Enter a prompt before sending.")
            return

        try:
            selection = self._capture_writer_selection()
            response = self.transport.request(self._build_chat_request(selection, prompt))
        except (TransportError, ValueError) as exc:
            self.panel.set_connected(False)
            self.panel.append_message(str(exc))
            return

        self.panel.record_request(
            provider=self.panel.state.provider,
            model=self.panel.state.model,
            privacy_scope=self.panel.state.privacy_scope,
            selection_text=selection.text,
        )
        self.panel.set_connected(True)

        response_type = response.get("type")
        if response_type == "DirectAnswer":
            text = response.get("text")
            self._pending_selection = None
            self.panel.clear_pending_proposal()
            self.panel.append_message(
                text if isinstance(text, str) else "Sidecar returned an empty answer."
            )
            return

        if response_type == "ToolProposal":
            proposals = response.get("proposals")
            if (
                not isinstance(proposals, list)
                or not proposals
                or not isinstance(proposals[0], dict)
            ):
                self.panel.append_message("Sidecar returned an invalid tool proposal payload.")
                return

            proposal = _proposal_from_payload(proposals[0])
            preview = proposal.preview
            summary = preview.summary if preview is not None else proposal.tool_id
            self._pending_selection = selection
            self.panel.set_pending_proposal(proposal)
            self.panel.append_message(summary)
            return

        message = response.get("message")
        if isinstance(message, str):
            self.panel.append_message(f"Error: {message}")
            return

        self.panel.append_message(f"Unexpected response type from sidecar: {response_type!r}")

    def _handle_approve(self, window: object) -> None:
        proposal = self.panel.state.pending_proposal
        if proposal is None or self._pending_selection is None:
            self.panel.append_message("No pending Writer proposal is available for approval.")
            return

        try:
            replacement_text = _extract_replacement_text(proposal)
            _apply_writer_replacement(self._pending_selection, replacement_text)
        except ValueError as exc:
            self.panel.append_message(str(exc))
            return

        self.panel.append_message(f"Applied {proposal.tool_id}")
        self.panel.clear_pending_proposal()
        self._pending_selection = None
        _set_control_text(window, "PromptInput", "")

    def _capture_writer_selection(self) -> RuntimeWriterSelection:
        frame = self.panel.frame
        controller = _get_controller(frame)
        model = _get_model(controller)
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
        return RuntimeWriterSelection(
            text=selection_text,
            text_ranges=text_ranges,
            selection_supplier=controller,
        )

    def _build_chat_request(
        self,
        selection: RuntimeWriterSelection,
        prompt: str,
    ) -> dict[str, object]:
        document_url = "file:///writer-document.odt"
        controller = _get_controller(self.panel.frame)
        model = _get_model(controller)
        if model is not None:
            model_url = None
            if hasattr(model, "getURL"):
                model_url = model.getURL()
            elif hasattr(model, "URL"):
                model_url = model.URL
            if isinstance(model_url, str) and model_url:
                document_url = model_url

        return {
            "type": "ChatRequest",
            "requestId": f"sidebar-{uuid4().hex}",
            "app": "writer",
            "document": {
                "canonicalUrl": document_url,
                "profileId": "default-profile",
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
            "historySummary": [],
        }


def _get_controller(frame: object | None) -> object:
    if frame is None:
        raise ValueError("Sidebar is not attached to an active document frame.")

    if hasattr(frame, "getController"):
        controller = frame.getController()
    elif hasattr(frame, "Controller"):
        controller = frame.Controller
    else:
        controller = None

    if controller is None:
        raise ValueError("Could not access the active document controller.")

    return controller


def _get_model(controller: object | None) -> object | None:
    if controller is None:
        return None

    if hasattr(controller, "getModel"):
        return controller.getModel()

    return getattr(controller, "Model", None)


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