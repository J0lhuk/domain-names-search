from datetime import UTC, datetime

from domain_checker.models import HistoryResult
from domain_checker.providers.history import merge_history


def test_merge_history_preserves_type_of_evidence() -> None:
    result = merge_history([
        HistoryResult(earliest_web_capture=datetime(2010, 1, 1, tzinfo=UTC)),
        HistoryResult(earliest_certificate_date=datetime(2012, 1, 1, tzinfo=UTC)),
    ])
    assert result.confirmed_registration_date is None
    assert result.earliest_web_capture == datetime(2010, 1, 1, tzinfo=UTC)
    assert result.earliest_certificate_date == datetime(2012, 1, 1, tzinfo=UTC)
