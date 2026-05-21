SAFE_FORMATTING_TOOL_IDS = {
    "Writer.ToggleBold",
    "Writer.ToggleItalic",
    "Writer.ToggleUnderline",
    "Writer.ApplyHeading1",
    "Writer.ApplyHeading2",
    "Writer.ApplyHeading3",
    "Writer.ApplyBullets",
    "Writer.AlignLeft",
    "Writer.AlignCenter",
    "Writer.AlignRight",
    "Calc.ToggleBold",
    "Calc.ToggleItalic",
    "Calc.AlignLeft",
    "Calc.AlignCenter",
    "Calc.AlignRight",
    "Calc.ApplyNumberFormatCurrency",
    "Calc.ApplyNumberFormatPercent",
    "Calc.ApplyNumberFormatDate",
    "Impress.ToggleBold",
    "Impress.ToggleItalic",
    "Impress.ApplyBullets",
    "Impress.AlignLeft",
    "Impress.AlignCenter",
    "Impress.AlignRight",
}


def is_safe_formatting_tool(tool_id: str) -> bool:
    return tool_id in SAFE_FORMATTING_TOOL_IDS
