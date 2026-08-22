#!/usr/bin/env python3
"""Install one catalogued AI2Apps model and stream conversion progress."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_id")
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument(
        "--memory-tier",
        choices=("auto", "lean", "compact", "optimal"),
        default="auto",
    )
    parser.add_argument("--source", default="huggingface")
    parser.add_argument(
        "--storage-policy",
        choices=("keep_source", "delete_after", "stream_reclaim"),
        default=None,
        help=(
            "keep the source checkpoint, delete it after conversion, or "
            "reclaim source shards progressively while converting"
        ),
    )
    parser.add_argument(
        "--token-env",
        default="HF_TOKEN",
        help="environment variable containing an optional Hugging Face token",
    )
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    from ai2apps.model_installer import AI2AppsInstaller, InstallStatus
    from omlx.admin.hf_downloader import HFDownloader

    root = args.model_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    installer = AI2AppsInstaller(HFDownloader(str(root)))
    task = await installer.start(
        args.model_id,
        args.source,
        args.memory_tier,
        os.environ.get(args.token_env, ""),
        args.storage_policy,
    )
    last = None
    while task.status not in {
        InstallStatus.COMPLETED,
        InstallStatus.FAILED,
        InstallStatus.CANCELLED,
    }:
        snapshot = (
            task.status.value,
            task.phase,
            round(task.progress, 1),
            task.detail,
        )
        if snapshot != last:
            print(json.dumps(task.to_dict(), ensure_ascii=False), flush=True)
            last = snapshot
        await asyncio.sleep(args.poll_seconds)
    print(json.dumps(task.to_dict(), ensure_ascii=False), flush=True)
    if task.status is not InstallStatus.COMPLETED:
        raise SystemExit(task.error or task.status.value)


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
