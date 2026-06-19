"""Local JSON storage for YouTube Learning Tracker."""

import json
import os
from typing import Optional
from models.video import Video, WatchStatus


class Storage:
    def __init__(self, path: str = "data/videos.json"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            self._write({})

    def _read(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_video(self, video: Video):
        data = self._read()
        data[video.video_id] = video.to_dict()
        self._write(data)

    def get_video(self, video_id: str) -> Optional[Video]:
        data = self._read()
        if video_id not in data:
            return None
        return Video.from_dict(data[video_id])

    def get_all_videos(self) -> list[Video]:
        data = self._read()
        return [Video.from_dict(v) for v in data.values()]

    def delete_video(self, video_id: str) -> bool:
        data = self._read()
        if video_id not in data:
            return False
        del data[video_id]
        self._write(data)
        return True

    def update_video(self, video: Video):
        video.update_timestamp()
        self.save_video(video)

    def search_videos(self, query: str) -> list[Video]:
        query = query.lower()
        return [
            v for v in self.get_all_videos()
            if query in v.title.lower()
            or query in v.channel.lower()
            or query in v.manual_notes.lower()
            or any(query in tag.lower() for tag in v.tags)
        ]

    def filter_by_status(self, status: WatchStatus) -> list[Video]:
        return [v for v in self.get_all_videos() if v.status == status]

    def count_by_status(self) -> dict:
        counts = {s.value: 0 for s in WatchStatus}
        for v in self.get_all_videos():
            counts[v.status.value] += 1
        return counts
