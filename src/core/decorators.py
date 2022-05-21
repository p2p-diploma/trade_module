import functools
import inspect

from exceptions import SomethingWentWrongException


def transactional(func):
    @functools.wraps(func)
    async def wrap_func(*args, **kwargs):
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            await kwargs["db"].commit()
        except Exception:
            await kwargs["db"].rollback()
            raise SomethingWentWrongException()

        return result

    return wrap_func
