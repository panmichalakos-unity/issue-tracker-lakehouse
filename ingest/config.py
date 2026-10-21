"""Local paths, fixed fixture clock and small demonstration thresholds."""

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
DATA = ROOT / "data"
WAREHOUSE = DATA / "warehouse.duckdb"
MANIFEST_PATH = DATA / "manifest.json"

# Frozen clock so ingest + tests match on any machine.
NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
LOOKBACK_HOURS = 72
FAST_SYNC_THRESHOLD = 10
ADAPTIVE_THRESHOLD = 5
OPS_GROUP = "ops"
FULL_SYNC_START = datetime(2020, 1, 1, tzinfo=timezone.utc)
