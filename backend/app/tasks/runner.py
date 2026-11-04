"""Helpers for running async services from synchronous Celery tasks."""

import asyncio
from collections.abc import Coroutine
from typing import Any


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine to completion in a fresh event loop."""
    return asyncio.run(coro)
