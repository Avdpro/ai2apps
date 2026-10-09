"""Portable continuation packets shared by the Host and portrait Workers.

Packets are private task intermediates, never Studio Output artifacts. A Host
must bind them to its frozen input/model digest and exact predecessor before
reusing them. Workers additionally validate the model-specific state tensor.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

SCHEMA = "ai2apps.avatar-segment/v1"
MAX_VIDEO_BYTES = 128 * 1024 * 1024
MAX_STATE_BYTES = 32 * 1024 * 1024
MAX_RECEIPT_BYTES = 16 * 1024
_HEX = re.compile(r"[0-9a-f]{64}")
_FIELDS = {
    "schema",
    "job_digest",
    "index",
    "start_frame",
    "end_frame",
    "fps",
    "previous_state",
    "state_sha256",
    "video_sha256",
}


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for data in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def job_digest(identity: dict) -> str:
    """Identity includes frozen inputs, parameters, Package and checkpoint pins."""
    data = json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def validate_receipt(value: dict) -> dict:
    if (
        not isinstance(value, dict)
        or set(value) != _FIELDS
        or value["schema"] != SCHEMA
    ):
        raise ValueError("Invalid avatar segment receipt")
    for field in ("job_digest", "state_sha256", "video_sha256"):
        if not isinstance(value[field], str) or not _HEX.fullmatch(value[field]):
            raise ValueError(f"Invalid segment {field}")
    for field in ("index", "start_frame", "end_frame", "fps"):
        if type(value[field]) is not int or value[field] < 0:
            raise ValueError(f"Invalid segment {field}")
    if not 1 <= value["fps"] <= 120 or value["end_frame"] <= value["start_frame"]:
        raise ValueError("Invalid segment frame interval")
    prior = value["previous_state"]
    if value["index"] == 0:
        if prior is not None or value["start_frame"] != 0:
            raise ValueError("First segment must begin at zero without a predecessor")
    elif not isinstance(prior, str) or not _HEX.fullmatch(prior):
        raise ValueError("Continuation segment requires a predecessor digest")
    return value


def write_packet(
    destination: Path,
    video: Path,
    state: Path,
    *,
    identity: str,
    index: int,
    start_frame: int,
    end_frame: int,
    fps: int,
    previous_state: str | None,
) -> dict:
    """Write one bounded, atomic ZIP_STORED packet without archive paths."""
    for path, limit in ((video, MAX_VIDEO_BYTES), (state, MAX_STATE_BYTES)):
        if (
            path.is_symlink()
            or not path.is_file()
            or not 0 < path.stat().st_size <= limit
        ):
            raise ValueError("Invalid or oversized avatar segment payload")
    receipt = validate_receipt(
        dict(
            schema=SCHEMA,
            job_digest=identity,
            index=index,
            start_frame=start_frame,
            end_frame=end_frame,
            fps=fps,
            previous_state=previous_state,
            state_sha256=file_digest(state),
            video_sha256=file_digest(video),
        )
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".partial")
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.write(video, "video.mp4")
            archive.write(state, "state.npy")
            archive.writestr("receipt.json", json.dumps(receipt, sort_keys=True))
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return receipt


def read_packet(
    packet: Path,
    *,
    identity: str,
    index: int,
    start_frame: int,
    end_frame: int,
    fps: int,
    previous_state: str | None,
    destination: Path | None = None,
) -> dict:
    """Validate the whole packet before atomically accepting a private segment.

    No extractall, supplied paths, symlinks, compressed payloads, duplicate names
    or unbounded archive reads. An invalid packet cannot replace prior output.
    destination, when supplied, must be a new task-owned directory.
    """
    limits = {
        "video.mp4": MAX_VIDEO_BYTES,
        "state.npy": MAX_STATE_BYTES,
        "receipt.json": MAX_RECEIPT_BYTES,
    }
    if packet.is_symlink() or packet.stat().st_size > sum(limits.values()) + 4096:
        raise ValueError("Oversized avatar segment packet")
    parent = destination.parent if destination is not None else packet.parent
    if destination is not None:
        parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            raise ValueError("Segment destination already exists")
    temporary = Path(tempfile.mkdtemp(dir=parent, prefix=".avatar-segment-"))
    try:
        with zipfile.ZipFile(packet) as archive:
            members = archive.infolist()
            if len(members) != 3 or {m.filename for m in members} != set(limits):
                raise ValueError("Unexpected or duplicate avatar packet members")
            for member in members:
                if (
                    member.compress_type != zipfile.ZIP_STORED
                    or member.flag_bits & 1
                    or not 0 < member.file_size <= limits[member.filename]
                    or member.file_size != member.compress_size
                ):
                    raise ValueError("Invalid avatar packet member")
                with (
                    archive.open(member) as source,
                    (temporary / member.filename).open("wb") as target,
                ):
                    remaining = member.file_size
                    while remaining:
                        data = source.read(min(1024 * 1024, remaining))
                        if not data:
                            raise ValueError("Truncated avatar packet member")
                        target.write(data)
                        remaining -= len(data)
                    if source.read(1):
                        raise ValueError("Oversized avatar packet member")
        receipt = validate_receipt(json.loads((temporary / "receipt.json").read_text()))
        expected = dict(
            job_digest=identity,
            index=index,
            start_frame=start_frame,
            end_frame=end_frame,
            fps=fps,
            previous_state=previous_state,
        )
        if any(receipt[k] != v for k, v in expected.items()):
            raise ValueError(
                "Avatar segment does not match the frozen job or predecessor"
            )
        if (
            file_digest(temporary / "video.mp4") != receipt["video_sha256"]
            or file_digest(temporary / "state.npy") != receipt["state_sha256"]
        ):
            raise ValueError("Avatar segment payload digest mismatch")
        if destination is not None:
            os.rename(temporary, destination)
        return receipt
    except (zipfile.BadZipFile, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid avatar segment packet") from exc
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
