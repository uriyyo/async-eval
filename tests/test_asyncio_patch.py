from asyncio import BaseEventLoop

from pytest import raises


class CustomEventLoop(BaseEventLoop):
    pass


class AsyncioEventLoop(BaseEventLoop):
    __module__ = "asyncio"


def test_async_evaluate_is_not_available_for_eventloop(mocker):
    mocker.patch("async_eval.asyncio_patch.is_async_debug_available", return_value=False)

    from async_eval.ext.pydevd.code import evaluate_expression

    with raises(
        RuntimeError,
        match=r"^Can not evaluate async code with event loop .*\. "
        r"Only native asyncio event loop can be used for async code evaluating.$",
    ):
        evaluate_expression(
            object(),
            object(),
            "await regular()",
            True,
        )


def test_async_evaluate_is_not_available_for_trio(mocker):
    mocker.patch("async_eval.asyncio_patch.is_trio_not_running", return_value=False)

    from async_eval.asyncio_patch import verify_async_debug_available

    with raises(
        RuntimeError,
        match=r"^Can not evaluate async code with trio event loop. "
        r"Only native asyncio event loop can be used for async code evaluating.$",
    ):
        verify_async_debug_available()
