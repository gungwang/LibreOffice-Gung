from dataclasses import dataclass

from loaia_shared.errors import ValidationError
from loaia_shared.schema.actions import ToolProposal
from loaia_shared.schema.messages import ChatRequest, ContextEnvelope, DocumentRef, SelectionContext
from loaia_shared.types import AppType, PrivacyScope


@dataclass(slots=True)
class WriterSelectionState:
    text: str


def extract_writer_selection(text: str) -> ContextEnvelope:
    return ContextEnvelope(selection=SelectionContext(mimeType="text/plain", text=text))


def build_writer_chat_request(
    selection: WriterSelectionState,
    user_message: str,
    request_id: str = "writer-request-1",
    canonical_url: str = "file:///writer-document.odt",
    profile_id: str = "default-profile",
    provider: str = "openai-compatible",
    model: str = "local-default",
) -> ChatRequest:
    return ChatRequest(
        requestId=request_id,
        app=AppType.WRITER,
        document=DocumentRef(canonicalUrl=canonical_url, profileId=profile_id),
        provider=provider,
        model=model,
        privacyScope=PrivacyScope.SELECTION_ONLY,
        context=extract_writer_selection(selection.text),
        userMessage=user_message,
    )


def apply_writer_proposal(selection: WriterSelectionState, proposal: ToolProposal) -> str:
    if proposal.tool_id != "Writer.ReplaceSelection":
        raise ValidationError(f"Unsupported Writer proposal: {proposal.tool_id}")

    replacement_text = _extract_replacement_text(proposal)
    selection.text = replacement_text
    return selection.text


def _extract_replacement_text(proposal: ToolProposal) -> str:
    preview_after = proposal.preview.after if proposal.preview else None
    if preview_after:
        return preview_after

    replacement_text = proposal.arguments.get("replacementText")
    if isinstance(replacement_text, str):
        return replacement_text

    raise ValidationError("Writer replacement proposal does not contain replacement text")
