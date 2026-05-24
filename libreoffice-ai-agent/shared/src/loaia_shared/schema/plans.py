from pydantic import BaseModel, Field

from loaia_shared.schema.actions import ActionPreview, ToolProposal


class ExpectedObservation(BaseModel):
    probe: str
    comparison: str = "equals"
    value: object | None = None


class PlanStep(BaseModel):
    step_id: str = Field(alias="stepId")
    capability_id: str = Field(alias="capabilityId")
    descriptor_hash: str = Field(alias="descriptorHash")
    arguments: dict[str, object] = Field(default_factory=dict)
    preview: ActionPreview | None = None
    target_scope: str = Field(default="selection", alias="targetScope")
    approval_mode: str = Field(default="auto", alias="approvalMode")
    expected_observation: ExpectedObservation | None = Field(
        default=None,
        alias="expectedObservation",
    )
    on_failure: str = Field(default="stop", alias="onFailure")

    model_config = {"populate_by_name": True}


class ExecutionPlan(BaseModel):
    type: str = "ExecutionPlan"
    session_id: str = Field(alias="sessionId")
    goal: str
    steps: list[PlanStep]

    model_config = {"populate_by_name": True}


class ProbeResult(BaseModel):
    probe: str
    status: str
    actual: object | None = None
    expected: object | None = None


class ObservationReport(BaseModel):
    type: str = "ObservationReport"
    session_id: str = Field(alias="sessionId")
    step_id: str = Field(alias="stepId")
    outcome: str
    preconditions: list[ProbeResult] = Field(default_factory=list)
    postconditions: list[ProbeResult] = Field(default_factory=list)
    summary: str = ""

    model_config = {"populate_by_name": True}


class PlanRevision(BaseModel):
    type: str = "PlanRevision"
    session_id: str = Field(alias="sessionId")
    action: str
    reason: str
    next_step_id: str | None = Field(default=None, alias="nextStepId")
    next_proposal: ToolProposal | None = Field(default=None, alias="nextProposal")

    model_config = {"populate_by_name": True}