import calendar

import regex
from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def validate_emoji(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if (len(value) > 32 or not regex.fullmatch(r"\X", value)
            or not regex.search(r"\p{Extended_Pictographic}|\p{Regional_Indicator}|\u20e3", value)):
        raise ValueError("Enter a single Emoji symbol")
    return value


def emoji_key(value: str) -> str:
    return value.replace("\ufe0f", "").replace("\ufe0e", "")


def extract_ai_emoji(text: str, excluded: list[str]) -> str:
    """Tolerate prose while preserving complete Unicode emoji graphemes."""
    if not isinstance(text, str):
        return ""
    excluded_keys = {emoji_key(value) for value in excluded}
    for cluster in regex.finditer(r"\X", text):
        try:
            emoji = validate_emoji(cluster.group())
        except ValueError:
            continue
        if emoji and emoji_key(emoji) not in excluded_keys:
            return emoji
    return ""


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    auto_execute: bool = True
    frequency: Literal["off", "once", "hourly", "daily", "weekly", "monthly"] = Field(default="off",description="off means no repeating or timed schedule; a caller may still launch once immediately. once means one future execution at once_at, never an unspecified immediate run.")
    hour: int = Field(default=9, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    weekday: int = Field(default=0, ge=0, le=6)
    day: int = Field(default=1, ge=1, le=31)
    timezone: str = "Asia/Shanghai"
    once_at: str = Field(default="",max_length=80)

    @model_validator(mode="after")
    def valid_once(self):
        if self.frequency == "once":
            try:stamp=datetime.fromisoformat(self.once_at.replace("Z","+00:00"))
            except ValueError as exc:raise ValueError("A scheduled-once task needs an ISO timestamp") from exc
            if stamp.tzinfo is None:raise ValueError("Scheduled-once time needs an explicit timezone offset")
            self.once_at=stamp.astimezone(UTC).isoformat()
        elif self.once_at:
            raise ValueError("once_at is only supported for scheduled-once tasks")
        return self

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as error:
            raise ValueError("Unknown time zone") from error
        return value


def resolve_schedule(
    changes: dict, *, reference: datetime, timezone: str = "UTC", previous: dict | None = None,
) -> Schedule:
    """Resolve a reviewed schedule patch using the request instant and prior plan."""
    patch = dict(changes)
    delay = patch.pop("delay_minutes", None)
    values = {**(previous or {"timezone": timezone}), **patch}
    if delay is not None:
        if type(delay) is not int or not 1 <= delay <= 525600:
            raise ValueError("delay_minutes must be an integer from 1 to 525600")
        if patch.get("frequency", "once") != "once" or patch.get("once_at"):
            raise ValueError("Choose either a relative delay or an explicit schedule")
        if reference.utcoffset() is None:
            raise ValueError("Relative scheduling requires an aware request time")
        values.update(frequency="once", once_at=(reference + timedelta(minutes=delay)).isoformat())
    elif "frequency" in patch and patch["frequency"] != "once" and "once_at" not in patch:
        values["once_at"] = ""
    return Schedule.model_validate(values)


def upcoming_schedule_time(schedule: dict) -> str | None:
    due = next_due(schedule, datetime.now(UTC))
    return due.isoformat() if due else None


class CodexBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(default="", max_length=300)
    project_name: str = Field(default="", max_length=500)
    project_path: str = Field(default="", max_length=4096)
    host_id: str = Field(default="local", max_length=300)
    thread_id: str = Field(default="", max_length=300, pattern=r"^[A-Za-z0-9_-]*$")
    thread_title: str = Field(default="", max_length=500)
    inherit_project: bool = True


class CodexUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    at: str = Field(max_length=100)
    summary: str = Field(min_length=1, max_length=8000)


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codex: CodexBinding = Field(default_factory=CodexBinding)
    codex_updates: list[CodexUpdate] = Field(default_factory=list, max_length=30)
    title: str = Field(min_length=1, max_length=500)
    directory_id: str
    parent_id: str | None = None
    description: str = Field(default="", max_length=100000)
    priority: Literal["U", "S", "A", "B", "C", "D"] = "C"
    highlight: Literal["", "lime", "yellow", "peach", "pink", "blue", "lavender"] = ""
    emoji: str = Field(default="", max_length=32)

    _valid_emoji = field_validator("emoji")(validate_emoji)

    status: Literal["not_started", "in_progress", "awaiting_acceptance", "completed", "paused"] = "not_started"
    progress: int = Field(default=0, ge=0, le=100, strict=True)
    completed: bool = False
    executor: Literal["internal", "managed", "codex", "claude", "codex_desktop"] = "internal"
    model: str = Field(default="", max_length=300)
    working_directory: str = Field(default="", max_length=4096)
    schedule: Schedule = Field(default_factory=Schedule)
    position: int = 0


def next_due(schedule: dict, after: datetime) -> datetime | None:
    """Next wall-clock slot, strictly after the supplied UTC instant.

    Month days beyond the month length clamp to its last day. DST gaps skip;
    folds run once using the first occurrence.
    """
    s = Schedule.model_validate(schedule)
    if s.frequency == "off":
        return None
    if s.frequency == "once":
        stamp=datetime.fromisoformat(s.once_at)
        return stamp if stamp>after else None
    zone = ZoneInfo(s.timezone)
    local = after.astimezone(zone)
    if s.frequency == "hourly":
        base = local.replace(minute=s.minute, second=0, microsecond=0)
        for i in range(4):
            candidate = (base + timedelta(hours=i)).replace(fold=0)
            utc = candidate.astimezone(UTC)
            if utc > after and utc.astimezone(zone).replace(
                tzinfo=None
            ) == candidate.replace(tzinfo=None):
                return utc
    else:
        for offset in range(370):
            date = local.date() + timedelta(days=offset)
            if s.frequency == "weekly" and date.weekday() != s.weekday:
                continue
            if s.frequency == "monthly" and date.day != min(
                s.day, calendar.monthrange(date.year, date.month)[1]
            ):
                continue
            candidate = datetime(
                date.year, date.month, date.day, s.hour, s.minute, tzinfo=zone
            )
            utc = candidate.astimezone(UTC)
            if utc > after and utc.astimezone(zone).replace(
                tzinfo=None
            ) == candidate.replace(tzinfo=None):
                return utc
    raise ValueError("Cannot calculate next schedule time")


def latest_due(schedule: dict, now: datetime) -> datetime:
    s = Schedule.model_validate(schedule)
    if s.frequency == "once":return datetime.fromisoformat(s.once_at)
    lookback = {"hourly": 2, "daily": 49, "weekly": 24 * 8, "monthly": 24 * 63}[
        s.frequency
    ]
    cursor = now - timedelta(hours=lookback)
    latest = cursor
    while (slot := next_due(schedule, cursor)) is not None and slot <= now:
        latest = cursor = slot
    return latest


def normalize_task_state(data, old=None):
    """Keep the completion checkbox, explicit status and percentage consistent."""
    previous = old or {"status": "not_started", "progress": 0, "completed": False}
    if data["status"] != previous["status"]:
        if data["status"] == "completed":
            data["progress"] = 100
        elif data["status"] == "not_started":
            data["progress"] = 0
        elif data["progress"] == 100 and data["status"] != "awaiting_acceptance":
            data["progress"] = 0
    elif data["progress"] != previous["progress"]:
        if data["progress"] == 100 and data["status"] != "awaiting_acceptance":
            data["status"] = "completed"
        elif data["status"] == "completed" or (data["progress"] > 0 and data["status"] == "not_started"):
            data["status"] = "in_progress"
    elif data["completed"] != previous["completed"]:
        data["status"] = "completed" if data["completed"] else "not_started"
        data["progress"] = 100 if data["completed"] else 0
    data["completed"] = data["status"] == "completed"
    return data
