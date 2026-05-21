from enum import StrEnum

from pydantic import BaseModel, Field


class SafetyClass(StrEnum):
    READ_ONLY = "read-only"
    SAFE_FORMATTING = "safe-formatting"
    CONTENT_EDIT = "content-edit"
    DESTRUCTIVE = "destructive"


class ActionPreview(BaseModel):
    summary: str
    before: str | None = None
    after: str | None = None


class ToolProposal(BaseModel):
    proposal_id: str = Field(alias="proposalId")
    tool_id: str = Field(alias="toolId")
    safety_class: SafetyClass = Field(alias="safetyClass")
    requires_approval: bool = Field(alias="requiresApproval")
    preview: ActionPreview | None = None
    arguments: dict[str, object] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}
