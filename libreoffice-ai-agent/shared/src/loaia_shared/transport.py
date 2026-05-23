import json
from collections.abc import Mapping
from typing import cast

from loaia_shared.errors import TransportError

DEFAULT_NAMED_PIPE_ADDRESS = r"\\.\pipe\loaia-sidecar"


def encode_transport_payload(payload: Mapping[str, object]) -> bytes:
    return json.dumps(dict(payload), ensure_ascii=True).encode("utf-8")


def decode_transport_payload(raw_payload: bytes) -> dict[str, object]:
    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransportError("Transport payload is not valid UTF-8 JSON") from exc

    if not isinstance(payload, dict):
        raise TransportError("Transport payload must decode to a JSON object")

    return cast(dict[str, object], payload)