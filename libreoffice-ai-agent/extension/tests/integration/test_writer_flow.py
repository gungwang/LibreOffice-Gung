import os
import threading
from uuid import uuid4

import pytest

from loaia.bootstrap import SIDEBAR_RESOURCE_URL
from loaia.broker.client import SidecarClient
from loaia.broker.transport import SidecarTransportClient
from loaia.chat_controller import ChatController
from loaia.context.writer import build_writer_chat_request, capture_writer_selection
from loaia.sidebar_panel import SidebarPanel
from loaia_shared.defaults import get_default_model, get_default_provider
from loaia_sidecar.providers.base import ProviderChunk, ProviderRequest
from loaia_sidecar.server import LoaiaSidecarServer
from loaia_sidecar.transport.named_pipe import NamedPipeTransport

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows named pipes only")


class FakeWriterTextRange:
    def __init__(self, text: str) -> None:
        self.text = text

    def getString(self) -> str:
        return self.text

    def setString(self, text: str) -> None:
        self.text = text


class FakeWriterSelection:
    def __init__(self, *ranges: FakeWriterTextRange) -> None:
        self._ranges = ranges

    def getCount(self) -> int:
        return len(self._ranges)

    def getByIndex(self, index: int) -> FakeWriterTextRange:
        return self._ranges[index]


class FakeWriterSelectionSupplier:
    def __init__(self, selection: FakeWriterSelection) -> None:
        self._selection = selection
        self.last_selected_range: FakeWriterTextRange | None = None

    def getSelection(self) -> FakeWriterSelection:
        return self._selection

    def select(self, text_range: FakeWriterTextRange) -> None:
        self.last_selected_range = text_range


class FakeProviderAdapter:
    name = "openrouter"

    def __init__(self, answer: str) -> None:
        self.answer = answer

    def complete(self, request: ProviderRequest) -> str:
        return self.answer

    def stream(self, request: ProviderRequest):
        return iter(())


def test_writer_preview_then_approve_apply_round_trip() -> None:
    address = rf"\\.\pipe\loaia-test-{uuid4()}"
    adapter = FakeProviderAdapter(
        '{"action":"replace-selection","replacementText":"HELLO WORLD"}'
    )
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})
    transport = NamedPipeTransport(address=address, handler=server.handle_message)
    transport.start()

    preview_worker = threading.Thread(target=transport.serve_once)
    preview_worker.start()

    panel = SidebarPanel(title="LibreOffice AI Agent", resource_url=SIDEBAR_RESOURCE_URL)
    controller = ChatController(
        panel=panel,
        client=SidecarClient(transport=SidecarTransportClient(address=address)),
    )
    text_range = FakeWriterTextRange("hello world")
    selection_supplier = FakeWriterSelectionSupplier(FakeWriterSelection(text_range))
    selection = capture_writer_selection(selection_supplier)
    request = build_writer_chat_request(
        selection=selection,
        user_message="Please convert this selection to uppercase.",
        request_id="writer-preview-1",
        provider=adapter.name,
    )

    try:
        preview_summary = controller.submit(request)
        preview_worker.join(timeout=2)

        assert preview_summary == "Preview Writer selection replacement"
        assert panel.state.connected is True
        assert panel.state.provider == adapter.name
        assert panel.state.model == get_default_model()
        assert panel.state.privacy_scope == "selection-only"
        assert panel.state.selection_preview == "hello world"
        assert panel.state.pending_proposal is not None
        assert panel.state.pending_proposal.preview is not None
        assert panel.state.pending_proposal.preview.after == "HELLO WORLD"

        approve_worker = threading.Thread(target=transport.serve_once)
        approve_worker.start()
        applied_text = controller.approve_pending_writer_proposal(selection)
        approve_worker.join(timeout=2)
    finally:
        transport.close()

    assert panel.state.selection_preview == "HELLO WORLD"

    assert applied_text == "HELLO WORLD"
    assert selection.text == "HELLO WORLD"
    assert text_range.text == "HELLO WORLD"
    assert selection_supplier.last_selected_range is text_range
    assert panel.state.pending_proposal is None