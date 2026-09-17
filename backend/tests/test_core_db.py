"""
Tests for database initialization.

Tests the init_db function that creates the initial superuser if needed.
"""

from unittest.mock import MagicMock, patch

from sqlmodel import Session

from app.core.db import init_db
from app.models import User


class TestInitDb:
    """Test init_db function."""

    def test_init_db_creates_superuser_when_not_exists(self):
        """Test that init_db creates superuser if it doesn't exist."""
        mock_session = MagicMock(spec=Session)
        # Simulate that no user exists
        mock_session.exec.return_value.first.return_value = None

        with patch("app.core.db.crud.create_user") as mock_create_user:
            mock_user = MagicMock(spec=User)
            mock_create_user.return_value = mock_user

            init_db(mock_session)

            # Verify that create_user was called
            mock_create_user.assert_called_once()
            call_args = mock_create_user.call_args
            assert call_args[1]["session"] == mock_session
            user_create = call_args[1]["user_create"]
            assert user_create.is_superuser is True

    def test_init_db_does_not_create_superuser_when_exists(self):
        """Test that init_db doesn't create superuser if it already exists."""
        mock_session = MagicMock(spec=Session)
        # Simulate that user already exists
        mock_existing_user = MagicMock(spec=User)
        mock_session.exec.return_value.first.return_value = mock_existing_user

        with patch("app.core.db.crud.create_user") as mock_create_user:
            init_db(mock_session)

            # Verify that create_user was NOT called
            mock_create_user.assert_not_called()

    def test_init_db_queries_database(self):
        """Test that init_db queries for existing superuser."""
        mock_session = MagicMock(spec=Session)
        mock_session.exec.return_value.first.return_value = None

        with patch("app.core.db.crud.create_user"):
            init_db(mock_session)

            # Verify that session.exec was called
            mock_session.exec.assert_called_once()

    def test_init_db_passes_session_to_crud(self):
        """Test that init_db passes session to crud.create_user."""
        mock_session = MagicMock(spec=Session)
        mock_session.exec.return_value.first.return_value = None

        with patch("app.core.db.crud.create_user") as mock_create_user:
            init_db(mock_session)

            # Verify session was passed
            assert mock_create_user.call_args[1]["session"] is mock_session
