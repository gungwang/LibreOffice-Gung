from pydantic import BaseModel, Field

from loaia_shared.types import AppType


class HistorySessionKey(BaseModel):
    profile_id: str = Field(alias="profileId")
    canonical_document_url: str = Field(alias="canonicalDocumentUrl")
    app_type: AppType = Field(alias="appType")

    model_config = {"populate_by_name": True}


class HistoryMessage(BaseModel):
    role: str
    text: str
    provider: str | None = None
    model: str | None = None


class HistoryEvent(BaseModel):
    event_type: str = Field(alias="eventType")
    payload: dict[str, object] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}
