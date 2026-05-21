class NamedPipeTransport:
    """Placeholder named-pipe transport.

    Phase 0 should replace this with a real Windows named-pipe server.
    """

    def start(self) -> None:
        raise NotImplementedError("Named-pipe transport is not implemented yet")

    def stop(self) -> None:
        raise NotImplementedError("Named-pipe transport is not implemented yet")
