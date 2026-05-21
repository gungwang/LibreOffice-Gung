import os
import threading
from uuid import uuid4

import pytest

from loaia.bootstrap import SIDEBAR_RESOURCE_URL
from loaia.broker.client import SidecarClient
from loaia.broker.transport import SidecarTransportClient
from loaia.chat_controller import ChatController
from loaia.context.writer import WriterSelectionState, build_writer_chat_request
from loaia.sidebar_panel import SidebarPanel
from loaia_sidecar.server import LoaiaSidecarServer
from loaia_sidecar.transport.named_pipe import NamedPipeTransport


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows named pipes only")


def test_writer_preview_then_approve_apply_round_trip() -> None:
    address = rf"\\.\pipe\loaia-test-{uuid4()}"
    transport = NamedPipeTransport(address=address, handler=LoaiaSidecarServer().handle_message)
    transport.start()

    worker = threading.Thread(target=transport.serve_once)
    worker.start()

    panel = SidebarPanel(title="LibreOffice AI Agent", resource_url=SIDEBAR_RESOURCE_URL)
    controller = ChatController(
        panel=panel,
        client=SidecarClient(transport=SidecarTransportClient(address=address)),
    )
    selection = WriterSelectionState(text="hello world")
    request = build_writer_chat_request(
        selection=selection,
        user_message="Please convert this selection to uppercase.",
        request_id="writer-preview-1",
    )

    try:
        preview_summary = controller.submit(request)
    finally:
        worker.join(timeout=2)
        transport.close()

    assert preview_summary == "Preview Writer selection replacement"
    assert panel.state.pending_proposal is not None
    assert panel.state.pending_proposal.preview is not None
    assert panel.state.pending_proposal.preview.after == "HELLO WORLD"

    applied_text = controller.approve_pending_writer_proposal(selection)

    assert applied_text == "HELLO WORLD"
    assert selection.text == "HELLO WORLD"
    assert panel.state.pending_proposal is None