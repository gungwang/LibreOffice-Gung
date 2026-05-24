from __future__ import annotations

from dataclasses import dataclass

from loaia_shared.schema.plans import ExecutionPlan, ObservationReport


@dataclass(frozen=True, slots=True)
class ReplanDecision:
    action: str
    reason: str
    next_step_id: str | None = None


def evaluate_observation(plan: ExecutionPlan, observation: ObservationReport) -> ReplanDecision:
    if observation.outcome == "satisfied":
        next_step = _find_next_step_id(plan, observation.step_id)
        if next_step is None:
            return ReplanDecision(action="complete", reason="All planned steps satisfied.")
        return ReplanDecision(
            action="continue",
            reason="Current step satisfied its expected observation.",
            next_step_id=next_step,
        )

    if observation.outcome in {"failed", "unchanged", "partial"}:
        return ReplanDecision(
            action="replan",
            reason="Observed outcome did not satisfy the current plan step.",
        )

    return ReplanDecision(
        action="stop",
        reason="Observation result is unknown or unsupported.",
    )


def _find_next_step_id(plan: ExecutionPlan, step_id: str) -> str | None:
    for index, step in enumerate(plan.steps):
        if step.step_id != step_id:
            continue
        if index + 1 >= len(plan.steps):
            return None
        return plan.steps[index + 1].step_id
    return None