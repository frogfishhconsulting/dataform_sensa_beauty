from __future__ import annotations

import enum


class RunStatus(str, enum.Enum):
    queued = "queued"
    collecting = "collecting"
    analyzing = "analyzing"
    drafting = "drafting"
    awaiting_approval = "awaiting_approval"
    pushing = "pushing"
    complete = "complete"
    failed = "failed"


class Platform(str, enum.Enum):
    reddit = "reddit"
    x = "x"
    youtube = "youtube"


class ClusterType(str, enum.Enum):
    pain_point = "pain_point"
    highlight = "highlight"


class PushStatus(str, enum.Enum):
    dry_run_ok = "dry_run_ok"
    pushed = "pushed"
    failed = "failed"

