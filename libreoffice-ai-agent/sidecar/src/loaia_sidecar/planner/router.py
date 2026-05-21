from loaia_shared.schema.messages import ChatRequest


class RequestRouter:
    """Selects the high-level handling path for a request."""

    def route(self, request: ChatRequest) -> str:
        if request.context.selection and request.context.selection.text.strip():
            return "selection-flow"
        return "consent-escalation"
