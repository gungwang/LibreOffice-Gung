from loaia.broker.transport import SidecarTransportClient
from loaia_shared.schema.messages import ChatRequest


class SidecarClient:
    def __init__(self, transport: SidecarTransportClient | None = None) -> None:
        self.transport = transport or SidecarTransportClient()

    def send_chat(self, request: ChatRequest) -> str:
        del request
        return "Extension-side broker client scaffold is connected to a placeholder path."
