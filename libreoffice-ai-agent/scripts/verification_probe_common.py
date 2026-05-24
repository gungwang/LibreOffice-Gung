from __future__ import annotations

import json
import os
import time
from pathlib import Path

import uno

SIDEBAR_RESOURCE_URL = "private:resource/toolpanel/LoaiaPanelFactory/LoaiaPanel"
STATE_ROOT_ENV_VAR = "LOAIA_EXTENSION_STATE_ROOT"
STATE_FILE_NAME = "sidebar-state.json"


def connect(pipe_name: str) -> object:
    local_context = uno.getComponentContext()
    resolver = local_context.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver",
        local_context,
    )
    uno_url = f"uno:pipe,name={pipe_name};urp;StarOffice.ComponentContext"
    last_error: Exception | None = None
    for _ in range(30):
        try:
            return resolver.resolve(uno_url)
        except Exception as exc:  # pragma: no cover - runtime-only under LibreOffice
            last_error = exc
            time.sleep(1)

    raise RuntimeError(f"Could not connect to LibreOffice over {uno_url}: {last_error}")


def wait_for_uno_result(
    callback: object,
    description: str,
    attempts: int = 20,
    delay_seconds: float = 0.5,
) -> object:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            result = callback()
            if result is not None:
                return result
        except Exception as exc:  # pragma: no cover - runtime-only under LibreOffice
            last_error = exc

        time.sleep(delay_seconds)

    if last_error is not None:
        raise RuntimeError(
            f"Could not access {description} after LibreOffice startup: {last_error}"
        ) from last_error

    raise RuntimeError(f"Could not access {description} after LibreOffice startup.")


def resolve_sidebar_state_root() -> Path:
    configured_root = os.environ.get(STATE_ROOT_ENV_VAR, "").strip()
    if configured_root:
        return Path(configured_root)

    app_data = os.environ.get("APPDATA", "").strip()
    if app_data:
        return Path(app_data) / "LibreOfficeAIAgent"

    return Path.home() / ".libreoffice-ai-agent"


def sidebar_state_file() -> Path:
    return resolve_sidebar_state_root() / STATE_FILE_NAME


def load_sidebar_state() -> dict[str, object]:
    state_file = sidebar_state_file()
    if not state_file.exists():
        return {}

    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def coerce_sidebar_messages(session_payload: dict[str, object]) -> list[dict[str, str]]:
    raw_messages = session_payload.get("messages")
    if not isinstance(raw_messages, list):
        return []

    messages: list[dict[str, str]] = []
    for message in raw_messages:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        text = message.get("text")
        if not isinstance(role, str) or not isinstance(text, str):
            continue

        normalized: dict[str, str] = {
            "role": role,
            "text": text,
        }
        provider = message.get("provider")
        if isinstance(provider, str):
            normalized["provider"] = provider
        model = message.get("model")
        if isinstance(model, str):
            normalized["model"] = model
        messages.append(normalized)

    return messages


def find_sidebar_session(
    *,
    last_prompt: str | None = None,
    require_result: bool = False,
    require_error: bool = False,
) -> tuple[dict[str, object], dict[str, object]] | None:
    state_data = load_sidebar_state()
    sessions = state_data.get("sessions")
    if not isinstance(sessions, dict):
        return None

    for payload in sessions.values():
        if not isinstance(payload, dict):
            continue

        prompt_value = payload.get("lastPrompt")
        result_value = payload.get("lastResult")
        error_value = payload.get("lastError")

        if last_prompt is not None and prompt_value != last_prompt:
            continue
        if require_result and (not isinstance(result_value, str) or not result_value.strip()):
            continue
        if require_error and (not isinstance(error_value, str) or not error_value.strip()):
            continue

        return state_data, payload

    return None


def make_property(name: str, value: object) -> object:
    prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    prop.Name = name
    prop.Value = value
    return prop


def make_url(command: str) -> object:
    url = uno.createUnoStruct("com.sun.star.util.URL")
    url.Complete = f"vnd.org.libreoffice.ai.agent:{command}"
    url.Protocol = "vnd.org.libreoffice.ai.agent:"
    url.Path = command
    return url


def model_text(control: object) -> str:
    model = control.getModel()

    # ListBox / ComboBox: return selected item text
    items = getattr(model, "StringItemList", None)
    selected = getattr(model, "SelectedItems", None)
    if items is not None and selected is not None:
        if selected and len(items) > selected[0]:
            return items[selected[0]]
        # Editable ComboBox may have typed text in the Text property
        text = getattr(model, "Text", None)
        if isinstance(text, str) and text:
            return text
        return ""

    for attribute_name in ("Text", "Label"):
        value = getattr(model, attribute_name, None)
        if isinstance(value, str):
            return value

    return ""


def set_model_text(control: object, value: str) -> None:
    if hasattr(control, "setText"):
        control.setText(value)
        return

    model = control.getModel()
    for attribute_name in ("Text", "Label"):
        if hasattr(model, attribute_name):
            setattr(model, attribute_name, value)
            return

    if hasattr(model, "setPropertyValue"):
        for property_name in ("Text", "Label"):
            try:
                model.setPropertyValue(property_name, value)
                return
            except Exception:
                continue


def load_document(context: object, component_url: str) -> tuple[object, object]:
    service_manager = context.ServiceManager
    desktop = service_manager.createInstanceWithContext(
        "com.sun.star.frame.Desktop",
        context,
    )
    document = desktop.loadComponentFromURL(
        component_url,
        "_blank",
        0,
        (make_property("Hidden", False),),
    )
    wait_for_uno_result(document.getCurrentController, "document controller")
    return desktop, document


def get_sidebar_panel_window(context: object, frame: object) -> object:
    factory_manager = context.getValueByName(
        "/singletons/com.sun.star.ui.theUIElementFactoryManager"
    )
    ui_element = factory_manager.createUIElement(
        SIDEBAR_RESOURCE_URL,
        (
            make_property("Frame", frame),
            make_property("ParentWindow", frame.getContainerWindow()),
        ),
    )
    return ui_element.getRealInterface().Window


def open_sidebar(frame: object) -> None:
    open_sidebar_url = make_url("open-sidebar")
    open_dispatch = frame.queryDispatch(open_sidebar_url, "_self", 0)
    if open_dispatch is None:
        raise RuntimeError("Protocol dispatch is not available for open-sidebar.")

    open_dispatch.dispatch(open_sidebar_url, ())


def control_is_enabled(control: object) -> bool:
    if hasattr(control, "isEnabled"):
        return bool(control.isEnabled())

    model = control.getModel()
    enabled = getattr(model, "Enabled", None)
    if isinstance(enabled, bool):
        return enabled

    return False


def close_document_session(document: object | None, desktop: object | None) -> None:
    if document is not None:
        try:
            document.close(True)
        except Exception:
            pass

    if desktop is not None:
        try:
            desktop.terminate()
        except Exception:
            pass