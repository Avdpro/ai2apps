"""Authenticated client for the per-instance desktop Helper control endpoint."""

from __future__ import annotations

import json
import os
import re
import socket
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

_TOKEN = re.compile(r"^[0-9a-f]{64}$")
_BROWSER_PROFILE_KEY = re.compile(r"^(?:default|[0-9a-f]{32})$")
_MAX_MESSAGE_BYTES = 64 * 1024


class HelperControlError(RuntimeError):
    """The Helper control channel is missing, unavailable, or rejected."""


@dataclass(frozen=True, slots=True)
class HelperControlClient:
    endpoint_path: str
    token: str
    timeout_seconds: float = 3.0

    @classmethod
    def from_environment(cls) -> HelperControlClient | None:
        endpoint_path = os.environ.get("AI2APPS_HELPER_ENDPOINT")
        token = os.environ.get("AI2APPS_HELPER_TOKEN")
        if endpoint_path is None and token is None:
            return None
        if not endpoint_path or not os.path.isabs(endpoint_path):
            raise HelperControlError("AI2APPS_HELPER_ENDPOINT must be absolute")
        if not token or not _TOKEN.fullmatch(token):
            raise HelperControlError("AI2APPS_HELPER_TOKEN is invalid")
        return cls(endpoint_path=endpoint_path, token=token)

    def _read_endpoint(self) -> tuple[str, int]:
        try:
            with open(self.endpoint_path, "rb") as endpoint_file:
                raw = endpoint_file.read(4097)
        except OSError as exc:
            raise HelperControlError(f"Helper endpoint is unavailable: {exc}") from exc
        if len(raw) > 4096:
            raise HelperControlError("Helper endpoint descriptor is too large")
        try:
            endpoint = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HelperControlError("Helper endpoint descriptor is invalid") from exc
        if not isinstance(endpoint, dict):
            raise HelperControlError("Helper endpoint descriptor is invalid")
        host = endpoint.get("host")
        port = endpoint.get("port")
        if (
            endpoint.get("version") != 1
            or host != "127.0.0.1"
            or not isinstance(port, int)
            or isinstance(port, bool)
            or not 1024 <= port <= 65535
        ):
            raise HelperControlError("Helper endpoint descriptor is unsafe")
        return host, port

    def launch_browser_agent(
        self,
        *,
        actor_user_id: str,
        initial_url: str | None = None,
        profile_key: str = "default",
    ) -> dict[str, Any]:
        self._validate_actor_user_id(actor_user_id)
        self._validate_browser_profile_key(profile_key)
        if initial_url is not None:
            parsed = urlparse(initial_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise HelperControlError("initial_url must use http or https")
            if len(initial_url.encode("utf-8")) > 2048:
                raise HelperControlError("initial_url is too long")
        request: dict[str, Any] = {
            "version": 1,
            "request_id": str(uuid.uuid4()),
            "token": self.token,
            "operation": "browser.launch",
            "actor_user_id": actor_user_id,
            "browser_profile_key": profile_key,
        }
        if initial_url is not None:
            request["initial_url"] = initial_url
        response = self._exchange(request)
        if response.get("request_id") != request["request_id"]:
            raise HelperControlError("Helper response request_id mismatch")
        if response.get("ok") is not True:
            raise HelperControlError(str(response.get("error") or "Helper rejected request"))
        result = response.get("result")
        if not isinstance(result, dict):
            raise HelperControlError("Helper response result is invalid")
        self._validate_browser_agent_result(result)
        return result

    def release_browser_agent(
        self, *, actor_user_id: str, profile_key: str = "default"
    ) -> dict[str, Any]:
        self._validate_actor_user_id(actor_user_id)
        self._validate_browser_profile_key(profile_key)
        request: dict[str, Any] = {
            "version": 1,
            "request_id": str(uuid.uuid4()),
            "token": self.token,
            "operation": "browser.release",
            "actor_user_id": actor_user_id,
            "browser_profile_key": profile_key,
        }
        response = self._exchange(request)
        if response.get("request_id") != request["request_id"]:
            raise HelperControlError("Helper response request_id mismatch")
        if response.get("ok") is not True:
            raise HelperControlError(str(response.get("error") or "Helper rejected request"))
        result = response.get("result")
        if not isinstance(result, dict):
            raise HelperControlError("Helper response result is invalid")
        self._validate_browser_release_result(result)
        return result

    def delete_browser_profile(
        self, *, actor_user_id: str, profile_key: str
    ) -> dict[str, Any]:
        self._validate_actor_user_id(actor_user_id)
        self._validate_browser_profile_key(profile_key)
        if profile_key == "default":
            raise HelperControlError("The default browser Profile cannot be deleted")
        request = {
            "version": 1,
            "request_id": str(uuid.uuid4()),
            "token": self.token,
            "operation": "browser.delete",
            "actor_user_id": actor_user_id,
            "browser_profile_key": profile_key,
        }
        response = self._exchange(request)
        if response.get("request_id") != request["request_id"]:
            raise HelperControlError("Helper response request_id mismatch")
        if response.get("ok") is not True:
            raise HelperControlError(str(response.get("error") or "Helper rejected request"))
        result = response.get("result")
        if not isinstance(result, dict) or result.get("status") != "deleted":
            raise HelperControlError("Helper browser Profile delete status is invalid")
        self._validate_result_profile_id(result)
        if result.get("automation") is not None:
            raise HelperControlError("Helper browser Profile delete leaked automation data")
        return result

    def restart_local(self, *, actor_user_id: str) -> dict[str, Any]:
        """Ask the owning desktop Helper to restart its supervised Local."""

        self._validate_actor_user_id(actor_user_id)
        request = {
            "version": 1,
            "request_id": str(uuid.uuid4()),
            "token": self.token,
            "operation": "local.restart",
            "actor_user_id": actor_user_id,
        }
        response = self._exchange(request)
        if response.get("request_id") != request["request_id"]:
            raise HelperControlError("Helper response request_id mismatch")
        if response.get("ok") is not True:
            raise HelperControlError(str(response.get("error") or "Helper rejected request"))
        result = response.get("result")
        if not isinstance(result, dict) or result.get("status") != "restarting":
            raise HelperControlError("Helper Local restart status is invalid")
        if result.get("automation") is not None:
            raise HelperControlError("Helper Local restart leaked automation data")
        return {"status": "restarting"}

    def renew_browser_agent(self, *, actor_user_id: str) -> dict[str, Any]:
        return self._change_browser_agent_lease(
            actor_user_id=actor_user_id,
            operation="browser.renew",
            expected_status="renewed",
        )

    def pause_browser_agent(self, *, actor_user_id: str) -> dict[str, Any]:
        return self._change_browser_agent_lease(
            actor_user_id=actor_user_id,
            operation="browser.pause",
            expected_status="paused",
        )

    def resume_browser_agent(self, *, actor_user_id: str) -> dict[str, Any]:
        return self._change_browser_agent_lease(
            actor_user_id=actor_user_id,
            operation="browser.resume",
            expected_status="resumed",
        )

    def _change_browser_agent_lease(
        self,
        *,
        actor_user_id: str,
        operation: str,
        expected_status: str,
    ) -> dict[str, Any]:
        self._validate_actor_user_id(actor_user_id)
        request = {
            "version": 1,
            "request_id": str(uuid.uuid4()),
            "token": self.token,
            "operation": operation,
            "actor_user_id": actor_user_id,
        }
        response = self._exchange(request)
        if response.get("request_id") != request["request_id"]:
            raise HelperControlError("Helper response request_id mismatch")
        if response.get("ok") is not True:
            raise HelperControlError(str(response.get("error") or "Helper rejected request"))
        result = response.get("result")
        if not isinstance(result, dict):
            raise HelperControlError("Helper response result is invalid")
        self._validate_browser_lease_result(result, expected_status=expected_status)
        return result

    @staticmethod
    def _validate_actor_user_id(actor_user_id: str) -> None:
        if not isinstance(actor_user_id, str) or not 1 <= len(actor_user_id.encode("utf-8")) <= 200:
            raise HelperControlError("actor_user_id must contain 1 to 200 UTF-8 bytes")

    @staticmethod
    def _validate_browser_profile_key(profile_key: str) -> None:
        if not isinstance(profile_key, str) or not _BROWSER_PROFILE_KEY.fullmatch(profile_key):
            raise HelperControlError("browser_profile_key is invalid")

    @staticmethod
    def _validate_result_profile_id(result: dict[str, Any]) -> None:
        profile_id = result.get("profile_id")
        if not isinstance(profile_id, str) or not _TOKEN.fullmatch(profile_id):
            raise HelperControlError("Helper browser profile_id is invalid")

    @staticmethod
    def _validate_browser_agent_result(result: dict[str, Any]) -> None:
        if result.get("status") not in {"launched", "focused"}:
            raise HelperControlError("Helper browser status is invalid")
        HelperControlClient._validate_result_profile_id(result)
        pid = result.get("pid")
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            raise HelperControlError("Helper browser pid is invalid")
        automation = result.get("automation")
        if not isinstance(automation, dict):
            raise HelperControlError("Helper browser automation contract is missing")
        if automation.get("transport") != "webdriver-bidi":
            raise HelperControlError("Helper browser transport is invalid")
        web_socket_url = automation.get("web_socket_url")
        if not isinstance(web_socket_url, str):
            raise HelperControlError("Helper browser web_socket_url is invalid")
        parsed = urlparse(web_socket_url)
        try:
            port = parsed.port
        except ValueError as exc:
            raise HelperControlError("Helper browser web_socket_url is invalid") from exc
        if (
            parsed.scheme != "ws"
            or parsed.hostname != "127.0.0.1"
            or parsed.path != "/session"
            or parsed.params
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
            or port is None
            or not 1024 <= port <= 65535
        ):
            raise HelperControlError("Helper browser web_socket_url is not safe")
        authorization = automation.get("authorization")
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            raise HelperControlError("Helper browser authorization is invalid")
        if not _TOKEN.fullmatch(authorization.removeprefix("Bearer ")):
            raise HelperControlError("Helper browser authorization is invalid")

    @staticmethod
    def _validate_browser_release_result(result: dict[str, Any]) -> None:
        if result.get("status") not in {"released", "not_running"}:
            raise HelperControlError("Helper browser release status is invalid")
        profile_id = result.get("profile_id")
        if not isinstance(profile_id, str) or not _TOKEN.fullmatch(profile_id):
            raise HelperControlError("Helper browser profile_id is invalid")
        pid = result.get("pid")
        if pid is not None and (
            not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0
        ):
            raise HelperControlError("Helper browser pid is invalid")
        if result.get("automation") is not None:
            raise HelperControlError("Helper browser release leaked automation data")

    @staticmethod
    def _validate_browser_lease_result(
        result: dict[str, Any], *, expected_status: str
    ) -> None:
        if result.get("status") != expected_status:
            raise HelperControlError("Helper browser lease status is invalid")
        profile_id = result.get("profile_id")
        if not isinstance(profile_id, str) or not _TOKEN.fullmatch(profile_id):
            raise HelperControlError("Helper browser profile_id is invalid")
        pid = result.get("pid")
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            raise HelperControlError("Helper browser pid is invalid")
        if result.get("automation") is not None:
            raise HelperControlError("Helper browser lease leaked automation data")

    def _exchange(self, payload: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(encoded) > _MAX_MESSAGE_BYTES:
            raise HelperControlError("Helper request is too large")
        host, port = self._read_endpoint()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
                connection.settimeout(self.timeout_seconds)
                connection.connect((host, port))
                connection.sendall(encoded)
                chunks: list[bytes] = []
                size = 0
                while True:
                    chunk = connection.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > _MAX_MESSAGE_BYTES:
                        raise HelperControlError("Helper response is too large")
                    if b"\n" in chunk:
                        break
        except (OSError, TimeoutError) as exc:
            raise HelperControlError(f"Helper is unavailable: {exc}") from exc
        raw = b"".join(chunks).split(b"\n", 1)[0]
        try:
            response = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HelperControlError("Helper returned invalid JSON") from exc
        if not isinstance(response, dict):
            raise HelperControlError("Helper returned a non-object response")
        return response
