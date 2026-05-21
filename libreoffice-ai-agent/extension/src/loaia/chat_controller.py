from loaia.actions.registry import ACTION_REGISTRY
from loaia.broker.client import SidecarClient
from loaia.sidebar_panel import SidebarPanel
from loaia_shared.schema.messages import ChatRequest


class ChatController:
    def __init__(self, panel: SidebarPanel, client: SidecarClient) -> None:
        self.panel = panel
        self.client = client

    def submit(self, request: ChatRequest) -> str:
        _ = ACTION_REGISTRY
        response = self.client.send_chat(request)
        self.panel.append_message(response)
        return response
