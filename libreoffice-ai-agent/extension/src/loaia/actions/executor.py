"""Safe formatting action executor.

Maps tool IDs to UNO dispatch commands and executes them against the current
document frame. Safe formatting actions auto-apply without preview or approval.
"""

from __future__ import annotations

# Maps tool IDs to their corresponding UNO dispatch command URLs.
TOOL_UNO_DISPATCH_MAP: dict[str, str] = {
    # Writer
    "Writer.ToggleBold": ".uno:Bold",
    "Writer.ToggleItalic": ".uno:Italic",
    "Writer.ToggleUnderline": ".uno:Underline",
    "Writer.ApplyHeading1": ".uno:StyleApply",
    "Writer.ApplyHeading2": ".uno:StyleApply",
    "Writer.ApplyHeading3": ".uno:StyleApply",
    "Writer.ApplyBullets": ".uno:DefaultBulletList",
    "Writer.AlignLeft": ".uno:LeftPara",
    "Writer.AlignCenter": ".uno:CenterPara",
    "Writer.AlignRight": ".uno:RightPara",
    # Calc
    "Calc.ToggleBold": ".uno:Bold",
    "Calc.ToggleItalic": ".uno:Italic",
    "Calc.AlignLeft": ".uno:AlignLeft",
    "Calc.AlignCenter": ".uno:AlignHorizontalCenter",
    "Calc.AlignRight": ".uno:AlignRight",
    "Calc.ApplyNumberFormatCurrency": ".uno:NumberFormatCurrency",
    "Calc.ApplyNumberFormatPercent": ".uno:NumberFormatPercent",
    "Calc.ApplyNumberFormatDate": ".uno:NumberFormatDate",
    # Impress
    "Impress.ToggleBold": ".uno:Bold",
    "Impress.ToggleItalic": ".uno:Italic",
    "Impress.ApplyBullets": ".uno:DefaultBulletList",
    "Impress.AlignLeft": ".uno:LeftPara",
    "Impress.AlignCenter": ".uno:CenterPara",
    "Impress.AlignRight": ".uno:RightPara",
}

# Heading style arguments for Writer.ApplyHeading* actions.
HEADING_STYLE_ARGS: dict[str, str] = {
    "Writer.ApplyHeading1": "Heading 1",
    "Writer.ApplyHeading2": "Heading 2",
    "Writer.ApplyHeading3": "Heading 3",
}

SAFE_FORMATTING_TOOL_IDS = frozenset(TOOL_UNO_DISPATCH_MAP.keys())


def is_safe_formatting_action(tool_id: str) -> bool:
    return tool_id in SAFE_FORMATTING_TOOL_IDS


def execute_safe_formatting(frame: object, tool_id: str) -> str:
    """Execute a safe formatting action via UNO dispatch on the given frame.

    Returns a human-readable result message.
    Raises ValueError if the tool_id is not a recognized safe formatting action.
    """
    dispatch_url = TOOL_UNO_DISPATCH_MAP.get(tool_id)
    if dispatch_url is None:
        raise ValueError(f"Unknown safe formatting action: {tool_id}")

    dispatch_helper = _get_dispatch_helper()
    args = _build_dispatch_args(tool_id)
    dispatch_helper.executeDispatch(frame, dispatch_url, "", 0, args)
    return f"Applied {tool_id}"


def _build_dispatch_args(tool_id: str) -> tuple:
    """Build UNO PropertyValue arguments for dispatch commands that need them."""
    style_name = HEADING_STYLE_ARGS.get(tool_id)
    if style_name is None:
        return ()

    try:
        from com.sun.star.beans import PropertyValue  # type: ignore[import]

        prop = PropertyValue()
        prop.Name = "Template"
        prop.Value = style_name

        family_prop = PropertyValue()
        family_prop.Name = "Family"
        family_prop.Value = 1  # ParagraphStyles family

        return (prop, family_prop)
    except ImportError:
        return ()


def _get_dispatch_helper() -> object:
    """Get the global UNO dispatch helper service."""
    try:
        import uno  # type: ignore[import]
        from com.sun.star.frame import DispatchHelper  # type: ignore[import]  # noqa: F401

        ctx = uno.getComponentContext()
        smgr = ctx.ServiceManager
        return smgr.createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", ctx
        )
    except ImportError as exc:
        raise RuntimeError("UNO runtime is not available for safe formatting dispatch") from exc
