# async-eval

## Install

```
poetry install
```

If not using PyCharm or PyDev, then specify "all-extras" install pydevd-pycharm:

```
poetry install --all-extras
```

## Run tests

```
pytest
```

## Usage

```python
from async_eval import eval


async def foo() -> int:
    return 10


print(eval("await foo()"))
```
