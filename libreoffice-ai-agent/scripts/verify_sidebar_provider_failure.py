from __future__ import annotations

import sys

from verification_probe_common import (
    close_document_session,
    connect,
    control_is_enabled,
    get_sidebar_panel_window,
    load_document,
    make_property,
    make_url,
    model_text,
    set_model_text,
)


def shorten_text(text: str, limit: int = 90) -> str:
    normalized = text.strip()
    if len(normalized) <= limit:
        return normalized

    return f"{normalized[: limit - 3].rstrip()}..."


def flatten_text(text: str) -> str:
    return text.replace("\r", "\\r").replace("\n", "\\n")


def verify(
    context: object,
    prompt: str,
    initial_selection: str,
    provider: str,
    model: str,
    expected_error: str,
    expected_api_key_status: str = "missing",
) -> int:
    desktop = None
    document = None
    try:
        desktop, document = load_document(context, "private:factory/swriter")
        controller = document.getCurrentController()
        frame = controller.getFrame()

        open_sidebar_url = make_url("open-sidebar")
        save_settings_url = make_url("save-settings")
        preview_url = make_url("preview-selection")
        open_dispatch = frame.queryDispatch(open_sidebar_url, "_self", 0)
        save_dispatch = frame.queryDispatch(save_settings_url, "_self", 0)
        preview_dispatch = frame.queryDispatch(preview_url, "_self", 0)
        results: dict[str, str] = {
            "OPEN_SIDEBAR_DISPATCH_PRESENT": str(open_dispatch is not None),
            "SAVE_SETTINGS_DISPATCH_PRESENT": str(save_dispatch is not None),
            "PREVIEW_DISPATCH_PRESENT": str(preview_dispatch is not None),
        }

        if open_dispatch is None or save_dispatch is None or preview_dispatch is None:
            for key, value in results.items():
                print(f"{key}={value}")
            print("VALIDATION_PASSED=False")
            print("FAILURE=Protocol dispatch is not available for one or more provider-failure commands.")
            return 1

        open_dispatch.dispatch(open_sidebar_url, ())

        panel_window = get_sidebar_panel_window(context, frame)
        provider_input = panel_window.getControl("ProviderInput")
        model_input = panel_window.getControl("ModelInput")
        settings_status_control = panel_window.getControl("SettingsStatus")
        approve_button = panel_window.getControl("ApproveButton")

        status_after_open = model_text(panel_window.getControl("Status"))
        results["OPEN_STATUS_HAS_COMMAND"] = str(
            "Last command: open-sidebar" in status_after_open
        )
        results["APPROVE_DISABLED_AFTER_OPEN"] = str(
            not control_is_enabled(approve_button)
        )

        set_model_text(provider_input, provider)
        set_model_text(model_input, model)
        save_dispatch.dispatch(
            save_settings_url,
            (
                make_property("Provider", provider),
                make_property("Model", model),
            ),
        )

        status_after_save = model_text(panel_window.getControl("Status"))
        settings_after_save = model_text(settings_status_control)
        results["RAW_STATUS_AFTER_SAVE"] = flatten_text(status_after_save)
        results["RAW_SETTINGS_AFTER_SAVE"] = flatten_text(settings_after_save)
        results["PROVIDER_INPUT_AFTER_SAVE"] = model_text(provider_input)
        results["MODEL_INPUT_AFTER_SAVE"] = model_text(model_input)
        results["STATUS_HAS_PROVIDER_AFTER_SAVE"] = str(
            f"Provider: {provider}" in status_after_save
        )
        results["STATUS_HAS_MODEL_AFTER_SAVE"] = str(
            f"Model: {model}" in status_after_save
        )
        results["STATUS_HAS_API_KEY_AFTER_SAVE"] = str(
            f"API key: {expected_api_key_status}" in status_after_save
        )
        results["SETTINGS_STATUS_HAS_PROVIDER"] = str(
            f"Provider profile: {provider}" in settings_after_save
        )
        results["SETTINGS_STATUS_HAS_MODEL"] = str(
            f"Model profile: {model}" in settings_after_save
        )
        results["SETTINGS_STATUS_HAS_API_KEY"] = str(
            f"API key status: {expected_api_key_status}" in settings_after_save
        )
        results["SETTINGS_STATUS_HAS_SAVE_NOTICE"] = str(
            "Saved Writer-first provider settings." in settings_after_save
        )

        text = document.Text
        cursor = text.createTextCursor()
        text.insertString(cursor, initial_selection, False)
        cursor.gotoStart(False)
        cursor.goRight(len(initial_selection), True)
        controller.select(cursor)

        preview_dispatch.dispatch(
            preview_url,
            (make_property("Prompt", prompt),),
        )

        status_after_error = model_text(panel_window.getControl("Status"))
        summary_after_error = model_text(panel_window.getControl("Summary"))
        results["RAW_STATUS_AFTER_ERROR"] = flatten_text(status_after_error)
        results["RAW_SUMMARY_AFTER_ERROR"] = flatten_text(summary_after_error)
        expected_status_error = shorten_text(expected_error, limit=90)
        expected_recent_activity = shorten_text(f"Error: {expected_error}", limit=90)
        results["CONNECTED_AFTER_ERROR"] = str(
            "Connection: connected to sidecar" in status_after_error
        )
        results["LAST_COMMAND_AFTER_ERROR"] = str(
            "Last command: preview-selection" in status_after_error
        )
        results["HAS_EXPECTED_PROVIDER_AFTER_ERROR"] = str(
            f"Provider: {provider}" in status_after_error
        )
        results["HAS_EXPECTED_MODEL_AFTER_ERROR"] = str(
            f"Model: {model}" in status_after_error
        )
        results["HAS_EXPECTED_API_KEY_AFTER_ERROR"] = str(
            f"API key: {expected_api_key_status}" in status_after_error
        )
        results["HAS_EXPECTED_ERROR_IN_STATUS"] = str(
            f"Last error: {expected_status_error}" in status_after_error
        )
        results["HAS_PROMPT_IN_SUMMARY"] = str(f"Prompt:\n{prompt}" in summary_after_error)
        results["HAS_SELECTION_IN_SUMMARY"] = str(
            f"Selection:\n{initial_selection}" in summary_after_error
        )
        results["HAS_NO_PENDING_PREVIEW"] = str(
            "Pending preview:\nNo pending proposal." in summary_after_error
        )
        results["HAS_NO_RESULT"] = str(
            "Last result:\nNo completed result yet." in summary_after_error
        )
        results["HAS_RECENT_ERROR_ACTIVITY"] = str(
            f"- {expected_recent_activity}" in summary_after_error
        )
        results["DOC_TEXT"] = document.Text.getString()
        results["APPROVE_DISABLED_AFTER_ERROR"] = str(
            not control_is_enabled(approve_button)
        )

        failures: list[str] = []
        if results["PROVIDER_INPUT_AFTER_SAVE"] != provider:
            failures.append("Provider input did not keep the saved provider value.")
        if results["MODEL_INPUT_AFTER_SAVE"] != model:
            failures.append("Model input did not keep the saved model value.")
        if results["OPEN_STATUS_HAS_COMMAND"] != "True":
            failures.append("Sidebar status did not reflect the open-sidebar command.")
        if results["APPROVE_DISABLED_AFTER_OPEN"] != "True":
            failures.append("Approve should start disabled after opening the sidebar.")
        if results["STATUS_HAS_PROVIDER_AFTER_SAVE"] != "True":
            failures.append("Sidebar status did not show the saved provider after save-settings.")
        if results["STATUS_HAS_MODEL_AFTER_SAVE"] != "True":
            failures.append("Sidebar status did not show the saved model after save-settings.")
        if results["STATUS_HAS_API_KEY_AFTER_SAVE"] != "True":
            failures.append("Sidebar status did not show the expected API-key status after save-settings.")
        if results["SETTINGS_STATUS_HAS_PROVIDER"] != "True":
            failures.append("Settings section did not show the saved provider.")
        if results["SETTINGS_STATUS_HAS_MODEL"] != "True":
            failures.append("Settings section did not show the saved model.")
        if results["SETTINGS_STATUS_HAS_API_KEY"] != "True":
            failures.append("Settings section did not show the expected API-key status.")
        if results["SETTINGS_STATUS_HAS_SAVE_NOTICE"] != "True":
            failures.append("Settings section did not show the save confirmation notice.")
        if results["CONNECTED_AFTER_ERROR"] != "True":
            failures.append("Sidebar did not stay connected after the provider failure response.")
        if results["LAST_COMMAND_AFTER_ERROR"] != "True":
            failures.append("Sidebar status did not reflect the preview-selection command.")
        if results["HAS_EXPECTED_PROVIDER_AFTER_ERROR"] != "True":
            failures.append("Sidebar status did not retain the expected provider after provider failure.")
        if results["HAS_EXPECTED_MODEL_AFTER_ERROR"] != "True":
            failures.append("Sidebar status did not retain the expected model after provider failure.")
        if results["HAS_EXPECTED_API_KEY_AFTER_ERROR"] != "True":
            failures.append("Sidebar status did not retain the expected API-key status after provider failure.")
        if results["HAS_EXPECTED_ERROR_IN_STATUS"] != "True":
            failures.append("Sidebar status did not show the expected provider error.")
        if results["HAS_PROMPT_IN_SUMMARY"] != "True":
            failures.append("Sidebar summary did not retain the submitted prompt.")
        if results["HAS_SELECTION_IN_SUMMARY"] != "True":
            failures.append("Sidebar summary did not retain the selected text.")
        if results["HAS_NO_PENDING_PREVIEW"] != "True":
            failures.append("Sidebar summary did not keep the empty pending-preview state.")
        if results["HAS_NO_RESULT"] != "True":
            failures.append("Sidebar summary did not keep the empty last-result state.")
        if results["HAS_RECENT_ERROR_ACTIVITY"] != "True":
            failures.append("Sidebar recent activity did not include the provider error.")
        if results["DOC_TEXT"] != initial_selection:
            failures.append("Provider-failure flow unexpectedly changed the Writer document.")
        if results["APPROVE_DISABLED_AFTER_ERROR"] != "True":
            failures.append("Approve should stay disabled after a provider failure.")

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
        close_document_session(document=document, desktop=desktop)


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print(
            "Usage: verify_sidebar_provider_failure.py <pipe_name> <prompt> "
            "<initial_selection> <provider> <model> <expected_error>",
            file=sys.stderr,
        )
        return 2

    pipe_name, prompt, initial_selection, provider, model, expected_error = argv
    context = connect(pipe_name)
    return verify(
        context=context,
        prompt=prompt,
        initial_selection=initial_selection,
        provider=provider,
        model=model,
        expected_error=expected_error,
    )


def cli(argv: list[str]) -> int:
    try:
        return main(argv)
    except Exception as error:
        print(
            f"UNHANDLED_EXCEPTION={error.__class__.__name__}: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))