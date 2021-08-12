import textwrap

from pytest import fixture, mark, raises

from async_eval.async_eval import async_eval, is_async_code

from .utils import (  # noqa  # isort:skip
    MyException,
    ctxmanager,
    generator,
    raise_exc,
    regular,
)

try:
    import contextvars
except ImportError:
    contextvars = None


pytestmark = mark.asyncio


@mark.parametrize(
    "expr",
    [
        "await foo()",
        "async for i in range(10):pass",
        "async with i:pass",
        "[i async for i in generator()]",
        "{i async for i in generator()}",
        "{i: i async for i in generator()}",
        "(i async for i in generator())",
        "try:\n    await foo()\nexcept:pass",
        "[i for i in range() if await foo()]",
        "{i for i in range() if await foo()}",
        "{i: i for i in range() if await foo()}",
        "(i for i in range() if await foo())",
        "def foo(a = await bar()): pass",
        "async def foo(a = await bar()): pass",
        "@bar(await fizz())\ndef foo(): pass",
        "@bar(await fizz())\nasync def foo(): pass",
    ],
    ids=[
        "await",
        "async-for",
        "async-with",
        "async-list-comprehension",
        "async-set-comprehension",
        "async-dict-comprehension",
        "async-gen-expression",
        "nested-await",
        "async-list-with-async-if",
        "async-set-with-async-if",
        "async-dict-with-async-if",
        "gen-expression-with-async-if",
        "func-def-with-await-at-default-value",
        "async-func-def-with-await-at-default-value",
        "async-decorator-at-func",
        "async-decorator-at-async-func",
    ],
)
def test_is_async_code(expr):
    assert is_async_code(expr)


@mark.parametrize(
    "expr",
    [
        "12312asdfasdf",
        "foo()",
        "for i in range(10):pass",
        "with i:pass",
        "[i async i in generator()]",
        "{i async i in generator()}",
        "{i: i for i in generator()}",
        "(i for i in generator())",
        "def foo(a = bar()): pass",
        "async def foo(a = bar()): pass",
        "@bar(fizz())\ndef foo(): pass",
        "@bar(fizz())\nasync def foo(): pass",
        "def foo():\n    await bar()",
        "async def foo():\n    await bar()",
        "async def foo():pass",
        "class Foo:pass",
    ],
    ids=[
        "syntax-error",
        "expr",
        "for",
        "with",
        "list-comprehension",
        "set-comprehension",
        "dict-comprehension",
        "gen-expression",
        "func-def-with--default-value",
        "async-func-def-with-default-value",
        "decorator-at-func",
        "decorator-at-async-func",
        "func-with-async-body",
        "async-func-with-async-body",
        "async-func",
        "class-def",
    ],
)
def test_is_not_async_code(expr):
    assert not is_async_code(expr)


@mark.parametrize(
    "expr,result",
    [
        ("10", 10),
        ("regular", regular),
        ("await regular()", 10),
        ("[i async for i in generator()]", [*range(10)]),
        ("async with ctxmanager():\n    10", 10),
        ("await regular()\nawait regular() * 2", 20),
        ("async for i in generator():\n    i * 2", None),
    ],
    ids=[
        "literal",
        "not-async",
        "await",
        "async-comprehension",
        "async-with",
        "multiline",
        "async-for",
    ],
)
async def test_async_eval(expr, result):
    assert async_eval(expr) == result


@mark.parametrize(
    "expr,result",
    [
        ("a = 20", 20),
        ("a = regular", regular),
        ("a = await regular()", 10),
        ("a = [i async for i in generator()]", [*range(10)]),
        ("async with ctxmanager():\n    a = 10", 10),
        ("async for i in generator():\n    a = i", 9),
    ],
    ids=[
        "literal",
        "not-async",
        "await",
        "async-comprehension",
        "async-with",
        "async-for",
    ],
)
async def test_async_eval_modify_locals(expr, result):
    a = None
    async_eval(expr)
    assert a == result


async def test_eval_raise_exc():
    with raises(MyException):
        async_eval("await raise_exc()")


async def test_async_eval_dont_leak_internal_vars():
    _globals = _locals = {}
    async_eval("10", _globals, _locals)

    assert not _globals
    assert not _locals


if contextvars:
    ctx_var = contextvars.ContextVar("ctx_var")


@mark.skipif(
    contextvars is None,
    reason="contextvars is not available",
)
class TestContextVars:
    @fixture(autouse=True)
    def reset_var(self):
        ctx_var.set(0)

    def test_ctx_get(self):
        assert async_eval("ctx_var.get()") == 0

    def test_ctx_set(self):
        async_eval("ctx_var.set(10)")
        assert ctx_var.get() == 10

    # issue #7
    def test_ctx_var_reset(self):
        # fmt: off
        async_eval(textwrap.dedent("""
        from asyncio import sleep
        token = ctx_var.set(10)
        await sleep(0)  # switch to different task
        ctx_var.reset(token)
        """))
        # fmt: on

        assert ctx_var.get() == 0
