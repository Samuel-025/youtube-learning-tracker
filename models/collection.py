"""Collection (playlist) data model for YouTube Learning Tracker."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
import uuid


@dataclass
class Collection:
    name:        str
    id:          str        = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str        = ""
    emoji:       str        = "📁"
    video_ids:   list       = field(default_factory=list)   # ordered list of video_id strings
    created_at:  str        = field(default_factory=lambda: datetime.now().isoformat())
    updated_at:  str        = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Collection":
        known = {"id", "name", "description", "emoji", "video_ids", "created_at", "updated_at"}
        clean = {k: v for k, v in data.items() if k in known}
        return cls(**clean)

    def update_timestamp(self):
        self.updated_at = datetime.now().isoformat()

    @property
    def video_count(self) -> int:
        return len(self.video_ids)
