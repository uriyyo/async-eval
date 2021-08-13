import ast
import inspect
import sys
import textwrap
import types
from typing import Any, Iterable, Optional, Union, cast

try:
    from _pydevd_bundle.pydevd_save_locals import save_locals
except ImportError:  # pragma: no cover

    import ctypes

    def save_locals(frame: types.FrameType) -> None:
        ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(frame), ctypes.c_int(1))


_ASYNC_EVAL_CODE_TEMPLATE = textwrap.dedent(
    """\
__locals__ = locals()

async def __async_exec_func__():
    global __locals__
    locals().update(__locals__)
    try:
        pass
    finally:
        __locals__.update(locals())

__ctx__ = None

try:
    async def __async_exec_func__(
        __async_exec_func__=__async_exec_func__,
        contextvars=__import__('contextvars'),
    ):
        try:
            return await __async_exec_func__()
        finally:
            global __ctx__
            __ctx__ = contextvars.copy_context()

except ImportError:
    pass

try:
    __async_exec_func_result__ = __import__('asyncio').get_event_loop().run_until_complete(__async_exec_func__())
finally:
    if __ctx__ is not None:
        for var in __ctx__:
            var.set(__ctx__[var])

        try:
            del var
        except NameError:
            pass

    del __ctx__
    del __locals__
    del __async_exec_func__

    try:
        del __builtins__
    except NameError:
        pass
"""
)

if sys.version_info < (3, 7):

    def _parse_code(code: str) -> ast.AST:
        code = f"async def _():\n{textwrap.indent(code, '    ')}"
        func, *_ = cast(Iterable[ast.AsyncFunctionDef], ast.parse(code).body)
        return ast.Module(func.body)


else:
    _parse_code = ast.parse


def _compile_ast(node: ast.AST, filename: str = "<eval>", mode: str = "exec") -> types.CodeType:
    return cast(types.CodeType, compile(node, filename, mode))


ASTWithBody = Union[ast.Module, ast.With, ast.AsyncWith]


def _make_stmt_as_return(parent: ASTWithBody, root: ast.AST) -> types.CodeType:
    node = parent.body[-1]

    if isinstance(node, ast.Expr):
        parent.body[-1] = ast.copy_location(ast.Return(node.value), node)

    try:
        return _compile_ast(root)
    except (SyntaxError, TypeError):  # pragma: no cover  # TODO: found case to cover except body
        parent.body[-1] = node
        return _compile_ast(root)


def _transform_to_async(code: str) -> types.CodeType:
    base: ast.Module = ast.parse(_ASYNC_EVAL_CODE_TEMPLATE)
    module: ast.Module = cast(ast.Module, _parse_code(code))

    func: ast.AsyncFunctionDef = cast(ast.AsyncFunctionDef, base.body[1])
    try_stmt: ast.Try = cast(ast.Try, func.body[-1])

    try_stmt.body = module.body

    parent: ASTWithBody = module
    while isinstance(parent.body[-1], (ast.AsyncWith, ast.With)):
        parent = cast(ASTWithBody, parent.body[-1])

    return _make_stmt_as_return(parent, base)


class _AsyncNodeFound(Exception):
    pass


class _AsyncCodeVisitor(ast.NodeVisitor):
    @classmethod
    def check(cls, code: str) -> bool:
        try:
            node = _parse_code(code)
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


# async equivalent of builtin eval function
def async_eval(code: str, _globals: Optional[dict] = None, _locals: Optional[dict] = None) -> Any:
    caller: types.FrameType = inspect.currentframe().f_back  # type: ignore

    if _locals is None:
        _locals = caller.f_locals

    if _globals is None:
        _globals = caller.f_globals

    code_obj = _transform_to_async(code)

    try:
        exec(code_obj, _globals, _locals)
        return _locals.pop("__async_exec_func_result__")
    finally:
        save_locals(caller)


sys.__async_eval__ = async_eval  # type: ignore

__all__ = ["async_eval", "is_async_code"]
