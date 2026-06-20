"""SettingsStore — read/write app-level settings to data/settings.json."""

from __future__ import annotations

import json
from pathlib import Path

_DEFAULTS: dict = {
    "weekly_goal_hours": 0,
}


class SettingsStore:
    """Persist key-value settings in a tiny JSON file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = {**_DEFAULTS}
        self._load()

    # ── private ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._path.exists():
            try:
                stored = json.loads(self._path.read_text(encoding="utf-8"))
                self._data.update(stored)
            except (json.JSONDecodeError, OSError):
                pass  # corrupt or missing — keep defaults

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── public API ────────────────────────────────────────────────────────

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self._save()

    # ── typed convenience helpers ─────────────────────────────────────────

    @property
    def weekly_goal_hours(self) -> float:
        return float(self._data.get("weekly_goal_hours", 0))

    @weekly_goal_hours.setter
    def weekly_goal_hours(self, value: float) -> None:
        self._data["weekly_goal_hours"] = max(0.0, float(value))
        self._save()
