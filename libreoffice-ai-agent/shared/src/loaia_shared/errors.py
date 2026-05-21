class LoaiaError(Exception):
    """Base project error."""


class ValidationError(LoaiaError):
    """Raised when a request or proposal fails local validation."""


class TransportError(LoaiaError):
    """Raised when extension-to-sidecar transport fails."""
