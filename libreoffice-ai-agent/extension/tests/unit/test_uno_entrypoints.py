from types import SimpleNamespace

from loaia.bootstrap import (
    OPEN_SIDEBAR_COMMAND,
    PROTOCOL_SCHEME,
    SIDEBAR_RESOURCE_URL,
    ExtensionBootstrap,
)
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