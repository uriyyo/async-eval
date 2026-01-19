import warnings

from .async_eval import (
    get_current_loop,
    is_async_debug_available,
    is_trio_running,
    verify_async_debug_available,
)

warnings.warn(
    "This module is deprecated and will be removed in a future release.",
    category=DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "get_current_loop",
    "is_async_debug_available",
    "is_trio_running",
    "verify_async_debug_available",
]
