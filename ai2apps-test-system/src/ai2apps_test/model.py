from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PRIORITIES = ("P0", "P1", "P2", "P3")
TERMINAL_STATUSES = {"passed", "failed", "blocked", "skipped"}


@dataclass(frozen=True)
class Component:
    id: str
    kind: str
    name: str
    group: str
    release_status: str = "shipping"
    source: str = ""
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Case:
    id: str
    name: str
    priority: str | None
    group: str
    executor: str
    component_id: str | None = None
    command: tuple[str, ...] = ()
    timeout_seconds: int = 300
    requires: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    description: str = ""
    required: bool = True
    group_id: str | None = None
    enabled: bool = True
    lifecycle: str = "enabled"
    source_type: str = "built-in"
    source_path: str = ""
    editable: bool = False
    instructions: tuple[str, ...] = ()
    expectations: tuple[str, ...] = ()
    cleanup: tuple[str, ...] = ()
    fixtures: tuple[str, ...] = ()
    revision: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["command"] = list(self.command)
        data["requires"] = list(self.requires)
        data["tags"] = list(self.tags)
        data["instructions"] = list(self.instructions)
        data["expectations"] = list(self.expectations)
        data["cleanup"] = list(self.cleanup)
        data["fixtures"] = list(self.fixtures)
        data["groupId"] = self.group_id
        data["componentId"] = self.component_id
        data["timeoutSeconds"] = self.timeout_seconds
        data["sourceType"] = self.source_type
        data["sourcePath"] = self.source_path
        return data


@dataclass(frozen=True)
class TestGroup:
    id: str
    name: str
    description: str = ""
    kind: str = "regular"
    enabled: bool = True
    default_selected: bool = False
    order: int = 500
    tags: tuple[str, ...] = ()
    lifecycle: str = "enabled"
    source_type: str = "built-in"
    source_path: str = ""
    editable: bool = False
    revision: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["tags"] = list(self.tags)
        data["defaultSelected"] = self.default_selected
        data["sourceType"] = self.source_type
        data["sourcePath"] = self.source_path
        return data


def priority_includes(selected: str, case_priority: str | None) -> bool:
    if case_priority is None:
        return False
    return PRIORITIES.index(case_priority) <= PRIORITIES.index(selected)
