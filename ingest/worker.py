"""Fetch one project: fast window, or deep-sync with adaptive partitions."""

from __future__ import annotations

from datetime import datetime, timedelta

from ingest.adaptive import split_range
from ingest.client import FixtureClient
from ingest.config import (
    ADAPTIVE_THRESHOLD,
    FAST_SYNC_THRESHOLD,
    FULL_SYNC_START,
    LOOKBACK_HOURS,
    NOW,
)
from ingest.flatten import explode_changelog, flatten_issue


def fetch_project(
    client: FixtureClient,
    project_id: int,
    watermark: datetime | None = None,
    now: datetime | None = None,
) -> dict:
    clock = now or NOW
    if watermark is None:
        start = FULL_SYNC_START
        field = "created"
        mode = "full"
    else:
        start = watermark - timedelta(hours=LOOKBACK_HOURS)
        field = "updated"
        mode = "incremental"

    count = client.approximate_count(project_id, start, clock, field)
    if count <= FAST_SYNC_THRESHOLD:
        issues = client.issues_in_window(project_id, start, clock, field)
        partitions = 1
        mode = f"{mode}_fast"
    else:
        def count_fn(window_start, window_end):
            return client.approximate_count(
                project_id, window_start, window_end, field
            )

        windows = split_range(count_fn, start, clock, ADAPTIVE_THRESHOLD)
        issues = []
        seen = set()
        for window_start, window_end in windows:
            for issue in client.issues_in_window(
                project_id, window_start, window_end, field
            ):
                if issue["id"] in seen:
                    continue
                seen.add(issue["id"])
                issues.append(issue)
        partitions = len(windows)
        mode = f"{mode}_deep"

    staging = [flatten_issue(issue) for issue in issues]
    changelog = []
    for issue in issues:
        changelog.extend(explode_changelog(issue))
    issue_ids = {int(issue["id"]) for issue in issues}
    comments = client.comments_for_issues(issue_ids)
    return {
        "project_id": project_id,
        "mode": mode,
        "count": count,
        "partitions": partitions,
        "issues": staging,
        "changelog": changelog,
        "comments": comments,
    }
