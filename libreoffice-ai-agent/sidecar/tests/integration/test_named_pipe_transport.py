import os
import threading
from uuid import uuid4

import pytest

from loaia.broker.client import SidecarClient
from loaia.broker.transport import SidecarTransportClient
from loaia_shared.schema.messages import ChatRequest, DocumentRef, HandshakeRequest
from loaia_shared.types import AppType, PrivacyScope
from loaia_sidecar.server import LoaiaSidecarServer
from loaia_sidecar.transport.named_pipe import NamedPipeTransport


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows named pipes only")


def test_named_pipe_handshake_round_trip() -> None:
    address = rf"\\.\pipe\loaia-test-{uuid4()}"
    transport = NamedPipeTransport(address=address, handler=LoaiaSidecarServer().handle_message)
    transport.start()

    worker = threading.Thread(target=transport.serve_once)
    worker.start()

    try:
        response = SidecarTransportClient(address=address).request(HandshakeRequest())
    finally:
        worker.join(timeout=2)
        transport.close()

    assert response["type"] == "HandshakeResponse"
    assert "tool-proposals" in response["capabilities"]


def test_named_pipe_chat_round_trip() -> None:
    address = rf"\\.\pipe\loaia-test-{uuid4()}"
    transport = NamedPipeTransport(address=address, handler=LoaiaSidecarServer().handle_message)
    transport.start()

    worker = threading.Thread(target=transport.serve_once)
    worker.start()

    request = ChatRequest(
        requestId="req-1",
        app=AppType.WRITER,
        document=DocumentRef(canonicalUrl="file:///example.odt", profileId="profile-1"),
        provider="openai-compatible",
        model="local-default",
        privacyScope=PrivacyScope.SELECTION_ONLY,
        context={},
        userMessage="Summarize this selection.",
    )

    try:
        response = SidecarClient(transport=SidecarTransportClient(address=address)).send_chat(request)
    finally:
        worker.join(timeout=2)
        transport.close()

    assert "Sidecar scaffold is running" in response