"""Issue JSON → bronze row, changelog events extracted."""

from datetime import datetime, timezone


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00").replace("+0000", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def flatten_issue(issue: dict) -> dict:
    fields = issue["fields"]
    due = fields.get("duedate")
    assignee = fields.get("assignee") or {}
    custom = {
        key: value
        for key, value in fields.items()
        if key.startswith("customfield_")
    }
    sprint = fields.get("sprint") or {}
    return {
        "id": int(issue["id"]),
        "project_id": int(fields["project"]["id"]),
        "issue_key": issue["key"],
        "issue_type": fields["issuetype"]["name"],
        "status": fields["status"]["name"],
        "summary": fields["summary"],
        "assignee_id": assignee.get("accountId"),
        "assignee_name": assignee.get("displayName"),
        "sprint_id": sprint.get("id"),
        "created": _parse_ts(fields["created"]),
        "updated": _parse_ts(fields["updated"]),
        "due_date": due,
        "custom_fields": custom,
    }


def explode_changelog(issue: dict) -> list[dict]:
    rows = []
    histories = (issue.get("changelog") or {}).get("histories") or []
    for history in histories:
        changed_at = _parse_ts(history["created"])
        for item in history.get("items") or []:
            rows.append(
                {
                    "issue_id": int(issue["id"]),
                    "changed_at": changed_at,
                    "field": item.get("field"),
                    "from_value": item.get("fromString"),
                    "to_value": item.get("toString"),
                }
            )
    return rows
