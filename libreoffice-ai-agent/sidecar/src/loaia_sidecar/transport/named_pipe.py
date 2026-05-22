from collections.abc import Callable, Iterable
from multiprocessing.connection import Client, Listener
from threading import Thread
from typing import Union

from loaia_shared.errors import TransportError
from loaia_shared.transport import (
    DEFAULT_NAMED_PIPE_ADDRESS,
    decode_transport_payload,
    encode_transport_payload,
)

MessageHandler = Callable[[dict[str, object]], dict[str, object]]
StreamingMessageHandler = Callable[
    [dict[str, object]], Union[dict[str, object], Iterable[dict[str, object]]]
]


class NamedPipeTransport:
    """Windows named-pipe transport for extension-to-sidecar requests."""

    def __init__(
        self,
        address: str = DEFAULT_NAMED_PIPE_ADDRESS,
        handler: StreamingMessageHandler | None = None,
    ) -> None:
        self.address = address
        self._handler: StreamingMessageHandler = handler or self._missing_handler
        self._listener: Listener | None = None
        self._stopped = False

    def start(self) -> None:
        if self._listener is not None:
            return

        self._stopped = False
        self._listener = Listener(self.address, family="AF_PIPE", authkey=None)

    def serve_once(self) -> None:
        self.start()

        listener = self._listener
        if listener is None:
            raise TransportError("Named-pipe listener is not available")

        connection = listener.accept()
        # Handle in a daemon thread so the listener can accept the next
        # connection immediately (needed for CancelRequest during streaming).
        thread = Thread(
            target=self._handle_connection, args=(connection,), daemon=True
        )
        thread.start()

    def _handle_connection(self, connection: object) -> None:
        with connection:
            try:
                payload = decode_transport_payload(connection.recv_bytes())
            except EOFError:
                if self._stopped:
                    return
                return

            result = self._handler(payload)
            if isinstance(result, dict):
                connection.send_bytes(encode_transport_payload(result))
            else:
                for frame in result:
                    connection.send_bytes(encode_transport_payload(frame))

    def serve_forever(self) -> None:
        self.start()

        try:
            while not self._stopped:
                self.serve_once()
        finally:
            self.close()

    def stop(self) -> None:
        self._stopped = True
        self._wake_listener()

    def close(self) -> None:
        if self._listener is None:
            return

        self._listener.close()
        self._listener = None

    def _wake_listener(self) -> None:
        if self._listener is None:
            return

        try:
            with Client(self.address, family="AF_PIPE", authkey=None):
                return
        except OSError:
            return

    @staticmethod
    def _missing_handler(_: dict[str, object]) -> dict[str, object]:
        raise TransportError("Named-pipe transport has no request handler")
