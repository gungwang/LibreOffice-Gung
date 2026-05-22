import json

import pytest

from loaia_sidecar.config.settings import SidecarSettings
from loaia_sidecar.providers.base import ProviderRequest
from loaia_sidecar.providers.openai_compatible import OpenAICompatibleAdapter


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_openai_compatible_adapter_posts_chat_completion() -> None:
    captured_request: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        captured_request["url"] = request.full_url
        captured_request["method"] = request.get_method()
        captured_request["timeout"] = timeout
        captured_request["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "The answer is 42.",
                        }
                    }
                ]
            }
        )

    settings = SidecarSettings(local_endpoint_url="http://127.0.0.1:11434/v1")
    adapter = OpenAICompatibleAdapter(settings=settings, urlopen_impl=fake_urlopen)

    result = adapter.complete(
        ProviderRequest(
            provider="openai-compatible",
            model="qwen2.5-14b-instruct",
            prompt="What is the meaning of life?",
            context_text="selection text",
        )
    )

    assert result == "The answer is 42."
    assert captured_request["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert captured_request["method"] == "POST"
    payload = captured_request["payload"]
    assert payload["model"] == "qwen2.5-14b-instruct"
    assert len(payload["messages"]) == 1
    assert "selection text" in payload["messages"][0]["content"]


def test_openai_compatible_adapter_handles_endpoint_url_trailing_slash() -> None:
    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        assert request.full_url == "http://localhost:8080/v1/chat/completions"
        return FakeResponse(
            {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        )

    settings = SidecarSettings(local_endpoint_url="http://localhost:8080/v1/")
    adapter = OpenAICompatibleAdapter(settings=settings, urlopen_impl=fake_urlopen)

    result = adapter.complete(
        ProviderRequest(
            provider="openai-compatible",
            model="test-model",
            prompt="test",
            context_text="",
        )
    )
    assert result == "ok"


def test_openai_compatible_adapter_raises_on_invalid_response() -> None:
    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        return FakeResponse({"choices": []})

    settings = SidecarSettings()
    adapter = OpenAICompatibleAdapter(settings=settings, urlopen_impl=fake_urlopen)

    with pytest.raises(RuntimeError, match="did not contain any choices"):
        adapter.complete(
            ProviderRequest(
                provider="openai-compatible",
                model="test-model",
                prompt="test",
                context_text="",
            )
        )


def test_openai_compatible_adapter_raises_on_http_error() -> None:
    from urllib.error import HTTPError

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        raise HTTPError(
            url="http://localhost:11434/v1/chat/completions",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=None,
        )

    settings = SidecarSettings()
    adapter = OpenAICompatibleAdapter(settings=settings, urlopen_impl=fake_urlopen)

    with pytest.raises(RuntimeError, match="Local endpoint request failed"):
        adapter.complete(
            ProviderRequest(
                provider="openai-compatible",
                model="test-model",
                prompt="test",
                context_text="",
            )
        )


def test_openai_compatible_adapter_raises_on_url_error() -> None:
    from urllib.error import URLError

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        raise URLError("Connection refused")

    settings = SidecarSettings()
    adapter = OpenAICompatibleAdapter(settings=settings, urlopen_impl=fake_urlopen)

    with pytest.raises(RuntimeError, match="Local endpoint unreachable"):
        adapter.complete(
            ProviderRequest(
                provider="openai-compatible",
                model="test-model",
                prompt="test",
                context_text="",
            )
        )
