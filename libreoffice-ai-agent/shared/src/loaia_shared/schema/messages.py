from pydantic import BaseModel, Field

from loaia_shared.schema.actions import ToolProposal
from loaia_shared.types import AppType, PrivacyScope


class DocumentRef(BaseModel):
    canonical_url: str = Field(alias="canonicalUrl")
    profile_id: str = Field(alias="profileId")

    model_config = {"populate_by_name": True}


class SelectionContext(BaseModel):
    mime_type: str = Field(alias="mimeType")
    text: str

    model_config = {"populate_by_name": True}


class ContextEnvelope(BaseModel):
    selection: SelectionContext | None = None


class HandshakeRequest(BaseModel):
    type: str = "HandshakeRequest"
    client_version: str = Field(default="0.1.0", alias="clientVersion")

    model_config = {"populate_by_name": True}


class HandshakeResponse(BaseModel):
    type: str = "HandshakeResponse"
    server_version: str = Field(alias="serverVersion")
    capabilities: list[str]
    available_providers: list[str] = Field(alias="availableProviders")

    model_config = {"populate_by_name": True}


class ChatRequest(BaseModel):
    type: str = "ChatRequest"
    request_id: str = Field(alias="requestId")
    app: AppType
    document: DocumentRef
    provider: str
    model: str
    privacy_scope: PrivacyScope = Field(alias="privacyScope")
    context: ContextEnvelope
    user_message: str = Field(alias="userMessage")
    history_summary: list[dict[str, object]] = Field(default_factory=list, alias="historySummary")

    model_config = {"populate_by_name": True}


class CancelRequest(BaseModel):
    type: str = "CancelRequest"
    request_id: str = Field(alias="requestId")

    model_config = {"populate_by_name": True}


class StreamChunk(BaseModel):
    type: str = "StreamChunk"
    request_id: str = Field(alias="requestId")
    text: str

    model_config = {"populate_by_name": True}


class DirectAnswer(BaseModel):
    type: str = "DirectAnswer"
    request_id: str = Field(alias="requestId")
    text: str

    model_config = {"populate_by_name": True}


class ConsentRequest(BaseModel):
    type: str = "ConsentRequest"
    request_id: str = Field(alias="requestId")
    requested_scope: str = Field(alias="requestedScope")
    reason: str

    model_config = {"populate_by_name": True}


class ToolProposalEnvelope(BaseModel):
    type: str = "ToolProposal"
    request_id: str = Field(alias="requestId")
    proposals: list[ToolProposal]

    model_config = {"populate_by_name": True}


class ErrorResponse(BaseModel):
    type: str = "ErrorResponse"
    request_id: str = Field(alias="requestId")
    message: str

    model_config = {"populate_by_name": True}
