from __future__ import annotations

import time

import uno

SIDEBAR_RESOURCE_URL = "private:resource/toolpanel/LoaiaPanelFactory/LoaiaPanel"


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
    for attribute_name in ("Text", "Label"):
        value = getattr(model, attribute_name, None)
        if isinstance(value, str):
            return value

    return ""


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