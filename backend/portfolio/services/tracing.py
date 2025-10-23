from contextlib import contextmanager

try:
    from ddtrace import tracer as _dd_tracer  # type: ignore
except Exception:  # ddtrace not installed or disabled
    _dd_tracer = None


@contextmanager
def span(name: str, resource: str | None = None, tags: dict | None = None):
    if _dd_tracer is None:
        yield None
        return

    s_cm = _dd_tracer.trace(name, resource=resource)
    s = s_cm.__enter__()
    try:
        if tags:
            for k, v in tags.items():
                try:
                    s.set_tag(k, v)
                except Exception:
                    pass
        yield s
    except Exception as e:
        try:
            s.set_tag("error", True)
            s.set_tag("error.msg", str(e))
        except Exception:
            pass
        raise
    finally:
        s_cm.__exit__(None, None, None)

