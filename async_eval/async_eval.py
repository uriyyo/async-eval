import ast
import inspect
import platform
import sys
import textwrap
import types
from asyncio.tasks import _enter_task, _leave_task, current_task
from concurrent.futures import ThreadPoolExecutor
from contextvars import Context, copy_context
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
    no_type_check,
)

_: Any


def is_pypy() -> bool:
    return platform.python_implementation().lower() == "pypy"


try:
    from _pydevd_bundle.pydevd_save_locals import save_locals as _save_locals
except ImportError:  # pragma: no cover
    import ctypes

    try:
        _ = ctypes.pythonapi

        def _save_locals(frame: types.FrameType) -> None:
            ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(frame), ctypes.c_int(1))
    except AttributeError:

        def _save_locals(frame: types.FrameType) -> None:
            pass


def save_locals(frame: types.FrameType) -> None:
    if not is_pypy():
        _save_locals(frame)


def _noop(*_: Any, **__: Any) -> Any:  # pragma: no cover
    return None


try:
    _ = verify_async_debug_available  # type: ignore # noqa
except NameError:  # pragma: no cover
    try:
        from async_eval.asyncio_patch import verify_async_debug_available
    except ImportError:
        verify_async_debug_available = _noop

try:
    _ = get_current_loop  # type: ignore # noqa
except NameError:  # pragma: no cover
    try:
        from async_eval.asyncio_patch import get_current_loop
    except ImportError:
        get_current_loop = _noop

try:
    _ = is_trio_running  # type: ignore # noqa
except NameError:  # pragma: no cover
    try:
        from async_eval.asyncio_patch import is_trio_running
    except ImportError:
        is_trio_running = _noop


_ASYNC_EVAL_CODE_TEMPLATE = textwrap.dedent(
    """\
async def __async_func__(_locals, _ctx=None):
    async def __func_wrapper__(_locals):
        locals().update(_locals)
        try:
            pass
        finally:
            _locals.update(locals())
            _locals.pop("_ctx", None)
            _locals.pop("_locals", None)

    if _ctx:
        for v in _ctx:
            v.set(_ctx[v])

    from contextvars import copy_context

    try:
      return False, await __func_wrapper__(_locals), copy_context()
    except Exception as excpz:
       return True, excpz, copy_context()
""",
)


def _compile_ast(node: ast.AST, filename: str = "<eval>", mode: str = "exec") -> types.CodeType:
    return cast(types.CodeType, compile(node, filename, mode))  # type: ignore


ASTWithBody = Union[ast.Module, ast.With, ast.AsyncWith]


def _make_stmt_as_return(parent: ASTWithBody, root: ast.AST, filename: str) -> types.CodeType:
    node = parent.body[-1]

    if isinstance(node, ast.Expr):
        parent.body[-1] = ast.copy_location(ast.Return(node.value), node)

    try:
        return _compile_ast(root, filename)
    except (SyntaxError, TypeError):  # pragma: no cover  # TODO: found case to cover except body
        parent.body[-1] = node
        return _compile_ast(root, filename)


def _transform_to_async(code: str, filename: str) -> types.CodeType:
    base = ast.parse(_ASYNC_EVAL_CODE_TEMPLATE)
    module = ast.parse(code)

    func: ast.AsyncFunctionDef = cast(ast.AsyncFunctionDef, cast(ast.AsyncFunctionDef, base.body[0]).body[0])
    try_stmt: ast.Try = cast(ast.Try, func.body[-1])

    try_stmt.body = module.body

    parent: ASTWithBody = module
    while isinstance(parent.body[-1], (ast.AsyncWith, ast.With)):
        parent = cast(ASTWithBody, parent.body[-1])

    return _make_stmt_as_return(parent, base, filename)


def _compile_async_func(
    code: types.CodeType,
    _locals: Dict[str, Any],
    _globals: Dict[str, Any],
) -> Callable[[Dict[str, Any]], Awaitable[Tuple[bool, Any, Context]]]:
    exec(code, _globals, _locals)

    return cast(
        Callable[[Dict[str, Any]], Awaitable[Tuple[bool, Any, Context]]],
        _locals.pop("__async_func__"),
    )


class _AsyncNodeFound(Exception):
    pass


class _AsyncCodeVisitor(ast.NodeVisitor):
    @classmethod
    def check(cls, code: str) -> bool:
        try:
            node = ast.parse(code)
        except SyntaxError:
            return False

        try:
            return bool(cls().visit(node))
        except _AsyncNodeFound:
            return True

    def _ignore(self, _: ast.AST) -> Any:
        return

    def _done(self, _: Optional[ast.AST] = None) -> Any:
        raise _AsyncNodeFound

    def _visit_gen(self, node: Union[ast.GeneratorExp, ast.ListComp, ast.DictComp, ast.SetComp]) -> Any:
        if any(gen.is_async for gen in node.generators):
            self._done()

        super().generic_visit(node)

    def _visit_func(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> Any:
        # check only args and decorators
        for n in (node.args, *node.decorator_list):
            super().generic_visit(n)

    # special check for a function def
    visit_AsyncFunctionDef = _visit_func
    visit_FunctionDef = _visit_func

    # no need to check class definitions
    visit_ClassDef = _ignore  # type: ignore

    # basic async statements
    visit_AsyncFor = _done  # type: ignore
    visit_AsyncWith = _done  # type: ignore
    visit_Await = _done  # type: ignore

    # all kind of a generator/comprehensions (they can be async)
    visit_GeneratorExp = _visit_gen
    visit_ListComp = _visit_gen
    visit_SetComp = _visit_gen
    visit_DictComp = _visit_gen


def is_async_code(code: str) -> bool:
    return _AsyncCodeVisitor.check(code)


T = TypeVar("T")


@no_type_check
def _asyncio_run_coro(coro: Awaitable[T]) -> T:
    loop = get_current_loop()

    if not loop.is_running():
        return loop.run_until_complete(coro)

    current = current_task(loop)

    t = loop.create_task(coro)

    try:
        if current is not None:
            _leave_task(loop, current)

        while not t.done():
            loop._run_once()

        return t.result()
    finally:
        if current is not None:
            _enter_task(loop, current)


@no_type_check
def _trio_run_coro(coro: Awaitable[T]) -> T:
    import trio

    async def _run() -> T:
        return await coro

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(trio.run, _run).result()


@no_type_check
def _run_coro(func: Callable[..., Awaitable[T]], _locals: Any) -> T:
    if is_trio_running():
        return _trio_run_coro(func(_locals, copy_context()))

    return _asyncio_run_coro(func(_locals))


def _reflect_context(ctx: Context) -> None:
    for v in ctx:
        v.set(ctx[v])


# async equivalent of builtin eval function
def async_eval(
    code: str,
    _globals: Optional[Dict[str, Any]] = None,
    _locals: Optional[Dict[str, Any]] = None,
    *,
    filename: str = "<eval>",
) -> Any:
    verify_async_debug_available()

    caller: types.FrameType = inspect.currentframe().f_back  # type: ignore

    if _locals is None:
        _locals = caller.f_locals

    if _globals is None:
        _globals = caller.f_globals

    code_obj = _transform_to_async(code, filename)
    func = _compile_async_func(code_obj, _locals, _globals)

    try:
        is_exc, result, ctx = _run_coro(func, _locals)

        _reflect_context(ctx)

        if is_exc:
            raise result

        return result
    finally:
        save_locals(caller)


sys.__async_eval__ = async_eval  # type: ignore

__all__ = ["async_eval", "is_async_code"]
