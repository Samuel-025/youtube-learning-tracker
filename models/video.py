"""Video data model for YouTube Learning Tracker."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from typing import Optional


class WatchStatus(str, Enum):
    SAVED     = "saved"
    WATCHING  = "watching"
    COMPLETED = "completed"
    DROPPED   = "dropped"
    REWATCH   = "rewatch"


@dataclass
class Video:
    video_id:          str
    url:               str
    title:             str
    channel:           str
    thumbnail_url:     str
    published_at:      str
    duration:          str
    status:            WatchStatus      = WatchStatus.SAVED
    transcript_text:   str              = ""
    transcript_source: str              = ""   # 'yt-dlp (manual subs)', 'yt-dlp (auto subs)', 'youtube-transcript-api', 'manual', 'upload'
    summary_bullets:   list             = field(default_factory=list)
    summary_paragraph: str              = ""
    auto_notes:        list             = field(default_factory=list)
    manual_notes:      str              = ""
    tags:              list             = field(default_factory=list)
    local_path:        str              = ""   # absolute path to downloaded audio/video file
    created_at:        str              = field(default_factory=lambda: datetime.now().isoformat())
    updated_at:        str              = field(default_factory=lambda: datetime.now().isoformat())

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
            "created_at", "updated_at",
        }
        clean = {k: v for k, v in data.items() if k in known}
        # Coerce status string → enum
        raw_status = clean.get("status", "saved")
        try:
            clean["status"] = WatchStatus(raw_status)
        except ValueError:
            clean["status"] = WatchStatus.SAVED
        return cls(**clean)

    def update_timestamp(self):
        self.updated_at = datetime.now().isoformat()
