from loaia.document_session import resolve_history_session_key
from loaia.session_store import JsonSidebarSessionStore, SqliteSidebarSessionStore
from loaia.sidebar_actions import SidebarDialogEventHandler
from loaia.sidebar_panel import SidebarPanel, SidebarToolPanel, SidebarUIElement

EXTENSION_IDENTIFIER = "org.gungwang.libreoffice-ai-agent"
PROTOCOL_SCHEME = "vnd.org.libreoffice.ai.agent:"
OPEN_SIDEBAR_COMMAND = "open-sidebar"
SEND_MESSAGE_COMMAND = "send-message"
SAVE_SETTINGS_COMMAND = "save-settings"
SIDEBAR_FACTORY_NAME = "LoaiaPanelFactory"
SIDEBAR_PANEL_ID = "LoaiaPanel"
SIDEBAR_RESOURCE_URL = f"private:resource/toolpanel/{SIDEBAR_FACTORY_NAME}/{SIDEBAR_PANEL_ID}"
SIDEBAR_DECK_ID = "LoaiaDeck"
SIDEBAR_DIALOG_PATH = "toolpanels/sidebar_shell.xdl"


def _show_sidebar_deck(frame: object | None) -> None:
    """Programmatically open the LibreOffice sidebar and show the AI deck."""
    if frame is None:
        return

    try:
        # Best approach: dispatch directly to our deck via .uno:SidebarDeck.DeckId
        # This both opens the sidebar and switches to our deck in one step.
        _dispatch_uno_command(frame, f".uno:SidebarDeck.{SIDEBAR_DECK_ID}")
    except Exception:
        pass

    try:
        # Fallback: try getSidebar API
        controller = frame.getController() if hasattr(frame, "getController") else None
        if controller is None:
            return

        sidebar = None
        if hasattr(controller, "getSidebar"):
            sidebar = controller.getSidebar()
        if sidebar is None:
            _dispatch_uno_command(frame, ".uno:Sidebar")
            if hasattr(controller, "getSidebar"):
                sidebar = controller.getSidebar()

        if sidebar is not None:
            if hasattr(sidebar, "setVisible"):
                sidebar.setVisible(True)
            if hasattr(sidebar, "requestDeck"):
                sidebar.requestDeck(SIDEBAR_DECK_ID)
    except Exception:
        pass


def _dispatch_uno_command(frame: object, command: str) -> None:
    """Dispatch a .uno: command to the given frame."""
    try:
        dispatch_helper = None
        context = getattr(frame, "ComponentContext", None)
        if context is None and hasattr(frame, "getComponentContext"):
            context = frame.getComponentContext()

        if context is not None:
            smgr = context.getServiceManager()
            if smgr is not None:
                dispatch_helper = smgr.createInstanceWithContext(
                    "com.sun.star.frame.DispatchHelper", context
                )

        if dispatch_helper is None:
            # Try via global component context
            import uno  # noqa: F401 — available in LO Python
            ctx = uno.getComponentContext()
            smgr = ctx.getServiceManager()
            dispatch_helper = smgr.createInstanceWithContext(
                "com.sun.star.frame.DispatchHelper", ctx
            )

        if dispatch_helper is not None:
            dispatch_helper.executeDispatch(frame, command, "", 0, ())
    except Exception:
        pass


class ExtensionBootstrap:
    def __init__(
        self,
        transport: object | None = None,
        session_store: JsonSidebarSessionStore | SqliteSidebarSessionStore | None = None,
    ) -> None:
        self._panel: SidebarPanel | None = None
        self._event_handler: SidebarDialogEventHandler | None = None
        self._transport = transport
        self._session_store = session_store or JsonSidebarSessionStore()

    def get_panel(self) -> SidebarPanel:
        if self._panel is None:
            self._panel = SidebarPanel(
                title="AI Agent",
                resource_url=SIDEBAR_RESOURCE_URL,
            )
            settings = self._session_store.load_settings()
            self._panel.apply_settings(
                provider=settings.provider,
                model=settings.model,
                api_key_status=settings.api_key_status,
            )

        return self._panel

    def get_event_handler(self) -> SidebarDialogEventHandler:
        if self._event_handler is None:
            self._event_handler = SidebarDialogEventHandler(
                panel=self.get_panel(),
                transport=self._transport,
                session_store=self._session_store,
            )

        return self._event_handler

    def open_sidebar(self, frame: object | None = None) -> SidebarPanel:
        panel = self.get_panel()
        panel.attach_frame(frame)
        self._restore_panel_session(panel)
        panel.mark_visible()
        panel.set_last_command(OPEN_SIDEBAR_COMMAND)
        _show_sidebar_deck(frame)
        return panel

    def send_message(
        self,
        frame: object | None = None,
        prompt: str | None = None,
        pipe_address: str | None = None,
        window: object | None = None,
    ) -> str:
        panel = self.get_panel()
        panel.attach_frame(frame)
        panel.set_last_command(SEND_MESSAGE_COMMAND)
        return self.get_event_handler().handle_send(
            window=window,
            prompt=prompt,
            pipe_address=pipe_address,
        )

    def save_settings(
        self,
        frame: object | None = None,
        window: object | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> str:
        panel = self.get_panel()
        panel.attach_frame(frame)
        panel.set_last_command(SAVE_SETTINGS_COMMAND)
        return self.get_event_handler().save_settings(
            window=window,
            provider=provider,
            model=model,
        )

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

    def _restore_panel_session(self, panel: SidebarPanel) -> None:
        settings = self._session_store.load_settings()
        panel.apply_settings(
            provider=settings.provider,
            model=settings.model,
            api_key_status=settings.api_key_status,
        )
        session_snapshot = self._session_store.load_session(
            resolve_history_session_key(panel.frame)
        )
        panel.restore_session(
            last_prompt=session_snapshot.last_prompt,
            last_result=session_snapshot.last_result,
            last_error=session_snapshot.last_error,
            messages=session_snapshot.message_texts,
        )


_DEFAULT_BOOTSTRAP = ExtensionBootstrap()


def bootstrap() -> ExtensionBootstrap:
    return _DEFAULT_BOOTSTRAP
