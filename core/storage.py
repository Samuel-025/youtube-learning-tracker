"""Local JSON storage for YouTube Learning Tracker.

All data is stored in data/videos.json and data/collections.json on the local machine.
Both files are gitignored — they are never committed to GitHub.
"""

import json
import logging
import os
import threading
from datetime import datetime          # fix B13: moved to module-level
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
        # fix B3: snapshot the raw dict inside the lock so no concurrent write
        # can mutate it between read and Video.from_dict() parse.
        with _STORAGE_LOCK:
            data = self._read()
            raw = data.get(video_id)
        if raw is None:
            return None
        try:
            return Video.from_dict(raw)
        except Exception as exc:
            logger.warning("Skipped corrupt video record %s: %s", video_id, exc)
            return None

    def get_all_videos(self) -> list[Video]:
        # fix B3: snapshot raw items inside the lock, parse outside.
        with _STORAGE_LOCK:
            raw_items = list(self._read().items())
        videos: list[Video] = []
        for vid_id, v in raw_items:
            try:
                videos.append(Video.from_dict(v))
            except Exception as exc:
                logger.warning("Skipped corrupt video record %s: %s", vid_id, exc)
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
    #  E1 / E2 — Data Portability                                         #
    # ------------------------------------------------------------------ #

    def export_json(self) -> dict:
        """Return a single dict containing all videos and collections for export.

        Thread-safe: both files are snapshotted under a single lock acquisition.
        The returned dict has schema_version=1 so future import code can migrate.
        """
        with _STORAGE_LOCK:
            videos      = self._read()
            collections = self._read_collections()
        return {
            "schema_version": 1,
            "exported_at":    datetime.now().isoformat(),
            "videos":         videos,
            "collections":    collections,
        }

    def import_json(self, payload: dict, merge: bool = True) -> tuple[int, int]:
        """Import videos and collections from an export payload.

        merge=True  → skip existing IDs (safe top-up / second-machine sync).
        merge=False → full overwrite; replaces entire library with payload data.

        Returns (videos_imported, collections_imported) — counts of *new* records
        written.  In overwrite mode this equals the total payload size.
        """
        videos_in      = payload.get("videos", {})
        collections_in = payload.get("collections", {})

        with _STORAGE_LOCK:
            if merge:
                existing_v = self._read()
                existing_c = self._read_collections()
                new_v = {k: v for k, v in videos_in.items() if k not in existing_v}
                new_c = {k: v for k, v in collections_in.items() if k not in existing_c}
                existing_v.update(new_v)
                existing_c.update(new_c)
                self._write(existing_v)
                self._write_collections(existing_c)
            else:
                self._write(videos_in)
                self._write_collections(collections_in)
                new_v = videos_in
                new_c = collections_in

        return len(new_v), len(new_c)

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
            raw = data.get(coll_id)
        if raw is None:
            return None
        try:
            return Collection.from_dict(raw)
        except Exception as exc:
            logger.warning("Skipped corrupt collection record %s: %s", coll_id, exc)
            return None

    def get_all_collections(self) -> list[Collection]:
        with _STORAGE_LOCK:
            raw_items = list(self._read_collections().items())
        colls: list[Collection] = []
        for coll_id, c in raw_items:
            try:
                colls.append(Collection.from_dict(c))
            except Exception as exc:
                logger.warning("Skipped corrupt collection record %s: %s", coll_id, exc)
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
                data[coll_id]["updated_at"] = datetime.now().isoformat()  # fix B13
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
            data[coll_id]["updated_at"] = datetime.now().isoformat()  # fix B13
            self._write_collections(data)
        return True

    def get_videos_in_collection(self, coll_id: str) -> list[Video]:
        # fix B8: single get_all_videos() call instead of N+1 get_video() calls
        coll = self.get_collection(coll_id)
        if not coll:
            return []
        all_videos = {v.video_id: v for v in self.get_all_videos()}
        return [all_videos[vid_id] for vid_id in coll.video_ids if vid_id in all_videos]

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
