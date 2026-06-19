"""Video data model for YouTube Learning Tracker."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from typing import Optional


class WatchStatus(str, Enum):
    SAVED = "saved"
    WATCHING = "watching"
    COMPLETED = "completed"
    DROPPED = "dropped"
    REWATCH = "rewatch"


@dataclass
class Video:
    video_id: str
    url: str
    title: str
    channel: str
    thumbnail_url: str
    published_at: str
    duration: str
    status: WatchStatus = WatchStatus.SAVED
    transcript_text: str = ""
    transcript_source: str = ""  # 'auto', 'manual', 'upload'
    summary_bullets: list = field(default_factory=list)
    summary_paragraph: str = ""
    auto_notes: list = field(default_factory=list)
    manual_notes: str = ""
    tags: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Video":
        data["status"] = WatchStatus(data.get("status", "saved"))
        return cls(**data)

    def update_timestamp(self):
        self.updated_at = datetime.now().isoformat()
