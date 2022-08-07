from typing import Any


def _noop(*_: Any, **__: Any) -> Any:  # pragma: no cover
    return False


try:  # pragma: no cover
    # only for testing purposes
    _ = is_async_code  # noqa
    _ = verify_async_debug_available  # type: ignore  # noqa
except NameError:  # pragma: no cover
    try:
        from async_eval.async_eval import is_async_code
        from async_eval.asyncio_patch import verify_async_debug_available
    except ImportError:
        is_async_code = _noop
        verify_async_debug_available = _noop


def make_code_async(code: str) -> str:
    if not code:
        return code

    original_code = code.replace("@" + "LINE" + "@", "\n")

    if is_async_code(original_code):
        return f"__import__('sys').__async_eval__({original_code!r}, globals(), locals())"

    return code


# 1. Add ability to evaluate async expression
from _pydevd_bundle import pydevd_save_locals, pydevd_vars

original_evaluate = pydevd_vars.evaluate_expression


def evaluate_expression(thread_id: object, frame_id: object, expression: str, doExec: bool) -> Any:
    if is_async_code(expression):
        verify_async_debug_available()
        doExec = False

    try:
        return original_evaluate(thread_id, frame_id, make_code_async(expression), doExec)
    finally:
        frame = pydevd_vars.find_frame(thread_id, frame_id)

        if frame is not None:
            pydevd_save_locals.save_locals(frame)
            del frame


pydevd_vars.evaluate_expression = evaluate_expression

# 2. Add ability to use async breakpoint conditions
from _pydevd_bundle.pydevd_breakpoints import LineBreakpoint


def normalize_line_breakpoint(line_breakpoint: LineBreakpoint) -> None:
    line_breakpoint.expression = make_code_async(line_breakpoint.expression)
    line_breakpoint.condition = make_code_async(line_breakpoint.condition)


original_init = LineBreakpoint.__init__


def line_breakpoint_init(self: LineBreakpoint, *args: Any, **kwargs: Any) -> None:
    original_init(self, *args, **kwargs)
    normalize_line_breakpoint(self)


LineBreakpoint.__init__ = line_breakpoint_init

# Update old breakpoints
import gc

for obj in gc.get_objects():  # pragma: no cover
    if isinstance(obj, LineBreakpoint):
        normalize_line_breakpoint(obj)

# 3. Add ability to use async code in console
from _pydevd_bundle import pydevd_console_integration

original_console_exec = pydevd_console_integration.console_exec


def console_exec(thread_id: object, frame_id: object, expression: str, dbg: Any) -> Any:
    return original_console_exec(thread_id, frame_id, make_code_async(expression), dbg)


pydevd_console_integration.console_exec = console_exec

# 4. Add ability to use async code
from _pydev_bundle.pydev_console_types import Command


def command_run(self: Command) -> None:
    text = make_code_async(self.code_fragment.text)
    symbol = self.symbol_for_fragment(self.code_fragment)

    self.more = self.interpreter.runsource(text, "<input>", symbol)


Command.run = command_run

import sys
from runpy import run_path

if __name__ == "__main__":  # pragma: no cover
    run_path(sys.argv.pop(1), {}, "__main__")  # pragma: no cover
