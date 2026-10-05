"""Bounded Session-local glob and content search without following symlinks."""

import fnmatch
import os
import stat
import time
from functools import cache
from pathlib import PurePosixPath

import regex

from .models import WorkspaceError

MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 10_000
MAX_FILES = 2_000
MAX_SECONDS = 3.0


def match_glob(path, pattern):
    if "/" not in pattern:
        return fnmatch.fnmatchcase(PurePosixPath(path).name, pattern)
    parts, patterns = path.split("/"), pattern.split("/")

    @cache
    def match(i, j):
        if j == len(patterns):
            return i == len(parts)
        if patterns[j] == "**":
            return match(i, j + 1) or (i < len(parts) and match(i + 1, j))
        return (
            i < len(parts)
            and fnmatch.fnmatchcase(parts[i], patterns[j])
            and match(i + 1, j + 1)
        )

    return match(0, 0)


def _open(base, relative, flags):
    """Open each path component under the workspace without symlink traversal."""
    fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parts = PurePosixPath(relative).parts
        for i, part in enumerate(parts):
            following = os.open(
                part,
                (flags if i == len(parts) - 1 else os.O_RDONLY | os.O_DIRECTORY)
                | os.O_NOFOLLOW,
                dir_fd=fd,
            )
            os.close(fd)
            fd = following
        return fd
    except BaseException:
        os.close(fd)
        raise


def scan(
    base,
    target,
    *,
    query=None,
    pattern="*",
    mode="literal",
    case_sensitive=False,
    context_lines=0,
    include_hidden=False,
    limit=100,
):
    if not 1 <= limit <= 1000 or not 0 <= context_lines <= 5:
        raise WorkspaceError("invalid_search", "Invalid result or context limit")
    if (
        not pattern
        or len(pattern) > 256
        or pattern.startswith("/")
        or len(pattern.split("/")) > 64
        or ".." in PurePosixPath(pattern).parts
        or "\x00" in pattern
    ):
        raise WorkspaceError(
            "invalid_pattern", "Use a relative glob pattern of at most 256 characters"
        )
    if mode not in {"literal", "regex"} or (
        query is not None and (not query or len(query) > 4096)
    ):
        raise WorkspaceError(
            "invalid_query", "Use a non-empty query of at most 4096 characters"
        )
    compiled = None
    if query is not None and mode == "regex":
        try:
            compiled = regex.compile(query, 0 if case_sensitive else regex.IGNORECASE)
        except regex.error as error:
            raise WorkspaceError("invalid_regex", str(error)) from error
    started = time.monotonic()
    matches, reasons = [], set()
    files = entries = total_bytes = skipped = 0
    target_relative = target.relative_to(base).as_posix()
    stack = [target_relative]
    candidates = []
    if target.is_file():
        candidates.append(target_relative)
        stack.clear()

    def expired():
        if time.monotonic() - started > MAX_SECONDS:
            reasons.add("time_limit")
            return True
        return False

    while (stack or candidates) and not expired():
        if not candidates:
            directory = stack.pop()
            try:
                fd = _open(base, directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    with os.scandir(fd) as listing:
                        for entry in listing:
                            entries += 1
                            if entries > MAX_ENTRIES or expired():
                                reasons.add(
                                    "entry_limit"
                                    if entries > MAX_ENTRIES
                                    else "time_limit"
                                )
                                break
                            if entry.is_symlink() or (
                                entry.name.startswith(".") and not include_hidden
                            ):
                                continue
                            relative = (
                                PurePosixPath(directory) / entry.name
                            ).as_posix()
                            if entry.is_dir(follow_symlinks=False):
                                if len(PurePosixPath(relative).parts) < 64:
                                    stack.append(relative)
                                else:
                                    reasons.add("depth_limit")
                            elif entry.is_file(follow_symlinks=False):
                                candidates.append(relative)
                finally:
                    os.close(fd)
            except OSError:
                reasons.add("unreadable_path")
            if "entry_limit" in reasons or "time_limit" in reasons:
                break
            continue
        relative = candidates.pop()
        if not include_hidden and any(
            p.startswith(".") for p in PurePosixPath(relative).parts
        ):
            continue
        if not match_glob(relative, pattern):
            continue
        files += 1
        if files > MAX_FILES:
            reasons.add("file_limit")
            break
        if query is None:
            matches.append({"path": relative})
        else:
            try:
                fd = _open(base, relative, os.O_RDONLY | os.O_NONBLOCK)
                with os.fdopen(fd, "rb") as source:
                    if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                        skipped += 1
                        continue
                    raw = source.read(
                        min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total_bytes) + 1
                    )
                total_bytes += len(raw)
                if total_bytes > MAX_TOTAL_BYTES:
                    reasons.add("byte_limit")
                    break
                if len(raw) > MAX_FILE_BYTES:
                    skipped += 1
                    reasons.add("large_file_skipped")
                    continue
                if b"\x00" in raw:
                    skipped += 1
                    continue
                lines = raw.decode("utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                skipped += 1
                reasons.add("unreadable_or_non_utf8")
                continue
            for i, line in enumerate(lines):
                if expired():
                    break
                try:
                    hit = (
                        bool(compiled.search(line, timeout=0.02))
                        if compiled
                        else (
                            query in line
                            if case_sensitive
                            else query.casefold() in line.casefold()
                        )
                    )
                except TimeoutError:
                    reasons.add("regex_timeout")
                    break
                if hit:
                    item = {
                        "path": relative,
                        "line": i + 1,
                        "text": line[:500],
                        "text_truncated": len(line) > 500,
                    }
                    if context_lines:
                        item["context"] = [
                            {"line": j + 1, "text": lines[j][:500]}
                            for j in range(
                                max(0, i - context_lines),
                                min(len(lines), i + context_lines + 1),
                            )
                        ]
                    matches.append(item)
                    if len(matches) > limit:
                        break
            if "regex_timeout" in reasons or "time_limit" in reasons:
                break
        if len(matches) > limit:
            reasons.add("result_limit")
            break
    return {
        "matches": sorted(matches[:limit], key=lambda m: (m["path"], m.get("line", 0))),
        "truncated": bool(reasons),
        "incomplete_reasons": sorted(reasons),
        "scanned_files": min(files, MAX_FILES),
        "scanned_bytes": total_bytes,
        "skipped_files": skipped,
    }
