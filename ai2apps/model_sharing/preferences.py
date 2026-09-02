"""Durable Device- and model-level preferences for Compute sharing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ai2apps.core import utc_now_text
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase


def _canonical_uuid(value: str, field: str) -> str:
    try:
        parsed = UUID(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a UUID") from error
    if str(parsed) != value:
        raise ValueError(f"{field} must be canonical")
    return value


@dataclass(frozen=True, slots=True)
class ModelShareModelPreference:
    model_id: str
    service_key: str
    model_revision: str
    runtime: str
    enabled: bool
    rate_card_id: str
    rate_card_version: str
    max_concurrency: int
    estimated_tokens_per_second: int
    updated_at: str

    @classmethod
    def from_row(cls, row: Any) -> ModelShareModelPreference:
        return cls(
            model_id=row["model_id"],
            service_key=row["service_key"],
            model_revision=row["model_revision"],
            runtime=row["runtime"],
            enabled=bool(row["enabled"]),
            rate_card_id=row["rate_card_id"],
            rate_card_version=row["rate_card_version"],
            max_concurrency=int(row["max_concurrency"]),
            estimated_tokens_per_second=int(row["estimated_tokens_per_second"]),
            updated_at=row["updated_at"],
        )


class ModelSharePreferencesRepository:
    def __init__(self, database: PlatformDatabase, events: EventStore) -> None:
        self.database = database
        self.events = events

    def device_enabled(self) -> bool:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT enabled FROM model_share_device_preferences WHERE singleton=1"
            ).fetchone()
        return bool(row[0]) if row is not None else False

    def selected_count(self) -> int:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT count(*) FROM model_share_model_preferences WHERE enabled=1"
            ).fetchone()
        return int(row[0])

    def set_device_enabled(self, enabled: bool) -> bool:
        if enabled and self.selected_count() == 0:
            raise ValueError("Select at least one model before enabling Compute sharing")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO model_share_device_preferences(singleton,enabled,updated_at)
                   VALUES(1,?,?) ON CONFLICT(singleton) DO UPDATE SET
                   enabled=excluded.enabled,updated_at=excluded.updated_at""",
                (int(enabled), now),
            )
            self.events.append_in_transaction(
                connection,
                event_type="model_share.device.preference.changed",
                subject_id="device",
                payload={"enabled": enabled},
            )
        return enabled

    def models(self) -> tuple[ModelShareModelPreference, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM model_share_model_preferences ORDER BY service_key,model_id"
            ).fetchall()
        return tuple(ModelShareModelPreference.from_row(row) for row in rows)

    def model(self, model_id: str) -> ModelShareModelPreference | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM model_share_model_preferences WHERE model_id=?",
                (model_id,),
            ).fetchone()
        return None if row is None else ModelShareModelPreference.from_row(row)

    def save_model(
        self,
        *,
        model_id: str,
        service_key: str,
        model_revision: str,
        runtime: str,
        rate_card_id: str,
        rate_card_version: str,
        max_concurrency: int,
        estimated_tokens_per_second: int,
        enabled: bool | None = None,
    ) -> ModelShareModelPreference:
        _canonical_uuid(rate_card_id, "rateCardId")
        if not rate_card_version or len(rate_card_version) > 128:
            raise ValueError("rateCardVersion is invalid")
        if not 1 <= max_concurrency <= 32:
            raise ValueError("maxConcurrency must be between 1 and 32")
        if not 1 <= estimated_tokens_per_second <= 1_000_000:
            raise ValueError("estimatedTokensPerSecond is invalid")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            prior = connection.execute(
                "SELECT enabled FROM model_share_model_preferences WHERE model_id=?",
                (model_id,),
            ).fetchone()
            effective_enabled = bool(prior[0]) if enabled is None and prior is not None else bool(enabled)
            connection.execute(
                """INSERT INTO model_share_model_preferences(
                   model_id,service_key,model_revision,runtime,enabled,rate_card_id,
                   rate_card_version,max_concurrency,estimated_tokens_per_second,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(model_id) DO UPDATE SET
                   service_key=excluded.service_key,model_revision=excluded.model_revision,
                   runtime=excluded.runtime,enabled=excluded.enabled,
                   rate_card_id=excluded.rate_card_id,
                   rate_card_version=excluded.rate_card_version,
                   max_concurrency=excluded.max_concurrency,
                   estimated_tokens_per_second=excluded.estimated_tokens_per_second,
                   updated_at=excluded.updated_at""",
                (
                    model_id,
                    service_key,
                    model_revision,
                    runtime,
                    int(effective_enabled),
                    rate_card_id,
                    rate_card_version,
                    max_concurrency,
                    estimated_tokens_per_second,
                    now,
                ),
            )
            self.events.append_in_transaction(
                connection,
                event_type="model_share.model.preference.changed",
                subject_id=model_id,
                payload={
                    "service_key": service_key,
                    "enabled": effective_enabled,
                    "rate_card_version": rate_card_version,
                    "max_concurrency": max_concurrency,
                    "estimated_tokens_per_second": estimated_tokens_per_second,
                },
            )
            row = connection.execute(
                "SELECT * FROM model_share_model_preferences WHERE model_id=?",
                (model_id,),
            ).fetchone()
        return ModelShareModelPreference.from_row(row)

    def set_model_enabled(self, model_id: str, enabled: bool) -> ModelShareModelPreference:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM model_share_model_preferences WHERE model_id=?",
                (model_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Configure sharing preferences before enabling this model")
            connection.execute(
                "UPDATE model_share_model_preferences SET enabled=?,updated_at=? WHERE model_id=?",
                (int(enabled), now, model_id),
            )
            remaining = int(
                connection.execute(
                    "SELECT count(*) FROM model_share_model_preferences WHERE enabled=1"
                ).fetchone()[0]
            )
            if remaining == 0:
                connection.execute(
                    """INSERT INTO model_share_device_preferences(singleton,enabled,updated_at)
                       VALUES(1,0,?) ON CONFLICT(singleton) DO UPDATE SET
                       enabled=0,updated_at=excluded.updated_at""",
                    (now,),
                )
            self.events.append_in_transaction(
                connection,
                event_type="model_share.model.preference.changed",
                subject_id=model_id,
                payload={"enabled": enabled},
            )
            updated = connection.execute(
                "SELECT * FROM model_share_model_preferences WHERE model_id=?",
                (model_id,),
            ).fetchone()
        return ModelShareModelPreference.from_row(updated)
