"""Bisect a time range until each partition is at most `threshold` issues."""

from datetime import datetime, timedelta


def split_range(
    count_fn,
    start: datetime,
    end: datetime,
    threshold: int,
    min_width: timedelta = timedelta(minutes=1),
) -> list[tuple[datetime, datetime]]:
    """Return contiguous [start, end) windows whose counts are <= threshold.

    `count_fn(start, end)` returns how many issues fall in [start, end).
    If a window cannot shrink further and is still over threshold, it is
    returned as-is. The fixture client can return every matching row; a live
    API would need an explicit paging or overflow strategy.
    """
    count = count_fn(start, end)
    if count <= threshold:
        return [(start, end)]
    if end - start <= min_width:
        return [(start, end)]
    mid = start + (end - start) / 2
    if mid <= start or mid >= end:
        return [(start, end)]
    return split_range(count_fn, start, mid, threshold, min_width) + split_range(
        count_fn, mid, end, threshold, min_width
    )


def bin_pack(
    projects: list[tuple[int, int]],
    target_issues: int = 20,
    max_projects: int = 3,
) -> list[list[int]]:
    """Greedy bin-pack (id, count). Large projects get their own batch."""
    descending = sorted(projects, key=lambda row: row[1], reverse=True)
    batches: list[list[tuple[int, int]]] = []
    for project_id, count in descending:
        if count >= target_issues:
            batches.append([(project_id, count)])
            continue
        placed = False
        for batch in batches:
            batch_count = sum(item[1] for item in batch)
            if len(batch) < max_projects and batch_count + count <= target_issues:
                batch.append((project_id, count))
                placed = True
                break
        if not placed:
            batches.append([(project_id, count)])
    return [[project_id for project_id, _ in batch] for batch in batches]
