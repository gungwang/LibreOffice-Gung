from dataclasses import dataclass, field


@dataclass(slots=True)
class SidebarState:
    provider: str = "openai-compatible"
    model: str = "local-default"
    privacy_scope: str = "selection-only"
    connected: bool = False
    messages: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SidebarPanel:
    title: str
    state: SidebarState = field(default_factory=SidebarState)

    def append_message(self, text: str) -> None:
        self.state.messages.append(text)
