"""Atomically write an informational receipt after a successful database commit."""

import json
import os
from pathlib import Path
import tempfile

from ingest.config import MANIFEST_PATH


def save(doc: dict, path: Path | None = None) -> None:
    target = Path(path or MANIFEST_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                         prefix=target.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(doc, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
