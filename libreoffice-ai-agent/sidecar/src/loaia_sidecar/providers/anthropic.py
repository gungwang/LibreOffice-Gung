from loaia_sidecar.providers.base import BaseProviderAdapter, ProviderRequest


class AnthropicAdapter(BaseProviderAdapter):
    name = "anthropic"

    def complete(self, request: ProviderRequest) -> str:
        raise NotImplementedError("Anthropic adapter is not implemented yet")

    def stream(self, request: ProviderRequest):
        raise NotImplementedError("Anthropic adapter is not implemented yet")
