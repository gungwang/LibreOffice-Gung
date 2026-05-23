"""Tests for the undo context manager."""

from __future__ import annotations

import pytest

from loaia.undo import undo_context


class FakeUndoManager:
    """Records enterUndoContext / leaveUndoContext calls."""

    def __init__(self) -> None:
        self.contexts: list[str] = []
        self.left: int = 0

    def enterUndoContext(self, title: str) -> None:
        self.contexts.append(title)

    def leaveUndoContext(self) -> None:
        self.left += 1


class FakeDocumentModel:
    def __init__(self) -> None:
        self.undo_manager = FakeUndoManager()

    def getUndoManager(self) -> FakeUndoManager:
        return self.undo_manager


def test_undo_context_enters_and_leaves() -> None:
    model = FakeDocumentModel()
    with undo_context(model, "AI: Writer.ReplaceSelection"):
        pass
    assert model.undo_manager.contexts == ["AI: Writer.ReplaceSelection"]
    assert model.undo_manager.left == 1


def test_undo_context_leaves_on_exception() -> None:
    model = FakeDocumentModel()
    with pytest.raises(ValueError, match="boom"):
        with undo_context(model, "AI: test"):
            raise ValueError("boom")
    assert model.undo_manager.contexts == ["AI: test"]
    assert model.undo_manager.left == 1


def test_undo_context_skips_when_model_is_none() -> None:
    # Should not raise — simply runs the block without undo grouping.
    with undo_context(None, "AI: test"):
        pass


def test_undo_context_skips_when_no_undo_manager() -> None:
    # Model without getUndoManager — graceful degradation.
    model = object()
    with undo_context(model, "AI: test"):
        pass
