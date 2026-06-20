"""Video data model for YouTube Learning Tracker."""

import dataclasses
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
    url:            