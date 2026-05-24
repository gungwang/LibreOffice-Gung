from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from verification_probe_common import (
    close_document_session,
    connect,
    load_document,
    make_property,
    make_url,
    wait_for_uno_result,
)

NON_SCAFFOLD_SENTINEL = "__NON_SCAFFOLD__"
SCAFFOLD_DIRECT_ANSWER = (
    "Sidecar scaffold is running. Planner and provider execution are not implemented yet."
)
STATE_ROOT_ENV_VAR = "LOAIA_EXTENSION_STATE_ROOT"
STATE_FILE_NAME = "sidebar-state.json"


def flatten_text(text: str) -> str:
    return text.replace("\r", "\\r").replace("\n", "\\n")


def _state_file_path() -> Path:
    state_root = os.environ.get(STATE_ROOT_ENV_VAR, "").strip()
    if not state_root:
        raise RuntimeError(
            f"{STATE_ROOT_ENV_VAR} is not set for direct-answer verification."
        )

    return Path(state_root) / STATE_FILE_NAME


def _load_state_data() -> dict[str, object]:
    state_file = _state_file_path()
    if not state_file.exists():
        return {}

    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _coerce_messages(payload: dict[str, object]) -> list[dict[str, str]]:
    raw_messages = payload.get("messages")
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


def _load_session_snapshot(prompt: str) -> tuple[dict[str, object], dict[str, object]] | None:
    state_data = _load_state_data()
    sessions = state_data.get("sessions")
    if not isinstance(sessions, dict):
        return None

    for payload in sessions.values():
        if not isinstance(payload, dict):
            continue

        last_prompt = payload.get("lastPrompt")
        last_result = payload.get("lastResult")
        if last_prompt == prompt and isinstance(last_result, str) and last_result.strip():
            return state_data, payload

    return None


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


def verify(
    context: object,
    prompt: str,
    initial_selection: str,
    expected_answer: str,
    expected_provider: str | None = None,
    expected_model: str | None = None,
) -> int:
    desktop = None
    document = None
    try:
        desktop, document = load_document(context, "private:factory/swriter")
        controller = document.getCurrentController()
        frame = controller.getFrame()

        open_sidebar_url = make_url("open-sidebar")
        preview_url = make_url("preview-selection")
        open_dispatch = frame.queryDispatch(open_sidebar_url, "_self", 0)
        preview_dispatch = frame.queryDispatch(preview_url, "_self", 0)
        results: dict[str, str] = {
            "OPEN_SIDEBAR_DISPATCH_PRESENT": str(open_dispatch is not None),
            "PREVIEW_DISPATCH_PRESENT": str(preview_dispatch is not None),
        }

        if open_dispatch is None or preview_dispatch is None:
            for key, value in results.items():
                print(f"{key}={value}")
            print("VALIDATION_PASSED=False")
            print("FAILURE=Protocol dispatch is not available for one or more commands.")
            return 1

        open_dispatch.dispatch(open_sidebar_url, ())

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

        state_data, session_payload = wait_for_uno_result(
            lambda: _load_session_snapshot(prompt),
            "direct-answer session state",
        )
        state_file = _state_file_path()
        messages = _coerce_messages(session_payload)
        user_message = next((message for message in reversed(messages) if message["role"] == "user"), None)
        assistant_message = next(
            (message for message in reversed(messages) if message["role"] == "assistant"),
            None,
        )
        rendered_result = (
            assistant_message["text"] if assistant_message is not None else ""
        )

        results["STATE_FILE_PRESENT"] = str(state_file.exists())
        results["STATE_FILE_PATH"] = str(state_file)
        results["SESSION_COUNT"] = str(
            len(state_data.get("sessions", {}))
            if isinstance(state_data.get("sessions"), dict)
            else 0
        )
        results["LAST_PROMPT_MATCHES"] = str(session_payload.get("lastPrompt") == prompt)
        results["LAST_RESULT"] = flatten_text(str(session_payload.get("lastResult") or ""))
        results["HAS_USER_MESSAGE"] = str(
            user_message is not None and user_message.get("text") == prompt
        )
        results["HAS_ASSISTANT_MESSAGE"] = str(assistant_message is not None)
        results["HAS_RECENT_ACTIVITY"] = str(len(messages) >= 2)
        results["MESSAGE_COUNT"] = str(len(messages))
        if expected_provider is not None:
            results["HAS_EXPECTED_PROVIDER"] = str(
                assistant_message is not None
                and assistant_message.get("provider") == expected_provider
            )
        if expected_model is not None:
            results["HAS_EXPECTED_MODEL"] = str(
                assistant_message is not None
                and assistant_message.get("model") == expected_model
            )
        if expected_answer == NON_SCAFFOLD_SENTINEL:
            results["HAS_EXPECTED_ANSWER"] = str(
                rendered_result not in ("", "No completed result yet.", SCAFFOLD_DIRECT_ANSWER)
            )
        else:
            results["HAS_EXPECTED_ANSWER"] = str(
                rendered_result == expected_answer
            )
        results["DOC_TEXT"] = document.Text.getString()

        failures: list[str] = []
        if results["STATE_FILE_PRESENT"] != "True":
            failures.append("Direct-answer session state file was not created.")
        if results["LAST_PROMPT_MATCHES"] != "True":
            failures.append("Session state did not retain the submitted prompt.")
        if results["HAS_USER_MESSAGE"] != "True":
            failures.append("Session history did not record the user prompt.")
        if results["HAS_ASSISTANT_MESSAGE"] != "True":
            failures.append("Session history did not record the assistant answer.")
        if expected_provider is not None and results["HAS_EXPECTED_PROVIDER"] != "True":
            failures.append("Session history did not show the expected provider.")
        if expected_model is not None and results["HAS_EXPECTED_MODEL"] != "True":
            failures.append("Session history did not show the expected model.")
        if results["HAS_EXPECTED_ANSWER"] != "True":
            failures.append("Session state did not record the direct answer result.")
        if results["HAS_RECENT_ACTIVITY"] != "True":
            failures.append("Session history did not include both sides of the direct-answer exchange.")
        if results["DOC_TEXT"] != initial_selection:
            failures.append("Direct answer flow unexpectedly changed the Writer document.")

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
    if len(argv) not in (4, 6):
        print(
            "Usage: verify_sidebar_direct_answer.py <pipe_name> <prompt> "
            "<initial_selection> <expected_answer> "
            "[<expected_provider> <expected_model>]",
            file=sys.stderr,
        )
        return 2

    pipe_name, prompt, initial_selection, expected_answer, *extra = argv
    expected_provider = extra[0] if len(extra) == 2 else None
    expected_model = extra[1] if len(extra) == 2 else None
    context = connect(pipe_name)
    return verify(
        context=context,
        prompt=prompt,
        initial_selection=initial_selection,
        expected_answer=expected_answer,
        expected_provider=expected_provider,
        expected_model=expected_model,
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