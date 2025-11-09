# async-eval

## Install

```
uv sync
```

If not using PyCharm or PyDev, then specify "all-extras" install pydevd-pycharm:

```
uv sync --dev --all-extras
```

## Run tests

```
uv run pytest
```

## Usage

```python
from async_eval import eval


async def foo() -> int:
    return 10


print(eval("await foo()"))
```
