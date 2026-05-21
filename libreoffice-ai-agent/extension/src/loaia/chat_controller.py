from loaia.actions.registry import ACTION_REGISTRY
from loaia.broker.client import SidecarClient
from loaia.context.writer import WriterSelectionState, apply_writer_proposal
from loaia.sidebar_panel import SidebarPanel
from loaia_shared.errors import ValidationError
from loaia_shared.schema.messages import ChatRequest, DirectAnswer, ToolProposalEnvelope


class ChatController:
    def __init__(self, panel: SidebarPanel, client: SidecarClient) -> None:
        self.panel = panel
        self.client = client

    def submit(self, request: ChatRequest) -> str:
        selection = request.context.selection
        selection_text = selection.text if selection is not None else None
        self.panel.record_request(
            provider=request.provider,
            model=request.model,
            privacy_scope=str(request.privacy_scope),
            selection_text=selection_text,
        )

        response = self.client.request_chat(request)
        self.panel.set_connected(True)

        if isinstance(response, DirectAnswer):
            self.panel.clear_pending_proposal()
            self.panel.append_message(response.text)
            return response.text

        if isinstance(response, ToolProposalEnvelope):
            proposal = self._select_proposal(response)
            self.panel.set_pending_proposal(proposal)
            preview_summary = proposal.preview.summary if proposal.preview else proposal.tool_id
            self.panel.append_message(preview_summary)
            return preview_summary

        raise ValidationError("Unsupported chat response shape")

    def approve_pending_writer_proposal(self, selection: WriterSelectionState) -> str:
        proposal = self.panel.state.pending_proposal
        if proposal is None:
            raise ValidationError("No pending writer proposal is available for approval")

        applied_text = apply_writer_proposal(selection, proposal)
        self.panel.append_message(f"Applied {proposal.tool_id}")
        self.panel.clear_pending_proposal()
        return applied_text

    @staticmethod
    def _select_proposal(response: ToolProposalEnvelope):
        if not response.proposals:
            raise ValidationError("Sidecar returned an empty tool proposal envelope")

        proposal = response.proposals[0]
        if proposal.tool_id not in ACTION_REGISTRY:
            raise ValidationError(f"Unknown tool proposal: {proposal.tool_id}")

        return proposal
