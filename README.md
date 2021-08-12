# async-eval

```python
from async_eval import eval


async def foo() -> int:
    return 10


print(eval("await foo()"))
```
