from loaia_shared.schema.plans import ExecutionPlan, ObservationReport, PlanStep
from loaia_shared.types import AppType
from loaia_sidecar.planner.evaluator import evaluate_observation
from loaia_sidecar.planner.retriever import CapabilityRetriever


def test_retriever_prefers_writer_rewrite_capability_for_rewrite_prompt() -> None:
    retriever = CapabilityRetriever()

    candidates = retriever.search(
        app=AppType.WRITER,
        query="Rewrite this selection in a more formal tone.",
        limit=3,
    )

    assert candidates
    assert candidates[0].descriptor.tool_id == "Writer.ReplaceSelection"


def test_evaluator_requests_replan_when_observation_fails() -> None:
    plan = ExecutionPlan(
        sessionId="sess-1",
        goal="Create a chart",
        steps=[
            PlanStep(
                stepId="step-1",
                capabilityId="Calc.CreateChartFromSelection",
                descriptorHash="abc123",
                onFailure="replan",
            )
        ],
    )
    observation = ObservationReport(
        sessionId="sess-1",
        stepId="step-1",
        outcome="failed",
        summary="Chart count did not change.",
    )

    decision = evaluate_observation(plan, observation)

    assert decision.action == "replan"