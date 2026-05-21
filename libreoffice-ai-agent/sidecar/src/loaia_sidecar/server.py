from loaia_shared.schema.messages import ChatRequest, DirectAnswer, HandshakeResponse


class LoaiaSidecarServer:
    """Minimal sidecar server skeleton.

    The real implementation will own the transport loop, provider dispatch,
    streaming lifecycle, and structured tool proposal generation.
    """

    def __init__(self) -> None:
        self.capabilities = [
            "handshake",
            "streaming",
            "tool-proposals",
            "consent-escalation",
        ]

    def handshake(self) -> HandshakeResponse:
        return HandshakeResponse(
            serverVersion="0.1.0",
            capabilities=self.capabilities,
            availableProviders=[
                "openai-compatible",
                "anthropic",
                "gemini",
                "openrouter",
            ],
        )

    def handle_chat_request(self, request: ChatRequest) -> DirectAnswer:
        return DirectAnswer(
            requestId=request.request_id,
            text=(
                "Sidecar scaffold is running. Planner and provider execution "
                "are not implemented yet."
            ),
        )

    def run(self) -> None:
        # Placeholder until the named-pipe transport loop is implemented.
        print("LibreOffice AI Agent sidecar scaffold started")
