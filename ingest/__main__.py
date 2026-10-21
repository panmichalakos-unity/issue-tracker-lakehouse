import argparse

from ingest.orchestrator import run
from ingest.warehouse import load_bronze


def main() -> None:
    parser = argparse.ArgumentParser(description='Build the offline issue-tracker bronze snapshot')
    parser.add_argument('--incremental', action='store_true',
                        help='Merge updates using per-project watermarks from an existing snapshot')
    args = parser.parse_args()
    watermarks = None
    if args.incremental:
        watermarks = {}
        for issue in load_bronze()['issues']:
            project = issue['project_id']
            watermarks[project] = max(watermarks.get(project, issue['updated']), issue['updated'])
    summary = run(watermarks=watermarks)
    print("ingest complete")
    print(f"  mode: {summary['mode']}")
    print(f"  issues: {summary['issue_count']}")
    print(f"  changelog rows: {summary['changelog_count']}")
    print(f"  batches: {summary['batches']}")
    for project_id, info in summary["modes"].items():
        print(
            f"  project {project_id}: {info['mode']} "
            f"count={info['count']} partitions={info['partitions']}"
        )


if __name__ == "__main__":
    main()
