from datetime import datetime, timezone

from ingest.adaptive import bin_pack, split_range
from ingest.client import FixtureClient
from ingest.merger import merge_on_id
from ingest.orchestrator import run
from ingest.worker import fetch_project


def test_adaptive_splits_when_over_threshold():
    stamps = [
        datetime(2024, 2, d, tzinfo=timezone.utc) for d in range(1, 17)
    ]

    def count_fn(start, end):
        return sum(1 for stamp in stamps if start <= stamp < end)

    windows = split_range(
        count_fn,
        datetime(2024, 2, 1, tzinfo=timezone.utc),
        datetime(2024, 2, 17, tzinfo=timezone.utc),
        threshold=5,
    )
    assert len(windows) >= 2
    assert all(count_fn(start, end) <= 5 for start, end in windows)
    assert sum(count_fn(start, end) for start, end in windows) == 16


def test_bin_pack_isolates_large_projects():
    batches = bin_pack([(100, 10), (200, 16), (300, 8)], target_issues=20, max_projects=3)
    assert [200] in batches


def test_merge_keeps_latest_project_on_move():
    rows = [
        {
            "id": 5001,
            "project_id": 100,
            "issue_key": "ALP-99",
            "updated": datetime(2024, 1, 4, tzinfo=timezone.utc),
        },
        {
            "id": 5001,
            "project_id": 300,
            "issue_key": "GAM-1",
            "updated": datetime(2024, 5, 1, tzinfo=timezone.utc),
        },
    ]
    merged = merge_on_id(rows)
    assert len(merged) == 1
    assert merged[0]["project_id"] == 300
    assert merged[0]["issue_key"] == "GAM-1"


def test_beta_uses_deep_sync(tmp_path):
    client = FixtureClient()
    result = fetch_project(client, 200)
    assert "deep" in result["mode"]
    assert result["partitions"] >= 2
    assert result["count"] == 16


def test_alpha_uses_fast_sync():
    result = fetch_project(FixtureClient(), 100)
    assert "fast" in result["mode"]
    assert result["partitions"] == 1


def test_full_run_writes_one_row_per_issue(tmp_path):
    warehouse = tmp_path / "warehouse.duckdb"
    manifest = tmp_path / "manifest.json"
    summary = run(
        warehouse_path=warehouse,
        manifest_path=manifest,
    )
    assert summary["issue_count"] == 34
    assert 200 in summary["modes"]
    assert "deep" in summary["modes"][200]["mode"]
