from types import SimpleNamespace

from loaia.bootstrap import SIDEBAR_RESOURCE_URL
from loaia.sidebar_actions import SidebarDialogEventHandler
from loaia.sidebar_panel import SidebarPanel, SidebarToolPanel


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


class FakeFrame:
    def __init__(self, controller: FakeWriterController) -> None:
        self.controller = controller

    def getController(self) -> FakeWriterController:
        return self.controller


class FakeModel:
    def __init__(self, attribute_name: str, value: str = "") -> None:
        setattr(self, attribute_name, value)


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
            "PromptInput": FakeControl("Text", prompt),
            "Summary": FakeControl("Text"),
            "Privacy": FakeControl("Label"),
        }

    def getControl(self, name: str) -> FakeControl:
        return self.controls[name]


class FakeTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    def request(self, payload: dict[str, object]) -> dict[str, object]:
        self.requests.append(payload)
        return self.response


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

    assert tool_panel.event_handler.callHandlerMethod(window, None, "Send") is True

    assert transport.requests[0]["type"] == "ChatRequest"
    assert transport.requests[0]["userMessage"] == "Please convert this selection to uppercase."
    assert transport.requests[0]["context"] == {
        "selection": {"mimeType": "text/plain", "text": "hello world"}
    }
    assert panel.state.connected is True
    assert panel.state.selection_preview == "hello world"
    assert panel.state.pending_proposal is not None
    assert panel.state.pending_proposal.preview.after == "HELLO WORLD"
    assert "Provider: openai-compatible" in window.controls["Status"].model.Label
    assert (
        "Pending preview:\nPreview Writer selection replacement"
        in window.controls["Summary"].model.Text
    )


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
    assert window.controls["PromptInput"].model.Text == ""
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