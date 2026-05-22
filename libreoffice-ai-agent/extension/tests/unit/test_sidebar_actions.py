from types import SimpleNamespace
from unittest.mock import patch

from loaia.bootstrap import SIDEBAR_RESOURCE_URL
from loaia.document_session import DocumentSessionKey
from loaia.session_store import InMemorySidebarSessionStore
from loaia.sidebar_actions import SidebarDialogEventHandler
from loaia.sidebar_panel import SidebarPanel, SidebarToolPanel
from loaia_shared.defaults import get_default_provider
from loaia_shared.errors import TransportError
from loaia_shared.types import AppType


class FakeWriterTextRange:
    def __init__(self, text: str) -> None:
        self.text = text

    def getString(self) -> str:
        return self.text

    def setString(self, text: str) -> None:
        self.text = text


class FakeSelectionAccess:
    def __init__(self, *ranges: FakeWriterTextRange) -> None:
        self.ranges = ranges

    def getCount(self) -> int:
        return len(self.ranges)

    def getByIndex(self, index: int) -> FakeWriterTextRange:
        return self.ranges[index]


class FakeWriterController:
    def __init__(self, text_range: FakeWriterTextRange) -> None:
        self.model = SimpleNamespace(Text=True, URL="file:///test-writer-document.odt")
        self.selection = FakeSelectionAccess(text_range)
        self.last_selected_range: FakeWriterTextRange | None = None

    def getModel(self) -> object:
        return self.model

    def getSelection(self) -> FakeSelectionAccess:
        return self.selection

    def select(self, text_range: FakeWriterTextRange) -> None:
        self.last_selected_range = text_range


class FakeWriterControllerWithoutSelectionApi:
    def __init__(self) -> None:
        self.model = SimpleNamespace(Text=True, URL="file:///test-writer-document.odt")

    def getModel(self) -> object:
        return self.model


class FakeCalcController:
    def __init__(self) -> None:
        self.model = SimpleNamespace(URL="file:///test-calc-document.ods")

    def getModel(self) -> object:
        return self.model


class FakeFrame:
    def __init__(self, controller: object) -> None:
        self.controller = controller

    def getController(self) -> object:
        return self.controller


class FakeModel:
    def __init__(self, attribute_name: str, value: str = "") -> None:
        setattr(self, attribute_name, value)
        self.Enabled = True


class FakeControl:
    def __init__(self, attribute_name: str, value: str = "") -> None:
        self.model = FakeModel(attribute_name, value)

    def getModel(self) -> FakeModel:
        return self.model

    def getText(self) -> str:
        return getattr(self.model, "Text", "")

    def setText(self, value: str) -> None:
        if hasattr(self.model, "Text"):
            self.model.Text = value


class FakeWindow:
    def __init__(self, prompt: str) -> None:
        self.controls = {
            "Title": FakeControl("Label"),
            "Status": FakeControl("Label"),
            "ProviderInput": FakeControl("Text", get_default_provider()),
            "ModelInput": FakeControl("Text", "openai/gpt-4.1-mini"),
            "SaveSettingsButton": FakeControl("Label"),
            "SettingsStatus": FakeControl("Label"),
            "PromptInput": FakeControl("Text", prompt),
            "SendButton": FakeControl("Label"),
            "CancelButton": FakeControl("Label"),
            "ApproveButton": FakeControl("Label"),
            "Summary": FakeControl("Text"),
            "Privacy": FakeControl("Label"),
        }

    def getControl(self, name: str) -> FakeControl:
        return self.controls[name]


class FakeTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []
        self.cancelled_ids: list[str] = []

    def request(self, payload: dict[str, object]) -> dict[str, object]:
        self.requests.append(payload)
        return self.response

    def request_streaming(
        self, payload: dict[str, object], on_chunk: object = None
    ) -> dict[str, object]:
        self.requests.append(payload)
        return self.response

    def send_cancel(self, request_id: str) -> None:
        self.cancelled_ids.append(request_id)


class FailingTransport:
    def __init__(self, message: str) -> None:
        self.message = message
        self.requests: list[dict[str, object]] = []

    def request(self, payload: dict[str, object]) -> dict[str, object]:
        self.requests.append(payload)
        raise TransportError(self.message)

    def request_streaming(
        self, payload: dict[str, object], on_chunk: object = None
    ) -> dict[str, object]:
        self.requests.append(payload)
        raise TransportError(self.message)

    def send_cancel(self, request_id: str) -> None:
        pass


def test_sidebar_send_action_previews_writer_proposal() -> None:
    panel = SidebarPanel(title="LibreOffice AI Agent", resource_url=SIDEBAR_RESOURCE_URL)
    text_range = FakeWriterTextRange("hello world")
    panel.attach_frame(FakeFrame(FakeWriterController(text_range)))
    window = FakeWindow(prompt="Please convert this selection to uppercase.")
    transport = FakeTransport(
        {
            "type": "ToolProposal",
            "proposals": [
                {
                    "proposalId": "proposal-1",
                    "toolId": "Writer.ReplaceSelection",
                    "safetyClass": "content-edit",
                    "requiresApproval": True,
                    "preview": {
                        "summary": "Preview Writer selection replacement",
                        "before": "hello world",
                        "after": "HELLO WORLD",
                    },
                    "arguments": {"replacementText": "HELLO WORLD"},
                }
            ],
        }
    )
    tool_panel = SidebarToolPanel(
        panel=panel,
        window=window,
        event_handler=SidebarDialogEventHandler(panel=panel, transport=transport),
    )

    assert window.controls["ApproveButton"].model.Enabled is False

    assert tool_panel.event_handler.callHandlerMethod(window, None, "Send") is True

    assert transport.requests[0]["type"] == "ChatRequest"
    assert transport.requests[0]["userMessage"] == "Please convert this selection to uppercase."
    assert transport.requests[0]["context"] == {
        "selection": {"mimeType": "text/plain", "text": "hello world"}
    }
    assert panel.state.connected is True
    assert panel.state.last_prompt == "Please convert this selection to uppercase."
    assert panel.state.last_result == "Preview Writer selection replacement"
    assert panel.state.last_error is None
    assert panel.state.selection_preview == "hello world"
    assert panel.state.pending_proposal is not None
    assert panel.state.pending_proposal.preview.after == "HELLO WORLD"
    expected_prompt = "Prompt:\nPlease convert this selection to uppercase."
    expected_result = "Last result:\nPreview Writer selection replacement"
    assert f"Provider: {get_default_provider()}" in window.controls["Status"].model.Label
    assert expected_prompt in window.controls["Summary"].model.Text
    assert (
        "Pending preview:\nPreview Writer selection replacement"
        in window.controls["Summary"].model.Text
    )
    assert expected_result in window.controls["Summary"].model.Text
    assert window.controls["ApproveButton"].model.Enabled is True


def test_sidebar_approve_action_applies_pending_writer_change() -> None:
    panel = SidebarPanel(title="LibreOffice AI Agent", resource_url=SIDEBAR_RESOURCE_URL)
    text_range = FakeWriterTextRange("hello world")
    controller = FakeWriterController(text_range)
    panel.attach_frame(FakeFrame(controller))
    window = FakeWindow(prompt="Please convert this selection to uppercase.")
    transport = FakeTransport(
        {
            "type": "ToolProposal",
            "proposals": [
                {
                    "proposalId": "proposal-1",
                    "toolId": "Writer.ReplaceSelection",
                    "safetyClass": "content-edit",
                    "requiresApproval": True,
                    "preview": {
                        "summary": "Preview Writer selection replacement",
                        "before": "hello world",
                        "after": "HELLO WORLD",
                    },
                    "arguments": {"replacementText": "HELLO WORLD"},
                }
            ],
        }
    )
    tool_panel = SidebarToolPanel(
        panel=panel,
        window=window,
        event_handler=SidebarDialogEventHandler(panel=panel, transport=transport),
    )

    tool_panel.event_handler.callHandlerMethod(window, None, "Send")
    assert tool_panel.event_handler.callHandlerMethod(window, None, "Approve") is True

    assert text_range.text == "HELLO WORLD"
    assert controller.last_selected_range is text_range
    assert panel.state.pending_proposal is None
    assert panel.state.selection_preview == "HELLO WORLD"
    assert panel.state.last_result == "Applied Writer.ReplaceSelection"
    assert window.controls["PromptInput"].model.Text == ""
    assert window.controls["ApproveButton"].model.Enabled is False
    assert "Last result:\nApplied Writer.ReplaceSelection" in window.controls["Summary"].model.Text
    expected_activity = "\n".join(
        [
            "Recent activity:",
            "- Preview Writer selection replacement",
            "- Applied Writer.ReplaceSelection",
        ]
    )
    assert (
        expected_activity
        in window.controls["Summary"].model.Text
    )


def test_sidebar_send_action_surfaces_transport_errors_clearly() -> None:
    panel = SidebarPanel(title="LibreOffice AI Agent", resource_url=SIDEBAR_RESOURCE_URL)
    text_range = FakeWriterTextRange("hello world")
    panel.attach_frame(FakeFrame(FakeWriterController(text_range)))
    window = FakeWindow(prompt="Please convert this selection to uppercase.")
    transport = FailingTransport("Could not connect to sidecar pipe at \\\\.\\pipe\\loaia-sidecar")
    tool_panel = SidebarToolPanel(
        panel=panel,
        window=window,
        event_handler=SidebarDialogEventHandler(panel=panel, transport=transport),
    )

    assert tool_panel.event_handler.callHandlerMethod(window, None, "Send") is True

    expected_error = "Could not connect to sidecar pipe at \\\\.\\pipe\\loaia-sidecar"
    expected_status_error = f"Last error: {expected_error}"

    assert transport.requests[0]["type"] == "ChatRequest"
    assert panel.state.connected is False
    assert panel.state.last_prompt == "Please convert this selection to uppercase."
    assert panel.state.last_error == expected_error
    assert panel.state.last_result is None
    assert panel.state.pending_proposal is None
    assert expected_status_error in window.controls["Status"].model.Label
    assert (
        "Prompt:\nPlease convert this selection to uppercase."
        in window.controls["Summary"].model.Text
    )
    assert "Last result:\nNo completed result yet." in window.controls["Summary"].model.Text
    assert window.controls["ApproveButton"].model.Enabled is False


def test_sidebar_send_action_surfaces_empty_selection_error_clearly() -> None:
    panel = SidebarPanel(title="LibreOffice AI Agent", resource_url=SIDEBAR_RESOURCE_URL)
    text_range = FakeWriterTextRange("")
    panel.attach_frame(FakeFrame(FakeWriterController(text_range)))
    window = FakeWindow(prompt="Please convert this selection to uppercase.")
    transport = FakeTransport(
        {
            "type": "ToolProposal",
            "proposals": [],
        }
    )
    tool_panel = SidebarToolPanel(
        panel=panel,
        window=window,
        event_handler=SidebarDialogEventHandler(panel=panel, transport=transport),
    )

    assert tool_panel.event_handler.callHandlerMethod(window, None, "Send") is True

    expected_error = "Select text in Writer before sending a request."
    expected_status_error = f"Last error: {expected_error}"

    assert transport.requests == []
    assert panel.state.connected is False
    assert panel.state.last_prompt == "Please convert this selection to uppercase."
    assert panel.state.last_error == expected_error
    assert panel.state.selection_preview is None
    assert panel.state.last_result is None
    assert panel.state.pending_proposal is None
    assert expected_status_error in window.controls["Status"].model.Label
    assert (
        "Prompt:\nPlease convert this selection to uppercase."
        in window.controls["Summary"].model.Text
    )
    assert "Selection:\nNo captured selection yet." in window.controls["Summary"].model.Text
    assert "Pending preview:\nNo pending proposal." in window.controls["Summary"].model.Text
    assert "Last result:\nNo completed result yet." in window.controls["Summary"].model.Text
    assert (
        "Recent activity:\n- Select text in Writer before sending a request."
        in window.controls["Summary"].model.Text
    )
    assert window.controls["ApproveButton"].model.Enabled is False


def test_sidebar_send_action_surfaces_non_writer_error_clearly() -> None:
    panel = SidebarPanel(title="LibreOffice AI Agent", resource_url=SIDEBAR_RESOURCE_URL)
    panel.attach_frame(FakeFrame(FakeCalcController()))
    window = FakeWindow(prompt="Please convert this selection to uppercase.")
    transport = FakeTransport(
        {
            "type": "ToolProposal",
            "proposals": [],
        }
    )
    tool_panel = SidebarToolPanel(
        panel=panel,
        window=window,
        event_handler=SidebarDialogEventHandler(panel=panel, transport=transport),
    )

    assert tool_panel.event_handler.callHandlerMethod(window, None, "Send") is True

    expected_error = "Select a cell with content in Calc before sending a request."
    expected_status_error = f"Last error: {expected_error}"

    assert transport.requests == []
    assert panel.state.connected is False
    assert panel.state.last_prompt == "Please convert this selection to uppercase."
    assert panel.state.last_error == expected_error
    assert panel.state.selection_preview is None
    assert panel.state.last_result is None
    assert panel.state.pending_proposal is None
    assert expected_status_error in window.controls["Status"].model.Label
    assert (
        "Prompt:\nPlease convert this selection to uppercase."
        in window.controls["Summary"].model.Text
    )
    assert "Selection:\nNo captured selection yet." in window.controls["Summary"].model.Text
    assert "Pending preview:\nNo pending proposal." in window.controls["Summary"].model.Text
    assert "Last result:\nNo completed result yet." in window.controls["Summary"].model.Text
    assert (
        "Recent activity:\n- Select a cell with content in Calc before sending a request."
        in window.controls["Summary"].model.Text
    )
    assert window.controls["ApproveButton"].model.Enabled is False


def test_sidebar_send_action_surfaces_missing_selection_api_error_clearly() -> None:
    panel = SidebarPanel(title="LibreOffice AI Agent", resource_url=SIDEBAR_RESOURCE_URL)
    panel.attach_frame(FakeFrame(FakeWriterControllerWithoutSelectionApi()))
    window = FakeWindow(prompt="Please convert this selection to uppercase.")
    transport = FakeTransport(
        {
            "type": "ToolProposal",
            "proposals": [],
        }
    )
    tool_panel = SidebarToolPanel(
        panel=panel,
        window=window,
        event_handler=SidebarDialogEventHandler(panel=panel, transport=transport),
    )

    assert tool_panel.event_handler.callHandlerMethod(window, None, "Send") is True

    expected_error = "Current document controller does not expose selection APIs."
    expected_status_error = f"Last error: {expected_error}"

    assert transport.requests == []
    assert panel.state.connected is False
    assert panel.state.last_prompt == "Please convert this selection to uppercase."
    assert panel.state.last_error == expected_error
    assert panel.state.selection_preview is None
    assert panel.state.last_result is None
    assert panel.state.pending_proposal is None
    assert expected_status_error in window.controls["Status"].model.Label
    assert (
        "Prompt:\nPlease convert this selection to uppercase."
        in window.controls["Summary"].model.Text
    )
    assert "Selection:\nNo captured selection yet." in window.controls["Summary"].model.Text
    assert "Pending preview:\nNo pending proposal." in window.controls["Summary"].model.Text
    assert "Last result:\nNo completed result yet." in window.controls["Summary"].model.Text
    assert (
        "Recent activity:\n- Current document controller does not expose selection APIs."
        in window.controls["Summary"].model.Text
    )
    assert window.controls["ApproveButton"].model.Enabled is False


def test_sidebar_send_action_can_override_pipe_address_for_runtime_probe() -> None:
    panel = SidebarPanel(title="LibreOffice AI Agent", resource_url=SIDEBAR_RESOURCE_URL)
    text_range = FakeWriterTextRange("hello world")
    panel.attach_frame(FakeFrame(FakeWriterController(text_range)))
    window = FakeWindow(prompt="Please convert this selection to uppercase.")
    default_transport = FailingTransport("default transport should not be used")
    override_transport = FakeTransport(
        {
            "type": "DirectAnswer",
            "text": (
                "Sidecar scaffold is running. Planner and provider execution are "
                "not implemented yet."
            ),
        }
    )
    handler = SidebarDialogEventHandler(panel=panel, transport=default_transport)

    with patch(
        "loaia.sidebar_actions.RuntimeSidecarTransportClient",
        return_value=override_transport,
    ) as transport_client:
        result = handler.preview_current_selection(
            window=window,
            prompt="Please summarize this selection.",
            pipe_address=r"\\.\pipe\loaia-sidecar-missing-test",
        )

    assert result == (
        "Sidecar scaffold is running. Planner and provider execution are not "
        "implemented yet."
    )
    assert default_transport.requests == []
    assert transport_client.call_args.kwargs == {
        "address": r"\\.\pipe\loaia-sidecar-missing-test"
    }
    assert override_transport.requests[0]["type"] == "ChatRequest"
    assert override_transport.requests[0]["userMessage"] == "Please summarize this selection."


def test_sidebar_save_settings_persists_provider_and_model() -> None:
    store = InMemorySidebarSessionStore()
    panel = SidebarPanel(title="LibreOffice AI Agent", resource_url=SIDEBAR_RESOURCE_URL)
    window = FakeWindow(prompt="Please convert this selection to uppercase.")
    tool_panel = SidebarToolPanel(
        panel=panel,
        window=window,
        event_handler=SidebarDialogEventHandler(panel=panel, session_store=store),
    )
    window.controls["ProviderInput"].model.Text = "openrouter"
    window.controls["ModelInput"].model.Text = "openai/gpt-4.1"

    assert tool_panel.event_handler.callHandlerMethod(window, None, "SaveSettings") is True

    settings = store.load_settings()
    assert settings.provider == "openrouter"
    assert settings.model == "openai/gpt-4.1"
    assert panel.state.provider == "openrouter"
    assert panel.state.model == "openai/gpt-4.1"
    assert "Saved Writer-first provider settings." in window.controls["SettingsStatus"].model.Label


def test_sidebar_send_action_uses_only_prior_history_in_request_summary() -> None:
    store = InMemorySidebarSessionStore()
    session_key = DocumentSessionKey(
        profile_id="default-profile",
        canonical_document_url="file:///test-writer-document.odt",
        app_type=AppType.WRITER,
    )
    store.record_request(
        session_key,
        "Earlier prompt",
        provider=get_default_provider(),
        model="openai/gpt-4.1-mini",
    )
    store.record_result(
        session_key,
        "Earlier answer",
        provider=get_default_provider(),
        model="openai/gpt-4.1-mini",
    )
    panel = SidebarPanel(title="LibreOffice AI Agent", resource_url=SIDEBAR_RESOURCE_URL)
    text_range = FakeWriterTextRange("hello world")
    panel.attach_frame(FakeFrame(FakeWriterController(text_range)))
    panel.apply_settings(
        provider=get_default_provider(),
        model="openai/gpt-4.1-mini",
        api_key_status="missing",
    )
    window = FakeWindow(prompt="Please convert this selection to uppercase.")
    transport = FakeTransport(
        {
            "type": "DirectAnswer",
            "text": "Remote answer",
        }
    )
    tool_panel = SidebarToolPanel(
        panel=panel,
        window=window,
        event_handler=SidebarDialogEventHandler(
            panel=panel,
            transport=transport,
            session_store=store,
        ),
    )

    assert tool_panel.event_handler.callHandlerMethod(window, None, "Send") is True

    history_summary = transport.requests[0]["historySummary"]
    assert [item["role"] for item in history_summary] == ["user", "assistant"]
    assert [item["text"] for item in history_summary] == ["Earlier prompt", "Earlier answer"]
    assert "Please convert this selection to uppercase." not in [
        item["text"] for item in history_summary
    ]