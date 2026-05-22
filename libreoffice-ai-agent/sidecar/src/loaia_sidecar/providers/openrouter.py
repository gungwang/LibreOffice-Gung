from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from loaia_sidecar.config.secrets import SecretStore
from loaia_sidecar.config.settings import SidecarSettings
from loaia_sidecar.providers.base import BaseProviderAdapter, ProviderChunk, ProviderRequest


class OpenRouterAdapter(BaseProviderAdapter):
    name = "openrouter"

    def __init__(
        self,
        settings: SidecarSettings,
        secret_store: SecretStore,
        urlopen_impl: Callable[..., object] = urlopen,
    ) -> None:
        self.settings = settings
        self.secret_store = secret_store
        self._urlopen = urlopen_impl

    def complete(self, request: ProviderRequest) -> str:
        api_key = self.secret_store.get_api_key(self.name)
        if api_key is None:
            raise ValueError(
                "OpenRouter API key is not configured. "
                "Set OPENROUTER_API_KEY or LOAIA_OPENROUTER_API_KEY."
            )

        encoded_payload = json.dumps(
            {
                "model": request.model,
                "messages": [
                    {
                        "role": "user",
                        "content": _build_user_message(
                            prompt=request.prompt,
                            context_text=request.context_text,
                        ),
                    }
                ],
            }
        ).encode("utf-8")
        http_request = Request(
            url="https://openrouter.ai/api/v1/chat/completions",
            data=encoded_payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Title": "LibreOffice AI Agent",
            },
            method="POST",
        )

        try:
            with self._urlopen(
                http_request,
                timeout=self.settings.request_timeout_seconds,
            ) as response:
                raw_body = response.read()
        except HTTPError as exc:
            detail = _extract_error_detail(exc.read())
            message = detail or str(exc.reason)
            raise RuntimeError(
                f"OpenRouter request failed with HTTP {exc.code}: {message}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

        try:
            response_payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("OpenRouter response was not valid JSON") from exc

        return _extract_assistant_text(response_payload)

    def stream(self, request: ProviderRequest) -> Iterable[ProviderChunk]:
        api_key = self.secret_store.get_api_key(self.name)
        if api_key is None:
            raise ValueError(
                "OpenRouter API key is not configured. "
                "Set OPENROUTER_API_KEY or LOAIA_OPENROUTER_API_KEY."
            )

        encoded_payload = json.dumps(
            {
                "model": request.model,
                "messages": [
                    {
                        "role": "user",
                        "content": _build_user_message(
                            prompt=request.prompt,
                            context_text=request.context_text,
                        ),
                    }
                ],
                "stream": True,
            }
        ).encode("utf-8")
        http_request = Request(
            url="https://openrouter.ai/api/v1/chat/completions",
            data=encoded_payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
                "X-Title": "LibreOffice AI Agent",
            },
            method="POST",
        )

        try:
            response = self._urlopen(
                http_request,
                timeout=self.settings.request_timeout_seconds,
            )
        except HTTPError as exc:
            detail = _extract_error_detail(exc.read())
            message = detail or str(exc.reason)
            raise RuntimeError(
                f"OpenRouter request failed with HTTP {exc.code}: {message}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

        try:
            yield from _parse_sse_chunks(response)
        finally:
            response.close()


def _build_user_message(prompt: str, context_text: str) -> str:
    sections: list[str] = []
    if context_text.strip():
        sections.append(f"Selected context:\n{context_text.strip()}")
    sections.append(f"User request:\n{prompt.strip()}")
    return "\n\n".join(sections)


def _extract_assistant_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise RuntimeError("OpenRouter response was not a JSON object")

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("OpenRouter response did not contain any choices")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("OpenRouter response choice was malformed")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("OpenRouter response did not contain an assistant message")

    content = message.get("content")
    if isinstance(content, str):
        text = content.strip()
        if text:
            return text

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue

            text = item.get("text")
            if isinstance(text, str) and text:
                text_parts.append(text)

        combined_text = "".join(text_parts).strip()
        if combined_text:
            return combined_text

    raise RuntimeError("OpenRouter response did not contain assistant text")


def _extract_error_detail(raw_body: bytes) -> str:
    decoded_body = raw_body.decode("utf-8", errors="ignore").strip()
    if not decoded_body:
        return ""

    try:
        payload = json.loads(decoded_body)
    except json.JSONDecodeError:
        return decoded_body

    if not isinstance(payload, dict):
        return decoded_body

    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    return decoded_body


def _parse_sse_chunks(response: object) -> Iterable[ProviderChunk]:
    """Parse Server-Sent Events from an OpenAI-compatible streaming response."""
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
        if not line.startswith("data: "):
            continue

        data = line[len("data: "):]
        if data == "[DONE]":
            break

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict):
            continue

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            continue

        delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
        if not isinstance(delta, dict):
            continue

        content = delta.get("content")
        if isinstance(content, str) and content:
            yield ProviderChunk(text=content)
