import json

import pytest

from loaia_sidecar.config.secrets import SecretStore
from loaia_sidecar.config.settings import SidecarSettings
from loaia_sidecar.providers.base import ProviderRequest
from loaia_sidecar.providers.openrouter import OpenRouterAdapter


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_openrouter_adapter_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LOAIA_OPENROUTER_API_KEY", raising=False)

    adapter = OpenRouterAdapter(
        settings=SidecarSettings(),
        secret_store=SecretStore(),
        urlopen_impl=lambda *_args, **_kwargs: None,
    )

    with pytest.raises(ValueError, match="OpenRouter API key is not configured"):
        adapter.complete(
            ProviderRequest(
                provider="openrouter",
                model="openai/gpt-4.1-mini",
                prompt="Summarize this selection.",
                context_text="hello world",
            )
        )


def test_openrouter_adapter_posts_chat_completion_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    captured_request: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        headers = {key.lower(): value for key, value in request.header_items()}
        captured_request["url"] = request.full_url
        captured_request["method"] = request.get_method()
        captured_request["timeout"] = timeout
        captured_request["headers"] = headers
        captured_request["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "OpenRouter response text.",
                        }
                    }
                ]
            }
        )

    adapter = OpenRouterAdapter(
        settings=SidecarSettings(request_timeout_seconds=45),
        secret_store=SecretStore(),
        urlopen_impl=fake_urlopen,
    )

    result = adapter.complete(
        ProviderRequest(
            provider="openrouter",
            model="openai/gpt-4.1-mini",
            prompt="Summarize this selection.",
            context_text="hello world",
        )
    )

    assert result == "OpenRouter response text."
    assert captured_request["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured_request["method"] == "POST"
    assert captured_request["timeout"] == 45
    assert captured_request["headers"] == {
        "accept": "application/json",
        "authorization": "Bearer test-openrouter-key",
        "content-type": "application/json",
        "x-title": "LibreOffice AI Agent",
    }
    assert captured_request["payload"] == {
        "model": "openai/gpt-4.1-mini",
        "messages": [
            {
                "role": "user",
                "content": (
                    "Selected context:\nhello world\n\n"
                    "User request:\nSummarize this selection."
                ),
            }
        ],
    }