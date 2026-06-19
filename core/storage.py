"""Local JSON storage for YouTube Learning Tracker.

All data is stored in data/videos.json and data/collections.json on the local machine.
Both files are gitignored — they are never committed to GitHub.
"""

import json
import logging
import os
import threading
from typing import Optional
from models.video import Video, WatchStatus
from models.collection import Collection

logger = logging.getLogger(__name__)

# fix #1: one lock per process guards both JSON files
_STORAGE_LOCK = threading.Lock()


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
        """Atomic write: write to .tmp then os.replace() so no partial writes."""
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)  # fix #1: atomic on all OSes

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
        """Atomic write for collections file."""
        tmp = self._coll_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self._coll_path)  # fix #1: atomic

    # ------------------------------------------------------------------ #
    #  CRUD — Videos                                                       #
    # ------------------------------------------------------------------ #

    def save_video(self, video: Video) -> None:
        with _STORAGE_LOCK:  # fix #1: serialize concurrent Streamlit reruns
            data = self._read()
            data[video.video_id] = video.to_dict()
            self._write(data)

    def get_video(self, video_id: str) -> Optional[Video]:
        with _STORAGE_LOCK:
            data = self._read()
        if video_id not in data:
            return None
        try:
            return Video.from_dict(data[video_id])
        except Exception as exc:
            logger.warning("Skipped corrupt video record %s: %s", video_id, exc)  # fix #13
            return None

    def get_all_videos(self) -> list[Video]:
        with _STORAGE_LOCK:
            data = self._read()
        videos: list[Video] = []
        for vid_id, v in data.items():
            try:
                videos.append(Video.from_dict(v))
            except Exception as exc:
                logger.warning("Skipped corrupt video record %s: %s", vid_id, exc)  # fix #13
        return videos

    def delete_video(self, video_id: str) -> bool:
        with _STORAGE_LOCK:  # fix #8: hold lock for entire delete + collection update
            data = self._read()
            if video_id not in data:
                return False
            del data[video_id]
            self._write(data)

            # fix #8: batch collection updates — single read + single write
            coll_data = self._read_collections()
            changed   = False
            for coll_dict in coll_data.values():
                ids = coll_dict.get("video_ids", [])
                if video_id in ids:
                    ids.remove(video_id)
                    changed = True
            if changed:
                self._write_collections(coll_data)
        return True

    def update_video(self, video: Video) -> None:
        video.update_timestamp()
        self.save_video(video)

    def clear_all_videos(self) -> None:
        """Delete every video AND wipe all collection video_ids in one atomic pass."""
        with _STORAGE_LOCK:
            self._write({})
            coll_data = self._read_collections()
            for coll_dict in coll_data.values():
                coll_dict["video_ids"] = []
            self._write_collections(coll_data)

    # ------------------------------------------------------------------ #
    #  CRUD — Collections                                                  #
    # ------------------------------------------------------------------ #

    def save_collection(self, coll: Collection) -> None:
        with _STORAGE_LOCK:
            data = self._read_collections()
            data[coll.id] = coll.to_dict()
            self._write_collections(data)

    def get_collection(self, coll_id: str) -> Optional[Collection]:
        with _STORAGE_LOCK:
            data = self._read_collections()
        if coll_id not in data:
            return None
        try:
            return Collection.from_dict(data[coll_id])
        except Exception as exc:
            logger.warning("Skipped corrupt collection record %s: %s", coll_id, exc)  # fix #13
            return None

    def get_all_collections(self) -> list[Collection]:
        with _STORAGE_LOCK:
            data = self._read_collections()
        colls: list[Collection] = []
        for coll_id, c in data.items():
            try:
                colls.append(Collection.from_dict(c))
            except Exception as exc:
                logger.warning("Skipped corrupt collection record %s: %s", coll_id, exc)  # fix #13
        return sorted(colls, key=lambda c: c.created_at)

    def update_collection(self, coll: Collection) -> None:
        coll.update_timestamp()
        self.save_collection(coll)

    def delete_collection(self, coll_id: str) -> bool:
        with _STORAGE_LOCK:
            data = self._read_collections()
            if coll_id not in data:
                return False
            del data[coll_id]
            self._write_collections(data)
        return True

    def add_video_to_collection(self, coll_id: str, video_id: str) -> bool:
        with _STORAGE_LOCK:
            data = self._read_collections()
            if coll_id not in data:
                return False
            ids = data[coll_id].setdefault("video_ids", [])
            if video_id not in ids:
                ids.append(video_id)
                from datetime import datetime
                data[coll_id]["updated_at"] = datetime.now().isoformat()
            self._write_collections(data)
        return True

    def remove_video_from_collection(self, coll_id: str, video_id: str) -> bool:
        with _STORAGE_LOCK:
            data = self._read_collections()
            if coll_id not in data:
                return False
            ids = data[coll_id].get("video_ids", [])
            if video_id not in ids:
                return False
            ids.remove(video_id)
            from datetime import datetime
            data[coll_id]["updated_at"] = datetime.now().isoformat()
            self._write_collections(data)
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
        """Case-insensitive search across title, channel, notes, tags, bullets, and auto_notes."""
        q = query.lower()
        results: list[Video] = []
        for v in self.get_all_videos():
            notes       = (v.manual_notes or "").lower()
            tags        = [t.lower() for t in (v.tags or [])]
            bullets     = " ".join(v.summary_bullets or []).lower()
            auto_notes  = " ".join(v.auto_notes or []).lower()
            if (
                q in v.title.lower()
                or q in v.channel.lower()
                or q in notes
                or any(q in t for t in tags)
                or q in (v.summary_paragraph or "").lower()
                or q in bullets
                or q in auto_notes
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
