"""Video data model for YouTube Learning Tracker."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from typing import Optional
import re


class WatchStatus(str, Enum):
    SAVED     = "saved"
    WATCHING  = "watching"
    COMPLETED = "completed"
    DROPPED   = "dropped"
    REWATCH   = "rewatch"


def _parse_duration_sec(duration_str: str) -> int:
    """Convert human duration string to total seconds.

    Handles formats produced by the YouTube Data API / yt-dlp:
        '10:34'          ->  634
        '1:23:45'        -> 5025
        'PT1H23M45S'     -> 5025  (ISO 8601)
        '45'             ->   45  (bare seconds)
    Returns 0 if unparseable.
    """
    if not duration_str:
        return 0
    s = duration_str.strip()

    # ISO 8601  PT1H23M45S
    iso = re.fullmatch(
        r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', s, re.IGNORECASE
    )
    if iso:
        h, m, sec = (int(x) if x else 0 for x in iso.groups())
        return h * 3600 + m * 60 + sec

    # HH:MM:SS or MM:SS
    parts = s.split(':')
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 1:
        return parts[0]
    return 0


@dataclass
class Video:
    video_id:             str
    url:                  str
    title:                str
    channel:              str
    thumbnail_url:        str
    published_at:         str
    duration:             str
    status:               WatchStatus  = WatchStatus.SAVED
    transcript_text:      str          = ""
    transcript_source:    str          = ""   # 'yt-dlp (manual subs)', etc.
    summary_bullets:      list[str]    = field(default_factory=list)   # fix #15: typed
    summary_paragraph:    str          = ""
    auto_notes:           list[str]    = field(default_factory=list)   # fix #15: typed
    manual_notes:         str          = ""
    tags:                 list[str]    = field(default_factory=list)   # fix #15: typed
    local_path:           str          = ""   # absolute path to downloaded file
    # ── Watch progress ───────────────────────────────────────────
    watch_progress_sec:   int          = 0    # seconds watched so far
    duration_sec:         int          = 0    # total seconds (parsed from `duration`)
    # ────────────────────────────────────────────────────
    created_at:           str          = field(default_factory=lambda: datetime.now().isoformat())
    updated_at:           str          = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        """Auto-populate duration_sec from the human-readable duration string."""
        if self.duration_sec == 0 and self.duration:
            self.duration_sec = _parse_duration_sec(self.duration)
        # fix #15: coerce any non-str items that crept in via JSON into str
        self.summary_bullets = [str(b) for b in self.summary_bullets]
        self.auto_notes      = [str(n) for n in self.auto_notes]
        self.tags            = [str(t) for t in self.tags]

    @property
    def progress_pct(self) -> float:
        """Return watch progress as 0.0 – 100.0.  Returns 0 if duration unknown."""
        if self.duration_sec and self.duration_sec > 0:
            return min(100.0, self.watch_progress_sec / self.duration_sec * 100)
        return 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Video":
        """
        Safe loader: tolerates extra/missing keys as the schema evolves.
        Unknown keys are silently dropped; missing keys fall back to defaults.
        """
        known = {
            "video_id", "url", "title", "channel", "thumbnail_url",
            "published_at", "duration", "status", "transcript_text",
            "transcript_source", "summary_bullets", "summary_paragraph",
            "auto_notes", "manual_notes", "tags", "local_path",
            "watch_progress_sec", "duration_sec",
            "created_at", "updated_at",
        }
        clean = {k: v for k, v in data.items() if k in known}
        raw_status = clean.get("status", "saved")
        try:
            clean["status"] = WatchStatus(raw_status)
        except ValueError:
            clean["status"] = WatchStatus.SAVED
        return cls(**clean)

    def update_timestamp(self):
        self.updated_at = datetime.now().isoformat()
