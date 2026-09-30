import inspect


def call_flexibly(fn, *signatures):
    """Call `fn` with the first `(args, kwargs)` pair its signature accepts.

    Lets user callbacks choose their own parameters (e.g. `provider(widget)` or
    `provider()`) without catching TypeErrors raised inside the callback.
    """
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):  # builtins without introspectable signatures
        args, kwargs = signatures[0]
        return fn(*args, **kwargs)

    for args, kwargs in signatures:
        try:
            signature.bind(*args, **kwargs)
        except TypeError:
            continue
        return fn(*args, **kwargs)

    raise TypeError(f"{getattr(fn, '__qualname__', fn)!r} accepts none of the supported call signatures")
