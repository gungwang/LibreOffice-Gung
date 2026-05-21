from loaia_sidecar.providers.base import BaseProviderAdapter, ProviderRequest


class OpenRouterAdapter(BaseProviderAdapter):
    name = "openrouter"

    def complete(self, request: ProviderRequest) -> str:
        raise NotImplementedError("OpenRouter adapter is not implemented yet")

    def stream(self, request: ProviderRequest):
        raise NotImplementedError("OpenRouter adapter is not implemented yet")
