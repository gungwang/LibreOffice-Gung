from dataclasses import dataclass, field

try:
    import unohelper
    from com.sun.star.ui import XToolPanel, XUIElement
    from com.sun.star.ui.UIElementType import TOOLPANEL as TOOL_PANEL_UI_TYPE
except ImportError:  # pragma: no cover - exercised under LibreOffice runtime
    class _UnoBase:
        pass

    class XUIElement:  # type: ignore[no-redef]
        pass

    class XToolPanel:  # type: ignore[no-redef]
        pass

    class _UnoHelperModule:
        Base = _UnoBase

    unohelper = _UnoHelperModule()
    TOOL_PANEL_UI_TYPE = 7


def _get_service_manager(context: object | None) -> object | None:
    if context is None:
        return None

    service_manager = getattr(context, "ServiceManager", None)
    if service_manager is not None:
        return service_manager

    get_service_manager = getattr(context, "getServiceManager", None)
    if callable(get_service_manager):
        return get_service_manager()

    return None


def _create_panel_window(
    context: object | None,
    parent_window: object | None,
    extension_identifier: str | None,
    dialog_path: str | None,
) -> object | None:
    if (
        context is None
        or parent_window is None
        or not extension_identifier
        or not dialog_path
    ):
        return parent_window

    try:
        package_info = context.getValueByName(
            "/singletons/com.sun.star.deployment.PackageInformationProvider"
        )
        package_location = package_info.getPackageLocation(extension_identifier)
        service_manager = _get_service_manager(context)
        if service_manager is None:
            return parent_window

        provider = service_manager.createInstanceWithContext(
            "com.sun.star.awt.ContainerWindowProvider",
            context,
        )
        dialog_url = f"{package_location}/{dialog_path}"
        return provider.createContainerWindow(dialog_url, "", parent_window, None)
    except Exception:
        return parent_window


@dataclass(slots=True)
class SidebarState:
    provider: str = "openai-compatible"
    model: str = "local-default"
    privacy_scope: str = "selection-only"
    connected: bool = False
    visible: bool = False
    last_command: str | None = None
    pending_proposal: object | None = None
    messages: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SidebarPanel:
    title: str
    resource_url: str
    frame: object | None = None
    state: SidebarState = field(default_factory=SidebarState)

    def append_message(self, text: str) -> None:
        self.state.messages.append(text)

    def attach_frame(self, frame: object | None) -> None:
        if frame is not None:
            self.frame = frame

    def mark_visible(self) -> None:
        self.state.visible = True

    def set_last_command(self, command: str) -> None:
        self.state.last_command = command

    def set_pending_proposal(self, proposal: object) -> None:
        self.state.pending_proposal = proposal

    def clear_pending_proposal(self) -> None:
        self.state.pending_proposal = None


class SidebarToolPanel(unohelper.Base, XToolPanel):
    def __init__(
        self,
        panel: SidebarPanel,
        window: object | None = None,
        context: object | None = None,
        extension_identifier: str | None = None,
        dialog_path: str | None = None,
    ) -> None:
        self.panel = panel
        self.context = context
        self.parent_window = window
        self.window = _create_panel_window(
            context=context,
            parent_window=window,
            extension_identifier=extension_identifier,
            dialog_path=dialog_path,
        )
        self.PanelWindow = self.window
        self.Window = self.window

    def getWindow(self) -> object | None:
        return self.window

    def createAccessible(self, parent_accessible: object) -> object | None:
        return self.window or parent_accessible


class SidebarUIElement(unohelper.Base, XUIElement):
    def __init__(
        self,
        frame: object | None,
        resource_url: str,
        tool_panel: SidebarToolPanel,
    ) -> None:
        self.frame = frame
        self.resource_url = resource_url
        self.tool_panel = tool_panel
        self.Frame = frame
        self.ResourceURL = resource_url
        self.Type = TOOL_PANEL_UI_TYPE

    def getRealInterface(self) -> SidebarToolPanel:
        return self.tool_panel

    def getFrame(self) -> object | None:
        return self.frame

    def getResourceURL(self) -> str:
        return self.resource_url

    def getType(self) -> int:
        return TOOL_PANEL_UI_TYPE
