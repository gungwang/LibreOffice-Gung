from loaia_sidecar.server import LoaiaSidecarServer


def test_handshake_lists_capabilities() -> None:
    response = LoaiaSidecarServer().handshake()
    assert "streaming" in response.capabilities
