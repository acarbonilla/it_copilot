from dataclasses import dataclass

from django.conf import settings


class ProviderUnavailable(Exception):
    pass


class ProviderProtocolError(Exception):
    pass


@dataclass(frozen=True)
class ProviderAnswer:
    content: str
    citation_ids: tuple[str, ...]


class DisabledByDefaultProviderAdapter:
    """Provider boundary only; IC-019 never performs a network request."""

    def generate(self, *, question, evidence):
        if not settings.COPILOT_PROVIDER_ENABLED:
            raise ProviderUnavailable("Provider is disabled")
        if not settings.COPILOT_PRIVATE_TRANSFER_AUTHORIZED:
            raise ProviderUnavailable("Private evidence transfer is not authorized")
        if settings.COPILOT_PROVIDER_MODEL not in settings.COPILOT_PROVIDER_MODEL_ALLOWLIST:
            raise ProviderUnavailable("Provider model is not allowed")
        raise ProviderUnavailable("No live provider transport is installed")
