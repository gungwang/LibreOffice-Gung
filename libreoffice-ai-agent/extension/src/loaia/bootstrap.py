from loaia.sidebar_actions import SidebarDialogEventHandler
from loaia.sidebar_panel import SidebarPanel, SidebarToolPanel, SidebarUIElement

EXTENSION_IDENTIFIER = "org.gungwang.libreoffice-ai-agent"
PROTOCOL_SCHEME = "vnd.org.libreoffice.ai.agent:"
OPEN_SIDEBAR_COMMAND = "open-sidebar"
PREVIEW_SELECTION_COMMAND = "preview-selection"
APPROVE_PENDING_COMMAND = "approve-pending"
SIDEBAR_FACTORY_NAME = "LoaiaPanelFactory"
SIDEBAR_PANEL_ID = "LoaiaPanel"
SIDEBAR_RESOURCE_URL = f"private:resource/toolpanel/{SIDEBAR_FACTORY_NAME}/{SIDEBAR_PANEL_ID}"
SIDEBAR_DIALOG_PATH = "toolpanels/sidebar_shell.xdl"


class ExtensionBootstrap:
    def __init__(self, transport: object | None = None) -> None:
        self._panel: SidebarPanel | None = None
        self._event_handler: SidebarDialogEventHandler | None = None
        self._transport = transport

    def get_panel(self) -> SidebarPanel:
        if self._panel is None:
            self._panel = SidebarPanel(
                title="LibreOffice AI Agent",
                resource_url=SIDEBAR_RESOURCE_URL,
            )

        return self._panel

    def get_event_handler(self) -> SidebarDialogEventHandler:
        if self._event_handler is None:
            self._event_handler = SidebarDialogEventHandler(
                panel=self.get_panel(),
                transport=self._transport,
            )

        return self._event_handler

    def open_sidebar(self, frame: object | None = None) -> SidebarPanel:
        panel = self.get_panel()
        panel.attach_frame(frame)
        panel.mark_visible()
        panel.set_last_command(OPEN_SIDEBAR_COMMAND)
        return panel

    def preview_selection(
        self,
        frame: object | None = None,
        prompt: str | None = None,
        window: object | None = None,
    ) -> str:
        panel = self.get_panel()
        panel.attach_frame(frame)
        panel.set_last_command(PREVIEW_SELECTION_COMMAND)
        return self.get_event_handler().preview_current_selection(window=window, prompt=prompt)

    def approve_pending(
        self,
        frame: object | None = None,
        window: object | None = None,
    ) -> str:
        panel = self.get_panel()
        panel.attach_frame(frame)
        panel.set_last_command(APPROVE_PENDING_COMMAND)
        return self.get_event_handler().approve_pending(window=window)

    def create_sidebar_ui_element(
        self,
        resource_url: str,
        frame: object | None = None,
        parent_window: object | None = None,
        context: object | None = None,
    ) -> SidebarUIElement:
        panel = self.open_sidebar(frame=frame)
        tool_panel = SidebarToolPanel(
            panel=panel,
            window=parent_window,
            context=context,
            extension_identifier=EXTENSION_IDENTIFIER,
            dialog_path=SIDEBAR_DIALOG_PATH,
            event_handler=self.get_event_handler(),
        )
        return SidebarUIElement(
            frame=frame,
            resource_url=resource_url,
            tool_panel=tool_panel,
        )


_DEFAULT_BOOTSTRAP = ExtensionBootstrap()


def bootstrap() -> ExtensionBootstrap:
    return _DEFAULT_BOOTSTRAP
