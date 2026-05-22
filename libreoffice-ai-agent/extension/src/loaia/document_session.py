from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

from loaia_shared.types import AppType

DEFAULT_PROFILE_ID = "default-profile"
DEFAULT_DOCUMENT_URL = "file:///writer-document.odt"

_cached_profile_id: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentSessionKey:
    profile_id: str
    canonical_document_url: str
    app_type: AppType


def get_controller(frame: object | None) -> object:
    if frame is None:
        raise ValueError("Sidebar is not attached to an active document frame.")

    if hasattr(frame, "getController"):
        controller = frame.getController()
    elif hasattr(frame, "Controller"):
        controller = frame.Controller
    else:
        controller = None

    if controller is None:
        raise ValueError("Could not access the active document controller.")

    return controller


def get_model(controller: object | None) -> object | None:
    if controller is None:
        return None

    if hasattr(controller, "getModel"):
        return controller.getModel()

    return getattr(controller, "Model", None)


def resolve_document_url(frame: object | None) -> str:
    try:
        controller = get_controller(frame)
        model = get_model(controller)
    except ValueError:
        return DEFAULT_DOCUMENT_URL

    if model is None:
        return DEFAULT_DOCUMENT_URL

    model_url = None
    if hasattr(model, "getURL"):
        model_url = model.getURL()
    elif hasattr(model, "URL"):
        model_url = model.URL

    if isinstance(model_url, str) and model_url:
        return model_url

    return DEFAULT_DOCUMENT_URL


def resolve_app_type(frame: object | None) -> AppType | None:
    try:
        controller = get_controller(frame)
        model = get_model(controller)
    except ValueError:
        return None

    if model is None:
        return None

    # Math documents expose a formula component — check BEFORE Text because
    # Math models also have a Text attribute.
    if hasattr(model, "getFormula") or (
        hasattr(model, "Formula") and not hasattr(model, "Sheets")
    ):
        return AppType.MATH

    if hasattr(model, "Text"):
        return AppType.WRITER

    if hasattr(model, "Sheets"):
        return AppType.CALC

    if hasattr(model, "DrawPages"):
        # Both Draw and Impress have DrawPages; distinguish via Presentations
        # (only Impress has a presentation API) or URL fallback.
        if hasattr(model, "getPresentation") or hasattr(model, "Presentation"):
            return AppType.IMPRESS
        document_url = resolve_document_url(frame).casefold()
        if document_url.endswith(".odp") or "simpress" in document_url:
            return AppType.IMPRESS
        # Draw document (has DrawPages but no Presentation).
        return AppType.DRAW

    # Base documents expose a DatabaseDocument service.
    if hasattr(model, "DataSource"):
        return AppType.BASE

    document_url = resolve_document_url(frame).casefold()
    if document_url.endswith(".ods") or "scalc" in document_url:
        return AppType.CALC

    if document_url.endswith(".odp") or "simpress" in document_url:
        return AppType.IMPRESS

    if document_url.endswith(".odg") or "sdraw" in document_url:
        return AppType.DRAW

    if document_url.endswith(".odf") or "smath" in document_url:
        return AppType.MATH

    if document_url.endswith(".odb") or "sbase" in document_url:
        return AppType.BASE

    return None


def resolve_profile_id() -> str:
    """Resolve the active LibreOffice user profile ID.

    Tries the UNO PathSubstitution service to get the ``$(user)`` path, then
    hashes it into a stable short identifier. Falls back to DEFAULT_PROFILE_ID
    when running outside of LibreOffice (e.g. in tests).
    """
    global _cached_profile_id  # noqa: PLW0603
    if _cached_profile_id is not None:
        return _cached_profile_id

    try:
        import uno  # type: ignore[import]

        ctx = uno.getComponentContext()
        smgr = ctx.ServiceManager
        path_sub = smgr.createInstanceWithContext(
            "com.sun.star.util.PathSubstitution", ctx
        )
        user_path = path_sub.substituteVariables("$(user)", True)
        if isinstance(user_path, str) and user_path:
            profile_id = sha1(user_path.encode("utf-8")).hexdigest()[:12]
            _cached_profile_id = profile_id
            return profile_id
    except Exception:
        pass

    return DEFAULT_PROFILE_ID


def resolve_history_session_key(frame: object | None) -> DocumentSessionKey | None:
    app_type = resolve_app_type(frame)
    if app_type is None:
        return None

    return DocumentSessionKey(
        profile_id=resolve_profile_id(),
        canonical_document_url=resolve_document_url(frame),
        app_type=app_type,
    )