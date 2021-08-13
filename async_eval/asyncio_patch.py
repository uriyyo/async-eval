import asyncio
import functools
import sys
from asyncio import AbstractEventLoop
from typing import Any, Callable

try:
    from nest_asyncio import _patch_loop, apply
except ImportError:  # pragma: no cover

    def _noop(*args: Any, **kwargs: Any) -> None:
        pass

    _patch_loop = apply = _noop


def is_async_debug_available(loop: Any = None) -> bool:
    if loop is None:
        loop = asyncio.get_event_loop()

    return bool(loop.__class__.__module__.lstrip("_").startswith("asyncio"))


def patch_asyncio() -> None:
    if hasattr(sys, "__async_eval_patched__"):  # pragma: no cover
        return

    if not is_async_debug_available():  # pragma: no cover
        return

    if sys.platform.lower().startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore
        except AttributeError:
            pass

    apply()

    def _patch_loop_if_not_patched(loop: AbstractEventLoop) -> None:
        if not hasattr(loop, "_nest_patched") and is_async_debug_available(loop):
            _patch_loop(loop)

    def _patch_asyncio_api(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            loop = func(*args, **kwargs)
            _patch_loop_if_not_patched(loop)
            return loop

        return wrapper

    asyncio.get_event_loop = _patch_asyncio_api(asyncio.get_event_loop)
    asyncio.new_event_loop = _patch_asyncio_api(asyncio.new_event_loop)

    _set_event_loop = asyncio.set_event_loop

    @functools.wraps(asyncio.set_event_loop)
    def set_loop_wrapper(loop: AbstractEventLoop) -> None:
        _patch_loop_if_not_patched(loop)
        _set_event_loop(loop)

    asyncio.set_event_loop = set_loop_wrapper  # type: ignore
    sys.__async_eval_patched__ = True  # type: ignore


patch_asyncio()

__all__ = ["patch_asyncio", "is_async_debug_available"]
