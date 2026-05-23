"""Math context extraction for sidebar requests."""

from __future__ import annotations

from loaia_shared.schema.messages import ContextEnvelope, SelectionContext


def extract_math_formula(text: str) -> ContextEnvelope:
    return ContextEnvelope(selection=SelectionContext(mimeType="text/plain", text=text))


def capture_math_formula(controller: object) -> str:
    """Capture the current Math formula markup.

    Returns the StarMath formula string from the document model.
    """
    model = None
    if hasattr(controller, "getModel"):
        model = controller.getModel()
    elif hasattr(controller, "Model"):
        model = controller.Model

    if model is None:
        return ""

    # Math documents expose getFormula() on the model.
    if hasattr(model, "getFormula"):
        return model.getFormula() or ""

    if hasattr(model, "Formula"):
        return model.Formula or ""

    return ""


def apply_math_formula(controller: object, formula: str) -> str:
    """Replace the Math formula with a new one.

    Returns a result message.
    """
    model = None
    if hasattr(controller, "getModel"):
        model = controller.getModel()
    elif hasattr(controller, "Model"):
        model = controller.Model

    if model is None:
        raise ValueError("Cannot access the Math document model.")

    if hasattr(model, "setFormula"):
        model.setFormula(formula)
        return f"Updated Math formula: {formula}"

    if hasattr(model, "Formula"):
        model.Formula = formula
        return f"Updated Math formula: {formula}"

    raise ValueError("Math model does not support formula replacement.")
