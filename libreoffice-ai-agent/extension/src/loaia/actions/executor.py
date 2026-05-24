"""Catalog-backed UNO dispatch executor."""

from __future__ import annotations

from loaia_shared.capabilities.compiler import (
    get_compiled_capabilities,
    get_dispatch_alias_map,
    get_dispatch_tool_map,
    get_safe_formatting_tool_ids,
)

TOOL_UNO_DISPATCH_MAP: dict[str, str] = get_dispatch_tool_map()
SAFE_FORMATTING_TOOL_IDS = get_safe_formatting_tool_ids()
DISPATCH_ALIAS_TO_TOOL_ID = get_dispatch_alias_map()
COMMAND_TO_TOOL_ID = {command: tool_id for tool_id, command in TOOL_UNO_DISPATCH_MAP.items()}


def is_safe_formatting_action(tool_id: str) -> bool:
    return tool_id in SAFE_FORMATTING_TOOL_IDS


def can_execute_via_dispatch(tool_id: str) -> bool:
    return tool_id in TOOL_UNO_DISPATCH_MAP


def execute_safe_formatting(frame: object, tool_id: str, **kwargs: object) -> str:
    if not is_safe_formatting_action(tool_id):
        raise ValueError(f"{tool_id} is not classified as safe formatting")
    return execute_dispatch_action(frame, tool_id, **kwargs)


def execute_dispatch_action(frame: object, tool_id: str, **kwargs: object) -> str:
    dispatch_url = TOOL_UNO_DISPATCH_MAP.get(tool_id)
    if dispatch_url is None:
        raise ValueError(f"Unknown catalog-backed UNO dispatch action: {tool_id}")

    dispatch_helper = _get_dispatch_helper()
    args = _build_dispatch_args(tool_id, **kwargs)
    dispatch_helper.executeDispatch(frame, dispatch_url, "", 0, args)
    return f"Applied {tool_id}"


def execute_uno_command(
    frame: object,
    *,
    target_tool_id: str | None = None,
    dispatch_alias: str | None = None,
    command: str | None = None,
    arguments: dict[str, object] | None = None,
) -> str:
    resolved_tool_id = _resolve_tool_id(
        target_tool_id=target_tool_id,
        dispatch_alias=dispatch_alias,
        command=command,
    )
    forwarded_arguments = dict(arguments or {})
    return execute_dispatch_action(frame, resolved_tool_id, **forwarded_arguments)


def _resolve_tool_id(
    *,
    target_tool_id: str | None,
    dispatch_alias: str | None,
    command: str | None,
) -> str:
    if isinstance(target_tool_id, str) and can_execute_via_dispatch(target_tool_id):
        return target_tool_id

    if isinstance(dispatch_alias, str):
        aliased_tool_id = DISPATCH_ALIAS_TO_TOOL_ID.get(dispatch_alias)
        if aliased_tool_id is not None:
            return aliased_tool_id

    if isinstance(command, str):
        whitelisted_tool_id = COMMAND_TO_TOOL_ID.get(command)
        if whitelisted_tool_id is not None:
            return whitelisted_tool_id

    raise ValueError("ExecuteUnoCommand requires a catalog-backed toolId, dispatchAlias, or command")


def _build_dispatch_args(tool_id: str, **kwargs: object) -> tuple:
    compiled = get_compiled_capabilities().get(tool_id)
    if compiled is None:
        return ()

    binding = compiled.descriptor.binding
    preset = binding.argument_preset
    preset_value = binding.argument_value
    if preset == "style-template":
        return _build_style_template_args(str(kwargs.get("styleName", preset_value)))
    if preset == "font-color":
        return _build_single_property_args("FontColor.Color", int(kwargs.get("colorValue", preset_value)))
    if preset == "char-back-color":
        return _build_single_property_args("CharBackColor.Color", int(kwargs.get("colorValue", preset_value)))
    if preset == "background-color":
        return _build_single_property_args("BackgroundColor.Color", int(kwargs.get("colorValue", preset_value)))
    if preset == "font-height":
        return _build_single_property_args(
            "FontHeight.Height",
            float(str(kwargs.get("fontSize", preset_value))),
        )
    if preset == "font-family":
        return _build_single_property_args(
            "CharFontName.FamilyName",
            str(kwargs.get("fontName", preset_value)),
        )
    return ()


def _build_style_template_args(style_name: str) -> tuple:
    try:
        from com.sun.star.beans import PropertyValue  # type: ignore[import]

        prop = PropertyValue()
        prop.Name = "Template"
        prop.Value = style_name

        family_prop = PropertyValue()
        family_prop.Name = "Family"
        family_prop.Value = 1
        return (prop, family_prop)
    except ImportError:
        return ()


def _build_single_property_args(name: str, value: object) -> tuple:
    try:
        from com.sun.star.beans import PropertyValue  # type: ignore[import]

        prop = PropertyValue()
        prop.Name = name
        prop.Value = value
        return (prop,)
    except ImportError:
        return ()


def _get_dispatch_helper() -> object:
    try:
        import uno  # type: ignore[import]

        ctx = uno.getComponentContext()
        smgr = ctx.ServiceManager
        return smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
    except ImportError as exc:
        raise RuntimeError("UNO runtime is not available for catalog-backed dispatch") from exc
