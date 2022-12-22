import asyncio
import functools
import sys
from asyncio import AbstractEventLoop
from typing import Any, Callable, Optional

try:  # pragma: no cover
    _ = _patch_loop  # noqa
    _ = apply  # noqa
except NameError:
    try:
        from nest_asyncio import _patch_loop, apply
    except ImportError:  # pragma: no cover

        def _noop(*_: Any, **__: Any) -> None:
            pass

        _patch_loop = apply = _noop


def is_trio_not_running() -> bool:
    try:
        from trio._core._run import GLOBAL_RUN_CONTEXT
    except ImportError:  # pragma: no cover
        return True

    return not hasattr(GLOBAL_RUN_CONTEXT, "runner")


def get_current_loop() -> Optional[Any]:  # pragma: no cover
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
            "Only native asyncio event loop can be used for async code evaluating."
        )

    if not is_async_debug_available():
        cls = get_current_loop().__class__

        raise RuntimeError(
            f"Can not evaluate async code with event loop {cls.__module__}.{cls.__qualname__}. "
            "Only native asyncio event loop can be used for async code evaluating."
        )


def patch_asyncio() -> None:
    if hasattr(sys, "__async_eval_patched__"):  # pragma: no cover
        return

    if not is_async_debug_available():  # pragma: no cover
        return

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

__all__ = [
    "patch_asyncio",
    "get_current_loop",
    "is_async_debug_available",
    "verify_async_debug_available",
]
