from __future__ import annotations

import sys
import time

import uno


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


def verify(
    context: object,
    prompt: str,
    initial_selection: str,
    expected_text: str,
) -> int:
    service_manager = context.ServiceManager
    desktop = service_manager.createInstanceWithContext(
        "com.sun.star.frame.Desktop",
        context,
    )
    document = None
    try:
        document = desktop.loadComponentFromURL(
            "private:factory/swriter",
            "_blank",
            0,
            (make_property("Hidden", False),),
        )
        controller = document.getCurrentController()
        frame = controller.getFrame()
        factory_manager = context.getValueByName(
            "/singletons/com.sun.star.ui.theUIElementFactoryManager"
        )
        ui_element = factory_manager.createUIElement(
            "private:resource/toolpanel/LoaiaPanelFactory/LoaiaPanel",
            (
                make_property("Frame", frame),
                make_property("ParentWindow", frame.getContainerWindow()),
            ),
        )
        panel_window = ui_element.getRealInterface().Window

        text = document.Text
        cursor = text.createTextCursor()
        text.insertString(cursor, initial_selection, False)
        cursor.gotoStart(False)
        cursor.goRight(len(initial_selection), True)
        controller.select(cursor)

        preview_url = make_url("preview-selection")
        approve_url = make_url("approve-pending")
        preview_dispatch = frame.queryDispatch(preview_url, "_self", 0)
        approve_dispatch = frame.queryDispatch(approve_url, "_self", 0)

        results: dict[str, str] = {
            "PREVIEW_DISPATCH_PRESENT": str(preview_dispatch is not None),
            "APPROVE_DISPATCH_PRESENT": str(approve_dispatch is not None),
        }

        if preview_dispatch is None or approve_dispatch is None:
            for key, value in results.items():
                print(f"{key}={value}")
            print("VALIDATION_PASSED=False")
            print("FAILURE=Protocol dispatch is not available for one or more commands.")
            return 1

        preview_dispatch.dispatch(
            preview_url,
            (make_property("Prompt", prompt),),
        )

        summary_after_preview = model_text(panel_window.getControl("Summary"))
        approve_button = panel_window.getControl("ApproveButton")
        results["HAS_PENDING_PREVIEW"] = str(
            "Pending preview:" in summary_after_preview
            and "Preview Writer selection replacement" in summary_after_preview
        )
        results["APPROVE_ENABLED_AFTER_PREVIEW"] = str(approve_button.isEnabled())

        approve_dispatch.dispatch(approve_url, ())

        summary_after_approve = model_text(panel_window.getControl("Summary"))
        results["DOC_TEXT"] = document.Text.getString()
        results["HAS_APPLIED_RESULT"] = str(
            "Applied Writer.ReplaceSelection" in summary_after_approve
        )
        results["APPROVE_ENABLED_AFTER_APPROVE"] = str(approve_button.isEnabled())

        failures: list[str] = []
        if results["HAS_PENDING_PREVIEW"] != "True":
            failures.append("Preview dispatch did not populate a pending proposal.")
        if results["APPROVE_ENABLED_AFTER_PREVIEW"] != "True":
            failures.append("Approve was not enabled after preview dispatch.")
        if results["DOC_TEXT"] != expected_text:
            failures.append(
                "Approval did not update the Writer document to the expected text."
            )
        if results["HAS_APPLIED_RESULT"] != "True":
            failures.append("Sidebar summary did not record the applied result.")
        if results["APPROVE_ENABLED_AFTER_APPROVE"] != "False":
            failures.append("Approve did not return to the disabled state after apply.")

        for key, value in results.items():
            print(f"{key}={value}")

        if failures:
            print("VALIDATION_PASSED=False")
            for failure in failures:
                print(f"FAILURE={failure}")
            return 1

        print("VALIDATION_PASSED=True")
        return 0
    finally:
        if document is not None:
            try:
                document.close(True)
            except Exception:
                pass
        try:
            desktop.terminate()
        except Exception:
            pass


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(
            "Usage: verify_protocol_actions.py <pipe_name> <prompt> "
            "<initial_selection> <expected_text>",
            file=sys.stderr,
        )
        return 2

    pipe_name, prompt, initial_selection, expected_text = argv
    context = connect(pipe_name)
    return verify(
        context=context,
        prompt=prompt,
        initial_selection=initial_selection,
        expected_text=expected_text,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))