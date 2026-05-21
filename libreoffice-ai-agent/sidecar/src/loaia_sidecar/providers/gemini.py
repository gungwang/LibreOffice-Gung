from loaia_sidecar.providers.base import BaseProviderAdapter, ProviderRequest


class GeminiAdapter(BaseProviderAdapter):
    name = "gemini"

    def complete(self, request: ProviderRequest) -> str:
        raise NotImplementedError("Gemini adapter is not implemented yet")

    def stream(self, request: ProviderRequest):
        raise NotImplementedError("Gemini adapter is not implemented yet")
