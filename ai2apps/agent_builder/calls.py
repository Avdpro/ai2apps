"""Resolve owned Web Agent capabilities to immutable, bounded call frames."""

from copy import deepcopy
import re
from typing import Any
from urllib.parse import quote

from ai2apps.core import ResourceConflictError


def bind_values(value: Any, inputs: dict, outputs: dict | None = None, variables: dict | None = None) -> Any:
    """Preserve file/array types for whole-value parameter and result bindings."""
    def lookup(expression):
        parts = expression.split(".")
        current = {"input": inputs, "steps": outputs or {}, "vars": variables or {}}
        for part in parts:
            if isinstance(current, list) and part.isdigit() and int(part) < len(current):
                current = current[int(part)]
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                raise ValueError(f"Unresolved Agent binding: {expression}")
        return deepcopy(current)

    if isinstance(value, dict):
        return {key: (re.sub(r"\$\{((?:input|steps|vars)\.[a-zA-Z0-9_.-]+)\}",
            lambda match: quote(str(lookup(match[1])), safe=""), item)
            if key == "url" and isinstance(item, str) and not re.fullmatch(r"\$\{[^}]+\}", item)
            else bind_values(item, inputs, outputs, variables)) for key, item in value.items()}
    if isinstance(value, list):
        return [bind_values(item, inputs, outputs, variables) for item in value]
    if not isinstance(value, str):
        return value
    pattern = r"\$\{((?:input|steps|vars)\.[a-zA-Z0-9_.-]+)\}"
    match = re.fullmatch(pattern, value)
    if match:
        return lookup(match[1])
    return re.sub(pattern, lambda match: str(lookup(match[1])), value)


def resolve_calls(store, owner: str, ir: dict, *, ancestry=(), budget=None) -> dict:
    """Snapshot only active, actor-owned capabilities; never trust caller-supplied IR."""
    from .service import active_generation, capability_ir

    budget = [100] if budget is None else budget
    if len(ancestry) > 4:
        raise ResourceConflictError("Agent call depth exceeds 4")
    result = deepcopy(ir)
    for step in result.get("steps", []):
        budget[0] -= 1
        if budget[0] < 0:
            raise ResourceConflictError("Agent call graph exceeds 100 steps")
        if step.get("operation") != "agent.call":
            continue
        args = step["arguments"]
        identity = (args["agent_id"], args["capability"])
        if identity in ancestry:
            raise ResourceConflictError("Recursive Agent call cycle")
        from .foundations import PREFIX, GENERATION, foundation_ir
        if identity[0].startswith(PREFIX):
            try:
                child = foundation_ir(identity[0], identity[1], args.get("generation_id", GENERATION))
            except ValueError as error:
                raise ResourceConflictError(str(error)) from error
            resolved = resolve_calls(store, owner, child, ancestry=(*ancestry, identity), budget=budget)
            step["call"] = {"agent_id":identity[0], "generation_id":args.get("generation_id", GENERATION),
                "capability":identity[1], "ir":resolved}
            step["effect"] = "interact" if "interact" in resolved.get("effects", []) else "read"
            continue
        from .login import LOGIN_AGENT_PREFIX, LOGIN_GENERATION, login_ir
        if identity[0].startswith(LOGIN_AGENT_PREFIX):
            if identity[1] != "site.ensure-login" or args.get("generation_id", LOGIN_GENERATION) != LOGIN_GENERATION:
                raise ResourceConflictError("Unknown system login capability or generation")
            try:
                child = login_ir(identity[0])
            except ValueError as error:
                raise ResourceConflictError(str(error)) from error
            budget[0] -= len(child["steps"])
            if budget[0] < 0:
                raise ResourceConflictError("Agent call graph exceeds 100 steps")
            step["call"] = {"agent_id": identity[0], "generation_id": LOGIN_GENERATION,
                "capability": identity[1], "ir": child}
            continue
        draft = store.get_draft(identity[0], owner)
        if draft.agent_type.value != "web":
            raise ResourceConflictError("Web Steps can only call Web Agent capabilities")
        generation = active_generation(store, draft)
        if args.get("generation_id") and args["generation_id"] != generation.id:
            raise ResourceConflictError("Called Agent generation changed; review the call again")
        child = capability_ir(generation.ir, identity[1])
        # Legacy sources also require an actual exported capability name.
        if not generation.ir.get("capabilities") and identity[1] not in {
            item.get("name") for item in generation.ir.get("capability_exports", [])
        } and not (
            not generation.ir.get("capability_exports")
            and identity[1] == f"agent.{draft.id}.run"
        ):
            raise ResourceConflictError("Called Agent capability is not exported")
        resolved = resolve_calls(store, owner, child, ancestry=(*ancestry, identity), budget=budget)
        step["call"] = {
            "agent_id": draft.id, "generation_id": generation.id,
            "capability": identity[1], "ir": resolved,
        }
        step["effect"] = "destructive" if "destructive" in resolved.get("effects", []) else "interact"
    result["effects"] = sorted({step.get("effect", "read") for step in result.get("steps", [])})
    return result


def namespace_ir(ir: dict, prefix: str) -> dict:
    result = deepcopy(ir)
    mapping = {step["id"]: prefix + "/" + step["id"] for step in result["steps"]}
    result["start"] = mapping[result["start"]]
    for step in result["steps"]:
        original = step["id"]
        step["local_id"] = original
        step["id"] = mapping[original]
        step["on"] = {key: mapping.get(target, target) for key, target in step.get("on", {}).items()}
        if step.get("arguments", {}).get("from_step") in mapping:
            step["arguments"]["from_step"] = mapping[step["arguments"]["from_step"]]
    return result
