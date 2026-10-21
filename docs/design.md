# Design notes

## Data flow and boundaries

The fixture client loads five JSON datasets. A worker selects a full or updated-time window for each project, using a 72-hour lookback for incremental extraction. Busy windows are bisected until they fit the demonstration threshold or reach the minimum interval. The orchestrator batches projects, collects results and reconciles the complete expected issue-ID set before committing data.

All bronze table replacements share one DuckDB transaction. Incremental mode first reads the existing snapshot, merges incoming rows at explicit grains and commits a new complete snapshot. It requires a prior full snapshot. JSON custom fields and UTC timestamps survive this round trip.

## Grains and modelling decisions

| Dataset | Grain | Reason |
|---|---|---|
| Issues | Immutable issue ID | An issue can move between projects and change key |
| Changelog | Issue ID, timestamp, field, from-value, to-value | Overlapping lookback windows should not duplicate observed change events |
| Comments | Comment ID | Updates replace the matching comment |
| Status history | Issue ID and observed status-event interval | Window functions reconstruct status intervals, including an initial event from the first change |
| Membership history | Account, group and validity window | Snapshot differences preserve historical membership rather than overwriting it |
| Comment membership | Comment ID | A range join answers whether the author was in a group at comment time |
| Epic violations | Epic key and rule code | Rules produce explicit records rather than dashboard-only expressions |

The changelog grain assumes distinct source events are distinguishable by that tuple. A live source with event IDs should use them. Status changes with identical timestamps would need an event sequence for deterministic ordering. Issues with no status changes do not currently produce a status-history interval.

Group-membership windows use half-open intervals, `[valid_from, valid_to)`, so a comment at the end boundary belongs to the next observed state. The snapshots record observed membership, not exact membership changes between observations. At present, display names are assumed stable; identities are account IDs.

## Failure and recovery contract

1. **Extraction fails:** no warehouse replacement has started. The existing snapshot and receipt remain.
2. **Issue IDs do not reconcile:** fail before writing anything.
3. **A database write fails:** roll back all bronze replacements together.
4. **Database commit succeeds, receipt fails:** the data is complete but the receipt may be old or absent. A rerun safely reconstructs/merges the data and rewrites the receipt.
5. **Run is repeated:** receipts never skip projects. Immutable IDs and event grains prevent duplicates.

Recovery means replaying extraction, not restoring an in-memory partial batch. Database and JSON receipt are separate resources; there is no claim of a distributed atomic commit between them. The receipt is explicitly non-authoritative.

The warehouse writer sets its session timezone to UTC before storing timezone-aware datetimes in timestamp columns. Tests check an unchanged incremental round trip to catch host-timezone shifts.

## Choosing a small local stack

Python keeps ingestion logic easy to inspect and test. DuckDB provides a transactional analytical store in one local file. dbt makes model dependencies, grain and quality checks visible. The pinned dependencies are tested on the CI matrix; no cloud credentials are needed for the demonstration.

The code trades throughput and memory efficiency for a transparent example: merges happen in memory, batches are sequential and each run writes a complete snapshot. Larger workloads would need durable staging, bounded memory, database-side merge operations and coordinated writers.

## Extending the example

- Replace the fixture client with a separate API adapter, including authentication, pagination, retry/backoff and rate-limit handling.
- Define how expected counts or IDs can be obtained independently of extraction, and how updates/deletions are reconciled.
- Add explicit source event IDs and ordering for tied timestamps.
- If per-project resume is needed, persist staged batches before marking them complete and bind state to the extraction input/window.
- Add deletion/tombstone rules and more temporal-boundary cases before relying on historical analytics.

These are extension ideas, not capabilities claimed by the current project.
