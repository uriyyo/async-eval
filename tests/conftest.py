import inspect

from pytest import Function


def pytest_collection_modifyitems(items) -> None:
    for item in items:
        if isinstance(item, Function) and inspect.iscoroutinefunction(item.obj):
            item.add_marker("asyncio")
