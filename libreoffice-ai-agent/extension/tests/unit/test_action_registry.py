from loaia.actions.registry import ACTION_REGISTRY


def test_writer_toggle_bold_is_registered() -> None:
    assert "Writer.ToggleBold" in ACTION_REGISTRY
