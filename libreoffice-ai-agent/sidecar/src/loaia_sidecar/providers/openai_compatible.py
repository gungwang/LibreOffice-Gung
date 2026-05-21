from loaia_sidecar.providers.base import BaseProviderAdapter, ProviderRequest


class OpenAICompatibleAdapter(BaseProviderAdapter):
    name = "openai-compatible"

    def complete(self, request: ProviderRequest) -> str:
        raise NotImplementedError("OpenAI-compatible adapter is not implemented yet")

    def stream(self, request: ProviderRequest):
        raise NotImplementedError("OpenAI-compatible adapter is not implemented yet")
