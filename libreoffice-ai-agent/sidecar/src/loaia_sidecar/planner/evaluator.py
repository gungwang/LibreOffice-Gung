from __future__ import annotations

from dataclasses import dataclass

from loaia_shared.schema.plans import (
    ExecutionPlan,
    ExpectedObservation,
    ObservationReport,
    PlanStep,
    ProbeResult,
)


@dataclass(frozen=True, slots=True)
class ReplanDecision:
    action: str
    reason: str
    next_step_id: str | None = None


def evaluate_observation(plan: ExecutionPlan, observation: ObservationReport) -> ReplanDecision:
    step = _find_step(plan, observation.step_id)
    if step is None:
        return ReplanDecision(
            action="stop",
            reason="The observed plan step could not be found in the execution plan.",
        )

    probe_decision = _evaluate_probe_evidence(plan, step, observation)
    if probe_decision is not None:
        return probe_decision

    if observation.outcome == "satisfied":
        return _success_decision(plan, observation.step_id)

    if observation.outcome in {"failed", "unchanged", "partial"}:
        return _failure_decision(
            step,
            "Observed outcome did not satisfy the current plan step.",
        )

    return ReplanDecision(
        action="stop",
        reason="Observation result is unknown or unsupported.",
    )


def _evaluate_probe_evidence(
    plan: ExecutionPlan,
    step: PlanStep,
    observation: ObservationReport,
) -> ReplanDecision | None:
    failed_preconditions = [
        result.probe for result in observation.preconditions if result.status != "passed"
    ]
    if failed_preconditions:
        return _failure_decision(
            step,
            "Step preconditions failed: " + ", ".join(failed_preconditions) + ".",
        )

    if step.expected_observation is not None:
        probe_result = _find_probe_result(
            observation.postconditions,
            step.expected_observation.probe,
        )
        if probe_result is None:
            return _failure_decision(
                step,
                (
                    "Expected observation probe "
                    f"{step.expected_observation.probe!r} was not reported."
                ),
            )

        if not _probe_matches_expected(step.expected_observation, probe_result):
            return _failure_decision(
                step,
                (
                    "Expected observation probe "
                    f"{step.expected_observation.probe!r} did not match: "
                    f"expected {step.expected_observation.value!r}, got {probe_result.actual!r}."
                ),
            )

        return _success_decision(plan, observation.step_id)

    if not observation.postconditions:
        return None

    failed_postconditions = [
        result.probe for result in observation.postconditions if result.status != "passed"
    ]
    if failed_postconditions:
        return _failure_decision(
            step,
            "Step postconditions failed: " + ", ".join(failed_postconditions) + ".",
        )

    return _success_decision(plan, observation.step_id)


def _probe_matches_expected(
    expected_observation: ExpectedObservation,
    probe_result: ProbeResult,
) -> bool:
    comparison = expected_observation.comparison.casefold()
    if comparison == "equals":
        return probe_result.actual == expected_observation.value

    if comparison == "not-equals":
        return probe_result.actual != expected_observation.value

    return False


def _success_decision(plan: ExecutionPlan, step_id: str) -> ReplanDecision:
    next_step = _find_next_step_id(plan, step_id)
    if next_step is None:
        return ReplanDecision(action="complete", reason="All planned steps satisfied.")

    return ReplanDecision(
        action="continue",
        reason="Current step satisfied its expected observation.",
        next_step_id=next_step,
    )


def _failure_decision(step: PlanStep, reason: str) -> ReplanDecision:
    if step.on_failure == "replan":
        return ReplanDecision(
            action="replan",
            reason=reason,
        )

    return ReplanDecision(
        action="stop",
        reason=reason,
    )


def _find_step(plan: ExecutionPlan, step_id: str) -> PlanStep | None:
    for step in plan.steps:
        if step.step_id == step_id:
            return step
    return None


def _find_probe_result(results: list[ProbeResult], probe: str) -> ProbeResult | None:
    for result in results:
        if result.probe == probe:
            return result
    return None


def _find_next_step_id(plan: ExecutionPlan, step_id: str) -> str | None:
    for index, step in enumerate(plan.steps):
        if step.step_id != step_id:
            continue
        if index + 1 >= len(plan.steps):
            return None
        return plan.steps[index + 1].step_id
    return None