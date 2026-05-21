from dataclasses import dataclass, field
from typing import Callable

from loaia.sidebar_actions import SidebarDialogEventHandler
from loaia_shared.defaults import get_default_model, get_default_provider

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
    handler: object | None = None,
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
        return provider.createContainerWindow(dialog_url, "", parent_window, handler)
    except Exception:
        return parent_window


def _shorten_text(text: str | None, limit: int = 160) -> str:
    if text is None:
        return "None"

    normalized = text.strip()
    if not normalized:
        return "(empty selection)"

    if len(normalized) <= limit:
        return normalized

    return f"{normalized[: limit - 3].rstrip()}..."


def _describe_optional_text(text: str | None, empty_label: str, limit: int = 160) -> str:
    if text is None:
        return empty_label

    return _shorten_text(text, limit=limit)


def _summarize_pending_proposal(proposal: object | None) -> str:
    if proposal is None:
        return "No pending proposal."

    preview = getattr(proposal, "preview", None)
    summary = getattr(preview, "summary", None)
    before = getattr(preview, "before", None)
    after = getattr(preview, "after", None)
    tool_id = getattr(proposal, "tool_id", "unknown-tool")

    lines = [summary or f"Tool: {tool_id}"]
    if summary:
        lines.append(f"Tool: {tool_id}")
    if before is not None:
        lines.append(f"Before: {_shorten_text(before, limit=90)}")
    if after is not None:
        lines.append(f"After: {_shorten_text(after, limit=90)}")

    return "\n".join(lines)


def _summarize_recent_messages(messages: list[str]) -> str:
    if not messages:
        return "No chat activity yet."

    return "\n".join(f"- {_shorten_text(message, limit=90)}" for message in messages[-3:])


@dataclass(slots=True)
class SidebarState:
    provider: str = field(default_factory=get_default_provider)
    model: str = field(default_factory=get_default_model)
    privacy_scope: str = "selection-only"
    connected: bool = False
    visible: bool = False
    last_command: str | None = None
    last_prompt: str | None = None
    last_result: str | None = None
    last_error: str | None = None
    selection_preview: str | None = None
    pending_proposal: object | None = None
    messages: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SidebarPanel:
    title: str
    resource_url: str
    frame: object | None = None
    state: SidebarState = field(default_factory=SidebarState)
    _observers: list[Callable[["SidebarPanel"], None]] = field(
        default_factory=list,
        init=False,
        repr=False,
    )

    def bind_view(self, observer: Callable[["SidebarPanel"], None]) -> None:
        self._observers.append(observer)
        observer(self)

    def record_request(
        self,
        provider: str,
        model: str,
        privacy_scope: str,
        selection_text: str | None,
        user_message: str | None = None,
    ) -> None:
        self.state.provider = provider
        self.state.model = model
        self.state.privacy_scope = privacy_scope
        self.state.selection_preview = selection_text
        if user_message is not None:
            self.state.last_prompt = user_message
        self.state.last_error = None
        self._notify_observers()

    def set_selection_preview(self, selection_text: str | None) -> None:
        self.state.selection_preview = selection_text
        self._notify_observers()

    def set_connected(self, connected: bool) -> None:
        self.state.connected = connected
        self._notify_observers()

    def set_last_result(self, result: str | None) -> None:
        self.state.last_result = result
        self.state.last_error = None
        self._notify_observers()

    def set_last_error(self, error_message: str | None) -> None:
        self.state.last_error = error_message
        self._notify_observers()

    def append_message(self, text: str) -> None:
        self.state.messages.append(text)
        self._notify_observers()

    def attach_frame(self, frame: object | None) -> None:
        if frame is not None:
            self.frame = frame

    def mark_visible(self) -> None:
        self.state.visible = True
        self._notify_observers()

    def set_last_command(self, command: str) -> None:
        self.state.last_command = command
        self._notify_observers()

    def set_pending_proposal(self, proposal: object) -> None:
        self.state.pending_proposal = proposal
        self._notify_observers()

    def clear_pending_proposal(self) -> None:
        self.state.pending_proposal = None
        self._notify_observers()

    def render_status_text(self) -> str:
        connection_state = (
            "connected to sidecar" if self.state.connected else "waiting for first sidecar response"
        )
        last_command = self.state.last_command or "not opened via protocol yet"
        lines = [
            f"Connection: {connection_state}",
            f"Provider: {self.state.provider}",
            f"Model: {self.state.model}",
            f"Last command: {last_command}",
        ]
        if self.state.last_error is not None:
            lines.append(f"Last error: {_shorten_text(self.state.last_error, limit=90)}")

        return "\n".join(lines)

    def render_summary_text(self) -> str:
        prompt_summary = _describe_optional_text(
            self.state.last_prompt,
            empty_label="No prompt submitted yet.",
            limit=180,
        )
        selection_summary = _describe_optional_text(
            self.state.selection_preview,
            empty_label="No captured selection yet.",
            limit=180,
        )
        pending_summary = _summarize_pending_proposal(self.state.pending_proposal)
        result_summary = _describe_optional_text(
            self.state.last_result,
            empty_label="No completed result yet.",
            limit=180,
        )
        recent_activity = _summarize_recent_messages(self.state.messages)
        return "\n".join(
            [
                "Prompt:",
                prompt_summary,
                "",
                "Selection:",
                selection_summary,
                "",
                "Pending preview:",
                pending_summary,
                "",
                "Last result:",
                result_summary,
                "",
                "Recent activity:",
                recent_activity,
            ]
        )

    def render_privacy_text(self) -> str:
        visibility = "visible" if self.state.visible else "hidden"
        return "\n".join(
            [
                f"Privacy scope: {self.state.privacy_scope}",
                f"Panel state: {visibility}",
                "Broader document edits stay behind explicit approval.",
            ]
        )

    def _notify_observers(self) -> None:
        for observer in tuple(self._observers):
            observer(self)


class SidebarToolPanel(unohelper.Base, XToolPanel):
    def __init__(
        self,
        panel: SidebarPanel,
        window: object | None = None,
        context: object | None = None,
        extension_identifier: str | None = None,
        dialog_path: str | None = None,
        event_handler: object | None = None,
    ) -> None:
        self.panel = panel
        self.context = context
        self.parent_window = window
        self.event_handler = event_handler or SidebarDialogEventHandler(panel=panel)
        self.window = _create_panel_window(
            context=context,
            parent_window=window,
            extension_identifier=extension_identifier,
            dialog_path=dialog_path,
            handler=self.event_handler,
        )
        self.PanelWindow = self.window
        self.Window = self.window
        self.panel.bind_view(self.refresh_from_panel)

    def getWindow(self) -> object | None:
        return self.window

    def refresh_from_panel(self, panel: SidebarPanel) -> None:
        self._set_control_text("Title", panel.title)
        self._set_control_text("Status", panel.render_status_text())
        self._set_control_text("Summary", panel.render_summary_text())
        self._set_control_text("Privacy", panel.render_privacy_text())
        self._set_control_enabled("ApproveButton", panel.state.pending_proposal is not None)

    def createAccessible(self, parent_accessible: object) -> object | None:
        return self.window or parent_accessible

    def _set_control_text(self, control_name: str, value: str) -> None:
        if self.window is None or not hasattr(self.window, "getControl"):
            return

        try:
            control = self.window.getControl(control_name)
        except Exception:
            return

        if control is None or not hasattr(control, "getModel"):
            return

        model = control.getModel()
        if model is None:
            return

        for attribute_name in ("Text", "Label"):
            if hasattr(model, attribute_name):
                setattr(model, attribute_name, value)
                return

        if hasattr(model, "setPropertyValue"):
            for property_name in ("Text", "Label"):
                try:
                    model.setPropertyValue(property_name, value)
                    return
                except Exception:
                    continue

    def _set_control_enabled(self, control_name: str, enabled: bool) -> None:
        if self.window is None or not hasattr(self.window, "getControl"):
            return

        try:
            control = self.window.getControl(control_name)
        except Exception:
            return

        if control is None:
            return

        if hasattr(control, "setEnable"):
            try:
                control.setEnable(enabled)
                return
            except Exception:
                pass

        if not hasattr(control, "getModel"):
            return

        model = control.getModel()
        if model is None:
            return

        if hasattr(model, "Enabled"):
            model.Enabled = enabled
            return

        if hasattr(model, "setPropertyValue"):
            try:
                model.setPropertyValue("Enabled", enabled)
            except Exception:
                return


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
