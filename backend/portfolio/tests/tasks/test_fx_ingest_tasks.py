import pytest
from unittest.mock import patch

from portfolio.tasks import fx_ingest_latest_auto


@pytest.mark.django_db
class TestFxIngestTask:
    @patch('portfolio.tasks.upsert_latest_from_bcrp')
    def test_task_returns_service_result(self, mock_upsert):
        expected = {'compra': {'series': 'PD04645PD'}}
        mock_upsert.return_value = expected

        result = fx_ingest_latest_auto(mode='cierre')

        assert result == expected
        mock_upsert.assert_called_once_with(mode='cierre')

    @patch('portfolio.tasks.upsert_latest_from_bcrp')
    def test_task_re_raises_service_failure_in_eager_mode(self, mock_upsert):
        mock_upsert.side_effect = RuntimeError('provider unavailable')

        with pytest.raises(RuntimeError, match='provider unavailable'):
            fx_ingest_latest_auto.delay(mode='auto')
