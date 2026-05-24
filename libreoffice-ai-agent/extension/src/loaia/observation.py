from __future__ import annotations

import re

from loaia.context.impress import read_current_slide_layout, read_last_slide_text
from loaia_shared.capabilities.compiler import get_capability_descriptor
from loaia_shared.schema.plans import ProbeResult


def build_observation_results(
    proposal: object,
    *,
    selection_before: str | None,
    selection_after: str | None,
    summary: str = "",
    controller: object | None = None,
) -> tuple[list[ProbeResult], list[ProbeResult], str]:
    descriptor = get_capability_descriptor(_descriptor_tool_id(proposal))
    if descriptor is None:
        return [], [], "satisfied"

    preconditions = [
        _evaluate_probe(
            probe,
            proposal,
            selection_before,
            selection_after,
            summary,
            controller,
            stage="pre",
        )
        for probe in descriptor.precondition_probes
    ]
    postconditions = [
        _evaluate_probe(
            probe,
            proposal,
            selection_before,
            selection_after,
            summary,
            controller,
            stage="post",
        )
        for probe in descriptor.postcondition_probes
    ]
    return preconditions, postconditions, _derive_outcome(
        preconditions,
        postconditions,
        selection_before=selection_before,
        selection_after=selection_after,
    )


def expected_value_for_probe(proposal: object, probe: str) -> object | None:
    if probe == "selection.non_empty":
        return True
    if probe == "selection.equals_preview_after":
        preview = getattr(proposal, "preview", None)
        return getattr(preview, "after", None)
    if ".equals_argument." in probe:
        _, _, argument_name = probe.rpartition(".equals_argument.")
        arguments = getattr(proposal, "arguments", {})
        if isinstance(arguments, dict):
            return arguments.get(argument_name)
    if probe.startswith("summary.matches_argument."):
        argument_name = probe.removeprefix("summary.matches_argument.")
        arguments = getattr(proposal, "arguments", {})
        if isinstance(arguments, dict):
            return arguments.get(argument_name)
    return None


def _evaluate_probe(
    probe: str,
    proposal: object,
    selection_before: str | None,
    selection_after: str | None,
    summary: str,
    controller: object | None,
    *,
    stage: str,
) -> ProbeResult:
    actual = _actual_value_for_probe(
        probe,
        selection_before=selection_before,
        selection_after=selection_after,
        summary=summary,
        controller=controller,
        stage=stage,
    )
    expected = expected_value_for_probe(proposal, probe)
    status = "passed" if actual == expected else "failed"
    return ProbeResult(probe=probe, status=status, actual=actual, expected=expected)


def _actual_value_for_probe(
    probe: str,
    *,
    selection_before: str | None,
    selection_after: str | None,
    summary: str,
    controller: object | None,
    stage: str,
) -> object | None:
    if probe == "selection.non_empty":
        text = selection_before if stage == "pre" else selection_after
        return bool(text and text.strip())
    if probe == "selection.equals_preview_after":
        return selection_after
    if probe.startswith("selection.equals_argument."):
        return selection_after
    if probe == "impress.current_slide_layout.equals_argument.layout":
        if controller is None:
            return None
        return read_current_slide_layout(controller)
    if probe == "impress.last_slide_text.equals_argument.outline":
        if controller is None:
            return None
        return read_last_slide_text(controller)
    if probe == "summary.matches_argument.chartType":
        match = re.search(r"type hint:\s*([^\)]+)", summary, flags=re.IGNORECASE)
        return match.group(1).strip() if match is not None else None
    if probe == "summary.matches_argument.layout":
        match = re.search(r"Applied layout\s+(-?\d+)", summary, flags=re.IGNORECASE)
        return int(match.group(1)) if match is not None else None
    if probe == "summary.matches_argument.sortDirection":
        match = re.search(
            r"Sorted selected range\s*\((ascending|descending)\)",
            summary,
            flags=re.IGNORECASE,
        )
        return match.group(1).casefold() if match is not None else None
    if probe == "summary.matches_argument.outlineLength":
        match = re.search(r"outline\s*\((\d+)\s+chars\)", summary, flags=re.IGNORECASE)
        return int(match.group(1)) if match is not None else None
    return None


def _derive_outcome(
    preconditions: list[ProbeResult],
    postconditions: list[ProbeResult],
    *,
    selection_before: str | None,
    selection_after: str | None,
) -> str:
    if any(result.status != "passed" for result in preconditions):
        return "failed"

    if not postconditions:
        return "satisfied"

    passed_postconditions = [result for result in postconditions if result.status == "passed"]
    if len(passed_postconditions) == len(postconditions):
        return "satisfied"

    if not passed_postconditions and selection_before == selection_after:
        return "unchanged"

    return "partial"


def _descriptor_tool_id(proposal: object) -> str:
    tool_id = getattr(proposal, "tool_id", "")
    if tool_id != "App.ExecuteUnoCommand":
        return str(tool_id)

    arguments = getattr(proposal, "arguments", {})
    if isinstance(arguments, dict):
        target_tool_id = arguments.get("targetToolId")
        if isinstance(target_tool_id, str) and target_tool_id:
            return target_tool_id

    return str(tool_id)