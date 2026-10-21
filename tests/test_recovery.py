import json
from datetime import datetime, timezone

import duckdb
import pytest

from ingest.client import FixtureClient
from ingest.orchestrator import run
import ingest.orchestrator as orchestrator
from ingest.warehouse import load_bronze


def row_count(path):
    with duckdb.connect(str(path), read_only=True) as con:
        return con.execute('select count(*) from bronze.issues').fetchone()[0]


def test_repeated_run_preserves_issue_table(tmp_path):
    warehouse = tmp_path / 'warehouse.duckdb'
    manifest = tmp_path / 'manifest.json'
    run(warehouse_path=warehouse, manifest_path=manifest)
    run(warehouse_path=warehouse, manifest_path=manifest)
    assert row_count(warehouse) == 34


def test_bad_write_rolls_back_previous_snapshot(tmp_path):
    warehouse = tmp_path / 'warehouse.duckdb'
    manifest = tmp_path / 'manifest.json'
    run(warehouse_path=warehouse, manifest_path=manifest)
    previous_receipt = manifest.read_bytes()
    client = FixtureClient()
    client.group_members[0]['snapshot_date'] = 'invalid-date'
    with pytest.raises(duckdb.Error):
        run(client=client, warehouse_path=warehouse, manifest_path=manifest)
    assert row_count(warehouse) == 34
    assert manifest.read_bytes() == previous_receipt


def test_interrupted_extraction_preserves_snapshot_and_receipt(tmp_path, monkeypatch):
    warehouse, manifest = tmp_path / 'warehouse.duckdb', tmp_path / 'manifest.json'
    run(warehouse_path=warehouse, manifest_path=manifest)
    previous_receipt = manifest.read_bytes()
    fetch = orchestrator.fetch_project

    def interrupted(client, project_id, **kwargs):
        if project_id == 100:
            raise RuntimeError('simulated interrupted extraction')
        return fetch(client, project_id, **kwargs)

    monkeypatch.setattr(orchestrator, 'fetch_project', interrupted)
    with pytest.raises(RuntimeError, match='interrupted extraction'):
        run(warehouse_path=warehouse, manifest_path=manifest)
    assert row_count(warehouse) == 34
    assert manifest.read_bytes() == previous_receipt
    monkeypatch.setattr(orchestrator, 'fetch_project', fetch)
    assert run(warehouse_path=warehouse, manifest_path=manifest)['issue_count'] == 34


def test_reconciliation_rejects_wrong_id_even_when_count_matches(tmp_path, monkeypatch):
    warehouse, manifest = tmp_path / 'warehouse.duckdb', tmp_path / 'manifest.json'
    run(warehouse_path=warehouse, manifest_path=manifest)
    previous_receipt = manifest.read_bytes()
    fetch = orchestrator.fetch_project

    def wrong_id(client, project_id, **kwargs):
        result = fetch(client, project_id, **kwargs)
        if project_id == 100:
            result['issues'][0]['id'] = 999999
        return result

    monkeypatch.setattr(orchestrator, 'fetch_project', wrong_id)
    with pytest.raises(orchestrator.DriftError, match='reconciliation failed'):
        run(warehouse_path=warehouse, manifest_path=manifest)
    assert row_count(warehouse) == 34
    assert manifest.read_bytes() == previous_receipt


@pytest.mark.parametrize('receipt', ['not-json', '{"projects":{"100":"SUCCESS","200":"SUCCESS","300":"SUCCESS"}}'])
def test_old_or_corrupt_receipt_cannot_skip_extraction(tmp_path, receipt):
    warehouse, manifest = tmp_path / 'warehouse.duckdb', tmp_path / 'manifest.json'
    manifest.write_text(receipt)
    assert run(warehouse_path=warehouse, manifest_path=manifest)['issue_count'] == 34
    assert json.loads(manifest.read_text())['status'] == 'COMPLETED'


def test_receipt_failure_after_commit_is_safe_to_replay(tmp_path, monkeypatch):
    warehouse, manifest = tmp_path / 'warehouse.duckdb', tmp_path / 'manifest.json'
    save = orchestrator.save

    def fail_receipt(*args, **kwargs):
        raise OSError('simulated receipt write failure')

    monkeypatch.setattr(orchestrator, 'save', fail_receipt)
    with pytest.raises(OSError, match='receipt write failure'):
        run(warehouse_path=warehouse, manifest_path=manifest)
    assert row_count(warehouse) == 34
    assert not manifest.exists()
    monkeypatch.setattr(orchestrator, 'save', save)
    assert run(warehouse_path=warehouse, manifest_path=manifest)['issue_count'] == 34


def test_incremental_merge_preserves_unchanged_rows_and_deduplicates_history(tmp_path):
    warehouse, manifest = tmp_path / 'warehouse.duckdb', tmp_path / 'manifest.json'
    client = FixtureClient()
    client.issues[0]['fields']['customfield_demo'] = 'synthetic-value'
    run(client=client, warehouse_path=warehouse, manifest_path=manifest)
    baseline = load_bronze(warehouse)
    watermarks = {project: datetime(2024, 6, 1, tzinfo=timezone.utc) for project in (100, 200, 300)}
    # All rows fall before this window; an incremental run must retain them.
    run(client=client, watermarks=watermarks, warehouse_path=warehouse, manifest_path=manifest)
    assert load_bronze(warehouse) == baseline
    # Overlapping windows must not duplicate changelog events or comments.
    watermarks = {project: datetime(2024, 1, 1, tzinfo=timezone.utc) for project in (100, 200, 300)}
    run(client=client, watermarks=watermarks, warehouse_path=warehouse, manifest_path=manifest)
    after = load_bronze(warehouse)
    assert len(after['issues']) == len(baseline['issues']) == 34
    assert len(after['changelog']) == len(baseline['changelog'])
    assert len(after['comments']) == len(baseline['comments'])
    changed = next(row for row in after['issues'] if row['id'] == int(client.issues[0]['id']))
    assert changed['custom_fields'] == {'customfield_demo': 'synthetic-value'}
    assert changed['created'] == client.issues[0]['_created']


def test_incremental_merge_updates_one_issue_without_losing_others(tmp_path):
    warehouse, manifest = tmp_path / 'warehouse.duckdb', tmp_path / 'manifest.json'
    client = FixtureClient()
    run(client=client, warehouse_path=warehouse, manifest_path=manifest)
    client.issues[0]['fields']['summary'] = 'Synthetic updated title'
    client.issues[0]['_updated'] = datetime(2024, 6, 10, tzinfo=timezone.utc)
    client.issues[0]['fields']['updated'] = '2024-06-10T00:00:00Z'
    watermarks = {project: datetime(2024, 6, 1, tzinfo=timezone.utc) for project in (100, 200, 300)}
    run(client=client, watermarks=watermarks, warehouse_path=warehouse, manifest_path=manifest)
    issues = load_bronze(warehouse)['issues']
    assert len(issues) == 34
    changed = next(row for row in issues if row['id'] == int(client.issues[0]['id']))
    assert changed['summary'] == 'Synthetic updated title'


def test_incremental_bootstrap_requires_complete_snapshot(tmp_path):
    with pytest.raises(ValueError, match='full snapshot'):
        run(watermarks={100: datetime(2024, 6, 1, tzinfo=timezone.utc)},
            warehouse_path=tmp_path / 'absent.duckdb', manifest_path=tmp_path / 'manifest.json')


def test_issue_moved_to_another_project_retains_one_identity(tmp_path):
    warehouse, manifest = tmp_path / 'warehouse.duckdb', tmp_path / 'manifest.json'
    client = FixtureClient()
    run(client=client, warehouse_path=warehouse, manifest_path=manifest)
    issue = client.issues[0]
    issue['fields']['project']['id'] = 300
    issue['key'] = 'GAM-MOVED'
    issue['_updated'] = datetime(2024, 6, 10, tzinfo=timezone.utc)
    issue['fields']['updated'] = '2024-06-10T00:00:00Z'
    watermarks = {project: datetime(2024, 6, 1, tzinfo=timezone.utc) for project in (100, 200, 300)}
    run(client=client, watermarks=watermarks, warehouse_path=warehouse, manifest_path=manifest)
    issues = load_bronze(warehouse)['issues']
    matches = [row for row in issues if row['id'] == int(issue['id'])]
    assert len(issues) == 34
    assert len(matches) == 1
    assert matches[0]['project_id'] == 300
    assert matches[0]['issue_key'] == 'GAM-MOVED'
