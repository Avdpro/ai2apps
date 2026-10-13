"""Pure planning for the proposed Linux managed Runtime descriptor.

This internal draft is not registered as an installable Registry protocol. The
caller must verify the outer Package signature before trusting this input. No
network, pip, environment mutation or activation occurs here. Wheel METADATA,
ABI and installed-file validation remain materializer responsibilities.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from urllib.parse import urlsplit

from packaging.tags import cpython_tags, compatible_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version, InvalidVersion

SCHEMA = "ai2apps.runtime-install-plan/v2-draft"
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\Z")


class DescriptorError(ValueError):
    pass


def _keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise DescriptorError(f"{label}: unexpected or missing fields")


def _ids(value, label):
    if not isinstance(value, list) or any(
        not isinstance(v, str) or not _ID.fullmatch(v) for v in value
    ) or len(set(value)) != len(value):
        raise DescriptorError(f"{label}: expected unique identifiers")
    return tuple(value)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


@dataclass(frozen=True)
class InstallPlan:
    descriptor_digest: str
    environment_digest: str
    base_digest: str
    artifacts: tuple[str, ...]
    profiles: tuple[str, ...]
    download_bytes: int


def plan_install(document: dict, profiles: list[str], *, target: dict,
                 verified_cache: frozenset[str] = frozenset()) -> InstallPlan:
    """Validate all declarations; select only base + requested profile closure.

    verified_cache contains SHA256s already fully verified by the downloader,
    never filenames or unverified on-disk cache existence checks.
    """
    _keys(document, ("schema", "target", "artifacts", "base", "profiles"), "descriptor")
    if document["schema"] != SCHEMA:
        raise DescriptorError("unsupported descriptor schema")
    _keys(document["target"], ("platform", "python_abi", "glibc_min", "cuda", "layout"), "target")
    declared = document["target"]
    if any(not isinstance(v, str) or not v.strip() for v in declared.values()):
        raise DescriptorError("invalid target values")
    if declared["platform"] != "linux-aarch64" or declared["layout"] != "1":
        raise DescriptorError("unsupported target/layout")
    if target != declared:
        raise DescriptorError("target mismatch")
    artifacts = document["artifacts"]
    if not isinstance(artifacts, dict) or not artifacts or len(artifacts) > 4096:
        raise DescriptorError("invalid artifact inventory")
    for key, artifact in artifacts.items():
        if not isinstance(key, str) or not _ID.fullmatch(key):
            raise DescriptorError("invalid artifact id")
        _keys(artifact, ("name", "version", "filename", "sha256", "bytes", "sources", "requires"), key)
        if not isinstance(artifact["sha256"], str) or not _SHA.fullmatch(artifact["sha256"]):
            raise DescriptorError(f"{key}: invalid SHA256")
        if type(artifact["bytes"]) is not int or not 0 < artifact["bytes"] <= 16 * 1024**3:
            raise DescriptorError(f"{key}: invalid size")
        filename = artifact["filename"]
        if not isinstance(filename, str) or "/" in filename or "\\" in filename:
            raise DescriptorError(f"{key}: invalid wheel filename")
        try:
            name, version, _, tags = parse_wheel_filename(filename)
            expected_version = Version(artifact["version"])
        except (ValueError, TypeError, InvalidVersion) as exc:
            raise DescriptorError(f"{key}: invalid wheel/version") from exc
        if not isinstance(artifact["name"], str) or name != canonicalize_name(artifact["name"]) or version != expected_version:
            raise DescriptorError(f"{key}: wheel identity mismatch")
        abi_match = re.fullmatch(r'cp(3)([0-9]+)', declared['python_abi'])
        if not abi_match:
            raise DescriptorError('unsupported Python ABI')
        python_version = tuple(map(int, abi_match.groups()))
        platforms = sorted({t.platform for t in tags if t.platform == 'any'
                            or t.platform == 'linux_aarch64'
                            or re.fullmatch(r'manylinux(?:[0-9]+|_[0-9]+_[0-9]+)_aarch64', t.platform)})
        supported = set(cpython_tags(python_version=python_version, abis=[declared['python_abi']], platforms=platforms))
        supported.update(compatible_tags(python_version=python_version, interpreter=declared['python_abi'], platforms=platforms))
        if not platforms or not (tags & supported):
            raise DescriptorError(f'{key}: wheel architecture/Python ABI mismatch')
        sources = artifact["sources"]
        if not isinstance(sources, list) or not sources or len(sources) > 8:
            raise DescriptorError(f"{key}: missing/bounded sources")
        for source in sources:
            if not isinstance(source, str) or any(c.isspace() for c in source):
                raise DescriptorError(f"{key}: invalid source")
            try:
                url = urlsplit(source)
                valid = url.scheme == "https" and url.hostname and not url.username and not url.password and not url.query and not url.fragment and url.port in (None, 443)
            except ValueError:
                valid = False
            if not valid:
                raise DescriptorError(f"{key}: expected credential-free fixed HTTPS source")
        # DNS/redirect/SSRF validation must still be done at fetch time.
        for dependency in _ids(artifact["requires"], key):
            if dependency not in artifacts:
                raise DescriptorError(f"{key}: missing dependency {dependency}")
    base = _ids(document["base"], "base")
    profile_map = document["profiles"]
    if not isinstance(profile_map, dict) or len(profile_map) > 256:
        raise DescriptorError("invalid profiles")
    _ids(list(profile_map), "profile ids")
    for key, roots in profile_map.items():
        _ids(roots, key)
    selected = _ids(profiles, "selected profiles")
    if set(selected) - set(profile_map):
        raise DescriptorError("unknown selected profile")
    roots = list(base)
    for values in profile_map.values():
        if set(values) - set(artifacts):
            raise DescriptorError("unknown profile artifact")
    if not base or set(base) - set(artifacts):
        raise DescriptorError("invalid base artifacts")

    def closure(start):
        pending = list(start)
        found = set()
        identities = {}
        while pending:
            key = pending.pop()
            if key in found:
                continue
            found.add(key)
            artifact = artifacts[key]
            name = canonicalize_name(artifact["name"])
            if name in identities and identities[name] != key:
                raise DescriptorError(f"conflicting distributions: {name}")
            identities[name] = key
            pending.extend(artifact["requires"])
        return sorted(found)

    base_ids = closure(base)
    for profile in selected:
        roots.extend(profile_map[profile])
    result = closure(roots)
    if any(not isinstance(v, str) or not _SHA.fullmatch(v) for v in verified_cache):
        raise DescriptorError("invalid verified cache digest")
    def identity(ids):
        return _digest({"target": declared, "artifacts": {k: artifacts[k] for k in ids}})
    sizes = {}
    for key in result:
        artifact = artifacts[key]
        sha = artifact["sha256"]
        if sha in sizes and sizes[sha] != artifact["bytes"]:
            raise DescriptorError("same digest with conflicting sizes")
        sizes[sha] = artifact["bytes"]
    return InstallPlan(_digest(document), identity(result), identity(base_ids),
                       tuple(result), tuple(sorted(selected)),
                       sum(size for sha, size in sizes.items() if sha not in verified_cache))
