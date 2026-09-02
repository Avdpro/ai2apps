"""Privacy-preserving Model Share execution ledger."""

from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass

from ai2apps.core import utc_now_text
from ai2apps.storage import PlatformDatabase


@dataclass(frozen=True, slots=True)
class ModelShareJobRecord:
    contract_id: str
    session_id: str
    owner_user_id: str
    role: str
    status: str
    request_digest: str
    result_digest: str | None
    input_tokens: int | None
    output_tokens: int | None
    calculator_type: str | None
    maximum_charge_minor: str | None
    actual_usage: dict | None
    charged_minor: str | None
    released_minor: str | None


class ModelShareRepository:
    """Stores identifiers, digests, usage, and state; never prompt/output content."""

    def __init__(self, database: PlatformDatabase) -> None:
        self.database = database

    @staticmethod
    def _record(row: sqlite3.Row) -> ModelShareJobRecord:
        return ModelShareJobRecord(
            contract_id=row["contract_id"], session_id=row["session_id"],
            owner_user_id=row["owner_user_id"], role=row["role"], status=row["status"],
            request_digest=row["request_digest"], result_digest=row["result_digest"],
            input_tokens=row["input_tokens"], output_tokens=row["output_tokens"],
            calculator_type=row["calculator_type"],
            maximum_charge_minor=row["maximum_charge_minor"],
            actual_usage=(json.loads(row["actual_usage_json"])
                          if row["actual_usage_json"] else None),
            charged_minor=row["charged_minor"],
            released_minor=row["released_minor"],
        )

    def begin(self, *, contract_id: str, session_id: str, owner_user_id: str,
              role: str, request_digest: str, calculator_type: str | None = None,
              maximum_charge_minor: str | None = None) -> tuple[ModelShareJobRecord, bool]:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute("SELECT * FROM model_share_jobs WHERE contract_id=?", (contract_id,)).fetchone()
            created = row is None
            if row is None:
                connection.execute(
                    """
                    INSERT INTO model_share_jobs(
                        contract_id,session_id,owner_user_id,role,status,request_digest,
                        result_digest,input_tokens,output_tokens,created_at,updated_at
                    ) VALUES (?,?,?,?,? ,?,NULL,NULL,NULL,?,?)
                    """,
                    (contract_id, session_id, owner_user_id, role, "accepted", request_digest, now, now),
                )
                if calculator_type is not None:
                    connection.execute(
                        "UPDATE model_share_jobs SET calculator_type=?,maximum_charge_minor=? WHERE contract_id=?",
                        (calculator_type, maximum_charge_minor, contract_id),
                    )
                row = connection.execute("SELECT * FROM model_share_jobs WHERE contract_id=?", (contract_id,)).fetchone()
            elif any((row["session_id"] != session_id, row["owner_user_id"] != owner_user_id, row["role"] != role, row["request_digest"] != request_digest)):
                raise ValueError("Model Share Contract is already bound to another job")
        assert row is not None
        return self._record(row), created

    def set_status(self, contract_id: str, status: str, *, result_digest: str | None = None,
                   input_tokens: int | None = None, output_tokens: int | None = None,
                   actual_usage: dict | None = None, charged_minor: str | None = None,
                   released_minor: str | None = None) -> None:
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                UPDATE model_share_jobs SET status=?,result_digest=COALESCE(?,result_digest),
                    input_tokens=COALESCE(?,input_tokens),output_tokens=COALESCE(?,output_tokens),
                    actual_usage_json=COALESCE(?,actual_usage_json),
                    charged_minor=COALESCE(?,charged_minor),released_minor=COALESCE(?,released_minor),updated_at=?
                WHERE contract_id=?
                """,
                (status, result_digest, input_tokens, output_tokens,
                 json.dumps(actual_usage, separators=(",", ":"), sort_keys=True) if actual_usage is not None else None,
                 charged_minor, released_minor, utc_now_text(), contract_id),
            )

    def get(self, contract_id: str) -> ModelShareJobRecord | None:
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM model_share_jobs WHERE contract_id=?", (contract_id,)).fetchone()
        return None if row is None else self._record(row)

    def recent(self, owner_user_id: str, *, limit: int = 12) -> tuple[ModelShareJobRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM model_share_jobs WHERE owner_user_id=? ORDER BY updated_at DESC LIMIT ?",
                (owner_user_id, limit),
            ).fetchall()
        return tuple(self._record(row) for row in rows)
