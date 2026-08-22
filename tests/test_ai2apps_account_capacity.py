"""Account level and paid-plan capacity policy tests."""

from ai2apps.account_capacity import (
    BASE_LEVEL_LIMITS,
    SUBSCRIPTION_PLAN_LIMITS,
    capacity_policy_payload,
    effective_capacity_limits,
)


def test_base_account_level_limits_match_product_policy():
    assert {
        key: (value.max_core_devices, value.max_members_per_device)
        for key, value in BASE_LEVEL_LIMITS.items()
    } == {
        "unverified": (0, 0),
        "member": (1, 2),
        "creator": (1, 5),
        "trusted_creator": (3, 10),
        "core_contributor": (10, 20),
    }


def test_paid_plan_limits_match_product_policy():
    assert {
        key: (value.max_core_devices, value.max_members_per_device)
        for key, value in SUBSCRIPTION_PLAN_LIMITS.items()
    } == {
        "none": (0, 0),
        "subscriber": (5, 5),
        "team": (20, 50),
    }


def test_effective_limits_take_field_wise_max_without_downgrading_reputation():
    registered_subscriber = effective_capacity_limits("member", "subscriber")
    trusted_subscriber = effective_capacity_limits(
        "trusted_creator", "subscriber"
    )
    contributor_team = effective_capacity_limits("core_contributor", "team")

    assert registered_subscriber.to_api() == {
        "maxCoreDevices": 5,
        "maxMembersPerDevice": 5,
    }
    assert trusted_subscriber.to_api() == {
        "maxCoreDevices": 5,
        "maxMembersPerDevice": 10,
    }
    assert contributor_team.to_api() == {
        "maxCoreDevices": 20,
        "maxMembersPerDevice": 50,
    }


def test_capacity_policy_is_admission_only_and_pending_invites_reserve_seats():
    rules = capacity_policy_payload()["rules"]

    assert rules == {
        "effectiveLimit": "field_wise_max",
        "coreExcludedFromMemberCount": True,
        "pendingInvitationReservesSeat": True,
        "admissionOnly": True,
        "retroactiveRevocation": False,
    }
