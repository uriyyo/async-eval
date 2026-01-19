import inspect

from async_eval import async_eval

from . import code


def generate_main_script() -> str:
    return "\n".join(
        inspect.getsource(m)
        for m in (
            async_eval,
            code,
        )
    )


__all__ = ["generate_main_script"]
