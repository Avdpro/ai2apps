"""Stable lifecycle vocabularies shared by storage and future APIs."""

from enum import StrEnum


class AppInstanceMode(StrEnum):
    MULTIPLE = "multiple"
    SINGLETON = "singleton"


class SingletonScope(StrEnum):
    SYSTEM = "system"
    USER = "user"
    SESSION = "session"


class AppDefinitionStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class AppInstanceStatus(StrEnum):
    CREATING = "creating"
    ACTIVE = "active"
    BACKGROUND = "background"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    DEGRADED = "degraded"
    FAILED = "failed"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class SessionKind(StrEnum):
    APP = "app"
    CHAT_THREAD = "chat_thread"
    MINI_CHAT = "mini_chat"
    IN_APP_CHAT = "in_app_chat"
    AGENT_CHILD = "agent_child"


class SessionVisibility(StrEnum):
    LISTED = "listed"
    UNLISTED = "unlisted"


class SessionRetention(StrEnum):
    DURABLE = "durable"
    TEMPORARY = "temporary"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
    APP = "app"


class MessageStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
