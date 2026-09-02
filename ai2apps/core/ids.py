"""Opaque, prefixed identifiers for durable AI2Apps entities."""

from __future__ import annotations

from enum import StrEnum
from uuid import uuid4


class EntityIdKind(StrEnum):
    APP_DEFINITION = "app"
    APP_INSTANCE = "appi"
    SESSION = "ses"
    MESSAGE = "msg"
    MESSAGE_PART = "part"
    EVENT = "evt"
    SERVICE = "svc"
    SERVICE_INSTANCE = "svci"
    TOOL = "tool"
    TOOL_INVOCATION = "tinv"
    AGENT_DEFINITION = "agt"
    AGENT_RUN = "run"
    AGENT_DELEGATION = "dlg"
    RUN_STEP = "step"
    INTERACTION = "int"
    STATUS_LINE = "stl"
    CAPABILITY_POLICY = "pol"
    GRANT_LEASE = "grant"
    CAPABILITY_DECISION = "capd"
    CAPABILITY_REQUEST = "capr"
    SESSION_SANDBOX = "sbx"
    RESOURCE_HANDLE = "res"
    ARTIFACT = "art"
    ARTIFACT_EXPORT = "exp"
    PROCESS_EXECUTION = "proc"
    PROCESS_LOG = "plog"
    BROKER_REQUEST = "brq"
    SERVICE_PACKAGE = "spkg"
    PUBLISHER = "pub"
    PACKAGE_ATTESTATION = "att"
    SERVICE_OPERATION = "sop"
    WORKER_OPERATION = "wop"
    SERVICE_LOG = "slog"
    MANAGED_SERVICE_PROCESS = "msp"
    INTERACTIVE_PACKAGE = "ipkg"
    LOCAL_PATCH = "patch"
    EFFECTIVE_DEFINITION = "eff"
    APP_MOUNT = "mnt"
    APP_STATE_SNAPSHOT = "snap"
    INTERACTIVE_OPERATION = "iop"
    CODER_PROJECT = "cprj"
    CODER_THREAD = "cthr"
    ATTACHMENT = "attc"
    DOCUMENT_BLOB = "dbl"
    DOCUMENT_BLOCK = "dblk"
    SECRET = "sec"
    AGENT_DRAFT = "adraft"
    AGENT_GENERATION = "agen"
    AGENT_EVIDENCE = "aev"
    AGENT_WORKFLOW = "awf"
    AGENT_SCHEDULE = "asch"
    AGENT_SCHEDULE_DISPATCH = "asdp"
    AGENT_RECIPE = "arec"
    AGENT_PACKAGE_BINDING = "apb"
    AGENT_PACKAGE_EVENT = "apev"
    AGENT_HEALTH = "ahl"
    AGENT_SITE_STATE = "ast"
    AGENT_REPAIR = "arep"
    AGENT_APP_DEPENDENCY = "aadep"

    @property
    def prefix(self) -> str:
        return f"{self.value}_"


def new_entity_id(kind: EntityIdKind) -> str:
    """Create a lowercase opaque UUID4 identifier with a typed prefix."""

    return f"{kind.prefix}{uuid4().hex}"


def validate_entity_id(value: str, kind: EntityIdKind) -> str:
    """Validate the exact prefix and UUID payload used by platform IDs."""

    prefix = kind.prefix
    payload = value.removeprefix(prefix)
    if not value.startswith(prefix) or len(payload) != 32:
        raise ValueError(f"Expected {kind.value} identifier")
    try:
        int(payload, 16)
    except ValueError as exc:
        raise ValueError(f"Expected {kind.value} identifier") from exc
    if value != value.lower():
        raise ValueError(f"Expected lowercase {kind.value} identifier")
    return value
