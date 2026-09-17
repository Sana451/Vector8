"""
Tests for initial_data module.

Tests database initialization and seeding.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.initial_data import init, main


class TestInitFunction:
    """Test init() function."""

    def test_init_calls_init_db(self):
        """Test that init() creates session and calls init_db."""
        with patch("app.initial_data.Session") as mock_session_cls:
            with patch("app.initial_data.init_db") as mock_init_db:
                # Mock the session context manager
                mock_session = MagicMock()
                mock_session_cls.return_value.__enter__.return_value = mock_session
                mock_session_cls.return_value.__exit__.return_value = None

                init()

                # Verify Session was called with engine
                mock_session_cls.assert_called_once()
                # Verify init_db was called with the session
                mock_init_db.assert_called_once_with(mock_session)

    def test_init_context_manager_exits(self):
        """Test that init() properly exits session context."""
        with patch("app.initial_data.Session") as mock_session_cls:
            with patch("app.initial_data.init_db"):
                mock_session = MagicMock()
                mock_session_cls.return_value.__enter__.return_value = mock_session
                mock_session_cls.return_value.__exit__.return_value = None

                init()

                # Verify __exit__ was called (context manager cleanup)
                mock_session_cls.return_value.__exit__.assert_called_once()


class TestMainFunction:
    """Test main() function."""

    def test_main_logs_and_calls_init(self):
        """Test that main() logs messages and calls init()."""
        with patch("app.initial_data.init") as mock_init:
            with patch("app.initial_data.log") as mock_log:
                main()

                # Verify logging
                assert mock_log.info.call_count == 2
                mock_log.info.assert_any_call("creating_initial_data")
                mock_log.info.assert_any_call("initial_data_created")
                # Verify init was called
                mock_init.assert_called_once()

    def test_main_logs_before_and_after_init(self):
        """Test that main() logs in correct order."""
        with patch("app.initial_data.init"):
            with patch("app.initial_data.log") as mock_log:
                main()

                # Get the order of calls
                calls = mock_log.info.call_args_list
                assert len(calls) == 2
                assert calls[0][0][0] == "creating_initial_data"
                assert calls[1][0][0] == "initial_data_created"

    def test_main_with_init_exception(self):
        """Test that main() propagates exceptions from init()."""
        with patch("app.initial_data.init") as mock_init:
            mock_init.side_effect = Exception("Database error")
            with patch("app.initial_data.log"):
                with pytest.raises(Exception, match="Database error"):
                    main()
