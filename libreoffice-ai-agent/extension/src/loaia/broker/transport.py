from collections.abc import Callable, Mapping
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

    def request_streaming(
        self,
        payload: BaseModel | Mapping[str, object],
        on_chunk: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, object]:
        """Send a request and receive streamed frames.

        Calls *on_chunk* for each intermediate StreamChunk frame.
        Returns the final terminal frame (DirectAnswer, ToolProposal, or Error).
        """
        normalized_payload = self._normalize_payload(payload)

        try:
            with Client(self.address, family="AF_PIPE", authkey=None) as connection:
                connection.send_bytes(encode_transport_payload(normalized_payload))
                final_frame: dict[str, object] | None = None
                while True:
                    try:
                        frame = decode_transport_payload(connection.recv_bytes())
                    except EOFError:
                        break

                    frame_type = frame.get("type")
                    if frame_type == "StreamChunk":
                        if on_chunk is not None:
                            on_chunk(frame)
                    else:
                        final_frame = frame

                if final_frame is None:
                    raise TransportError("Sidecar closed connection without a final response")
                return final_frame
        except OSError as exc:
            raise TransportError(f"Could not connect to sidecar pipe at {self.address}") from exc

    @staticmethod
    def _normalize_payload(payload: BaseModel | Mapping[str, object]) -> dict[str, object]:
        if isinstance(payload, BaseModel):
            return cast(dict[str, object], payload.model_dump(by_alias=True, mode="json"))

        return dict(payload)
