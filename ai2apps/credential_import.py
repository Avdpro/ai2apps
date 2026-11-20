"""Local one-shot credential transfer. Native Helper owns consent and peer trust.

No public method returns credentials. The three native callbacks require the
per-boot Helper channel, never browser cookies, and all tickets are boot-local.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from ai2apps.identity import IdentityRepository


class CredentialImportError(ValueError):
    pass


class CredentialImportUncertain(CredentialImportError):
    """A failed storage rollback must not be represented as an unchanged key."""


def account_id(value):
    value = str(value)
    return value.removeprefix("ai2apps-user:")


def origin(value):
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise CredentialImportError("Cloud account origin must use HTTPS")
    return f"https://{parsed.netloc.lower()}"


class CredentialImport:
    TTL = 180
    MAX_ITEMS = 16

    def __init__(self, runtime, *, clock=time.monotonic):
        self.runtime, self.clock = runtime, clock
        self.lock = threading.RLock()
        self.tickets = {}
        self.offers = {}
        self.path = Path(runtime.config.paths.base_path) / "ai2apps" / "credential-owners.json"

    def _salt(self):
        backend = self.runtime.model_manager.secret_backend
        try:
            return backend.load("credential-import-version-salt")
        except KeyError:
            value = secrets.token_hex(32)
            backend.store("credential-import-version-salt", value)
            return value

    def _version(self, data):
        return hmac.new(self._salt().encode(), json.dumps(data, sort_keys=True, ensure_ascii=False).encode(), hashlib.sha256).hexdigest()

    def _owners(self):
        try:
            return json.loads(self.path.read_text())
        except FileNotFoundError:
            return {}

    def _write_owners(self, value):
        from ai2apps.model_manager import _atomic_json
        _atomic_json(self.path, value)

    def principal_context(self, principal):
        if principal.client_scope != "desktop" or not principal.is_core or principal.authentication_type == "legacy_api_key":
            raise CredentialImportError("Sign in to the Desktop core account first")
        identities = IdentityRepository(self.runtime.database)
        current = identities.principal_for(principal.actor_user_id)
        if (current.installation_id, current.membership_epoch) != (principal.installation_id, principal.membership_epoch):
            raise CredentialImportError("Account authorization changed")
        return {"user_id": account_id(principal.actor_user_id),
                "actor_id": principal.actor_user_id, "cloud_origin": origin(self.runtime.cloud.base_url),
                "installation_id": current.installation_id, "membership_epoch": current.membership_epoch,
                "security_id": self.runtime.security_identity.security_instance_id}

    async def live_identity(self, principal=None):
        if self.runtime.offline_mode:
            raise CredentialImportError("Sign in to AI2Apps online in both instances")
        if principal is None:
            identities = IdentityRepository(self.runtime.database)
            installation = identities.get_installation()
            if installation is None or installation.status != "active":
                raise CredentialImportError("Source instance is not signed in")
            principal = identities.principal_for(installation.core_user_id)
        context = self.principal_context(principal)
        # Each instance verifies its own private Cloud session; none is copied.
        browsers = list(getattr(self.runtime, "_browser_cloud_clients", {}).values())
        clients = [self.runtime.cloud, *browsers[-4:]]
        async def verify(cloud):
            if origin(cloud.base_url) != context["cloud_origin"]:
                return False
            try:
                response = await asyncio.wait_for(cloud.request("GET", "/v1/auth/me"), 8)
                data = response.json()
                user = data.get("user", {}) if isinstance(data, dict) else {}
                uid = user.get("id") or user.get("userId")
                if response.status_code == 200 and uid and account_id(uid) == context["user_id"]:
                    return True
            except Exception:
                return False
            return False
        tasks = [asyncio.create_task(verify(cloud)) for cloud in clients]
        try:
            for completed in asyncio.as_completed(tasks):
                if await completed:
                    return context
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        raise CredentialImportError("Reauthenticate the same AI2Apps account in both instances")

    @staticmethod
    def same_account(a, b):
        return (a.get("user_id"), a.get("cloud_origin")) == (b.get("user_id"), b.get("cloud_origin")) and bool(a.get("user_id"))

    def _entries(self, identity, *, include_secrets=False, include_foreign=False):
        store = self.runtime.model_manager
        owners = self._owners()
        found = []
        raw = store._cloud_data()
        for item in store.list_cloud():
            pid = item["id"]
            if pid == "ai2apps" or item.get("managed") or pid not in raw:
                continue
            value = store._load_provider_key(pid, raw[pid])
            if not value:
                continue
            config = {k: item.get(k) for k in ("name", "base_url", "protocol")}
            # Only declared model IDs; never propagate errors, arbitrary metadata or other secrets.
            found.append(self._entry("cloud", pid, config, value, identity, owners, include_secrets, include_foreign))
        from ai2apps.video.byok import PROVIDERS, credential
        for pid, spec in PROVIDERS.items():
            try:
                value = credential(self.runtime, pid, identity["actor_id"])
            except Exception:
                continue
            config = {"name": spec["name"], "base_url": spec["origin"]}
            found.append(self._entry("video", pid, config, value, identity, owners, include_secrets, include_foreign))
        return [entry for entry in found if entry is not None]

    def _entry(self, kind, pid, config, secret, identity, owners, include_secrets, include_foreign):
        key = kind + ":" + pid
        binding = self._version({"kind": kind, "id": pid, "config": config, "secret": secret})
        owner_binding = self._version({"kind": kind, "id": pid, "secret": secret})
        owner = owners.get(key)
        if owner and owner.get("binding") == owner_binding:
            if not self.same_account(owner, identity):
                if not include_foreign:
                    return None
                ownership = "foreign"
            else:
                ownership = "owned"
        else:
            ownership = "unclaimed"
        result = {"key": key, "kind": kind, "id": pid, "config": config,
                  "version": binding, "ownership": ownership}
        if include_secrets:
            result["secret"] = secret
        return result

    def mark_owner(self, identity, key):
        with self.lock:
            entry = next((e for e in self._entries(identity, include_secrets=True) if e["key"] == key), None)
            if entry is None:
                # A replacement credential invalidates any older binding; it is not inherited.
                owners = self._owners()
                owners.pop(key, None)
                self._write_owners(owners)
                entry = next((e for e in self._entries(identity, include_secrets=True) if e["key"] == key), None)
            if entry:
                owners = self._owners()
                owners[key] = {"user_id": identity["user_id"], "cloud_origin": identity["cloud_origin"],
                               "binding": self._version({"kind":entry["kind"],"id":entry["id"],"secret":entry["secret"]})}
                self._write_owners(owners)

    def _prune(self):
        for collection in (self.tickets, self.offers):
            for key, value in list(collection.items()):
                if value["expires"] < self.clock():
                    collection.pop(key, None)
            if len(collection) >= 32:
                raise CredentialImportError("Too many credential import requests")

    @staticmethod
    def _exportable(entry):
        config = entry["config"]
        name, address = config.get("name"), config.get("base_url")
        if not isinstance(name, str) or not 1 <= len(name) <= 120 or any(ord(c) < 32 for c in name):
            return False
        if not isinstance(address, str) or len(address) > 2048 or any(c.isspace() for c in address):
            return False
        url = urlsplit(address)
        return url.scheme == "https" and bool(url.hostname) and not (url.username or url.password or url.query or url.fragment)

    def begin(self, principal, action):
        identity = self.principal_context(principal)
        if action.get("action") not in {"list", "import"}:
            raise CredentialImportError("Unknown import action")
        if action["action"] == "import":
            selected = action.get("selected")
            if not isinstance(selected, list) or not 1 <= len(selected) <= self.MAX_ITEMS:
                raise CredentialImportError("Select 1 to 16 providers")
            if len(set(selected)) != len(selected) or not all(isinstance(k, str) and len(k) < 200 for k in selected):
                raise CredentialImportError("Invalid provider selection")
            if not isinstance(action.get("source"), str) or not isinstance(action.get("offer_id"), str):
                raise CredentialImportError("Choose an available source instance")
        with self.lock:
            self._prune()
            ticket = secrets.token_urlsafe(32)
            self.tickets[ticket] = {"identity": identity, "principal": principal, "action": action,
                                    "versions": {e["key"]:e["version"] for e in self._entries(identity, include_foreign=True)},
                                    "expires": self.clock() + self.TTL}
        return ticket

    async def native_context(self, ticket=None):
        if ticket:
            item = self.tickets.get(ticket)
            if not item or item["expires"] < self.clock():
                raise CredentialImportError("Import request expired; start again")
            identity = await self.live_identity(item["principal"])
            if identity != item["identity"]:
                raise CredentialImportError("Account or instance changed")
            return {"identity": identity, "action": item["action"], "target_versions": item["versions"]}
        identity = await self.live_identity()
        with self.lock:
            self._prune()
            entries = [entry for entry in self._entries(identity) if self._exportable(entry)]
            offer_id = secrets.token_urlsafe(32)
            self.offers[offer_id] = {"identity":identity,"entries":entries,"expires":self.clock()+self.TTL}
        return {"identity":identity, "providers":entries, "offer_id":offer_id}

    async def native_export(self, body):
        identity = await self.live_identity()
        with self.lock:
            offer = self.offers.pop(body.get("offer_id"), None)
            if not offer or offer["expires"] < self.clock() or offer["identity"] != identity:
                raise CredentialImportError("Source offer expired or account changed")
            if not self.same_account(identity, body.get("destination", {})):
                raise CredentialImportError("Instances must use the same AI2Apps account and Cloud")
            selected = body.get("selected", [])
            if not isinstance(selected, list) or not 1 <= len(selected) <= self.MAX_ITEMS or len(set(selected)) != len(selected):
                raise CredentialImportError("Invalid provider selection")
            entries = {e["key"]:e for e in self._entries(identity, include_secrets=True)}
            offered = {e["key"]:e for e in offer["entries"]}
            if any(k not in entries or k not in offered or entries[k]["version"] != offered[k]["version"] for k in selected):
                raise CredentialImportError("Source providers changed; review again")
            # Native consent explicitly includes claiming any legacy/unclaimed entries.
            for key in selected:
                self.mark_owner(identity, key)
            return {"identity":identity,"providers":[entries[k] for k in selected]}

    async def native_install(self, body):
        ticket = body.get("ticket")
        context = await self.native_context(ticket)
        with self.lock:
            item = self.tickets.pop(ticket, None)
            if not item:
                raise CredentialImportError("Import already consumed")
            action = item["action"]
            payload = body.get("payload", {})
            if not self.same_account(context["identity"], payload.get("identity", {})):
                raise CredentialImportError("Source account mismatch")
            entries = payload.get("providers", [])
            if sorted(e.get("key", "") for e in entries) != sorted(action["selected"]):
                raise CredentialImportError("Transfer selection mismatch")
            current_entries = self._entries(context["identity"], include_foreign=True)
            current = {e["key"]:e["version"] for e in current_entries}
            if any(e["key"] in action["selected"] and e["ownership"] == "foreign" for e in current_entries):
                raise CredentialImportError("Destination provider belongs to another account")
            for key in action["selected"]:
                if current.get(key) != item["versions"].get(key):
                    raise CredentialImportError("Destination changed; review again")
                if key in current and action.get("replace_existing") is not True:
                    raise CredentialImportError("Destination already has a key; explicitly approve replacement")
            results = []
            for entry in entries:
                try:
                    self._install_entry(context["identity"], entry)
                    results.append({"key":entry["key"],"status":"imported"})
                except CredentialImportUncertain:
                    results.append({"key":entry.get("key"),"status":"unknown"})
                except Exception:
                    # Never interpolate errors from a credential-bearing call.
                    results.append({"key":entry.get("key"),"status":"failed"})
            return {"status":"completed" if all(r["status"] == "imported" for r in results) else "partial", "items":results}

    def _install_entry(self, identity, entry):
        config, pid, kind = entry["config"], entry["id"], entry["kind"]
        secret = entry["secret"]
        if not isinstance(secret, str) or not secret or len(secret) > 4096:
            raise CredentialImportError("Invalid credential")
        if entry["key"] != kind + ":" + pid or pid == "ai2apps":
            raise CredentialImportError("Invalid provider")
        store = self.runtime.model_manager
        old_owners = self._owners()
        old_config = store._cloud_data().get(pid) if kind == "cloud" else None
        secret_key = store._credential_key(pid)
        if kind == "video":
            from ai2apps.video.byok import PROVIDERS, _secret_key
            if pid not in PROVIDERS or config["base_url"] != PROVIDERS[pid]["origin"]:
                raise CredentialImportError("Video API origin mismatch")
            secret_key = _secret_key(pid, identity["actor_id"])
        elif kind == "cloud":
            url = urlsplit(config["base_url"])
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise CredentialImportError("Provider must use an unambiguous HTTPS endpoint")
        else:
            raise CredentialImportError("Unsupported credential type")
        try:
            old_secret = store.secret_backend.load(secret_key)
        except KeyError:
            old_secret = None
        try:
            if kind == "cloud":
                store.put_cloud(pid, {**config, "api_key":secret})
            else:
                store.secret_backend.store(secret_key, secret)
            self.mark_owner(identity, entry["key"])
        except Exception:
            try:
                if old_secret is None:
                    store.secret_backend.delete(secret_key)
                else:
                    store.secret_backend.store(secret_key, old_secret)
                if kind == "cloud":
                    from ai2apps.model_manager import _atomic_json
                    records = store._cloud_data()
                    if old_config is None:
                        records.pop(pid, None)
                    else:
                        records[pid] = old_config
                    _atomic_json(store.cloud_path, {"version":2,"providers":records})
                self._write_owners(old_owners)
            except Exception:
                raise CredentialImportUncertain("Storage outcome is unknown; inspect configuration before another import") from None
            raise CredentialImportError("Provider import failed; previous configuration restored") from None


def service(runtime):
    current = getattr(runtime, "credential_import", None)
    if current is None:
        current = runtime.credential_import = CredentialImport(runtime)
    return current
