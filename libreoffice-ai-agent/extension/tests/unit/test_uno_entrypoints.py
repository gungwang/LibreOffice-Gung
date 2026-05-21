from types import SimpleNamespace

from loaia.bootstrap import (
    EXTENSION_IDENTIFIER,
    OPEN_SIDEBAR_COMMAND,
    PROTOCOL_SCHEME,
    SIDEBAR_DIALOG_PATH,
    SIDEBAR_RESOURCE_URL,
    ExtensionBootstrap,
)
from loaia.sidebar_actions import SidebarDialogEventHandler
from loaia.sidebar_panel import SidebarPanel, SidebarToolPanel
from loaia_python import LoaiaProtocolHandlerProvider, LoaiaSidebarPanelFactory


def test_protocol_handler_dispatch_opens_sidebar() -> None:
    runtime = ExtensionBootstrap()
    provider = LoaiaProtocolHandlerProvider(runtime=runtime)
    url = SimpleNamespace(
        Protocol=PROTOCOL_SCHEME,
        Path=OPEN_SIDEBAR_COMMAND,
        Complete=f"{PROTOCOL_SCHEME}{OPEN_SIDEBAR_COMMAND}",
    )

    dispatch = provider.queryDispatch(url, "_self", 0)

    assert dispatch is not None

    dispatch.dispatch(url, ())

    panel = runtime.get_panel()
    assert panel.state.visible is True
    assert panel.state.last_command == OPEN_SIDEBAR_COMMAND


def test_sidebar_factory_creates_toolpanel_ui_element() -> None:
    runtime = ExtensionBootstrap()
    factory = LoaiaSidebarPanelFactory(runtime=runtime)
    arguments = [
        SimpleNamespace(Name="Frame", Value="frame-1"),
        SimpleNamespace(Name="ParentWindow", Value="window-1"),
    ]

    ui_element = factory.createUIElement(SIDEBAR_RESOURCE_URL, arguments)

    assert ui_element.getResourceURL() == SIDEBAR_RESOURCE_URL
    assert ui_element.getType() == 7
    assert ui_element.getFrame() == "frame-1"
    assert ui_element.getRealInterface().getWindow() == "window-1"


def test_sidebar_toolpanel_uses_extension_dialog_when_context_available() -> None:
    class FakePackageInformationProvider:
        def getPackageLocation(self, extension_identifier: str) -> str:
            assert extension_identifier == EXTENSION_IDENTIFIER
            return "file:///mock-extension"

    class FakeContainerWindowProvider:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, object, object | None]] = []

        def createContainerWindow(
            self,
            dialog_url: str,
            unused_name: str,
            parent_window: object,
            handler: object | None,
        ) -> str:
            self.calls.append((dialog_url, unused_name, parent_window, handler))
            return f"dialog::{dialog_url}"

    class FakeServiceManager:
        def __init__(self, provider: FakeContainerWindowProvider) -> None:
            self.provider = provider

        def createInstanceWithContext(self, service_name: str, context: object) -> object:
            assert service_name == "com.sun.star.awt.ContainerWindowProvider"
            assert context is not None
            return self.provider

    class FakeContext:
        def __init__(self, provider: FakeContainerWindowProvider) -> None:
            self.ServiceManager = FakeServiceManager(provider)

        def getValueByName(self, value_name: str) -> FakePackageInformationProvider:
            assert value_name == "/singletons/com.sun.star.deployment.PackageInformationProvider"
            return FakePackageInformationProvider()

    panel = SidebarPanel(title="LibreOffice AI Agent", resource_url=SIDEBAR_RESOURCE_URL)
    provider = FakeContainerWindowProvider()
    tool_panel = SidebarToolPanel(
        panel=panel,
        window="window-1",
        context=FakeContext(provider),
        extension_identifier=EXTENSION_IDENTIFIER,
        dialog_path=SIDEBAR_DIALOG_PATH,
    )

    assert tool_panel.getWindow() == f"dialog::file:///mock-extension/{SIDEBAR_DIALOG_PATH}"
    assert provider.calls == [
        (
            f"file:///mock-extension/{SIDEBAR_DIALOG_PATH}",
            "",
            "window-1",
            tool_panel.event_handler,
        )
    ]
    assert isinstance(tool_panel.event_handler, SidebarDialogEventHandler)


def test_sidebar_toolpanel_refreshes_dialog_controls_from_panel_state() -> None:
    class FakeModel:
        def __init__(self, attribute_name: str) -> None:
            setattr(self, attribute_name, "")
            self.Enabled = True

    class FakeControl:
        def __init__(self, attribute_name: str) -> None:
            self.model = FakeModel(attribute_name)

        def getModel(self) -> FakeModel:
            return self.model

    class FakeWindow:
        def __init__(self) -> None:
            self.controls = {
                "Title": FakeControl("Label"),
                "Status": FakeControl("Label"),
                "Summary": FakeControl("Text"),
                "Privacy": FakeControl("Label"),
                "ApproveButton": FakeControl("Label"),
            }

        def getControl(self, name: str) -> FakeControl:
            return self.controls[name]

    panel = SidebarPanel(title="LibreOffice AI Agent", resource_url=SIDEBAR_RESOURCE_URL)
    window = FakeWindow()
    SidebarToolPanel(panel=panel, window=window)

    assert window.controls["ApproveButton"].model.Enabled is False

    panel.mark_visible()
    panel.set_last_command(OPEN_SIDEBAR_COMMAND)
    panel.record_request(
        provider="openai-compatible",
        model="local-default",
        privacy_scope="selection-only",
        selection_text="hello world",
        user_message="Please convert this selection to uppercase.",
    )
    panel.set_connected(True)
    panel.set_pending_proposal(
        SimpleNamespace(
            tool_id="Writer.ReplaceSelection",
            preview=SimpleNamespace(
                summary="Preview Writer selection replacement",
                before="hello world",
                after="HELLO WORLD",
            ),
        )
    )
    panel.set_last_result("Preview Writer selection replacement")
    panel.append_message("Preview Writer selection replacement")

    expected_prompt = "Prompt:\nPlease convert this selection to uppercase."
    expected_result = "Last result:\nPreview Writer selection replacement"

    assert window.controls["Title"].model.Label == "LibreOffice AI Agent"
    assert "Connection: connected to sidecar" in window.controls["Status"].model.Label
    assert "Provider: openai-compatible" in window.controls["Status"].model.Label
    assert expected_prompt in window.controls["Summary"].model.Text
    assert "Selection:\nhello world" in window.controls["Summary"].model.Text
    assert (
        "Pending preview:\nPreview Writer selection replacement"
        in window.controls["Summary"].model.Text
    )
    assert expected_result in window.controls["Summary"].model.Text
    assert "After: HELLO WORLD" in window.controls["Summary"].model.Text
    assert (
        "Recent activity:\n- Preview Writer selection replacement"
        in window.controls["Summary"].model.Text
    )
    assert "Privacy scope: selection-only" in window.controls["Privacy"].model.Label
    assert window.controls["ApproveButton"].model.Enabled is True