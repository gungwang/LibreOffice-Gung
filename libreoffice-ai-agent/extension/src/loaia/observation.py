from __future__ import annotations

import re

from loaia.context.calc import read_active_sheet_chart_count, read_selection_first_column_order
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
    state_before: dict[str, object] | None = None,
    state_after: dict[str, object] | None = None,
) -> tuple[list[ProbeResult], list[ProbeResult], str]:
    descriptor = get_capability_descriptor(_descriptor_tool_id(proposal))
    if descriptor is None:
        return [], [], "satisfied"

    effective_state_before = state_before
    effective_state_after = state_after
    if controller is not None and effective_state_before is None:
        effective_state_before = capture_observation_state(proposal, controller)
    if controller is not None and effective_state_after is None:
        effective_state_after = capture_observation_state(proposal, controller)

    preconditions = [
        _evaluate_probe(
            probe,
            proposal,
            selection_before,
            selection_after,
            summary,
            controller,
            effective_state_before,
            effective_state_after,
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
            effective_state_before,
            effective_state_after,
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


def capture_observation_state(
    proposal: object,
    controller: object | None,
) -> dict[str, object]:
    if controller is None:
        return {}

    state: dict[str, object] = {}
    tool_id = _descriptor_tool_id(proposal)

    if tool_id == "Calc.CreateChartFromSelection":
        chart_count = read_active_sheet_chart_count(controller)
        if chart_count is not None:
            state["calc.active_sheet_chart_count"] = chart_count

    if tool_id == "Calc.SortSelectedRange":
        order = read_selection_first_column_order(controller)
        if order is not None:
            state["calc.selection_first_column_order"] = order

    return state


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
    state_before: dict[str, object] | None,
    state_after: dict[str, object] | None,
    *,
    stage: str,
) -> ProbeResult:
    actual = _actual_value_for_probe(
        probe,
        selection_before=selection_before,
        selection_after=selection_after,
        summary=summary,
        controller=controller,
        state_before=state_before,
        state_after=state_after,
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
    state_before: dict[str, object] | None,
    state_after: dict[str, object] | None,
    stage: str,
) -> object | None:
    if probe == "selection.non_empty":
        text = selection_before if stage == "pre" else selection_after
        return bool(text and text.strip())
    if probe == "selection.equals_preview_after":
        return selection_after
    if probe.startswith("selection.equals_argument."):
        return selection_after
    if probe == "calc.active_sheet_chart_count.delta.equals_argument.chartCountDelta":
        before_count = _state_int_value(state_before, "calc.active_sheet_chart_count")
        after_count = _state_int_value(state_after, "calc.active_sheet_chart_count")
        if before_count is None or after_count is None:
            return None
        return after_count - before_count
    if probe == "calc.selection_first_column_order.equals_argument.sortDirection":
        return _state_string_value(state_after, "calc.selection_first_column_order")
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


def _state_int_value(state: dict[str, object] | None, key: str) -> int | None:
    if state is None:
        return None
    value = state.get(key)
    return int(value) if isinstance(value, int) else None


def _state_string_value(state: dict[str, object] | None, key: str) -> str | None:
    if state is None:
        return None
    value = state.get(key)
    return value if isinstance(value, str) else None


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