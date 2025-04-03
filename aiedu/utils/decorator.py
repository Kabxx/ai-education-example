from rich import print


def retry(
    max_retry: int,
):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for i in range(max_retry):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error = e
                print(f"Retrying {func.__name__} ... ({i + 1}/{max_retry})\n")

            raise error

        return wrapper

    return decorator


def async_retry(
    max_retry: int,
):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for i in range(max_retry):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    error = e
                print(f"Retrying {func.__name__} ... ({i + 1}/{max_retry})\n")
            raise error

        return wrapper

    return decorator
