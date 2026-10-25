"""Detached evidence ledger: an append-only JSON-lines file outside the database.

The event hash chain detects edits to individual events, but whoever controls
the whole database can rewrite every event and recompute the chain. Each issued
certificate's manifest and certificate digests are therefore also appended to
this file, which the verification CLI compares against. Keep it on separate
storage (or copy it off-host) for that comparison to mean anything.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterator
from pathlib import Path

_LOCK = threading.Lock()


class EvidenceLedger:
    def __init__(self, path: str | Path | None) -> None:
        self.path = Path(path) if path else None

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def append(self, entry: dict) -> bool:
        """Append one entry and fsync. Returns False when the ledger is disabled."""
        if self.path is None:
            return False
        line = json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n"
        with _LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
        return True

    def entries(self) -> Iterator[dict]:
        if self.path is None or not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def find(self, run_id: str) -> list[dict]:
        return [e for e in self.entries() if e.get("run_id") == run_id]
