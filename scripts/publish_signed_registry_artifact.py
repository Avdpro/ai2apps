#!/usr/bin/env python3
"""Submit, review, and publish an already signed AI2Apps registry artifact."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path

from ai2apps.cloud_client import (
    DEFAULT_AI2APPS_CLOUD_BASE_URL,
    AI2AppsCloudClient,
    CloudSessionStore,
    cloud_browser_cookie_name,
)
from ai2apps.config import PlatformConfig
from ai2apps.packages.registry import RegistryPackageManager
from ai2apps.secrets.factory import create_secret_backend


async def publish(
    *,
    base_path: Path,
    artifact_path: Path,
    envelope_path: Path,
    review_note: str,
    security_instance_id: str,
    browser_cookie_db: Path | None,
    list_only: bool,
    publishers_only: bool,
    submission_id: str | None,
) -> dict:
    config = PlatformConfig.from_base_path(base_path)
    assert config.paths is not None
    secret_backend = create_secret_backend(
        config.paths.secrets_path,
        configured=config.secret_backend,
        namespace=security_instance_id,
    )
    session_namespace = f"installation:{security_instance_id}"
    if browser_cookie_db is not None:
        cookie_name = cloud_browser_cookie_name(security_instance_id)
        connection = sqlite3.connect(
            f"file:{browser_cookie_db}?mode=ro&immutable=1",
            uri=True,
        )
        try:
            row = connection.execute(
                "SELECT value FROM moz_cookies WHERE name=? ORDER BY lastAccessed DESC LIMIT 1",
                (cookie_name,),
            ).fetchone()
        finally:
            connection.close()
        if row is None or not isinstance(row[0], str) or not row[0]:
            raise RuntimeError("AceFox Cloud browser session cookie is unavailable")
        session_namespace = f"browser:{row[0]}"
    cloud = AI2AppsCloudClient(
        base_url=DEFAULT_AI2APPS_CLOUD_BASE_URL,
        session_store=CloudSessionStore(
            secret_backend,
            DEFAULT_AI2APPS_CLOUD_BASE_URL,
            namespace=session_namespace,
        ),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=config.paths.packages_path,
        secrets=None,  # Not used when publishing a pre-signed envelope.
        extension_manager=None,
        service_manager=None,
    )
    try:
        if list_only:
            return {"submissions": await manager.submissions(limit=20)}
        if publishers_only:
            return {"publishers": await manager.publishers()}
        submitted = None
        requested = None
        if submission_id is None:
            envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
            submitted = await manager.submit(str(artifact_path), envelope)
            submission = submitted.get("submission", submitted)
            submission_id = submission.get("id")
            if not isinstance(submission_id, str) or not submission_id:
                raise RuntimeError("Cloud submission did not return a submission id")
            requested = await manager.request_review(submission_id)
        reviewed = await manager.review_submission(
            submission_id,
            "approved",
            review_note,
        )
        published = await manager.publish_submission(submission_id)
        return {
            "submission_id": submission_id,
            "submitted": submitted,
            "review_requested": requested,
            "reviewed": reviewed,
            "published": published,
        }
    finally:
        await cloud.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", type=Path, required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--envelope", type=Path)
    parser.add_argument("--security-instance-id", required=True)
    parser.add_argument("--browser-cookie-db", type=Path)
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--publishers-only", action="store_true")
    parser.add_argument(
        "--submission-id",
        help="Resume review/publication of an existing review-pending submission",
    )
    parser.add_argument(
        "--review-note",
        default="Verified signed and notarized production Runtime release.",
    )
    args = parser.parse_args()
    if not (args.list_only or args.publishers_only or args.submission_id) and (
        args.artifact is None or args.envelope is None
    ):
        parser.error(
            "--artifact and --envelope are required unless a query-only option is used"
        )
    result = asyncio.run(
        publish(
            base_path=args.base_path.expanduser().resolve(),
            artifact_path=(args.artifact or Path(".")).expanduser().resolve(),
            envelope_path=(args.envelope or Path(".")).expanduser().resolve(),
            review_note=args.review_note,
            security_instance_id=args.security_instance_id,
            browser_cookie_db=(
                None
                if args.browser_cookie_db is None
                else args.browser_cookie_db.expanduser().resolve()
            ),
            list_only=args.list_only,
            publishers_only=args.publishers_only,
            submission_id=args.submission_id,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
