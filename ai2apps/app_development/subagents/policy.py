"""Pure admission and role policy; host handlers remain authoritative."""

from .contracts import ROLES, Request, SubagentError

MAX_CHILDREN = 4
MAX_ACTIVE = 2
ROOT_TOKENS = 100000
PARENT_RESERVE = 10000


def validate_request(request: Request, *, depth=0, child_count=0):
    if request.role not in ROLES:
        raise SubagentError("invalid_role", "Use an installed coding role.")
    if depth:
        raise SubagentError("recursive_delegation_denied", "Children cannot delegate.")
    if child_count >= MAX_CHILDREN:
        raise SubagentError("child_limit", "Root has reached four child attempts.")
    if not request.task.strip() or len(request.task) > 32768:
        raise SubagentError("invalid_task", "Task must contain 1–32768 characters.")
    if not request.request_key or len(request.request_key) > 128:
        raise SubagentError(
            "invalid_request_key", "A bounded idempotency key is required."
        )
    if (
        not 1 <= request.max_steps <= 24
        or not 1 <= request.max_model_tokens <= 20000
        or not 1 <= request.timeout_seconds <= 900
    ):
        raise SubagentError("invalid_budget", "Child budget exceeds installed limits.")


def tools_for(role):
    common = [
        "appdev.child.inspect",
        "appdev.child.list",
        "appdev.child.read",
        "appdev.child.search",
        "appdev.child.validate",
        "appdev.child.changes",
    ]
    if role in {"tester", "worker"}:
        common += ["appdev.child.command", "appdev.child.command_status"]
    if role == "worker":
        common += ["appdev.child.write", "appdev.child.edit"]
    return common


def stale(inspected, current):
    return inspected != current
