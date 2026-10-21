"""Keep one row per issue id. A moved ticket (new project, same id) wins on updated."""


def merge_on_id(rows: list[dict]) -> list[dict]:
    best: dict[int, dict] = {}
    for row in rows:
        issue_id = int(row["id"])
        previous = best.get(issue_id)
        if previous is None or row["updated"] >= previous["updated"]:
            best[issue_id] = row
    return list(best.values())


def drift_ratio(api_count: int, table_count: int) -> float:
    if api_count == 0:
        return 0.0 if table_count == 0 else 1.0
    return abs(api_count - table_count) / api_count
