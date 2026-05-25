from __future__ import annotations

import os
import sys

from verification_probe_common import (
    coerce_sidebar_messages,
    close_document_session,
    connect,
    find_sidebar_session,
    load_document_with_controller,
    load_sidebar_state,
    make_property,
    make_url,
    wait_for_uno_result,
)

_CAPTURED_ANSWER_FILENAME = ".captured_last_result.txt"


def _load_saved_settings(provider: str, model: str) -> tuple[dict[str, object], dict[str, object]] | None:
    state_data = load_sidebar_state()
    settings = state_data.get("settings")
    if not isinstance(settings, dict):
        return None

    if settings.get("provider") != provider or settings.get("model") != model:
        return None

    return state_data, settings


def _load_saved_session(
    provider: str,
    model: str,
    prompt: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]] | None:
    settings_match = _load_saved_settings(provider, model)
    if settings_match is None:
        return None

    state_data, settings = settings_match
    session_match = find_sidebar_session(last_prompt=prompt, require_result=True)
    if session_match is None:
        return None

    _session_state_data, session_payload = session_match
    return state_data, settings, session_payload


def _answer_matches(actual_result: str, expected_answer: str) -> bool:
    if expected_answer == "*":
        return bool(actual_result.strip())

    return actual_result == expected_answer


def _capture_last_result(answer: str) -> None:
    state_root = os.environ.get("LOAIA_EXTENSION_STATE_ROOT", "")
    if not state_root:
        return

    cap_path = os.path.join(state_root, _CAPTURED_ANSWER_FILENAME)
    with open(cap_path, "w", encoding="utf-8") as handle:
        handle.write(answer)


def _load_captured_last_result() -> str:
    state_root = os.environ.get("LOAIA_EXTENSION_STATE_ROOT", "")
    if not state_root:
        return ""

    cap_path = os.path.join(state_root, _CAPTURED_ANSWER_FILENAME)
    if not os.path.isfile(cap_path):
        return ""

    with open(cap_path, encoding="utf-8") as handle:
        return handle.read().strip()


def _save_session(
    context: object,
    provider: str,
    model: str,
    prompt: str,
    initial_selection: str,
    expected_answer: str,
    expected_api_key_status: str,
) -> int:
    desktop = None
    document = None
    try:
        print("PHASE=save:load-document", flush=True)
        desktop, document, controller = load_document_with_controller(
            context,
            "private:factory/swriter",
        )
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
            print(
                "FAILURE=Protocol dispatch is not available for one or more persistence commands."
            )
            return 1

        print("PHASE=save:open-sidebar", flush=True)
        open_dispatch.dispatch(open_sidebar_url, ())
        print("PHASE=save:save-settings", flush=True)
        save_dispatch.dispatch(
            save_settings_url,
            (
                make_property("Provider", provider),
                make_property("Model", model),
            ),
        )

        _state_data, settings = wait_for_uno_result(
            lambda: _load_saved_settings(provider, model),
            "saved persistence settings",
        )
        results["SETTINGS_PROVIDER"] = str(settings.get("provider") or "")
        results["SETTINGS_MODEL"] = str(settings.get("model") or "")
        results["SETTINGS_SAVED"] = str(
            settings.get("provider") == provider and settings.get("model") == model
        )
        results["EXPECTED_API_KEY_STATUS_CHECK_SKIPPED"] = expected_api_key_status

        text = document.Text
        cursor = text.createTextCursor()
        text.insertString(cursor, initial_selection, False)
        cursor.gotoStart(False)
        cursor.goRight(len(initial_selection), True)
        controller.select(cursor)

        print("PHASE=save:preview-direct-answer", flush=True)
        preview_dispatch.dispatch(
            preview_url,
            (make_property("Prompt", prompt),),
        )

        _state_data, _settings, session_payload = wait_for_uno_result(
            lambda: _load_saved_session(provider, model, prompt),
            "saved persistence session",
        )
        actual_result = str(session_payload.get("lastResult") or "")
        messages = coerce_sidebar_messages(session_payload)
        user_message = next((message for message in reversed(messages) if message["role"] == "user"), None)
        assistant_message = next(
            (message for message in reversed(messages) if message["role"] == "assistant"),
            None,
        )
        results["LAST_PROMPT_MATCHES"] = str(session_payload.get("lastPrompt") == prompt)
        results["LAST_RESULT_MATCHES"] = str(_answer_matches(actual_result, expected_answer))
        results["HAS_USER_MESSAGE"] = str(
            user_message is not None and user_message.get("text") == prompt
        )
        results["HAS_ASSISTANT_MESSAGE"] = str(
            assistant_message is not None
            and _answer_matches(str(assistant_message.get("text") or ""), expected_answer)
        )
        results["HAS_EXPECTED_PROVIDER"] = str(
            assistant_message is not None and assistant_message.get("provider") == provider
        )
        results["HAS_EXPECTED_MODEL"] = str(
            assistant_message is not None and assistant_message.get("model") == model
        )
        results["LAST_ERROR_EMPTY"] = str(not session_payload.get("lastError"))
        if expected_answer == "*" and actual_result:
            _capture_last_result(actual_result)
            print(f"CAPTURED_LAST_RESULT={actual_result}", flush=True)
        results["DOC_TEXT"] = document.Text.getString()

        failures: list[str] = []
        if results["SETTINGS_SAVED"] != "True":
            failures.append("Persistence setup did not save the requested provider/model.")
        if results["LAST_PROMPT_MATCHES"] != "True":
            failures.append("Persistence setup did not retain the submitted prompt.")
        if results["LAST_RESULT_MATCHES"] != "True":
            failures.append("Persistence setup did not retain the direct answer.")
        if results["HAS_USER_MESSAGE"] != "True":
            failures.append("Persistence setup did not retain the user message.")
        if results["HAS_ASSISTANT_MESSAGE"] != "True":
            failures.append("Persistence setup did not retain the assistant message.")
        if results["HAS_EXPECTED_PROVIDER"] != "True":
            failures.append("Persistence setup did not record the expected provider metadata.")
        if results["HAS_EXPECTED_MODEL"] != "True":
            failures.append("Persistence setup did not record the expected model metadata.")
        if results["LAST_ERROR_EMPTY"] != "True":
            failures.append("Persistence setup unexpectedly recorded an error.")
        if results["DOC_TEXT"] != initial_selection:
            failures.append("Direct-answer persistence setup unexpectedly changed the document.")

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


def _restore_session(
    context: object,
    provider: str,
    model: str,
    prompt: str,
    expected_answer: str,
    expected_api_key_status: str,
) -> int:
    # When using wildcard matching, read the captured answer from the save phase.
    if expected_answer == "*":
        captured_answer = _load_captured_last_result()
        if captured_answer:
            expected_answer = captured_answer

    desktop = None
    document = None
    try:
        print("PHASE=restore:load-document", flush=True)
        desktop, document, controller = load_document_with_controller(
            context,
            "private:factory/swriter",
        )
        frame = controller.getFrame()

        open_sidebar_url = make_url("open-sidebar")
        open_dispatch = frame.queryDispatch(open_sidebar_url, "_self", 0)
        results: dict[str, str] = {
            "OPEN_SIDEBAR_DISPATCH_PRESENT": str(open_dispatch is not None),
        }

        if open_dispatch is None:
            for key, value in results.items():
                print(f"{key}={value}")
            print("VALIDATION_PASSED=False")
            print("FAILURE=Protocol dispatch is not available for open-sidebar.")
            return 1

        print("PHASE=restore:open-sidebar", flush=True)
        open_dispatch.dispatch(open_sidebar_url, ())
        _state_data, settings, session_payload = wait_for_uno_result(
            lambda: _load_saved_session(provider, model, prompt),
            "restored persistence session",
        )
        actual_result = str(session_payload.get("lastResult") or "")
        messages = coerce_sidebar_messages(session_payload)
        user_message = next((message for message in reversed(messages) if message["role"] == "user"), None)
        assistant_message = next(
            (message for message in reversed(messages) if message["role"] == "assistant"),
            None,
        )
        results["SETTINGS_PROVIDER"] = str(settings.get("provider") or "")
        results["SETTINGS_MODEL"] = str(settings.get("model") or "")
        results["SETTINGS_RESTORED"] = str(
            settings.get("provider") == provider and settings.get("model") == model
        )
        results["EXPECTED_API_KEY_STATUS_CHECK_SKIPPED"] = expected_api_key_status
        results["LAST_PROMPT_MATCHES"] = str(session_payload.get("lastPrompt") == prompt)
        results["LAST_RESULT_MATCHES"] = str(_answer_matches(actual_result, expected_answer))
        results["HAS_USER_MESSAGE"] = str(
            user_message is not None and user_message.get("text") == prompt
        )
        results["HAS_ASSISTANT_MESSAGE"] = str(
            assistant_message is not None
            and _answer_matches(str(assistant_message.get("text") or ""), expected_answer)
        )
        results["HAS_EXPECTED_PROVIDER"] = str(
            assistant_message is not None and assistant_message.get("provider") == provider
        )
        results["HAS_EXPECTED_MODEL"] = str(
            assistant_message is not None and assistant_message.get("model") == model
        )
        results["LAST_ERROR_EMPTY"] = str(not session_payload.get("lastError"))
        results["DOC_TEXT"] = document.Text.getString()

        failures: list[str] = []
        if results["SETTINGS_RESTORED"] != "True":
            failures.append("Persistence restore did not keep the saved provider/model.")
        if results["LAST_PROMPT_MATCHES"] != "True":
            failures.append("Persistence restore did not keep the saved prompt.")
        if results["LAST_RESULT_MATCHES"] != "True":
            failures.append("Persistence restore did not keep the saved result.")
        if results["HAS_USER_MESSAGE"] != "True":
            failures.append("Persistence restore did not keep the saved user message.")
        if results["HAS_ASSISTANT_MESSAGE"] != "True":
            failures.append("Persistence restore did not keep the saved assistant message.")
        if results["HAS_EXPECTED_PROVIDER"] != "True":
            failures.append("Persistence restore did not keep the provider metadata.")
        if results["HAS_EXPECTED_MODEL"] != "True":
            failures.append("Persistence restore did not keep the model metadata.")
        if results["LAST_ERROR_EMPTY"] != "True":
            failures.append("Persistence restore unexpectedly recorded an error.")
        if results["DOC_TEXT"] != "":
            failures.append("Persistence restore should not preload content into a new Writer document.")

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
    if len(argv) not in (7, 8):
        print(
            "Usage: verify_sidebar_persistence.py <pipe_name> <save|restore> "
            "<provider> <model> <prompt> <expected_answer> <expected_api_key_status> "
            "[<initial_selection for save>]",
            file=sys.stderr,
        )
        return 2

    pipe_name, mode, provider, model, prompt, expected_answer, expected_api_key_status, *rest = argv
    print("PHASE=connect:start", flush=True)
    context = connect(pipe_name)
    print("PHASE=connect:done", flush=True)

    if mode == "save":
        if len(rest) != 1:
            print(
                "Save mode requires an initial selection argument.",
                file=sys.stderr,
            )
            return 2

        return _save_session(
            context=context,
            provider=provider,
            model=model,
            prompt=prompt,
            initial_selection=rest[0],
            expected_answer=expected_answer,
            expected_api_key_status=expected_api_key_status,
        )

    if mode == "restore":
        if rest:
            print(
                "Restore mode does not accept an initial selection argument.",
                file=sys.stderr,
            )
            return 2

        return _restore_session(
            context=context,
            provider=provider,
            model=model,
            prompt=prompt,
            expected_answer=expected_answer,
            expected_api_key_status=expected_api_key_status,
        )

    print(f"Unsupported mode: {mode}", file=sys.stderr)
    return 2


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
