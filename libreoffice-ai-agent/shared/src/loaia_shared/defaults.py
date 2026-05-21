from __future__ import annotations

import os

DEFAULT_PROVIDER_ENV_VAR = "LOAIA_DEFAULT_PROVIDER"
DEFAULT_MODEL_ENV_VAR = "LOAIA_DEFAULT_MODEL"

DEFAULT_PROVIDER = "openai-compatible"
DEFAULT_MODEL = "local-default"


def get_default_provider() -> str:
    value = os.environ.get(DEFAULT_PROVIDER_ENV_VAR, "").strip()
    return value or DEFAULT_PROVIDER


def get_default_model() -> str:
    value = os.environ.get(DEFAULT_MODEL_ENV_VAR, "").strip()
    return value or DEFAULT_MODEL