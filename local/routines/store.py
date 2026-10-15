"""``{workspace}/routines/{id}.json``."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_CADENCE = ("daily_window", "weekly", "once")
_DEFAULT_TZ = "America/Martinique"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or _DEFAULT_TZ)
    except Exception:
        return ZoneInfo(_DEFAULT_TZ)


def initial_due(cadence: str, *, timezone_name: str, now: datetime | None = None) -> datetime:
    """Next local morning. Weekly lands on the coming Monday and does not backfill."""
    moment = now or _now()
    zone = _zone(timezone_name)
    local = moment.astimezone(zone)
    morning = local.replace(hour=9, minute=0, second=0, microsecond=0)
    if cadence == "daily_window":
        if morning <= local:
            morning = morning + timedelta(days=1)
        return morning.astimezone(timezone.utc)
    if cadence == "once":
        return moment
    # weekly: upcoming Monday 09:00, or next week if that hour has passed
    days = (0 - local.weekday()) % 7
    monday = morning + timedelta(days=days)
    if monday <= local:
        monday = monday + timedelta(days=7)
    return monday.astimezone(timezone.utc)


def advance_due(cadence: str, *, timezone_name: str, now: datetime | None = None) -> datetime | None:
    """One step forward from now. Missed weeks are not replayed."""
    if cadence == "once":
        return None
    moment = now or _now()
    if cadence == "daily_window":
        return initial_due("daily_window", timezone_name=timezone_name, now=moment)
    return (moment + timedelta(days=7)).astimezone(timezone.utc)


@dataclass
class Routine:
    id: str
    title: str
    instruction: str
    cadence: str = "weekly"
    timezone: str = _DEFAULT_TZ
    paused: bool = False
    owner_space: str = ""
    last_run_at: str | None = None
    next_due_at: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "instruction": self.instruction,
            "cadence": self.cadence,
            "timezone": self.timezone,
            "paused": self.paused,
            "owner_space": self.owner_space,
            "last_run_at": self.last_run_at,
            "next_due_at": self.next_due_at,
            "created_at": self.created_at,
        }


def routine_from_dict(data: dict) -> Routine:
    cadence = str(data.get("cadence") or "weekly")
    if cadence not in _CADENCE:
        cadence = "weekly"
    return Routine(
        id=str(data.get("id") or uuid.uuid4().hex[:12]),
        title=str(data.get("title") or "").strip() or "提醒",
        instruction=str(data.get("instruction") or "").strip(),
        cadence=cadence,
        timezone=str(data.get("timezone") or _DEFAULT_TZ),
        paused=bool(data.get("paused")),
        owner_space=str(data.get("owner_space") or ""),
        last_run_at=data.get("last_run_at") or None,
        next_due_at=data.get("next_due_at") or None,
        created_at=str(data.get("created_at") or ""),
    )


class RoutineStore:
    def __init__(self, workspace: Path | str):
        self.workspace = Path(workspace)
        self.folder = self.workspace / "routines"

    def path(self, routine_id: str) -> Path:
        return self.folder / f"{routine_id}.json"

    def load(self, routine_id: str) -> Routine | None:
        path = self.path(routine_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return routine_from_dict(data)

    def save(self, routine: Routine) -> Routine:
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.path(routine.id)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(routine.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return routine

    def list_routines(self) -> list[Routine]:
        if not self.folder.is_dir():
            return []
        found = []
        for path in sorted(self.folder.glob("*.json")):
            routine = self.load(path.stem)
            if routine is not None:
                found.append(routine)
        return found

    def create(
        self,
        *,
        title: str,
        instruction: str,
        cadence: str,
        owner_space: str,
        timezone_name: str = _DEFAULT_TZ,
        now: datetime | None = None,
    ) -> Routine:
        moment = now or _now()
        due = initial_due(cadence, timezone_name=timezone_name, now=moment)
        routine = Routine(
            id=uuid.uuid4().hex[:12],
            title=title.strip() or instruction[:24],
            instruction=instruction.strip(),
            cadence=cadence if cadence in _CADENCE else "weekly",
            timezone=timezone_name or _DEFAULT_TZ,
            paused=False,
            owner_space=owner_space,
            last_run_at=None,
            next_due_at=_iso(due) if cadence != "once" else _iso(moment),
            created_at=_iso(moment),
        )
        return self.save(routine)

    def pause(self, routine_id: str, paused: bool = True) -> Routine | None:
        routine = self.load(routine_id)
        if routine is None:
            return None
        routine.paused = paused
        return self.save(routine)

    def delete(self, routine_id: str) -> bool:
        path = self.path(routine_id)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def set_next_due(self, routine_id: str, when: datetime) -> Routine | None:
        routine = self.load(routine_id)
        if routine is None:
            return None
        routine.next_due_at = _iso(when)
        return self.save(routine)
