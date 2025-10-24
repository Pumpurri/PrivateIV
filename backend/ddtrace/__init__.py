"""
Lightweight fallback for environments where ddtrace is unavailable.
Provides the minimal surface area used by the app so management commands can run.
"""
from contextlib import contextmanager


class _DummySpan:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def set_tag(self, *args, **kwargs):
        return None


class _DummyTracer:
    def trace(self, *args, **kwargs):
        return _DummySpan()


def patch_all(*args, **kwargs):
    return None


tracer = _DummyTracer()
