"""Undo context manager for wrapping AI-applied document changes.

Provides a context manager that opens and closes an XUndoManager undo
context so that all modifications within the block can be reversed with
a single Ctrl+Z.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


@contextmanager
def undo_context(
    model: object | None, title: str = "AI Agent action"
) -> Iterator[None]:
    """Wrap document modifications in an undoable context.

    If *model* exposes ``getUndoManager()``, the block's changes are grouped
    under a single undo step with the given *title*.  If the undo manager is
    not available (e.g. in tests), the block runs without undo grouping.
    """
    undo_mgr = _get_undo_manager(model)
    if undo_mgr is not None:
        undo_mgr.enterUndoContext(title)
    try:
        yield
    except BaseException:
        if undo_mgr is not None:
            try:
                undo_mgr.leaveUndoContext()
            except Exception:
                pass
        raise
    else:
        if undo_mgr is not None:
            undo_mgr.leaveUndoContext()


def _get_undo_manager(model: object | None) -> object | None:
    if model is None:
        return None
    if hasattr(model, "getUndoManager"):
        try:
            return model.getUndoManager()
        except Exception:
            return None
    return None
