from loaia.broker.transport import SidecarTransportClient
from loaia_shared.errors import ValidationError
from loaia_shared.schema.messages import (
    ChatRequest,
    DirectAnswer,
    ErrorResponse,
    ToolProposalEnvelope,
)

ChatResponse = DirectAnswer | ToolProposalEnvelope


class SidecarClient:
    def __init__(self, transport: SidecarTransportClient | None = None) -> None:
        self.transport = transport or SidecarTransportClient()

    def request_chat(self, request: ChatRequest) -> ChatResponse:
        payload = self.transport.request(request)
        response_type = payload.get("type")

        if response_type == "DirectAnswer":
            return DirectAnswer.model_validate(payload)

        if response_type == "ToolProposal":
            return ToolProposalEnvelope.model_validate(payload)

        if response_type == "ErrorResponse":
            error = ErrorResponse.model_validate(payload)
            raise ValidationError(error.message)

        raise ValidationError(f"Unexpected response type from sidecar: {response_type!r}")

    def send_chat(self, request: ChatRequest) -> str:
        response = self.request_chat(request)
        if isinstance(response, DirectAnswer):
            return response.text

        raise ValidationError("Expected a direct answer but received a tool proposal")
