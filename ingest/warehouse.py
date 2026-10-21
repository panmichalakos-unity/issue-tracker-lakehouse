"""Write bronze tables into the local DuckDB file dbt will use."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

import duckdb

from ingest.config import WAREHOUSE


def _parse_ts(value):
    if value is None or isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00").replace("+0000", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def connect(path=None):
    target = Path(path or WAREHOUSE)
    target.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(target))
    # Store timezone-aware fixture timestamps as UTC, independent of the host.
    con.execute("SET TimeZone = 'UTC'")
    return con


def _json_or_none(value):
    if value is None:
        return None
    return json.dumps(value)


def replace_bronze(issues, changelog, comments, sprints, group_members, path=None) -> None:
    con = connect(path)
    try:
        con.execute("BEGIN TRANSACTION")
        _write_bronze(con, issues, changelog, comments, sprints, group_members)
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def _write_bronze(con, issues, changelog, comments, sprints, group_members):
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    con.execute("DROP TABLE IF EXISTS bronze.issues")
    con.execute("DROP TABLE IF EXISTS bronze.changelog")
    con.execute("DROP TABLE IF EXISTS bronze.comments")
    con.execute("DROP TABLE IF EXISTS bronze.sprints")
    con.execute("DROP TABLE IF EXISTS bronze.group_members")

    con.execute(
        """
        CREATE TABLE bronze.issues (
            id INTEGER,
            project_id INTEGER,
            issue_key VARCHAR,
            issue_type VARCHAR,
            status VARCHAR,
            summary VARCHAR,
            assignee_id VARCHAR,
            assignee_name VARCHAR,
            sprint_id INTEGER,
            created TIMESTAMP,
            updated TIMESTAMP,
            due_date VARCHAR,
            custom_fields VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE bronze.changelog (
            issue_id INTEGER,
            changed_at TIMESTAMP,
            field VARCHAR,
            from_value VARCHAR,
            to_value VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE bronze.comments (
            comment_id INTEGER,
            issue_id INTEGER,
            author_id VARCHAR,
            author_name VARCHAR,
            created TIMESTAMP,
            body VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE bronze.sprints (
            id INTEGER,
            name VARCHAR,
            state VARCHAR,
            project_id INTEGER,
            start_date TIMESTAMP,
            end_date TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE bronze.group_members (
            snapshot_date DATE,
            group_name VARCHAR,
            account_id VARCHAR,
            display_name VARCHAR
        )
        """
    )

    if issues:
        con.executemany(
            """
            INSERT INTO bronze.issues VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["project_id"],
                    row["issue_key"],
                    row["issue_type"],
                    row["status"],
                    row["summary"],
                    row["assignee_id"],
                    row["assignee_name"],
                    row["sprint_id"],
                    row["created"],
                    row["updated"],
                    row["due_date"],
                    _json_or_none(row["custom_fields"]),
                )
                for row in issues
            ],
        )
    if changelog:
        con.executemany(
            "INSERT INTO bronze.changelog VALUES (?, ?, ?, ?, ?)",
            [
                (
                    row["issue_id"],
                    row["changed_at"],
                    row["field"],
                    row["from_value"],
                    row["to_value"],
                )
                for row in changelog
            ],
        )
    if comments:
        con.executemany(
            "INSERT INTO bronze.comments VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    int(row["comment_id"]),
                    int(row["issue_id"]),
                    row["author_id"],
                    row["author_name"],
                    _parse_ts(row["created"]),
                    row["body"],
                )
                for row in comments
            ],
        )
    if sprints:
        con.executemany(
            "INSERT INTO bronze.sprints VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    int(row["id"]),
                    row["name"],
                    row["state"],
                    int(row["project_id"]),
                    _parse_ts(row["start_date"]),
                    _parse_ts(row["end_date"]),
                )
                for row in sprints
            ],
        )
    if group_members:
        con.executemany(
            "INSERT INTO bronze.group_members VALUES (?, ?, ?, ?)",
            [
                (
                    row["snapshot_date"],
                    row["group_name"],
                    row["account_id"],
                    row["display_name"],
                )
                for row in group_members
            ],
        )



def issue_count(path=None) -> int:
    con = connect(path)
    count = con.execute("SELECT COUNT(*) FROM bronze.issues").fetchone()[0]
    con.close()
    return int(count)


def load_bronze(path=None) -> dict[str, list[dict]]:
    """Read the last complete snapshot as input for an incremental merge."""
    target = Path(path or WAREHOUSE)
    if not target.is_file():
        raise ValueError("Run a full snapshot before supplying watermarks")
    with duckdb.connect(str(target), read_only=True) as con:
        tables = {row[0] for row in con.execute(
            "select table_name from information_schema.tables where table_schema='bronze'").fetchall()}
        if not {'issues', 'changelog', 'comments'}.issubset(tables):
            raise ValueError("Run a full snapshot before supplying watermarks")
        result = {}
        for table in ('issues', 'changelog', 'comments'):
            cursor = con.execute(f'SELECT * FROM bronze.{table}')
            names = [column[0] for column in cursor.description]
            rows = [dict(zip(names, values)) for values in cursor.fetchall()]
            for row in rows:
                for name, value in row.items():
                    if isinstance(value, datetime) and value.tzinfo is None:
                        row[name] = value.replace(tzinfo=timezone.utc)
                if table == 'issues' and row['custom_fields'] is not None:
                    row['custom_fields'] = json.loads(row['custom_fields'])
            result[table] = rows
        return result
