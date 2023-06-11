import inspect

from async_eval import async_eval, asyncio_patch

from . import code


def generate_main_script() -> str:
    return "\n".join(
        inspect.getsource(m)
        for m in (
            asyncio_patch,
            async_eval,
            code,
        )
    )


__all__ = ["generate_main_script"]
