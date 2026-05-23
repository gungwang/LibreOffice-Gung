"""Safe formatting action executor.

Maps tool IDs to UNO dispatch commands and executes them against the current
document frame. Safe formatting actions auto-apply without preview or approval.
"""

from __future__ import annotations

# Maps tool IDs to their corresponding UNO dispatch command URLs.
TOOL_UNO_DISPATCH_MAP: dict[str, str] = {
    # Writer - basic formatting
    "Writer.ToggleBold": ".uno:Bold",
    "Writer.ToggleItalic": ".uno:Italic",
    "Writer.ToggleUnderline": ".uno:Underline",
    "Writer.ToggleStrikethrough": ".uno:Strikeout",
    "Writer.ToggleSuperscript": ".uno:SuperScript",
    "Writer.ToggleSubscript": ".uno:SubScript",
    # Writer - headings
    "Writer.ApplyHeading1": ".uno:StyleApply",
    "Writer.ApplyHeading2": ".uno:StyleApply",
    "Writer.ApplyHeading3": ".uno:StyleApply",
    "Writer.ApplyDefaultStyle": ".uno:StyleApply",
    # Writer - alignment
    "Writer.AlignLeft": ".uno:LeftPara",
    "Writer.AlignCenter": ".uno:CenterPara",
    "Writer.AlignRight": ".uno:RightPara",
    "Writer.AlignJustify": ".uno:JustifyPara",
    # Writer - lists
    "Writer.ApplyBullets": ".uno:DefaultBulletList",
    "Writer.ApplyNumbering": ".uno:DefaultNumberingList",
    # Writer - indentation
    "Writer.IncreaseIndent": ".uno:IncrementIndent",
    "Writer.DecreaseIndent": ".uno:DecrementIndent",
    # Writer - line spacing
    "Writer.LineSpacingSingle": ".uno:SpacePara1",
    "Writer.LineSpacing1_5": ".uno:SpacePara15",
    "Writer.LineSpacingDouble": ".uno:SpacePara2",
    # Writer - font size
    "Writer.IncreaseFontSize": ".uno:Grow",
    "Writer.DecreaseFontSize": ".uno:Shrink",
    # Writer - font color (parametric — handled in execute)
    "Writer.FontColorRed": ".uno:Color",
    "Writer.FontColorBlue": ".uno:Color",
    "Writer.FontColorGreen": ".uno:Color",
    "Writer.FontColorBlack": ".uno:Color",
    "Writer.FontColorWhite": ".uno:Color",
    "Writer.FontColorOrange": ".uno:Color",
    "Writer.FontColorPurple": ".uno:Color",
    "Writer.FontColorYellow": ".uno:Color",
    # Writer - highlight / background color
    "Writer.HighlightYellow": ".uno:BackColor",
    "Writer.HighlightGreen": ".uno:BackColor",
    "Writer.HighlightRed": ".uno:BackColor",
    "Writer.HighlightBlue": ".uno:BackColor",
    "Writer.HighlightNone": ".uno:BackColor",
    # Writer - clear formatting
    "Writer.ClearFormatting": ".uno:ResetAttributes",
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
    # Draw
    "Draw.ToggleBold": ".uno:Bold",
    "Draw.ToggleItalic": ".uno:Italic",
    "Draw.ToggleUnderline": ".uno:Underline",
    "Draw.AlignLeft": ".uno:LeftPara",
    "Draw.AlignCenter": ".uno:CenterPara",
    "Draw.AlignRight": ".uno:RightPara",
}

# Heading style arguments for Writer.ApplyHeading* actions.
HEADING_STYLE_ARGS: dict[str, str] = {
    "Writer.ApplyHeading1": "Heading 1",
    "Writer.ApplyHeading2": "Heading 2",
    "Writer.ApplyHeading3": "Heading 3",
    "Writer.ApplyDefaultStyle": "Default Paragraph Style",
}

# Color values for font color and highlight tools (as 0xRRGGBB integers).
FONT_COLOR_VALUES: dict[str, int] = {
    "Writer.FontColorRed": 0xFF0000,
    "Writer.FontColorBlue": 0x0000FF,
    "Writer.FontColorGreen": 0x008000,
    "Writer.FontColorBlack": 0x000000,
    "Writer.FontColorWhite": 0xFFFFFF,
    "Writer.FontColorOrange": 0xFF8C00,
    "Writer.FontColorPurple": 0x800080,
    "Writer.FontColorYellow": 0xFFD700,
}

HIGHLIGHT_COLOR_VALUES: dict[str, int] = {
    "Writer.HighlightYellow": 0xFFFF00,
    "Writer.HighlightGreen": 0x00FF00,
    "Writer.HighlightRed": 0xFF0000,
    "Writer.HighlightBlue": 0x00BFFF,
    "Writer.HighlightNone": 0xFFFFFF,  # effectively "no highlight"
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
    # Heading / paragraph style
    style_name = HEADING_STYLE_ARGS.get(tool_id)
    if style_name is not None:
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

    # Font color
    color_value = FONT_COLOR_VALUES.get(tool_id)
    if color_value is not None:
        try:
            from com.sun.star.beans import PropertyValue  # type: ignore[import]

            prop = PropertyValue()
            prop.Name = "FontColor.Color"
            prop.Value = color_value
            return (prop,)
        except ImportError:
            return ()

    # Highlight / background color
    highlight_value = HIGHLIGHT_COLOR_VALUES.get(tool_id)
    if highlight_value is not None:
        try:
            from com.sun.star.beans import PropertyValue  # type: ignore[import]

            prop = PropertyValue()
            prop.Name = "BackColor.Color"
            prop.Value = highlight_value
            return (prop,)
        except ImportError:
            return ()

    return ()


def _get_dispatch_helper() -> object:
    """Get the global UNO dispatch helper service."""
    try:
        import uno  # type: ignore[import]

        ctx = uno.getComponentContext()
        smgr = ctx.ServiceManager
        return smgr.createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", ctx
        )
    except ImportError as exc:
        raise RuntimeError("UNO runtime is not available for safe formatting dispatch") from exc
