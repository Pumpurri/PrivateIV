from contextlib import contextmanager
from TradeSimulator.env import env_flag

if env_flag('DD_TRACE_ENABLED', default=False):
    try:
        from ddtrace import tracer as _dd_tracer  # type: ignore
    except Exception:  # tracing is optional even if ddtrace fails to load
        _dd_tracer = None
else:
    _dd_tracer = None


@contextmanager
def span(name: str, resource: str | None = None, tags: dict | None = None):
    if not env_flag('DD_TRACE_ENABLED', default=False) or _dd_tracer is None:
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
