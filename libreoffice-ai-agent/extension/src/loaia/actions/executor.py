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
    "Writer.ToggleShadow": ".uno:Shadowed",
    "Writer.ToggleOutline": ".uno:OutlineFont",
    "Writer.ToggleSmallCaps": ".uno:SmallCaps",
    # Writer - text case
    "Writer.CaseUpper": ".uno:ChangeCaseToUpper",
    "Writer.CaseLower": ".uno:ChangeCaseToLower",
    "Writer.CaseTitle": ".uno:ChangeCaseToTitleCase",
    "Writer.CaseSentence": ".uno:ChangeCaseToSentenceCase",
    "Writer.CaseToggle": ".uno:ChangeCaseToToggleCase",
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
    # Writer - paragraph spacing
    "Writer.IncreaseParaSpacing": ".uno:ParaspaceIncrease",
    "Writer.DecreaseParaSpacing": ".uno:ParaspaceDecrease",
    # Writer - font size
    "Writer.IncreaseFontSize": ".uno:Grow",
    "Writer.DecreaseFontSize": ".uno:Shrink",
    "Writer.SetFontSize": ".uno:FontHeight",
    # Writer - font name
    "Writer.SetFontName": ".uno:CharFontName",
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
    "Writer.HighlightYellow": ".uno:CharBackColor",
    "Writer.HighlightGreen": ".uno:CharBackColor",
    "Writer.HighlightRed": ".uno:CharBackColor",
    "Writer.HighlightBlue": ".uno:CharBackColor",
    "Writer.HighlightNone": ".uno:CharBackColor",
    # Writer - clear formatting
    "Writer.ClearFormatting": ".uno:ResetAttributes",
    # Writer - insert operations
    "Writer.InsertPageBreak": ".uno:InsertPagebreak",
    "Writer.InsertColumnBreak": ".uno:InsertColumnBreak",
    "Writer.InsertSpecialChar": ".uno:InsertSymbol",
    "Writer.InsertHyperlink": ".uno:HyperlinkDialog",
    "Writer.InsertComment": ".uno:InsertAnnotation",
    "Writer.InsertImage": ".uno:InsertGraphic",
    "Writer.InsertBookmark": ".uno:InsertBookmark",
    "Writer.InsertFootnote": ".uno:InsertFootnote",
    "Writer.InsertEndnote": ".uno:InsertEndnote",
    "Writer.InsertHeader": ".uno:InsertHeader",
    "Writer.InsertFooter": ".uno:InsertFooter",
    "Writer.InsertPageNumber": ".uno:InsertPageNumberField",
    "Writer.InsertDateField": ".uno:InsertDateField",
    "Writer.InsertTimeField": ".uno:InsertTimeField",
    # Writer - clipboard/edit
    "Writer.FormatPaintbrush": ".uno:FormatPaintbrush",
    "Writer.SelectAll": ".uno:SelectAll",
    "Writer.Undo": ".uno:Undo",
    "Writer.Redo": ".uno:Redo",
    # Writer - find
    "Writer.FindReplace": ".uno:SearchDialog",
    "Writer.WordCount": ".uno:WordCountDialog",
    "Writer.SpellCheck": ".uno:SpellingAndGrammarDialog",
    # Calc - basic formatting
    "Calc.ToggleBold": ".uno:Bold",
    "Calc.ToggleItalic": ".uno:Italic",
    "Calc.ToggleUnderline": ".uno:Underline",
    "Calc.ToggleStrikethrough": ".uno:Strikeout",
    # Calc - alignment
    "Calc.AlignLeft": ".uno:AlignLeft",
    "Calc.AlignCenter": ".uno:AlignHorizontalCenter",
    "Calc.AlignRight": ".uno:AlignRight",
    "Calc.AlignTop": ".uno:AlignTop",
    "Calc.AlignVCenter": ".uno:AlignVCenter",
    "Calc.AlignBottom": ".uno:AlignBottom",
    "Calc.WrapText": ".uno:WrapText",
    # Calc - number formats
    "Calc.ApplyNumberFormatCurrency": ".uno:NumberFormatCurrency",
    "Calc.ApplyNumberFormatPercent": ".uno:NumberFormatPercent",
    "Calc.ApplyNumberFormatDate": ".uno:NumberFormatDate",
    "Calc.ApplyNumberFormatDecimal": ".uno:NumberFormatDecimal",
    "Calc.ApplyNumberFormatScientific": ".uno:NumberFormatScientific",
    "Calc.IncreaseDecimals": ".uno:NumberFormatIncDecimals",
    "Calc.DecreaseDecimals": ".uno:NumberFormatDecDecimals",
    # Calc - cells
    "Calc.MergeCells": ".uno:ToggleMergeCells",
    "Calc.InsertRowAbove": ".uno:InsertRowsBefore",
    "Calc.InsertRowBelow": ".uno:InsertRowsAfter",
    "Calc.InsertColumnBefore": ".uno:InsertColumnsBefore",
    "Calc.InsertColumnAfter": ".uno:InsertColumnsAfter",
    "Calc.DeleteRows": ".uno:DeleteRows",
    "Calc.DeleteColumns": ".uno:DeleteColumns",
    # Calc - sort/filter
    "Calc.SortAscending": ".uno:SortAscending",
    "Calc.SortDescending": ".uno:SortDescending",
    "Calc.AutoFilter": ".uno:DataFilterAutoFilter",
    # Calc - other
    "Calc.FreezePanes": ".uno:FreezePanes",
    "Calc.AutoSum": ".uno:AutoSum",
    "Calc.InsertComment": ".uno:InsertAnnotation",
    "Calc.InsertImage": ".uno:InsertGraphic",
    "Calc.InsertChart": ".uno:InsertObjectChart",
    "Calc.FontColorRed": ".uno:Color",
    "Calc.FontColorBlue": ".uno:Color",
    "Calc.FontColorGreen": ".uno:Color",
    "Calc.FontColorBlack": ".uno:Color",
    "Calc.BackgroundColorYellow": ".uno:BackgroundColor",
    "Calc.BackgroundColorGreen": ".uno:BackgroundColor",
    "Calc.BackgroundColorRed": ".uno:BackgroundColor",
    "Calc.BackgroundColorBlue": ".uno:BackgroundColor",
    "Calc.BackgroundColorNone": ".uno:BackgroundColor",
    # Impress - formatting
    "Impress.ToggleBold": ".uno:Bold",
    "Impress.ToggleItalic": ".uno:Italic",
    "Impress.ToggleUnderline": ".uno:Underline",
    "Impress.ToggleStrikethrough": ".uno:Strikeout",
    "Impress.ApplyBullets": ".uno:DefaultBulletList",
    "Impress.ApplyNumbering": ".uno:DefaultNumbering",
    "Impress.AlignLeft": ".uno:LeftPara",
    "Impress.AlignCenter": ".uno:CenterPara",
    "Impress.AlignRight": ".uno:RightPara",
    "Impress.AlignJustify": ".uno:JustifyPara",
    "Impress.IncreaseFontSize": ".uno:Grow",
    "Impress.DecreaseFontSize": ".uno:Shrink",
    "Impress.ClearFormatting": ".uno:SetDefault",
    "Impress.FontColorRed": ".uno:Color",
    "Impress.FontColorBlue": ".uno:Color",
    "Impress.FontColorGreen": ".uno:Color",
    "Impress.FontColorBlack": ".uno:Color",
    # Impress - slides
    "Impress.InsertSlide": ".uno:InsertPage",
    "Impress.DuplicateSlide": ".uno:DuplicatePage",
    "Impress.DeleteSlide": ".uno:DeletePage",
    "Impress.StartPresentation": ".uno:Presentation",
    "Impress.StartFromCurrent": ".uno:PresentationCurrentSlide",
    # Impress - insert
    "Impress.InsertImage": ".uno:InsertGraphic",
    "Impress.InsertTable": ".uno:InsertTable",
    "Impress.InsertChart": ".uno:InsertObjectChart",
    "Impress.InsertTextBox": ".uno:Text",
    "Impress.InsertComment": ".uno:InsertAnnotation",
    # Draw - formatting
    "Draw.ToggleBold": ".uno:Bold",
    "Draw.ToggleItalic": ".uno:Italic",
    "Draw.ToggleUnderline": ".uno:Underline",
    "Draw.ToggleStrikethrough": ".uno:Strikeout",
    "Draw.AlignLeft": ".uno:LeftPara",
    "Draw.AlignCenter": ".uno:CenterPara",
    "Draw.AlignRight": ".uno:RightPara",
    "Draw.ClearFormatting": ".uno:SetDefault",
    # Draw - insert
    "Draw.InsertImage": ".uno:InsertGraphic",
    "Draw.InsertTextBox": ".uno:Text",
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
    "Calc.FontColorRed": 0xFF0000,
    "Calc.FontColorBlue": 0x0000FF,
    "Calc.FontColorGreen": 0x008000,
    "Calc.FontColorBlack": 0x000000,
    "Impress.FontColorRed": 0xFF0000,
    "Impress.FontColorBlue": 0x0000FF,
    "Impress.FontColorGreen": 0x008000,
    "Impress.FontColorBlack": 0x000000,
}

HIGHLIGHT_COLOR_VALUES: dict[str, int] = {
    "Writer.HighlightYellow": 0xFFFF00,
    "Writer.HighlightGreen": 0x00FF00,
    "Writer.HighlightRed": 0xFF0000,
    "Writer.HighlightBlue": 0x00BFFF,
    "Writer.HighlightNone": 0xFFFFFFFF,  # COL_AUTO / transparent
}

BACKGROUND_COLOR_VALUES: dict[str, int] = {
    "Calc.BackgroundColorYellow": 0xFFFF00,
    "Calc.BackgroundColorGreen": 0x00FF00,
    "Calc.BackgroundColorRed": 0xFF0000,
    "Calc.BackgroundColorBlue": 0x00BFFF,
    "Calc.BackgroundColorNone": 0xFFFFFFFF,
}

SAFE_FORMATTING_TOOL_IDS = frozenset(TOOL_UNO_DISPATCH_MAP.keys())


def is_safe_formatting_action(tool_id: str) -> bool:
    return tool_id in SAFE_FORMATTING_TOOL_IDS


def execute_safe_formatting(frame: object, tool_id: str, **kwargs: object) -> str:
    """Execute a safe formatting action via UNO dispatch on the given frame.

    Returns a human-readable result message.
    Raises ValueError if the tool_id is not a recognized safe formatting action.
    kwargs can include: fontSize (float), fontName (str) for parametric commands.
    """
    dispatch_url = TOOL_UNO_DISPATCH_MAP.get(tool_id)
    if dispatch_url is None:
        raise ValueError(f"Unknown safe formatting action: {tool_id}")

    dispatch_helper = _get_dispatch_helper()
    args = _build_dispatch_args(tool_id, **kwargs)
    dispatch_helper.executeDispatch(frame, dispatch_url, "", 0, args)
    return f"Applied {tool_id}"


def _build_dispatch_args(tool_id: str, **kwargs: object) -> tuple:
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

    # Character highlight color
    highlight_value = HIGHLIGHT_COLOR_VALUES.get(tool_id)
    if highlight_value is not None:
        try:
            from com.sun.star.beans import PropertyValue  # type: ignore[import]

            prop = PropertyValue()
            prop.Name = "CharBackColor.Color"
            prop.Value = highlight_value
            return (prop,)
        except ImportError:
            return ()

    # Background color (Calc cells)
    bg_value = BACKGROUND_COLOR_VALUES.get(tool_id)
    if bg_value is not None:
        try:
            from com.sun.star.beans import PropertyValue  # type: ignore[import]

            prop = PropertyValue()
            prop.Name = "BackgroundColor.Color"
            prop.Value = bg_value
            return (prop,)
        except ImportError:
            return ()

    # Font size (parametric)
    if tool_id.endswith(".SetFontSize"):
        font_size = kwargs.get("fontSize", 12)
        try:
            from com.sun.star.beans import PropertyValue  # type: ignore[import]

            prop = PropertyValue()
            prop.Name = "FontHeight.Height"
            prop.Value = float(str(font_size))
            return (prop,)
        except ImportError:
            return ()

    # Font name (parametric)
    if tool_id.endswith(".SetFontName"):
        font_name = kwargs.get("fontName", "Arial")
        try:
            from com.sun.star.beans import PropertyValue  # type: ignore[import]

            prop = PropertyValue()
            prop.Name = "CharFontName.FamilyName"
            prop.Value = str(font_name)
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
