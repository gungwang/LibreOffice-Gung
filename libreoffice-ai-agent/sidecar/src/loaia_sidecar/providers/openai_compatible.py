from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from loaia_sidecar.config.settings import SidecarSettings
from loaia_sidecar.providers.base import BaseProviderAdapter, ProviderChunk, ProviderRequest


class OpenAICompatibleAdapter(BaseProviderAdapter):
    name = "openai-compatible"

    def __init__(
        self,
        settings: SidecarSettings,
        urlopen_impl: Callable[..., object] = urlopen,
    ) -> None:
        self.settings = settings
        self._urlopen = urlopen_impl

    def complete(self, request: ProviderRequest) -> str:
        endpoint_url = self.settings.local_endpoint_url.rstrip("/")
        url = f"{endpoint_url}/chat/completions"

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
            url=url,
            data=encoded_payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
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
                f"Local endpoint request failed with HTTP {exc.code}: {message}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"Local endpoint unreachable at {endpoint_url}: {exc.reason}"
            ) from exc

        try:
            response_payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Local endpoint response was not valid JSON") from exc

        return _extract_assistant_text(response_payload)

    def stream(self, request: ProviderRequest) -> Iterable[ProviderChunk]:
        raise NotImplementedError("OpenAI-compatible streaming is not implemented yet")


def _build_user_message(prompt: str, context_text: str) -> str:
    sections: list[str] = []
    if context_text.strip():
        sections.append(f"Selected context:\n{context_text.strip()}")
    sections.append(f"User request:\n{prompt.strip()}")
    return "\n\n".join(sections)


def _extract_error_detail(raw_body: bytes | None) -> str | None:
    if raw_body is None:
        return None
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or "")
        if isinstance(error, str):
            return error
    return None


def _extract_assistant_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise RuntimeError("Local endpoint response was not a JSON object")

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Local endpoint response did not contain any choices")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("Local endpoint response choice was not a JSON object")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("Local endpoint response message was not a JSON object")

    content = message.get("content")
    if not isinstance(content, str):
        raise RuntimeError("Local endpoint response content was not a string")

    return content.strip()
