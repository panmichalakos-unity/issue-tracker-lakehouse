"""Extract, reconcile and atomically commit a complete fixture-backed snapshot."""

from __future__ import annotations

from datetime import datetime, timezone

from ingest.adaptive import bin_pack
from ingest.client import FixtureClient
from ingest.config import FULL_SYNC_START, MANIFEST_PATH, NOW
from ingest.manifest import save
from ingest.merger import merge_on_id
from ingest.warehouse import load_bronze, replace_bronze
from ingest.worker import fetch_project


class DriftError(RuntimeError):
    """The proposed snapshot does not contain exactly the expected issue IDs."""


def _merge_records(existing, incoming, keys):
    """Upsert at an explicit grain, normalising timestamps read from DuckDB."""
    def identity(row):
        values = []
        for name in keys:
            value = row[name]
            if isinstance(value, datetime):
                value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
                value = value.astimezone(timezone.utc).isoformat()
            values.append(value)
        return tuple(values)

    merged = {identity(row): row for row in existing}
    merged.update((identity(row), row) for row in incoming)
    return list(merged.values())


def run(
    client: FixtureClient | None = None,
    watermarks: dict[int, datetime] | None = None,
    warehouse_path=None,
    manifest_path=None,
) -> dict:
    """Refresh the snapshot; watermark runs merge into an existing snapshot.

    The fixture clock is fixed. A failed extraction or reconciliation never
    replaces the last snapshot. Restart recovery replays extraction; the JSON
    receipt is informational and is never used to skip projects.
    """
    client = client or FixtureClient()
    watermarks = watermarks or {}
    previous = load_bronze(warehouse_path) if watermarks else None
    projects = client.list_projects()
    project_ids = {int(project['id']) for project in projects}
    if set(watermarks) - project_ids:
        raise ValueError('Watermarks contain unknown project IDs')
    if any(value.tzinfo is None or value > NOW for value in watermarks.values()):
        raise ValueError('Watermarks must be timezone-aware and no later than the fixture clock')

    counts = [(project_id, client.approximate_count(project_id)) for project_id in sorted(project_ids)]
    batches = bin_pack(counts)
    staging_issues, staging_changelog, staging_comments = [], [], []
    modes = {}
    for batch in batches:
        for project_id in batch:
            result = fetch_project(client, project_id, watermark=watermarks.get(project_id))
            modes[project_id] = {key: result[key] for key in ('mode', 'count', 'partitions')}
            staging_issues.extend(result['issues'])
            staging_changelog.extend(result['changelog'])
            staging_comments.extend(result['comments'])

    issues = merge_on_id((previous['issues'] if previous else []) + staging_issues)
    changelog = _merge_records(
        previous['changelog'] if previous else [], staging_changelog,
        ('issue_id', 'changed_at', 'field', 'from_value', 'to_value'))
    comments = _merge_records(previous['comments'] if previous else [], staging_comments, ('comment_id',))

    expected_ids = {
        int(issue['id']) for issue in client.issues
        if int(issue['fields']['project']['id']) in project_ids
        and FULL_SYNC_START <= issue['_created'] < NOW
    }
    actual_ids = {row['id'] for row in issues}
    if actual_ids != expected_ids:
        raise DriftError(
            f'Issue ID reconciliation failed: missing={len(expected_ids - actual_ids)}, '
            f'unexpected={len(actual_ids - expected_ids)}; previous snapshot preserved')

    replace_bronze(issues, changelog, comments, client.sprints, client.group_members, path=warehouse_path)
    summary = {
        'batches': batches, 'modes': modes, 'issue_count': len(issues),
        'changelog_count': len(changelog), 'skipped': [], 'api_count': sum(count for _, count in counts),
        'mode': 'incremental' if watermarks else 'snapshot',
    }
    # A receipt failure may leave committed data with an old receipt. Replaying
    # remains safe because receipts never determine what the next run fetches.
    save({
        'status': 'COMPLETED', 'completed_at': datetime.now(timezone.utc).isoformat(),
        'fixture_as_of': NOW.isoformat(), 'issue_count': len(issues),
        'projects': {str(project_id): 'SUCCESS' for project_id in sorted(project_ids)},
        'mode': summary['mode'],
    }, manifest_path or MANIFEST_PATH)
    return summary
