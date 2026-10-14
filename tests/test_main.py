"""Smoke tests for the safe development entry point."""

from jhive.main import main


def test_main_logs_safe_startup(caplog):
    import logging

    caplog.set_level(logging.INFO)
    """The default entry point starts without enabling trading."""
    main()
    assert "no live market data or trading is enabled" in caplog.text
