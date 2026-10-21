"""Read fixture JSON as a stand-in for issue-tracker REST (no network)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ingest.config import FIXTURES


def _parse_ts(value: str) -> datetime:
    text = value.replace("Z", "+00:00").replace("+0000", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_json(name: str):
    path = FIXTURES / name
    return json.loads(path.read_text(encoding="utf-8"))


class FixtureClient:
    def __init__(self, fixtures_dir: Path | None = None) -> None:
        root = fixtures_dir or FIXTURES
        self.projects = json.loads((root / "projects.json").read_text(encoding="utf-8"))
        self.issues = json.loads((root / "issues.json").read_text(encoding="utf-8"))
        self.comments = json.loads((root / "comments.json").read_text(encoding="utf-8"))
        self.sprints = json.loads((root / "sprints.json").read_text(encoding="utf-8"))
        self.group_members = json.loads(
            (root / "group_members.json").read_text(encoding="utf-8")
        )
        for issue in self.issues:
            issue["_created"] = _parse_ts(issue["fields"]["created"])
            issue["_updated"] = _parse_ts(issue["fields"]["updated"])

    def list_projects(self) -> list[dict]:
        return list(self.projects)

    def issues_in_window(
        self,
        project_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        field: str = "updated",
    ) -> list[dict]:
        rows = []
        for issue in self.issues:
            if int(issue["fields"]["project"]["id"]) != int(project_id):
                continue
            stamp = issue["_updated"] if field == "updated" else issue["_created"]
            if start is not None and stamp < start:
                continue
            if end is not None and stamp >= end:
                continue
            rows.append(issue)
        return rows

    def approximate_count(
        self,
        project_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        field: str = "updated",
    ) -> int:
        return len(self.issues_in_window(project_id, start, end, field))

    def comments_for_issues(self, issue_ids: set[int]) -> list[dict]:
        return [row for row in self.comments if int(row["issue_id"]) in issue_ids]
