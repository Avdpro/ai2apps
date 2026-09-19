#!/usr/bin/env python3
"""Submit, review, and publish an already signed AI2Apps registry artifact."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path
from urllib.parse import quote

from ai2apps.cloud_client import (
    DEFAULT_AI2APPS_CLOUD_BASE_URL,
    AI2AppsCloudClient,
    CloudSessionStore,
    cloud_browser_cookie_name,
)
from ai2apps.config import PlatformConfig
from ai2apps.packages.registry import RegistryPackageManager
from ai2apps.secrets.factory import create_secret_backend
if __package__:
    from .registry_browser_session import live_browser_session_namespace
else:
    from registry_browser_session import live_browser_session_namespace


def browser_session_namespace(
    browser_cookie_db: Path, security_instance_id: str
) -> str:
    cookie_name = cloud_browser_cookie_name(security_instance_id)
    # Firefox can leave the newest session cookie in the WAL even after a
    # clean Shell shutdown.  immutable=1 ignores that WAL and can silently
    # reuse an older, non-step-up session.  Read the exact authorized profile
    # database in SQLite's normal read-only mode so its WAL is included
    # without copying or modifying the browser profile.
    connection = sqlite3.connect(
        f"{browser_cookie_db.as_uri()}?mode=ro",
        uri=True,
        timeout=30.0,
    )
    try:
        row = connection.execute(
            "SELECT value FROM moz_cookies WHERE name=? "
            "ORDER BY lastAccessed DESC LIMIT 1",
            (cookie_name,),
        ).fetchone()
    finally:
        connection.close()
    if row is None or not isinstance(row[0], str) or not row[0]:
        raise RuntimeError("AceFox Cloud browser session cookie is unavailable")
    return f"browser:{row[0]}"


def source_collection_path(package_id: str, version: str) -> str:
    if package_id.count("/") != 1:
        raise ValueError("Source operations require a namespace/name package id")
    namespace, name = package_id.split("/", 1)
    if not namespace or not name or not version:
        raise ValueError("Source operations require package namespace/name and version")
    return (
        "/v1/admin/registry/packages/"
        f"{quote(namespace, safe='')}/{quote(name, safe='')}/versions/"
        f"{quote(version, safe='')}/sources"
    )


async def source_response(
    cloud: AI2AppsCloudClient,
    method: str,
    path: str,
    *,
    body: dict | None = None,
    etag: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    headers = {}
    if etag is not None:
        headers["If-Match"] = etag
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    response = await cloud.request(method, path, json=body, headers=headers)
    try:
        try:
            value = response.json()
        except ValueError:
            value = {}
        if response.status_code >= 400:
            error = value.get("error", {}) if isinstance(value, dict) else {}
            raise RuntimeError(
                str(error.get("code") or f"source_request_failed_{response.status_code}")
                + ": "
                + str(error.get("message") or "Package source request failed")
            )
        return {"result": value, "etag": response.headers.get("etag")}
    finally:
        await response.aclose()


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
    sources_package_id: str | None,
    sources_version: str | None,
    source_action: str | None,
    source_kind: str | None,
    source_url: str | None,
    source_label: str | None,
    source_id: str | None,
    source_validation_id: str | None,
    source_validation_digest: str | None,
    source_etag: str | None,
    source_idempotency_key: str | None,
    reject_submission: bool,
    browser_live: bool = False,
) -> dict:
    config = PlatformConfig.from_base_path(base_path)
    assert config.paths is not None
    secret_backend = create_secret_backend(
        config.paths.secrets_path,
        configured=config.secret_backend,
        namespace=security_instance_id,
    )
    session_namespace = f"installation:{security_instance_id}"
    if browser_live and browser_cookie_db is not None:
        raise ValueError("Choose live browser or explicit offline cookie database, not both")
    if browser_live:
        session_namespace = await live_browser_session_namespace(base_path, security_instance_id)
    elif browser_cookie_db is not None:
        session_namespace = browser_session_namespace(
            browser_cookie_db, security_instance_id
        )
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
        if sources_package_id is not None:
            path = source_collection_path(sources_package_id, sources_version or "")
            if source_action in {None, "list"}:
                return await source_response(cloud, "GET", path)
            if source_action == "status":
                return await source_response(
                    cloud, "GET", f"{path}/{quote(source_id or '', safe='')}"
                )
            if source_action == "register":
                body = {"kind": source_kind, "url": source_url}
                if source_label:
                    body["label"] = source_label
                return await source_response(
                    cloud,
                    "POST",
                    path,
                    body=body,
                    etag=source_etag,
                    idempotency_key=source_idempotency_key,
                )
            if source_action == "validate":
                return await source_response(
                    cloud,
                    "POST",
                    f"{path}/{quote(source_id or '', safe='')}/validate",
                    idempotency_key=source_idempotency_key,
                )
            if source_action == "activate":
                return await source_response(
                    cloud,
                    "POST",
                    f"{path}/{quote(source_id or '', safe='')}/activate",
                    body={
                        "validationId": source_validation_id,
                        "validationDigest": source_validation_digest,
                    },
                    etag=source_etag,
                    idempotency_key=source_idempotency_key,
                )
            raise ValueError(f"Unsupported source action: {source_action}")
        if reject_submission:
            if submission_id is None:
                raise ValueError("--reject-submission requires --submission-id")
            reviewed = await manager.review_submission(
                submission_id,
                "rejected",
                review_note,
            )
            return {"submission_id": submission_id, "reviewed": reviewed}
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
    browser_auth = parser.add_mutually_exclusive_group()
    browser_auth.add_argument("--browser-cookie-db", type=Path, help="Explicit offline SQLite fallback")
    browser_auth.add_argument("--browser-live", action="store_true", help="Read the scoped session via authenticated live Shell BiDi (requires explicit Cookie authorization)")
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--publishers-only", action="store_true")
    parser.add_argument("--sources-package-id")
    parser.add_argument("--sources-version")
    parser.add_argument(
        "--source-action",
        choices=("list", "register", "status", "validate", "activate"),
    )
    parser.add_argument("--source-kind", choices=("github", "modelscope", "other"))
    parser.add_argument("--source-url")
    parser.add_argument("--source-label")
    parser.add_argument("--source-id")
    parser.add_argument("--source-validation-id")
    parser.add_argument("--source-validation-digest")
    parser.add_argument("--source-etag")
    parser.add_argument("--source-idempotency-key")
    parser.add_argument(
        "--submission-id",
        help="Resume review/publication of an existing review-pending submission",
    )
    parser.add_argument(
        "--reject-submission",
        action="store_true",
        help="Reject an existing immutable submission instead of publishing it",
    )
    parser.add_argument(
        "--review-note",
        default="Verified signed and notarized production Runtime release.",
    )
    args = parser.parse_args()
    if bool(args.sources_package_id) != bool(args.sources_version):
        parser.error("--sources-package-id and --sources-version must be used together")
    if args.source_action and not args.sources_package_id:
        parser.error("--source-action requires --sources-package-id and --sources-version")
    if args.source_action == "register" and not all(
        (args.source_kind, args.source_url, args.source_etag, args.source_idempotency_key)
    ):
        parser.error("source register requires kind, URL, ETag, and idempotency key")
    if args.source_action == "status" and not args.source_id:
        parser.error("source status requires --source-id")
    if args.source_action == "validate" and not all(
        (args.source_id, args.source_idempotency_key)
    ):
        parser.error("source validate requires --source-id and idempotency key")
    if args.source_action == "activate" and not all(
        (
            args.source_id,
            args.source_validation_id,
            args.source_validation_digest,
            args.source_etag,
            args.source_idempotency_key,
        )
    ):
        parser.error(
            "source activate requires source/validation IDs, digest, ETag, and idempotency key"
        )
    if not (
        args.list_only
        or args.publishers_only
        or args.submission_id
        or args.sources_package_id
    ) and (
        args.artifact is None or args.envelope is None
    ):
        parser.error(
            "--artifact and --envelope are required unless a query-only option is used"
        )
    if args.reject_submission and not args.submission_id:
        parser.error("--reject-submission requires --submission-id")
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
            sources_package_id=args.sources_package_id,
            sources_version=args.sources_version,
            source_action=args.source_action,
            source_kind=args.source_kind,
            source_url=args.source_url,
            source_label=args.source_label,
            source_id=args.source_id,
            source_validation_id=args.source_validation_id,
            source_validation_digest=args.source_validation_digest,
            source_etag=args.source_etag,
            source_idempotency_key=args.source_idempotency_key,
            reject_submission=args.reject_submission,
            browser_live=args.browser_live,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
