from .async_eval import async_eval as eval  # noqa
from .async_eval import is_async_code
from .asyncio_patch import patch_asyncio  # noqa

__all__ = ["eval", "is_async_code"]
