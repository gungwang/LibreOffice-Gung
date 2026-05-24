from loaia_shared.schema.plans import ExecutionPlan, ExpectedObservation, ObservationReport, PlanStep
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


def test_evaluator_prefers_expected_probe_over_outcome_label() -> None:
    plan = ExecutionPlan(
        sessionId="sess-1",
        goal="Rewrite and continue",
        steps=[
            PlanStep(
                stepId="step-1",
                capabilityId="Writer.ReplaceSelection",
                descriptorHash="abc123",
                expectedObservation=ExpectedObservation(
                    probe="selection.equals_preview_after",
                    value="HELLO WORLD",
                ),
                onFailure="replan",
            ),
            PlanStep(
                stepId="step-2",
                capabilityId="Writer.ToggleBold",
                descriptorHash="def456",
                onFailure="replan",
            ),
        ],
    )
    observation = ObservationReport(
        sessionId="sess-1",
        stepId="step-1",
        outcome="failed",
        postconditions=[
            {
                "probe": "selection.equals_preview_after",
                "status": "passed",
                "actual": "HELLO WORLD",
                "expected": "HELLO WORLD",
            }
        ],
        summary="Applied Writer.ReplaceSelection",
    )

    decision = evaluate_observation(plan, observation)

    assert decision.action == "continue"
    assert decision.next_step_id == "step-2"


def test_evaluator_replans_when_expected_probe_mismatches_even_if_outcome_satisfied() -> None:
    plan = ExecutionPlan(
        sessionId="sess-1",
        goal="Create chart",
        steps=[
            PlanStep(
                stepId="step-1",
                capabilityId="Calc.CreateChartFromSelection",
                descriptorHash="abc123",
                expectedObservation=ExpectedObservation(
                    probe="summary.matches_argument.chartType",
                    value="Pie",
                ),
                onFailure="replan",
            )
        ],
    )
    observation = ObservationReport(
        sessionId="sess-1",
        stepId="step-1",
        outcome="satisfied",
        preconditions=[
            {
                "probe": "selection.non_empty",
                "status": "passed",
                "actual": True,
                "expected": True,
            }
        ],
        postconditions=[
            {
                "probe": "summary.matches_argument.chartType",
                "status": "failed",
                "actual": "Bar",
                "expected": "Pie",
            }
        ],
        summary="Inserted chart (type hint: Bar) from selection.",
    )

    decision = evaluate_observation(plan, observation)

    assert decision.action == "replan"


def test_evaluator_replans_when_preconditions_fail() -> None:
    plan = ExecutionPlan(
        sessionId="sess-1",
        goal="Sort data",
        steps=[
            PlanStep(
                stepId="step-1",
                capabilityId="Calc.SortSelectedRange",
                descriptorHash="abc123",
                onFailure="replan",
            )
        ],
    )
    observation = ObservationReport(
        sessionId="sess-1",
        stepId="step-1",
        outcome="satisfied",
        preconditions=[
            {
                "probe": "selection.non_empty",
                "status": "failed",
                "actual": False,
                "expected": True,
            }
        ],
        summary="Sorted selected range (ascending).",
    )

    decision = evaluate_observation(plan, observation)

    assert decision.action == "replan"