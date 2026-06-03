"""
Journal append-only (JSONL) de órdenes y eventos.

Registro auditable de todo lo que pasa por el Executor (simulado o no).
Alimenta tanto la revisión humana como la futura visualización (dashboard).
"""

from __future__ import annotations

import json
from pathlib import Path

from hermes.core.config import Settings, get_settings


class Journal:
    def __init__(self, settings: Settings | None = None):
        s = settings or get_settings()
        self.path = Path(s.data_dir) / "journal.jsonl"

    def record(self, event: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        out: list[dict] = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def tail(self, n: int) -> list[dict]:
        return self.read_all()[-n:]
