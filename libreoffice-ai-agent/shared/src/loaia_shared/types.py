from enum import StrEnum


class AppType(StrEnum):
    WRITER = "writer"
    CALC = "calc"
    IMPRESS = "impress"
    DRAW = "draw"
    MATH = "math"
    BASE = "base"


class PrivacyScope(StrEnum):
    SELECTION_ONLY = "selection-only"
    CURRENT_PARAGRAPH = "current-paragraph"
    CURRENT_REGION = "current-region"
    FULL_DOCUMENT = "full-document"


class ProviderKind(StrEnum):
    OPENAI_COMPATIBLE = "openai-compatible"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
