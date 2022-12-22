from asyncio import AbstractEventLoop, BaseEventLoop

from pytest import mark, raises


def _is_patched(loop: AbstractEventLoop) -> bool:
    return hasattr(loop, "_nest_patched")


class CustomEventLoop(BaseEventLoop):
    pass


class AsyncioEventLoop(BaseEventLoop):
    __module__ = "asyncio"


def _test_asyncio_patch():
    from async_eval import asyncio_patch  # noqa # isort:skip
    from asyncio import get_event_loop, new_event_loop, set_event_loop  # isort:skip

    assert _is_patched(get_event_loop())
    assert _is_patched(new_event_loop())

    loop = AsyncioEventLoop()
    set_event_loop(loop)
    assert _is_patched(loop)


def _test_asyncio_patch_non_default_loop():
    from asyncio import get_event_loop, set_event_loop  # isort:skip

    set_event_loop(CustomEventLoop())

    from async_eval import asyncio_patch  # noqa # isort:skip

    assert not _is_patched(get_event_loop())


def test_asyncio_patch(run_in_process):
    run_in_process(_test_asyncio_patch)


@mark.skip(reason="Need to find way how to test it")
def test_asyncio_patch_non_default_loop(run_in_process):
    run_in_process(_test_asyncio_patch_non_default_loop)


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
