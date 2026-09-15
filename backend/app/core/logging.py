"""Structured logging configuration using structlog."""

import logging
from typing import Any

import structlog


def configure_logging(env: str | None = None) -> None:
    """
    Configure structlog for the application.
    Args:
        env: Environment name (e.g., "development", "production"). If None, uses default settings.
    """
    # Set up structlog with appropriate processors based on environment
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    # Use ConsoleRenderer for development, JSONRenderer for production
    if env == "development":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    # Also configure standard library logging to use structlog
    # This allows libraries that use logging to work seamlessly
    structlog.stdlib.recreate_defaults()


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a structlog logger instance.
    Args:
        name: Logger name, typically __name__. If None, returns root logger.
    Returns:
        A structlog BoundLogger instance.
    """
    return structlog.get_logger(name)
