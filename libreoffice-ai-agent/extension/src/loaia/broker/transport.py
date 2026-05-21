from collections.abc import Mapping
from multiprocessing.connection import Client
from typing import cast

from pydantic import BaseModel

from loaia_shared.errors import TransportError
from loaia_shared.transport import (
    DEFAULT_NAMED_PIPE_ADDRESS,
    decode_transport_payload,
    encode_transport_payload,
)


class SidecarTransportClient:
    """Extension-side client for the local sidecar named pipe."""

    def __init__(self, address: str = DEFAULT_NAMED_PIPE_ADDRESS) -> None:
        self.address = address

    def request(self, payload: BaseModel | Mapping[str, object]) -> dict[str, object]:
        normalized_payload = self._normalize_payload(payload)

        try:
            with Client(self.address, family="AF_PIPE", authkey=None) as connection:
                connection.send_bytes(encode_transport_payload(normalized_payload))
                return decode_transport_payload(connection.recv_bytes())
        except OSError as exc:
            raise TransportError(f"Could not connect to sidecar pipe at {self.address}") from exc

    @staticmethod
    def _normalize_payload(payload: BaseModel | Mapping[str, object]) -> dict[str, object]:
        if isinstance(payload, BaseModel):
            return cast(dict[str, object], payload.model_dump(by_alias=True, mode="json"))

        return dict(payload)
