from portfolio.services import tracing


def test_custom_spans_are_disabled_without_opt_in(monkeypatch, mocker):
    monkeypatch.delenv('DD_TRACE_ENABLED', raising=False)
    tracer = mocker.patch.object(tracing, '_dd_tracer')

    with tracing.span('portfolio.test') as active_span:
        assert active_span is None

    tracer.trace.assert_not_called()


def test_custom_spans_are_created_when_opted_in(monkeypatch, mocker):
    monkeypatch.setenv('DD_TRACE_ENABLED', 'true')
    tracer = mocker.patch.object(tracing, '_dd_tracer')

    with tracing.span('portfolio.test', resource='sample', tags={'count': 1}):
        pass

    tracer.trace.assert_called_once_with('portfolio.test', resource='sample')
    tracer.trace.return_value.__enter__.return_value.set_tag.assert_called_once_with('count', 1)
