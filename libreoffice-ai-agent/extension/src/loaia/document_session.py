from __future__ import annotations

from loaia_shared.schema.history import HistorySessionKey
from loaia_shared.types import AppType

DEFAULT_PROFILE_ID = "default-profile"
DEFAULT_DOCUMENT_URL = "file:///writer-document.odt"


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

    if hasattr(model, "Text"):
        return AppType.WRITER

    document_url = resolve_document_url(frame).casefold()
    if document_url.endswith(".ods"):
        return AppType.CALC

    if document_url.endswith(".odp"):
        return AppType.IMPRESS

    return None


def resolve_history_session_key(frame: object | None) -> HistorySessionKey | None:
    app_type = resolve_app_type(frame)
    if app_type is None:
        return None

    return HistorySessionKey(
        profileId=DEFAULT_PROFILE_ID,
        canonicalDocumentUrl=resolve_document_url(frame),
        appType=app_type,
    )