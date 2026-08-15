# SPDX-License-Identifier: Apache-2.0
"""Tests for opaque IDs, lifecycle vocabularies, and durable UTC timestamps."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from ai2apps.core import (
    AppInstanceStatus,
    EntityIdKind,
    format_utc,
    new_entity_id,
    parse_utc,
    utc_now_text,
    validate_entity_id,
)


@pytest.mark.parametrize("kind", list(EntityIdKind))
def test_entity_ids_have_exact_typed_prefix_and_uuid_payload(kind):
    values = {new_entity_id(kind) for _ in range(100)}

    assert len(values) == 100
    for value in values:
        assert value.startswith(kind.prefix)
        assert len(value) == len(kind.prefix) + 32
        assert value == value.lower()
        assert validate_entity_id(value, kind) == value


@pytest.mark.parametrize(
    ("value", "kind"),
    [
        ("ses_abc", EntityIdKind.SESSION),
        ("msg_00000000000000000000000000000000", EntityIdKind.SESSION),
        ("ses_0000000000000000000000000000000G", EntityIdKind.SESSION),
        ("SES_00000000000000000000000000000000", EntityIdKind.SESSION),
    ],
)
def test_entity_id_validation_rejects_wrong_shape(value, kind):
    with pytest.raises(ValueError):
        validate_entity_id(value, kind)


def test_utc_format_is_canonical_and_microsecond_precise():
    value = datetime(
        2026,
        8,
        11,
        12,
        34,
        56,
        123,
        tzinfo=timezone(timedelta(hours=8)),
    )

    encoded = format_utc(value)

    assert encoded == "2026-08-11T04:34:56.000123Z"
    assert parse_utc(encoded) == value.astimezone(UTC)
    assert len(utc_now_text()) == 27


def test_utc_helpers_reject_naive_or_invalid_values():
    with pytest.raises(ValueError, match="timezone-aware"):
        format_utc(datetime(2026, 8, 11))
    with pytest.raises(ValueError, match="include a timezone"):
        parse_utc("2026-08-11T12:00:00.000000")
    with pytest.raises(ValueError, match="Invalid RFC 3339"):
        parse_utc("not-a-time")


def test_lifecycle_values_are_stable_strings():
    assert AppInstanceStatus.ACTIVE == "active"
    assert AppInstanceStatus.SUSPENDED.value == "suspended"
