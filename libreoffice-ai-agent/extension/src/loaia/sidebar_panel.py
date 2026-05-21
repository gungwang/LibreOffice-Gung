from dataclasses import dataclass, field

from loaia_shared.schema.actions import ToolProposal

TOOL_PANEL_UI_TYPE = 7


@dataclass(slots=True)
class SidebarState:
    provider: str = "openai-compatible"
    model: str = "local-default"
    privacy_scope: str = "selection-only"
    connected: bool = False
    visible: bool = False
    last_command: str | None = None
    pending_proposal: ToolProposal | None = None
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

    def set_pending_proposal(self, proposal: ToolProposal) -> None:
        self.state.pending_proposal = proposal

    def clear_pending_proposal(self) -> None:
        self.state.pending_proposal = None


@dataclass(slots=True)
class SidebarToolPanel:
    panel: SidebarPanel
    window: object | None = None

    def getWindow(self) -> object | None:
        return self.window

    @property
    def Window(self) -> object | None:
        return self.getWindow()

    def createAccessible(self, parent_accessible: object) -> object:
        return parent_accessible


@dataclass(slots=True)
class SidebarUIElement:
    frame: object | None
    resource_url: str
    tool_panel: SidebarToolPanel

    def getRealInterface(self) -> SidebarToolPanel:
        return self.tool_panel

    def getFrame(self) -> object | None:
        return self.frame

    @property
    def Frame(self) -> object | None:
        return self.getFrame()

    def getResourceURL(self) -> str:
        return self.resource_url

    @property
    def ResourceURL(self) -> str:
        return self.getResourceURL()

    def getType(self) -> int:
        return TOOL_PANEL_UI_TYPE

    @property
    def Type(self) -> int:
        return self.getType()
