from __future__ import annotations

import os
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

_CAPTURED_ANSWER_FILENAME = ".captured_last_result.txt"


def extract_section(summary_text: str, header: str, next_header: str | None = None) -> str:
    header_marker = f"{header}:\n"
    start_index = summary_text.find(header_marker)
    if start_index < 0:
        return ""

    content_start = start_index + len(header_marker)
    if next_header is None:
        return summary_text[content_start:].strip()

    next_marker = f"\n\n{next_header}:\n"
    end_index = summary_text.find(next_marker, content_start)
    if end_index < 0:
        return summary_text[content_start:].strip()

    return summary_text[content_start:end_index].strip()


def _check_last_result(summary_text: str, expected_answer: str) -> tuple[bool, str]:
    """Check whether the expected answer is in the summary's Last result section.

    When expected_answer is "*", any non-empty result passes and the actual text
    is returned so it can be forwarded to the restore phase.
    """
    actual_result = extract_section(summary_text, "Last result", "Recent activity")
    if expected_answer == "*":
        no_result = actual_result in ("", "No completed result yet.")
        return (not no_result, actual_result)
    return (f"Last result:\n{expected_answer}" in summary_text, expected_answer)


def _check_recent_activity(summary_text: str, expected_answer: str) -> bool:
    """Check whether the expected answer appears in the Recent activity section."""
    recent_activity = extract_section(summary_text, "Recent activity")
    if expected_answer == "*":
        return recent_activity != ""
    return expected_answer in recent_activity


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
            print(
                "FAILURE=Protocol dispatch is not available for one or more persistence commands."
            )
            return 1

        print("PHASE=save:open-sidebar", flush=True)
        open_dispatch.dispatch(open_sidebar_url, ())
        panel_window = get_sidebar_panel_window(context, frame)
        provider_input = panel_window.getControl("ProviderInput")
        model_input = panel_window.getControl("ModelInput")
        settings_status_control = panel_window.getControl("SettingsStatus")
        approve_button = panel_window.getControl("ApproveButton")

        set_model_text(provider_input, provider)
        set_model_text(model_input, model)
        print("PHASE=save:save-settings", flush=True)
        save_dispatch.dispatch(
            save_settings_url,
            (
                make_property("Provider", provider),
                make_property("Model", model),
            ),
        )

        status_after_save = model_text(panel_window.getControl("Status"))
        settings_after_save = model_text(settings_status_control)
        results["PROVIDER_INPUT_AFTER_SAVE"] = model_text(provider_input)
        results["MODEL_INPUT_AFTER_SAVE"] = model_text(model_input)
        results["STATUS_HAS_EXPECTED_PROVIDER"] = str(f"Provider: {provider}" in status_after_save)
        results["STATUS_HAS_EXPECTED_MODEL"] = str(f"Model: {model}" in status_after_save)
        results["STATUS_HAS_API_KEY"] = str(
            f"API key: {expected_api_key_status}" in status_after_save
        )
        results["SETTINGS_STATUS_HAS_PROVIDER"] = str(
            f"Provider profile: {provider}" in settings_after_save
        )
        results["SETTINGS_STATUS_HAS_MODEL"] = str(f"Model profile: {model}" in settings_after_save)
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

        print("PHASE=save:preview-direct-answer", flush=True)
        preview_dispatch.dispatch(
            preview_url,
            (make_property("Prompt", prompt),),
        )

        status_after_answer = model_text(panel_window.getControl("Status"))
        summary_after_answer = model_text(panel_window.getControl("Summary"))
        results["ANSWER_STATUS_HAS_PROVIDER"] = str(f"Provider: {provider}" in status_after_answer)
        results["ANSWER_STATUS_HAS_MODEL"] = str(f"Model: {model}" in status_after_answer)
        results["ANSWER_STATUS_HAS_API_KEY"] = str(
            f"API key: {expected_api_key_status}" in status_after_answer
        )
        results["HAS_PROMPT_IN_SUMMARY"] = str(f"Prompt:\n{prompt}" in summary_after_answer)
        has_result, captured_answer = _check_last_result(summary_after_answer, expected_answer)
        results["HAS_LAST_RESULT_IN_SUMMARY"] = str(has_result)
        results["HAS_RECENT_ACTIVITY_IN_SUMMARY"] = str(
            _check_recent_activity(summary_after_answer, expected_answer)
        )
        if captured_answer and expected_answer == "*":
            # Persist captured answer for the restore phase to verify.
            state_root = os.environ.get("LOAIA_EXTENSION_STATE_ROOT", "")
            if state_root:
                cap_path = os.path.join(state_root, _CAPTURED_ANSWER_FILENAME)
                with open(cap_path, "w", encoding="utf-8") as f:
                    f.write(captured_answer)
            print(f"CAPTURED_LAST_RESULT={captured_answer}", flush=True)
        results["HAS_NO_PENDING_PREVIEW"] = str(
            "Pending preview:\nNo pending proposal." in summary_after_answer
        )
        results["APPROVE_DISABLED_AFTER_DIRECT_ANSWER"] = str(
            not control_is_enabled(approve_button)
        )
        results["DOC_TEXT"] = document.Text.getString()

        failures: list[str] = []
        if results["PROVIDER_INPUT_AFTER_SAVE"] != provider:
            failures.append("Provider input did not keep the saved provider value.")
        if results["MODEL_INPUT_AFTER_SAVE"] != model:
            failures.append("Model input did not keep the saved model value.")
        if results["STATUS_HAS_EXPECTED_PROVIDER"] != "True":
            failures.append("Sidebar status did not show the saved provider after save-settings.")
        if results["STATUS_HAS_EXPECTED_MODEL"] != "True":
            failures.append("Sidebar status did not show the saved model after save-settings.")
        if results["STATUS_HAS_API_KEY"] != "True":
            failures.append("Sidebar status did not show the expected API-key status.")
        if results["SETTINGS_STATUS_HAS_PROVIDER"] != "True":
            failures.append("Settings section did not show the saved provider.")
        if results["SETTINGS_STATUS_HAS_MODEL"] != "True":
            failures.append("Settings section did not show the saved model.")
        if results["SETTINGS_STATUS_HAS_API_KEY"] != "True":
            failures.append("Settings section did not show the expected API-key status.")
        if results["SETTINGS_STATUS_HAS_SAVE_NOTICE"] != "True":
            failures.append("Settings section did not show the save confirmation notice.")
        if results["ANSWER_STATUS_HAS_PROVIDER"] != "True":
            failures.append("Direct-answer status did not retain the saved provider.")
        if results["ANSWER_STATUS_HAS_MODEL"] != "True":
            failures.append("Direct-answer status did not retain the saved model.")
        if results["ANSWER_STATUS_HAS_API_KEY"] != "True":
            failures.append("Direct-answer status did not retain the expected API-key status.")
        if results["HAS_PROMPT_IN_SUMMARY"] != "True":
            failures.append("Sidebar summary did not retain the prompt before restart.")
        if results["HAS_LAST_RESULT_IN_SUMMARY"] != "True":
            failures.append("Sidebar summary did not retain the direct answer before restart.")
        if results["HAS_RECENT_ACTIVITY_IN_SUMMARY"] != "True":
            failures.append(
                "Sidebar recent activity did not retain the direct answer before restart."
            )
        if results["HAS_NO_PENDING_PREVIEW"] != "True":
            failures.append("Sidebar summary did not show the empty pending-preview state.")
        if results["APPROVE_DISABLED_AFTER_DIRECT_ANSWER"] != "True":
            failures.append("Approve should stay disabled after a direct answer.")
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
        state_root = os.environ.get("LOAIA_EXTENSION_STATE_ROOT", "")
        if state_root:
            cap_path = os.path.join(state_root, _CAPTURED_ANSWER_FILENAME)
            if os.path.isfile(cap_path):
                with open(cap_path, encoding="utf-8") as f:
                    expected_answer = f.read().strip()

    desktop = None
    document = None
    try:
        print("PHASE=restore:load-document", flush=True)
        desktop, document = load_document(context, "private:factory/swriter")
        controller = document.getCurrentController()
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
        panel_window = get_sidebar_panel_window(context, frame)
        status_after_open = model_text(panel_window.getControl("Status"))
        settings_after_open = model_text(panel_window.getControl("SettingsStatus"))
        summary_after_open = model_text(panel_window.getControl("Summary"))
        approve_button = panel_window.getControl("ApproveButton")
        provider_input = panel_window.getControl("ProviderInput")
        model_input = panel_window.getControl("ModelInput")

        results["STATUS_HAS_OPEN_COMMAND"] = str("Last command: open-sidebar" in status_after_open)
        results["STATUS_HAS_EXPECTED_PROVIDER"] = str(f"Provider: {provider}" in status_after_open)
        results["STATUS_HAS_EXPECTED_MODEL"] = str(f"Model: {model}" in status_after_open)
        results["STATUS_HAS_API_KEY"] = str(
            f"API key: {expected_api_key_status}" in status_after_open
        )
        results["PROVIDER_INPUT_RESTORED"] = model_text(provider_input)
        results["MODEL_INPUT_RESTORED"] = model_text(model_input)
        results["SETTINGS_STATUS_HAS_PROVIDER"] = str(
            f"Provider profile: {provider}" in settings_after_open
        )
        results["SETTINGS_STATUS_HAS_MODEL"] = str(f"Model profile: {model}" in settings_after_open)
        results["SETTINGS_STATUS_HAS_API_KEY"] = str(
            f"API key status: {expected_api_key_status}" in settings_after_open
        )
        results["HAS_PROMPT_IN_SUMMARY"] = str(f"Prompt:\n{prompt}" in summary_after_open)
        has_result, _ = _check_last_result(summary_after_open, expected_answer)
        results["HAS_LAST_RESULT_IN_SUMMARY"] = str(has_result)
        results["HAS_RECENT_ACTIVITY_IN_SUMMARY"] = str(
            _check_recent_activity(summary_after_open, expected_answer)
        )
        results["HAS_EMPTY_SELECTION_IN_SUMMARY"] = str(
            "Selection:\nNo captured selection yet." in summary_after_open
        )
        results["HAS_NO_PENDING_PREVIEW"] = str(
            "Pending preview:\nNo pending proposal." in summary_after_open
        )
        results["APPROVE_DISABLED_AFTER_RESTORE"] = str(not control_is_enabled(approve_button))

        failures: list[str] = []
        if results["STATUS_HAS_OPEN_COMMAND"] != "True":
            failures.append("Sidebar status did not reflect the fresh open-sidebar command.")
        if results["STATUS_HAS_EXPECTED_PROVIDER"] != "True":
            failures.append("Sidebar status did not restore the saved provider.")
        if results["STATUS_HAS_EXPECTED_MODEL"] != "True":
            failures.append("Sidebar status did not restore the saved model.")
        if results["STATUS_HAS_API_KEY"] != "True":
            failures.append("Sidebar status did not restore the expected API-key status.")
        if results["PROVIDER_INPUT_RESTORED"] != provider:
            failures.append("Provider input did not restore the saved value after restart.")
        if results["MODEL_INPUT_RESTORED"] != model:
            failures.append("Model input did not restore the saved value after restart.")
        if results["SETTINGS_STATUS_HAS_PROVIDER"] != "True":
            failures.append("Settings section did not restore the saved provider.")
        if results["SETTINGS_STATUS_HAS_MODEL"] != "True":
            failures.append("Settings section did not restore the saved model.")
        if results["SETTINGS_STATUS_HAS_API_KEY"] != "True":
            failures.append("Settings section did not restore the expected API-key status.")
        if results["HAS_PROMPT_IN_SUMMARY"] != "True":
            failures.append("Sidebar summary did not restore the saved prompt after restart.")
        if results["HAS_LAST_RESULT_IN_SUMMARY"] != "True":
            failures.append("Sidebar summary did not restore the saved result after restart.")
        if results["HAS_RECENT_ACTIVITY_IN_SUMMARY"] != "True":
            failures.append(
                "Sidebar recent activity did not restore the saved result after restart."
            )
        if results["HAS_EMPTY_SELECTION_IN_SUMMARY"] != "True":
            failures.append("Sidebar summary did not reset selection preview on restore.")
        if results["HAS_NO_PENDING_PREVIEW"] != "True":
            failures.append(
                "Sidebar summary did not keep the empty pending-preview state after restart."
            )
        if results["APPROVE_DISABLED_AFTER_RESTORE"] != "True":
            failures.append("Approve should be disabled after restoring a direct-answer session.")

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
