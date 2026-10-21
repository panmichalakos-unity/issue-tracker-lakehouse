from datetime import datetime, timedelta, timezone

from ingest.adaptive import split_range


def test_dense_minimum_window_terminates_without_losing_window():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(minutes=1)
    assert split_range(lambda a, b: 20, start, end, threshold=5) == [(start, end)]
