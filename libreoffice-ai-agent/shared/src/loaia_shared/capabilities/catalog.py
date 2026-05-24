from __future__ import annotations

from dataclasses import dataclass, field
import re

from loaia_shared.schema.actions import SafetyClass


@dataclass(frozen=True, slots=True)
class CapabilityBinding:
    kind: str = "none"
    dispatch_url: str | None = None
    dispatch_alias: str | None = None
    argument_preset: str | None = None
    argument_value: object | None = None


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    tool_id: str
    app: str
    title: str
    summary: str
    safety_class: SafetyClass
    requires_approval: bool
    binding: CapabilityBinding = field(default_factory=CapabilityBinding)
    intent_tags: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    precondition_probes: tuple[str, ...] = ()
    postcondition_probes: tuple[str, ...] = ()


DISPATCH_BINDINGS: dict[str, str] = {
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
    # Writer - font color
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

DISPATCH_ARGUMENT_PRESETS: dict[str, tuple[str, object]] = {
    "Writer.ApplyHeading1": ("style-template", "Heading 1"),
    "Writer.ApplyHeading2": ("style-template", "Heading 2"),
    "Writer.ApplyHeading3": ("style-template", "Heading 3"),
    "Writer.ApplyDefaultStyle": ("style-template", "Default Paragraph Style"),
    "Writer.FontColorRed": ("font-color", 0xFF0000),
    "Writer.FontColorBlue": ("font-color", 0x0000FF),
    "Writer.FontColorGreen": ("font-color", 0x008000),
    "Writer.FontColorBlack": ("font-color", 0x000000),
    "Writer.FontColorWhite": ("font-color", 0xFFFFFF),
    "Writer.FontColorOrange": ("font-color", 0xFF8C00),
    "Writer.FontColorPurple": ("font-color", 0x800080),
    "Writer.FontColorYellow": ("font-color", 0xFFD700),
    "Calc.FontColorRed": ("font-color", 0xFF0000),
    "Calc.FontColorBlue": ("font-color", 0x0000FF),
    "Calc.FontColorGreen": ("font-color", 0x008000),
    "Calc.FontColorBlack": ("font-color", 0x000000),
    "Impress.FontColorRed": ("font-color", 0xFF0000),
    "Impress.FontColorBlue": ("font-color", 0x0000FF),
    "Impress.FontColorGreen": ("font-color", 0x008000),
    "Impress.FontColorBlack": ("font-color", 0x000000),
    "Writer.HighlightYellow": ("char-back-color", 0xFFFF00),
    "Writer.HighlightGreen": ("char-back-color", 0x00FF00),
    "Writer.HighlightRed": ("char-back-color", 0xFF0000),
    "Writer.HighlightBlue": ("char-back-color", 0x00BFFF),
    "Writer.HighlightNone": ("char-back-color", 0xFFFFFFFF),
    "Calc.BackgroundColorYellow": ("background-color", 0xFFFF00),
    "Calc.BackgroundColorGreen": ("background-color", 0x00FF00),
    "Calc.BackgroundColorRed": ("background-color", 0xFF0000),
    "Calc.BackgroundColorBlue": ("background-color", 0x00BFFF),
    "Calc.BackgroundColorNone": ("background-color", 0xFFFFFFFF),
    "Writer.SetFontSize": ("font-height", 12.0),
    "Writer.SetFontName": ("font-family", "Arial"),
}

READ_ONLY_DISPATCH_TOOL_IDS = {
    "Writer.SelectAll",
    "Writer.WordCount",
    "Writer.SpellCheck",
    "Impress.StartPresentation",
    "Impress.StartFromCurrent",
}

DESTRUCTIVE_DISPATCH_TOOL_IDS = {
    "Writer.Undo",
    "Writer.Redo",
    "Calc.DeleteRows",
    "Calc.DeleteColumns",
    "Impress.DeleteSlide",
}

CONTENT_EDIT_DISPATCH_TOOL_IDS = {
    "Writer.InsertPageBreak",
    "Writer.InsertColumnBreak",
    "Writer.InsertSpecialChar",
    "Writer.InsertHyperlink",
    "Writer.InsertComment",
    "Writer.InsertImage",
    "Writer.InsertBookmark",
    "Writer.InsertFootnote",
    "Writer.InsertEndnote",
    "Writer.InsertHeader",
    "Writer.InsertFooter",
    "Writer.InsertPageNumber",
    "Writer.InsertDateField",
    "Writer.InsertTimeField",
    "Writer.FormatPaintbrush",
    "Writer.FindReplace",
    "Calc.MergeCells",
    "Calc.InsertRowAbove",
    "Calc.InsertRowBelow",
    "Calc.InsertColumnBefore",
    "Calc.InsertColumnAfter",
    "Calc.SortAscending",
    "Calc.SortDescending",
    "Calc.AutoFilter",
    "Calc.FreezePanes",
    "Calc.AutoSum",
    "Calc.InsertComment",
    "Calc.InsertImage",
    "Calc.InsertChart",
    "Impress.InsertSlide",
    "Impress.DuplicateSlide",
    "Impress.InsertImage",
    "Impress.InsertTable",
    "Impress.InsertChart",
    "Impress.InsertTextBox",
    "Impress.InsertComment",
    "Draw.InsertImage",
    "Draw.InsertTextBox",
}

CAPABILITY_METADATA_OVERRIDES: dict[str, dict[str, object]] = {
    "Writer.ToggleBold": {
        "examples": ("make this bold", "bold this selection"),
        "intent_tags": ("bold", "format", "emphasis"),
        "precondition_probes": ("selection.non_empty",),
    },
    "Writer.ToggleItalic": {
        "examples": ("italicize this", "make this italic"),
        "intent_tags": ("italic", "format"),
    },
    "Writer.ApplyBullets": {
        "examples": ("turn this into bullets", "add bullets to this"),
        "intent_tags": ("bullet", "bullets", "list"),
    },
    "Writer.AlignCenter": {
        "examples": ("center this text",),
        "intent_tags": ("center", "align", "alignment"),
    },
    "Calc.AlignCenter": {
        "examples": ("center this cell",),
        "intent_tags": ("center", "cell", "align", "alignment"),
    },
    "Impress.ApplyBullets": {
        "examples": ("add bullets to this",),
        "intent_tags": ("bullet", "bullets", "list"),
    },
    "Calc.CreateChartFromSelection": {
        "examples": ("create a pie chart from this data", "visualize this data as a chart"),
        "intent_tags": ("chart", "graph", "plot", "visualize", "pie", "line", "bar", "column"),
    },
    "Calc.SortSelectedRange": {
        "examples": ("sort this data in descending order", "sort this range ascending"),
        "intent_tags": ("sort", "order", "descending", "ascending", "arrange"),
    },
    "Impress.CreateSlideFromOutline": {
        "examples": ("create a new slide about project status",),
        "intent_tags": ("slide", "create", "new", "outline"),
    },
    "Impress.ApplyLayoutToCurrentSlide": {
        "examples": ("apply a blank layout to this slide",),
        "intent_tags": ("layout", "blank", "title", "content", "slide"),
    },
}

NON_DISPATCH_CAPABILITIES: dict[str, dict[str, object]] = {
    "Writer.GetSelection": {
        "app": "writer",
        "safety_class": SafetyClass.READ_ONLY,
        "requires_approval": False,
        "summary": "Read the current Writer selection",
        "intent_tags": ("selection", "read", "writer"),
    },
    "Writer.ReplaceSelection": {
        "app": "writer",
        "safety_class": SafetyClass.CONTENT_EDIT,
        "requires_approval": True,
        "summary": "Replace the selected Writer text",
        "intent_tags": ("rewrite", "rephrase", "simplify", "translate", "grammar", "selection"),
        "precondition_probes": ("selection.non_empty",),
        "postcondition_probes": ("selection.equals_preview_after",),
        "examples": (
            "rewrite this selection in a more formal tone",
            "fix the grammar in this text",
            "simplify this paragraph",
        ),
    },
    "Writer.InsertBelowSelection": {
        "app": "writer",
        "safety_class": SafetyClass.CONTENT_EDIT,
        "requires_approval": True,
        "summary": "Insert generated text below the current Writer selection",
        "intent_tags": ("insert", "below", "append", "draft", "write"),
        "precondition_probes": ("selection.non_empty",),
        "postcondition_probes": ("selection.equals_argument.replacementText",),
        "examples": ("insert below a summary paragraph", "draft a follow-up paragraph below this"),
    },
    "Writer.InsertTable": {
        "app": "writer",
        "safety_class": SafetyClass.CONTENT_EDIT,
        "requires_approval": True,
        "summary": "Insert a Writer table",
        "intent_tags": ("table", "insert", "create"),
        "examples": ("insert a 3x5 table", "create a table here"),
    },
    "Writer.ConvertToTable": {
        "app": "writer",
        "safety_class": SafetyClass.CONTENT_EDIT,
        "requires_approval": True,
        "summary": "Convert selected Writer text to a table",
        "intent_tags": ("table", "convert", "visualize"),
        "examples": ("convert this text to a table", "visualize this as a table"),
    },
    "Calc.GetSelectedRange": {
        "app": "calc",
        "safety_class": SafetyClass.READ_ONLY,
        "requires_approval": False,
        "summary": "Read the current Calc selection",
        "intent_tags": ("selection", "range", "read", "calc"),
    },
    "Calc.GetSelectedFormula": {
        "app": "calc",
        "safety_class": SafetyClass.READ_ONLY,
        "requires_approval": False,
        "summary": "Read the current Calc formula",
        "intent_tags": ("formula", "read", "calc"),
    },
    "Calc.InsertFormulaInSelection": {
        "app": "calc",
        "safety_class": SafetyClass.CONTENT_EDIT,
        "requires_approval": True,
        "summary": "Insert a formula into the current Calc selection",
        "intent_tags": ("formula", "insert", "sum", "average", "count", "calculate"),
        "precondition_probes": ("selection.non_empty",),
        "postcondition_probes": ("selection.equals_argument.formula",),
        "examples": ("insert a SUM formula for column A",),
    },
    "Calc.CreateChartFromSelection": {
        "app": "calc",
        "safety_class": SafetyClass.CONTENT_EDIT,
        "requires_approval": True,
        "summary": "Create a chart from the current Calc selection",
        "precondition_probes": ("selection.non_empty",),
        "postcondition_probes": ("summary.matches_argument.chartType",),
    },
    "Calc.SortSelectedRange": {
        "app": "calc",
        "safety_class": SafetyClass.CONTENT_EDIT,
        "requires_approval": True,
        "summary": "Sort the current Calc selection",
        "precondition_probes": ("selection.non_empty",),
        "postcondition_probes": ("summary.matches_argument.sortDirection",),
    },
    "Impress.GetSelectedText": {
        "app": "impress",
        "safety_class": SafetyClass.READ_ONLY,
        "requires_approval": False,
        "summary": "Read the current Impress selection",
        "intent_tags": ("selection", "text", "read", "impress"),
    },
    "Impress.ReplaceSelectedText": {
        "app": "impress",
        "safety_class": SafetyClass.CONTENT_EDIT,
        "requires_approval": True,
        "summary": "Replace selected Impress text",
        "intent_tags": ("rewrite", "rephrase", "simplify", "slide", "text"),
        "precondition_probes": ("selection.non_empty",),
        "postcondition_probes": ("selection.equals_preview_after",),
        "examples": ("rewrite this to be simpler",),
    },
    "Impress.CreateSlideFromOutline": {
        "app": "impress",
        "safety_class": SafetyClass.CONTENT_EDIT,
        "requires_approval": True,
        "summary": "Create a new slide from an outline",
        "postcondition_probes": ("summary.matches_argument.outlineLength",),
    },
    "Impress.ApplyLayoutToCurrentSlide": {
        "app": "impress",
        "safety_class": SafetyClass.CONTENT_EDIT,
        "requires_approval": True,
        "summary": "Apply a layout to the current slide",
        "postcondition_probes": ("summary.matches_argument.layout",),
    },
    "Draw.GetSelectedText": {
        "app": "draw",
        "safety_class": SafetyClass.READ_ONLY,
        "requires_approval": False,
        "summary": "Read the current Draw selection",
        "intent_tags": ("selection", "read", "draw"),
    },
    "Draw.ReplaceSelectedText": {
        "app": "draw",
        "safety_class": SafetyClass.CONTENT_EDIT,
        "requires_approval": True,
        "summary": "Replace selected Draw text",
        "intent_tags": ("rewrite", "rephrase", "simplify", "draw", "text"),
        "precondition_probes": ("selection.non_empty",),
        "postcondition_probes": ("selection.equals_preview_after",),
    },
    "Math.GetFormula": {
        "app": "math",
        "safety_class": SafetyClass.READ_ONLY,
        "requires_approval": False,
        "summary": "Read the current Math formula",
        "intent_tags": ("formula", "read", "math"),
    },
    "Math.ReplaceFormula": {
        "app": "math",
        "safety_class": SafetyClass.CONTENT_EDIT,
        "requires_approval": True,
        "summary": "Replace the current Math formula",
        "intent_tags": ("rewrite", "simplify", "expand", "factor", "convert", "formula"),
        "precondition_probes": ("selection.non_empty",),
        "postcondition_probes": ("selection.equals_argument.formula",),
    },
    "Base.GetContext": {
        "app": "base",
        "safety_class": SafetyClass.READ_ONLY,
        "requires_approval": False,
        "summary": "Read the current Base context",
        "intent_tags": ("base", "context", "read"),
    },
    "Base.ExplainQuery": {
        "app": "base",
        "safety_class": SafetyClass.READ_ONLY,
        "requires_approval": False,
        "summary": "Explain the current Base query",
        "intent_tags": ("base", "query", "explain", "sql"),
    },
    "App.ExecuteUnoCommand": {
        "app": "app",
        "safety_class": SafetyClass.CONTENT_EDIT,
        "requires_approval": True,
        "summary": "Execute a catalog-backed UNO dispatch command",
        "intent_tags": ("uno", "command", "dispatch", "execute"),
        "examples": (
            "execute the catalog-backed command for this action",
            "run a whitelisted uno command",
        ),
        "binding": CapabilityBinding(kind="generic-dispatch"),
    },
}


def _infer_app(tool_id: str) -> str:
    prefix, _, _ = tool_id.partition(".")
    return prefix.casefold()


def _default_dispatch_safety(tool_id: str) -> SafetyClass:
    if tool_id in READ_ONLY_DISPATCH_TOOL_IDS:
        return SafetyClass.READ_ONLY
    if tool_id in DESTRUCTIVE_DISPATCH_TOOL_IDS:
        return SafetyClass.DESTRUCTIVE
    if tool_id in CONTENT_EDIT_DISPATCH_TOOL_IDS:
        return SafetyClass.CONTENT_EDIT
    return SafetyClass.SAFE_FORMATTING


def _split_identifier_words(identifier: str) -> tuple[str, ...]:
    normalized = identifier.replace("_", " ")
    normalized = re.sub(r"(?<!^)(?=[A-Z])", " ", normalized)
    tokens = tuple(part.casefold() for part in normalized.split() if part)
    return tokens


def _humanize_tool_id(tool_id: str) -> str:
    _, _, action_name = tool_id.partition(".")
    return " ".join(word.capitalize() for word in _split_identifier_words(action_name))


def _default_intent_tags(tool_id: str, app: str) -> tuple[str, ...]:
    words = _split_identifier_words(tool_id.partition(".")[2])
    unique_words = tuple(dict.fromkeys((*words, app)))
    return unique_words


def _build_dispatch_descriptor(tool_id: str, dispatch_url: str) -> CapabilityDescriptor:
    metadata = CAPABILITY_METADATA_OVERRIDES.get(tool_id, {})
    app = _infer_app(tool_id)
    safety_class = metadata.get("safety_class", _default_dispatch_safety(tool_id))
    requires_approval = metadata.get(
        "requires_approval",
        safety_class not in {SafetyClass.READ_ONLY, SafetyClass.SAFE_FORMATTING},
    )
    argument_preset, argument_value = DISPATCH_ARGUMENT_PRESETS.get(tool_id, (None, None))
    binding = CapabilityBinding(
        kind="uno-dispatch",
        dispatch_url=dispatch_url,
        dispatch_alias=tool_id,
        argument_preset=argument_preset,
        argument_value=argument_value,
    )
    title = str(metadata.get("title", _humanize_tool_id(tool_id)))
    summary = str(metadata.get("summary", title))
    intent_tags = tuple(metadata.get("intent_tags", _default_intent_tags(tool_id, app)))
    examples = tuple(metadata.get("examples", ()))
    precondition_probes = tuple(metadata.get("precondition_probes", ()))
    postcondition_probes = tuple(metadata.get("postcondition_probes", ()))
    return CapabilityDescriptor(
        tool_id=tool_id,
        app=app,
        title=title,
        summary=summary,
        safety_class=safety_class,
        requires_approval=bool(requires_approval),
        binding=binding,
        intent_tags=intent_tags,
        examples=examples,
        precondition_probes=precondition_probes,
        postcondition_probes=postcondition_probes,
    )


def _build_manual_descriptor(tool_id: str, metadata: dict[str, object]) -> CapabilityDescriptor:
    app = str(metadata["app"])
    binding = metadata.get("binding", CapabilityBinding())
    title = str(metadata.get("title", _humanize_tool_id(tool_id)))
    summary = str(metadata.get("summary", title))
    intent_tags = tuple(metadata.get("intent_tags", _default_intent_tags(tool_id, app)))
    examples = tuple(metadata.get("examples", ()))
    precondition_probes = tuple(metadata.get("precondition_probes", ()))
    postcondition_probes = tuple(metadata.get("postcondition_probes", ()))
    return CapabilityDescriptor(
        tool_id=tool_id,
        app=app,
        title=title,
        summary=summary,
        safety_class=metadata["safety_class"],
        requires_approval=bool(metadata["requires_approval"]),
        binding=binding,
        intent_tags=intent_tags,
        examples=examples,
        precondition_probes=precondition_probes,
        postcondition_probes=postcondition_probes,
    )


CAPABILITY_CATALOG: tuple[CapabilityDescriptor, ...] = tuple(
    [
        *(_build_dispatch_descriptor(tool_id, dispatch_url) for tool_id, dispatch_url in DISPATCH_BINDINGS.items()),
        *(_build_manual_descriptor(tool_id, metadata) for tool_id, metadata in NON_DISPATCH_CAPABILITIES.items()),
    ]
)