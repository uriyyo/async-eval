import asyncio
from asyncio import AbstractEventLoop
from typing import Any


def is_trio_not_running() -> bool:
    try:
        from trio._core._run import GLOBAL_RUN_CONTEXT
    except ImportError:  # pragma: no cover
        return True

    return not hasattr(GLOBAL_RUN_CONTEXT, "runner")


def get_current_loop() -> AbstractEventLoop:  # pragma: no cover
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.new_event_loop()


def is_async_debug_available(loop: Any = None) -> bool:
    if loop is None:
        loop = get_current_loop()

    return bool(loop.__class__.__module__.lstrip("_").startswith("asyncio"))


def verify_async_debug_available() -> None:
    if not is_trio_not_running():
        raise RuntimeError(
            "Can not evaluate async code with trio event loop. "
            "Only native asyncio event loop can be used for async code evaluating.",
        )

    if not is_async_debug_available():
        cls = get_current_loop().__class__

        raise RuntimeError(
            f"Can not evaluate async code with event loop {cls.__module__}.{cls.__qualname__}. "
            "Only native asyncio event loop can be used for async code evaluating.",
        )


__all__ = [
    "get_current_loop",
    "is_async_debug_available",
    "verify_async_debug_available",
]
