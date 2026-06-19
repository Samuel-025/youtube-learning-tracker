"""Local JSON storage for YouTube Learning Tracker.

All data is stored in data/videos.json on the local machine.
This file is gitignored — it is never committed to GitHub.
"""

import json
import os
from typing import Optional
from models.video import Video, WatchStatus


class Storage:
    def __init__(self, path: str = "data/videos.json"):
        self.path = path
        if not os.path.isabs(path):
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.path = os.path.join(root, path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write({})

    # ------------------------------------------------------------------ #
    #  Internal I/O                                                        #
    # ------------------------------------------------------------------ #

    def _read(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write(self, data: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    #  CRUD                                                                #
    # ------------------------------------------------------------------ #

    def save_video(self, video: Video) -> None:
        data = self._read()
        data[video.video_id] = video.to_dict()
        self._write(data)

    def get_video(self, video_id: str) -> Optional[Video]:
        data = self._read()
        if video_id not in data:
            return None
        try:
            return Video.from_dict(data[video_id])
        except Exception:
            return None

    def get_all_videos(self) -> list[Video]:
        data = self._read()
        videos: list[Video] = []
        for v in data.values():
            try:
                videos.append(Video.from_dict(v))
            except Exception:
                pass  # skip corrupt records silently
        return videos

    def delete_video(self, video_id: str) -> bool:
        data = self._read()
        if video_id not in data:
            return False
        del data[video_id]
        self._write(data)
        return True

    def update_video(self, video: Video) -> None:
        video.update_timestamp()
        self.save_video(video)

    # ------------------------------------------------------------------ #
    #  Query helpers                                                       #
    # ------------------------------------------------------------------ #

    def search_videos(self, query: str) -> list[Video]:
        """Case-insensitive search across title, channel, notes, and tags."""
        q = query.lower()
        results: list[Video] = []
        for v in self.get_all_videos():
            # Guard: manual_notes / tags may be None in old records
            notes = (v.manual_notes or "").lower()
            tags  = [t.lower() for t in (v.tags or [])]
            if (
                q in v.title.lower()
                or q in v.channel.lower()
                or q in notes
                or any(q in t for t in tags)
                or q in (v.summary_paragraph or "").lower()
            ):
                results.append(v)
        return results

    def filter_by_status(self, status: WatchStatus) -> list[Video]:
        return [v for v in self.get_all_videos() if v.status == status]

    def count_by_status(self) -> dict:
        counts: dict[str, int] = {s.value: 0 for s in WatchStatus}
        for v in self.get_all_videos():
            counts[v.status.value] = counts.get(v.status.value, 0) + 1
        return counts

    # ------------------------------------------------------------------ #
    #  Introspection                                                       #
    # ------------------------------------------------------------------ #

    def get_storage_path(self) -> str:
        return self.path

    def get_storage_size(self) -> str:
        if not os.path.exists(self.path):
            return "0 B"
        size = os.path.getsize(self.path)
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"
