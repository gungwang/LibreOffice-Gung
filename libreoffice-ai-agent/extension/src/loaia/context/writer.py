from dataclasses import dataclass

from loaia_shared.errors import ValidationError
from loaia_shared.schema.actions import ToolProposal
from loaia_shared.schema.messages import ChatRequest, ContextEnvelope, DocumentRef, SelectionContext
from loaia_shared.types import AppType, PrivacyScope


@dataclass(slots=True)
class WriterSelectionState:
    text: str
    text_ranges: tuple[object, ...] = ()
    selection_supplier: object | None = None


def extract_writer_selection(text: str) -> ContextEnvelope:
    return ContextEnvelope(selection=SelectionContext(mimeType="text/plain", text=text))


def capture_writer_selection(selection_supplier: object) -> WriterSelectionState:
    text_ranges = _collect_text_ranges(selection_supplier)
    selection_text = "\n".join(_get_range_text(text_range) for text_range in text_ranges)
    return WriterSelectionState(
        text=selection_text,
        text_ranges=text_ranges,
        selection_supplier=selection_supplier,
    )


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

    if selection.text_ranges:
        _apply_uno_writer_replacement(selection, replacement_text)

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


def _collect_text_ranges(selection_supplier: object) -> tuple[object, ...]:
    try:
        index_access = selection_supplier.getSelection()
        count = index_access.getCount()
    except AttributeError as exc:
        raise ValidationError(
            "Writer selection supplier does not expose LibreOffice selection APIs"
        ) from exc

    if count < 1:
        raise ValidationError("Writer selection supplier returned no selected ranges")

    return tuple(index_access.getByIndex(index) for index in range(count))


def _get_range_text(text_range: object) -> str:
    try:
        text = text_range.getString()
    except AttributeError as exc:
        raise ValidationError("Writer selected range does not expose getString()") from exc

    if not isinstance(text, str):
        raise ValidationError("Writer selected range returned a non-string value")

    return text


def _apply_uno_writer_replacement(selection: WriterSelectionState, replacement_text: str) -> None:
    if len(selection.text_ranges) != 1:
        raise ValidationError(
            "Writer replace-selection currently supports exactly one selected range"
        )

    text_range = selection.text_ranges[0]

    try:
        text_range.setString(replacement_text)
    except AttributeError as exc:
        raise ValidationError("Writer selected range does not expose setString()") from exc

    selection_supplier = selection.selection_supplier
    if selection_supplier is not None and hasattr(selection_supplier, "select"):
        selection_supplier.select(text_range)
