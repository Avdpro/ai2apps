"""Read public GitHub Skill folders from a pinned Git tree."""

import hashlib
import json
import re
from urllib.parse import quote, unquote, urlsplit

import httpx

from .library import MAX_BYTES, MAX_FILES, skill_path

GITHUB_API = "https://api.github.com"
GITHUB_RAW = "https://raw.githubusercontent.com"


def parse_github_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com" or parsed.query or parsed.fragment:
        raise ValueError("Enter an HTTPS GitHub repository or folder link")
    parts = skill_path(unquote(parsed.path.strip("/"))).split("/")
    if len(parts) < 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts[:2]):
        raise ValueError("Enter a GitHub owner and repository")
    repo = parts[1].removesuffix(".git")
    if not repo or repo in {".", ".."}:
        raise ValueError("Invalid GitHub repository")
    rest = parts[2:]
    if rest and (rest[0] != "tree" or len(rest) < 2):
        raise ValueError("Use a repository link or a link to a folder on GitHub")
    return f"{parts[0]}/{repo}".lower(), rest[1:]


class GitHubSkills:
    def __init__(self, client):
        self.client = client

    def get(self, path, limit=MAX_BYTES, allow_missing=False):
        body = self.read(GITHUB_API + path, limit, allow_missing)
        return None if body is None else json.loads(body)

    def read(self, url, limit, allow_missing=False):
        with self.client.stream("GET", url) as response:
            if allow_missing and response.status_code in {404, 422}:
                return None
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > limit:
                    raise ValueError("GitHub response exceeds the import limit")
        return bytes(body)

    def resolve(self, url):
        repo, parts = parse_github_url(url)
        if not parts:
            metadata = self.get(f"/repos/{repo}")
            ref = metadata["default_branch"]
            result = self.get(f"/repos/{repo}/commits/{quote(ref, safe='')}")
            return repo, ref, "", result["sha"]
        for split in range(len(parts), 0, -1):
            ref = "/".join(parts[:split])
            result = self.get(f"/repos/{repo}/commits/{quote(ref, safe='')}", allow_missing=True)
            if result:
                return repo, ref, "/".join(parts[split:]), result["sha"]
        raise LookupError("GitHub reference was not found")

    def tree(self, repo, commit):
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Invalid GitHub commit")
        result = self.get(f"/repos/{repo}/git/trees/{commit}?recursive=1")
        if result.get("truncated"):
            raise ValueError("GitHub repository tree exceeds the import limit")
        return result["tree"]

    def discover(self, url):
        repo, ref, directory, commit = self.resolve(url)
        directories = [
            item["path"].removesuffix("/SKILL.md") if item["path"] != "SKILL.md" else ""
            for item in self.tree(repo, commit)
            if (item["path"] == "SKILL.md" or item["path"].endswith("/SKILL.md"))
            and item.get("mode") in {"100644", "100755"}
        ]
        if directory:
            directories = [path for path in directories if path == directory or path.startswith(directory + "/")]
        return {"repo": repo, "ref": ref, "commit": commit, "folders": sorted(directories)[:100]}

    def snapshot(self, url, folder, ref, commit):
        repo, resolved_ref, directory, resolved_commit = self.resolve(url)
        if (ref, commit) != (resolved_ref, resolved_commit):
            raise ValueError("GitHub reference changed. Find the Skill folders again")
        if folder:
            skill_path(folder)
        if directory and folder != directory and not folder.startswith(directory + "/"):
            raise ValueError("Select a Skill within the linked GitHub directory")
        prefix = folder + "/" if folder else ""
        entries = [
            item for item in self.tree(repo, commit)
            if item["path"].startswith(prefix) and item.get("type") != "tree"
        ]
        if not 1 <= len(entries) <= MAX_FILES or sum(item.get("size", 0) for item in entries) > MAX_BYTES:
            raise ValueError("Skill exceeds the file count or size limit")
        if not any(item["path"] == prefix + "SKILL.md" for item in entries):
            raise LookupError("SKILL.md was not found at that GitHub path")
        if any(item.get("mode") not in {"100644", "100755"} for item in entries):
            raise ValueError("Skill contains a link, submodule, or unsupported file")
        files = {}
        for item in entries:
            path = skill_path(item["path"][len(prefix):])
            sha = item["sha"]
            if not re.fullmatch(r"[0-9a-f]{40}", sha):
                raise ValueError("Invalid GitHub blob")
            data = self.read(f"{GITHUB_RAW}/{repo}/{commit}/{quote(item['path'])}", item["size"])
            blob_digest = hashlib.sha1(f"blob {len(data)}\0".encode() + data, usedforsecurity=False).hexdigest()
            if blob_digest != sha:
                raise ValueError("GitHub file does not match the selected commit")
            files[path] = data
        source = {"kind": "github", "url": url, "repository": repo,
                  "folder": folder, "ref": ref, "commit": commit}
        return (folder or repo).rsplit("/", 1)[-1], files, source, f"github:{repo}:{folder}"


def github_client():
    return httpx.Client(timeout=10, follow_redirects=False, trust_env=False,
                        headers={"Accept": "application/vnd.github+json", "User-Agent": "AI2Apps"})
