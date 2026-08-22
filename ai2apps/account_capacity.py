"""Shared Local fallback contract for account and installation capacity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapacityLimits:
    max_core_devices: int
    max_members_per_device: int

    def __post_init__(self) -> None:
        if self.max_core_devices < 0 or self.max_members_per_device < 0:
            raise ValueError("Capacity limits cannot be negative")

    def to_api(self) -> dict[str, int]:
        return {
            "maxCoreDevices": self.max_core_devices,
            "maxMembersPerDevice": self.max_members_per_device,
        }


BASE_LEVEL_LIMITS: dict[str, CapacityLimits] = {
    "unverified": CapacityLimits(0, 0),
    "member": CapacityLimits(1, 2),
    "creator": CapacityLimits(1, 5),
    "trusted_creator": CapacityLimits(3, 10),
    "core_contributor": CapacityLimits(10, 20),
}

SUBSCRIPTION_PLAN_LIMITS: dict[str, CapacityLimits] = {
    "none": CapacityLimits(0, 0),
    "subscriber": CapacityLimits(5, 5),
    "team": CapacityLimits(20, 50),
}


def effective_capacity_limits(
    level_id: str,
    subscription_plan: str | None = None,
) -> CapacityLimits:
    """Return the field-wise maximum of reputation and paid-plan limits."""

    level = BASE_LEVEL_LIMITS.get(level_id, CapacityLimits(0, 0))
    plan = SUBSCRIPTION_PLAN_LIMITS.get(
        subscription_plan or "none",
        SUBSCRIPTION_PLAN_LIMITS["none"],
    )
    return CapacityLimits(
        max(level.max_core_devices, plan.max_core_devices),
        max(level.max_members_per_device, plan.max_members_per_device),
    )


def capacity_policy_payload() -> dict[str, object]:
    """Expose the compatibility policy used until Cloud returns live limits."""

    return {
        "policyVersion": "account-capacity-v1",
        "baseLevels": {
            key: value.to_api() for key, value in BASE_LEVEL_LIMITS.items()
        },
        "subscriptionPlans": {
            key: value.to_api() for key, value in SUBSCRIPTION_PLAN_LIMITS.items()
        },
        "rules": {
            "effectiveLimit": "field_wise_max",
            "coreExcludedFromMemberCount": True,
            "pendingInvitationReservesSeat": True,
            "admissionOnly": True,
            "retroactiveRevocation": False,
        },
    }
