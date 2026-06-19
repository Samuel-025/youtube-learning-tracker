"""Local JSON storage for YouTube Learning Tracker.

All data is stored in data/videos.json and data/collections.json on the local machine.
Both files are gitignored — they are never committed to GitHub.
"""

import json
import os
from typing import Optional
from models.video import Video, WatchStatus
from models.collection import Collection


class Storage:
    def __init__(self, path: str = "data/videos.json"):
        self.path = path
        if not os.path.isabs(path):
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.path = os.path.join(root, path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write({})

        # Collections live in a sibling file next to videos.json
        self._coll_path = os.path.join(os.path.dirname(self.path), "collections.json")
        if not os.path.exists(self._coll_path):
            self._write_collections({})

    # ------------------------------------------------------------------ #
    #  Internal I/O — Videos                                              #
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
    #  Internal I/O — Collections                                         #
    # ------------------------------------------------------------------ #

    def _read_collections(self) -> dict:
        try:
            with open(self._coll_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write_collections(self, data: dict) -> None:
        with open(self._coll_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    #  CRUD — Videos                                                       #
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
                pass
        return videos

    def delete_video(self, video_id: str) -> bool:
        data = self._read()
        if video_id not in data:
            return False
        del data[video_id]
        self._write(data)
        # Also remove from any collections
        for coll in self.get_all_collections():
            if video_id in coll.video_ids:
                coll.video_ids.remove(video_id)
                self.update_collection(coll)
        return True

    def update_video(self, video: Video) -> None:
        video.update_timestamp()
        self.save_video(video)

    # ------------------------------------------------------------------ #
    #  CRUD — Collections                                                  #
    # ------------------------------------------------------------------ #

    def save_collection(self, coll: Collection) -> None:
        data = self._read_collections()
        data[coll.id] = coll.to_dict()
        self._write_collections(data)

    def get_collection(self, coll_id: str) -> Optional[Collection]:
        data = self._read_collections()
        if coll_id not in data:
            return None
        try:
            return Collection.from_dict(data[coll_id])
        except Exception:
            return None

    def get_all_collections(self) -> list[Collection]:
        data = self._read_collections()
        colls: list[Collection] = []
        for c in data.values():
            try:
                colls.append(Collection.from_dict(c))
            except Exception:
                pass
        return sorted(colls, key=lambda c: c.created_at)

    def update_collection(self, coll: Collection) -> None:
        coll.update_timestamp()
        self.save_collection(coll)

    def delete_collection(self, coll_id: str) -> bool:
        data = self._read_collections()
        if coll_id not in data:
            return False
        del data[coll_id]
        self._write_collections(data)
        return True

    def add_video_to_collection(self, coll_id: str, video_id: str) -> bool:
        coll = self.get_collection(coll_id)
        if not coll:
            return False
        if video_id not in coll.video_ids:
            coll.video_ids.append(video_id)
            self.update_collection(coll)
        return True

    def remove_video_from_collection(self, coll_id: str, video_id: str) -> bool:
        coll = self.get_collection(coll_id)
        if not coll or video_id not in coll.video_ids:
            return False
        coll.video_ids.remove(video_id)
        self.update_collection(coll)
        return True

    def get_videos_in_collection(self, coll_id: str) -> list[Video]:
        coll = self.get_collection(coll_id)
        if not coll:
            return []
        videos = []
        for vid_id in coll.video_ids:
            v = self.get_video(vid_id)
            if v:
                videos.append(v)
        return videos

    def get_collections_for_video(self, video_id: str) -> list[Collection]:
        """Return all collections that contain a given video."""
        return [c for c in self.get_all_collections() if video_id in c.video_ids]

    # ------------------------------------------------------------------ #
    #  Query helpers — Videos                                             #
    # ------------------------------------------------------------------ #

    def search_videos(self, query: str) -> list[Video]:
        """Case-insensitive search across title, channel, notes, and tags."""
        q = query.lower()
        results: list[Video] = []
        for v in self.get_all_videos():
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
