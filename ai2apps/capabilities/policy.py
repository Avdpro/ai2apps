"""Fail-closed capability policy evaluation with an optional AI auditor."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from .models import CapabilityDecision, PolicyEffect
from .repository import CapabilityRepository
from .risk import sanitize_value

Auditor = Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]


class CapabilityPolicyEngine:
    def __init__(self, repository: CapabilityRepository) -> None:
        self.repository = repository
        self._auditor: Auditor | None = None

    def bind_ai_auditor(self, auditor: Auditor | None) -> None:
        """Bind an independent auditor; invalid/error results fail closed to approval."""
        self._auditor = auditor

    async def evaluate(
        self,
        *,
        run_id: str,
        agent_key: str,
        tool_name: str,
        capabilities: tuple[str, ...],
        effects: tuple[str, ...],
        arguments: dict[str, Any],
    ) -> CapabilityDecision:
        leases = self.repository.active_leases_for_run(run_id, tool_name, arguments)
        leased = {
            capability
            for lease in leases
            for capability in lease.capabilities
            if capability in capabilities
        }
        unresolved = tuple(sorted(set(capabilities) - leased))
        if not unresolved:
            return CapabilityDecision(
                PolicyEffect.ALLOW,
                "grant_lease",
                capabilities,
                tuple(sorted(leased)),
                matched_lease_ids=tuple(x.id for x in leases),
                evidence={"lease_count": len(leases)},
            )

        matched = []
        effects_by_capability: dict[str, PolicyEffect] = {}
        for capability in unresolved:
            policies = self.repository.matching_policies(
                agent_key=agent_key, tool_name=tool_name, capability=capability
            )
            if policies:
                top_priority = policies[0].priority
                top = tuple(p for p in policies if p.priority == top_priority)
                matched.extend(top)
                # A deny wins ties; otherwise explicit approval wins allow ties.
                values = {p.effect for p in top}
                effects_by_capability[capability] = (
                    PolicyEffect.DENY
                    if PolicyEffect.DENY in values
                    else PolicyEffect.REQUIRE_APPROVAL
                    if PolicyEffect.REQUIRE_APPROVAL in values
                    else PolicyEffect.ALLOW
                )
            else:
                effects_by_capability[capability] = PolicyEffect.REQUIRE_APPROVAL
        if PolicyEffect.DENY in effects_by_capability.values():
            effect = PolicyEffect.DENY
        elif PolicyEffect.REQUIRE_APPROVAL in effects_by_capability.values():
            effect = PolicyEffect.REQUIRE_APPROVAL
        else:
            effect = PolicyEffect.ALLOW
        evidence: dict[str, Any] = {
            "policy_effects": {
                key: value.value for key, value in effects_by_capability.items()
            }
        }
        source = "policy"

        if effect is PolicyEffect.REQUIRE_APPROVAL and self._auditor is not None:
            request = {
                "run_id": run_id,
                "agent_key": agent_key,
                "tool_name": tool_name,
                "capabilities": unresolved,
                "effects": effects,
                "arguments": sanitize_value(arguments),
            }
            try:
                result = self._auditor(request)
                if inspect.isawaitable(result):
                    result = await result
                auditor_effect = PolicyEffect(
                    result.get("decision", "require_approval")
                )
                # AI may narrow approval to deny or allow, never override explicit deny.
                effect = auditor_effect
                source = "ai_auditor"
                evidence["ai_auditor"] = {
                    "decision": auditor_effect.value,
                    "reason": str(result.get("reason", "")),
                    "evidence": result.get("evidence", {}),
                }
            except Exception as exc:
                evidence["ai_auditor"] = {
                    "decision": "require_approval",
                    "error": type(exc).__name__,
                }
                effect = PolicyEffect.REQUIRE_APPROVAL

        return CapabilityDecision(
            effect,
            source,
            capabilities,
            tuple(
                sorted(
                    leased
                    | (set(unresolved) if effect is PolicyEffect.ALLOW else set())
                )
            ),
            matched_policy_ids=tuple(dict.fromkeys(p.id for p in matched)),
            matched_lease_ids=tuple(x.id for x in leases),
            evidence=evidence,
        )
