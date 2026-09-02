#!/usr/bin/env python3
"""Operate the Cloud checkpoint-distribution publication state machine."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from ai2apps.checkpoint_publishing import verification_receipt_for_envelope
from ai2apps.cloud_client import (
    DEFAULT_AI2APPS_CLOUD_BASE_URL,
    AI2AppsCloudClient,
    CloudSessionStore,
    cloud_browser_cookie_name,
)
from ai2apps.config import PlatformConfig
from ai2apps.packages.registry import RegistryPackageManager
from ai2apps.secrets.factory import create_secret_backend


def _browser_session_namespace(cookie_db: Path, security_instance_id: str) -> str:
    connection = sqlite3.connect(f"file:{cookie_db}?mode=ro&immutable=1", uri=True)
    try:
        row = connection.execute(
            "SELECT value FROM moz_cookies WHERE name=? ORDER BY lastAccessed DESC LIMIT 1",
            (cloud_browser_cookie_name(security_instance_id),),
        ).fetchone()
    finally:
        connection.close()
    if row is None or not isinstance(row[0], str) or not row[0]:
        raise RuntimeError("AceFox Cloud browser session cookie is unavailable")
    return f"browser:{row[0]}"


async def operate(args: argparse.Namespace) -> dict[str, Any]:
    config = PlatformConfig.from_base_path(args.base_path)
    assert config.paths is not None
    backend = create_secret_backend(
        config.paths.secrets_path,
        configured=config.secret_backend,
        namespace=args.security_instance_id,
    )
    namespace = f"installation:{args.security_instance_id}"
    if args.browser_cookie_db is not None:
        namespace = _browser_session_namespace(
            args.browser_cookie_db, args.security_instance_id
        )
    cloud = AI2AppsCloudClient(
        base_url=args.cloud_base_url,
        session_store=CloudSessionStore(
            backend, args.cloud_base_url, namespace=namespace
        ),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=config.paths.packages_path,
        secrets=None,
        extension_manager=None,
        service_manager=None,
    )
    results: dict[str, Any] = {}
    try:
        if args.list_publisher:
            results["publisherSubmissions"] = await manager.publisher_checkpoint_submissions(
                status=args.status, limit=args.limit
            )
        if args.list_review:
            results["reviewQueue"] = await manager.review_checkpoint_submissions(
                status=args.status, limit=args.limit
            )
        submission_id = args.submission_id
        if args.envelope is not None:
            envelope = json.loads(args.envelope.read_text(encoding="utf-8"))
            if args.verification_receipt is None:
                receipt = verification_receipt_for_envelope(envelope)
            else:
                receipt = json.loads(
                    args.verification_receipt.read_text(encoding="utf-8")
                )
                if not isinstance(receipt, dict) or not isinstance(
                    receipt.get("builder"), str
                ):
                    raise RuntimeError("verification receipt is invalid")
                expected = verification_receipt_for_envelope(
                    envelope, builder=receipt["builder"]
                )
                if receipt != expected:
                    raise RuntimeError("verification receipt does not match envelope")
            submitted = await manager.submit_checkpoint_distribution(envelope, receipt)
            results["submitted"] = submitted
            if not isinstance(submitted, dict) or not isinstance(submitted.get("id"), str):
                raise RuntimeError("Cloud submission did not return a submission id")
            submission_id = submitted["id"]
        if args.show:
            if submission_id is None:
                raise RuntimeError("--show requires --submission-id or --envelope")
            results["submission"] = await manager.checkpoint_submission(submission_id)
        if args.request_review:
            if submission_id is None:
                raise RuntimeError("--request-review requires --submission-id or --envelope")
            results["reviewRequested"] = await manager.request_checkpoint_review(
                submission_id
            )
        if args.decision is not None:
            if submission_id is None or args.note is None:
                raise RuntimeError("--decision requires a submission and --note")
            results["reviewed"] = await manager.review_checkpoint_submission(
                submission_id, args.decision, args.note
            )
        if args.publish:
            if submission_id is None:
                raise RuntimeError("--publish requires --submission-id or --envelope")
            results["published"] = await manager.publish_checkpoint_submission(
                submission_id
            )
        if args.distribution_id is not None:
            if args.status_action is None or args.reason is None:
                raise RuntimeError(
                    "--distribution-id requires --status-action and --reason"
                )
            results["statusChanged"] = (
                await manager.change_checkpoint_distribution_status(
                    args.distribution_id, args.status_action, args.reason
                )
            )
        return results
    finally:
        await cloud.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", type=Path, required=True)
    parser.add_argument("--security-instance-id", required=True)
    parser.add_argument("--cloud-base-url", default=DEFAULT_AI2APPS_CLOUD_BASE_URL)
    parser.add_argument("--browser-cookie-db", type=Path)
    parser.add_argument("--envelope", type=Path)
    parser.add_argument("--verification-receipt", type=Path)
    parser.add_argument("--submission-id")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--request-review", action="store_true")
    parser.add_argument("--decision", choices=("approved", "rejected"))
    parser.add_argument("--note")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--list-publisher", action="store_true")
    parser.add_argument("--list-review", action="store_true")
    parser.add_argument("--status")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--distribution-id")
    parser.add_argument("--status-action", choices=("yank", "revoke"))
    parser.add_argument("--reason")
    args = parser.parse_args()
    args.base_path = args.base_path.expanduser().resolve()
    if args.envelope is not None:
        args.envelope = args.envelope.expanduser().resolve()
    if args.verification_receipt is not None:
        args.verification_receipt = args.verification_receipt.expanduser().resolve()
    if args.browser_cookie_db is not None:
        args.browser_cookie_db = args.browser_cookie_db.expanduser().resolve()
    if not any(
        (
            args.envelope,
            args.show,
            args.request_review,
            args.decision,
            args.publish,
            args.list_publisher,
            args.list_review,
            args.distribution_id,
        )
    ):
        parser.error("select at least one checkpoint operation")
    print(json.dumps(asyncio.run(operate(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
