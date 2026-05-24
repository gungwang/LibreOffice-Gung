from __future__ import annotations

import sys

from verification_probe_common import (
    coerce_sidebar_messages,
    close_document_session,
    connect,
    find_sidebar_session,
    load_document,
    load_sidebar_state,
    make_property,
    make_url,
    wait_for_uno_result,
)


def _load_saved_settings(provider: str, model: str) -> tuple[dict[str, object], dict[str, object]] | None:
    state_data = load_sidebar_state()
    settings = state_data.get("settings")
    if not isinstance(settings, dict):
        return None

    if settings.get("provider") != provider or settings.get("model") != model:
        return None

    return state_data, settings


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
    stage = "load_document"
    try:
        stage = "load_document"
        desktop, document = load_document(context, "private:factory/swriter")
        stage = "get_controller"
        controller = document.getCurrentController()
        frame = controller.getFrame()

        stage = "query_dispatch"
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
            print(
                "FAILURE=Protocol dispatch is not available"
                " for one or more provider-failure commands."
            )
            return 1

        stage = "open_sidebar"
        open_dispatch.dispatch(open_sidebar_url, ())
        stage = "save_settings"
        save_dispatch.dispatch(
            save_settings_url,
            (
                make_property("Provider", provider),
                make_property("Model", model),
            ),
        )

        stage = "wait_for_saved_settings"
        _state_data, settings = wait_for_uno_result(
            lambda: _load_saved_settings(provider, model),
            "saved provider settings",
        )
        results["SETTINGS_PROVIDER"] = str(settings.get("provider") or "")
        results["SETTINGS_MODEL"] = str(settings.get("model") or "")
        results["SETTINGS_SAVED"] = str(
            settings.get("provider") == provider and settings.get("model") == model
        )
        results["EXPECTED_API_KEY_STATUS_CHECK_SKIPPED"] = expected_api_key_status

        text = document.Text
        cursor = text.createTextCursor()
        stage = "seed_document"
        text.insertString(cursor, initial_selection, False)
        cursor.gotoStart(False)
        cursor.goRight(len(initial_selection), True)
        controller.select(cursor)

        stage = "dispatch_preview"
        preview_dispatch.dispatch(
            preview_url,
            (make_property("Prompt", prompt),),
        )

        stage = "wait_for_provider_error"
        _state_data, session_payload = wait_for_uno_result(
            lambda: find_sidebar_session(last_prompt=prompt, require_error=True),
            "provider failure session state",
        )
        messages = coerce_sidebar_messages(session_payload)
        user_message = next((message for message in reversed(messages) if message["role"] == "user"), None)
        system_message = next((message for message in reversed(messages) if message["role"] == "system"), None)
        results["LAST_ERROR_MATCHES"] = str(session_payload.get("lastError") == expected_error)
        results["HAS_USER_MESSAGE"] = str(
            user_message is not None and user_message.get("text") == prompt
        )
        results["HAS_SYSTEM_MESSAGE"] = str(
            system_message is not None and system_message.get("text") == expected_error
        )
        results["HAS_NO_RESULT"] = str(not session_payload.get("lastResult"))
        results["DOC_TEXT"] = document.Text.getString()

        failures: list[str] = []
        if results["SETTINGS_SAVED"] != "True":
            failures.append("Save-settings did not persist the requested provider/model.")
        if results["LAST_ERROR_MATCHES"] != "True":
            failures.append("Provider failure flow did not record the expected error.")
        if results["HAS_USER_MESSAGE"] != "True":
            failures.append("Provider failure flow did not retain the submitted prompt.")
        if results["HAS_SYSTEM_MESSAGE"] != "True":
            failures.append("Provider failure flow did not record the provider error activity.")
        if results["HAS_NO_RESULT"] != "True":
            failures.append("Provider failure flow should not record a completed result.")
        if results["DOC_TEXT"] != initial_selection:
            failures.append("Provider-failure flow unexpectedly changed the Writer document.")

        for key, value in results.items():
            print(f"{key}={value}")

        if failures:
            print("VALIDATION_PASSED=False")
            for failure in failures:
                print(f"FAILURE={failure}")
            return 1

        print("VALIDATION_PASSED=True")
        return 0
    except Exception:
        print(f"FAILED_STAGE={stage}", file=sys.stderr)
        raise
    finally:
        try:
            close_document_session(document=document, desktop=desktop)
        except Exception:
            print("FAILED_STAGE=close_document_session", file=sys.stderr)
            raise


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
