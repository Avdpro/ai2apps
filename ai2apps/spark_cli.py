"""Linux/CUDA entry point for the AI2Apps control plane.

The Spark distribution deliberately runs inference in managed Model Runtime
Services.  Setting the runtime profile before importing :mod:`omlx` keeps MLX
and all other in-process model backends outside the control-plane process.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit


def _configure_spark_profile() -> None:
    """Select the inference-free host profile before any server import."""

    os.environ.setdefault("AI2APPS_RUNTIME_PROFILE", "cloud")
    os.environ.setdefault("AI2APPS_PRODUCT", "1")


def _doctor(arguments: list[str]) -> int:
    import argparse

    from ai2apps.environment_check import collect_environment_report

    parser = argparse.ArgumentParser(prog="ai2apps doctor")
    parser.add_argument("--deep", action="store_true", help="probe network and CUDA")
    parser.add_argument("--json", action="store_true", help="emit the full JSON report")
    parser.add_argument(
        "--base-path",
        type=Path,
        default=Path(os.environ.get("AI2APPS_HOME", "~/.ai2apps")).expanduser(),
    )
    parsed = parser.parse_args(arguments)
    report = collect_environment_report(
        model_dir=parsed.base_path / "models",
        hf_cache_dir=Path(
            os.environ.get("HF_HOME", "~/.cache/huggingface")
        ).expanduser()
        / "hub",
        check_network=parsed.deep,
    )
    if parsed.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        host = report["host"]
        accelerator = report.get("accelerator", {})
        print(f"AI2Apps host: {host['os']} {host['architecture']}")
        print(
            "Accelerator: "
            + str(accelerator.get("name") or accelerator.get("kind") or "not detected")
        )
        for check in report["checks"]:
            print(f"[{check['status']:<8}] {check['title']}: {check['detail']}")
        print(f"Overall: {report['status']}")
    return 0 if report["status"] != "critical" else 1


def _default_data_path() -> Path:
    return Path(
        os.environ.get("AI2APPS_HOME", "~/.local/share/ai2apps")
    ).expanduser()


def _prepare_serve_arguments() -> None:
    """Apply Spark-safe defaults while preserving every explicit CLI value."""

    if len(sys.argv) < 2 or sys.argv[1] != "serve":
        return
    if "--base-path" not in sys.argv:
        sys.argv.extend(("--base-path", str(_default_data_path())))
    if "--host" not in sys.argv:
        # Remote browser access should use an SSH tunnel until the operator
        # has deliberately configured authenticated HTTPS/LAN sharing.
        sys.argv.extend(("--host", "127.0.0.1"))


def _systemd_argument(value: str | Path) -> str:
    text = str(value)
    if "\n" in text or "\r" in text:
        raise ValueError("systemd argument contains a newline")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _docker_systemd_group(allowed: bool) -> str:
    """Preserve Docker access when the user manager predates group enrollment."""

    if not allowed or sys.platform != "linux":
        return ""
    import grp

    try:
        docker_gid = grp.getgrnam("docker").gr_gid
    except KeyError:
        return ""
    return "SupplementaryGroups=docker\n" if docker_gid in os.getgroups() else ""


def _service(arguments: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="ai2apps service")
    parser.add_argument("action", choices=("install", "start", "stop", "restart", "status"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--base-path", type=Path, default=_default_data_path())
    parser.add_argument("--no-start", action="store_true")
    parser.add_argument(
        "--allow-docker-control",
        action="store_true",
        help=(
            "grant the service Docker-daemon access for isolated CUDA Workers "
            "(Docker control is effectively root-equivalent)"
        ),
    )
    parsed = parser.parse_args(arguments)
    if not 1 <= parsed.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    unit_name = "ai2apps-spark.service"
    systemctl = ["systemctl", "--user"]
    if parsed.action == "install":
        unit_dir = Path.home() / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True, exist_ok=True)
        unit = unit_dir / unit_name
        command = " ".join(
            _systemd_argument(item)
            for item in (
                sys.executable,
                "-m",
                "ai2apps.spark_cli",
                "serve",
                "--base-path",
                parsed.base_path.expanduser(),
                "--host",
                parsed.host,
                "--port",
                str(parsed.port),
            )
        )
        unit.write_text(
            "[Unit]\n"
            "Description=AI2Apps Spark Local Service\n"
            "After=network-online.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            "Environment=AI2APPS_RUNTIME_PROFILE=cloud\n"
            f"{_docker_systemd_group(parsed.allow_docker_control)}"
            f"ExecStart={command}\n"
            "Restart=on-failure\n"
            "RestartSec=5\n\n"
            "[Install]\n"
            "WantedBy=default.target\n",
            encoding="utf-8",
        )
        subprocess.run([*systemctl, "daemon-reload"], check=True)
        if parsed.no_start:
            subprocess.run([*systemctl, "enable", unit_name], check=True)
        else:
            subprocess.run([*systemctl, "enable", "--now", unit_name], check=True)
        print(f"Installed {unit}")
        return 0

    result = subprocess.run([*systemctl, parsed.action, unit_name], check=False)
    return result.returncode


def _models(arguments: list[str]) -> int:
    """Configure a local OpenAI-compatible Runtime without editing JSON."""

    import argparse

    from ai2apps.model_manager import ModelManagerStore

    parser = argparse.ArgumentParser(prog="ai2apps models")
    parser.add_argument("action", choices=("add-openai", "list", "remove"))
    parser.add_argument("--id", dest="provider_id")
    parser.add_argument("--name")
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--api-key", default="local-runtime")
    parser.add_argument("--base-path", type=Path, default=_default_data_path())
    parser.add_argument("--allow-remote", action="store_true")
    parsed = parser.parse_args(arguments)
    store = ModelManagerStore(parsed.base_path.expanduser())

    if parsed.action == "list":
        for provider in store.list_cloud():
            if provider["builtin"] and not provider["configured"]:
                continue
            print(
                f"{provider['id']}\t{provider['base_url']}\t"
                f"{provider['enabled_model_count']}/{provider['model_count']} models"
            )
        return 0

    if not parsed.provider_id:
        parser.error("--id is required")
    if parsed.action == "remove":
        removed = store.delete_cloud(parsed.provider_id)
        print("removed" if removed else "not configured")
        return 0 if removed else 1

    if not parsed.base_url or not parsed.model:
        parser.error("add-openai requires --base-url and --model")
    endpoint = urlsplit(parsed.base_url)
    if endpoint.scheme not in {"http", "https"} or not endpoint.hostname:
        parser.error("--base-url must be an HTTP(S) URL")
    loopback_names = {"localhost", "127.0.0.1", "::1"}
    if endpoint.hostname not in loopback_names and not parsed.allow_remote:
        parser.error("local Runtimes must use a loopback URL (or pass --allow-remote)")
    store.put_cloud(
        parsed.provider_id,
        {
            "name": parsed.name or parsed.provider_id,
            "base_url": parsed.base_url,
            "protocol": "openai",
            "models": [parsed.model],
            "api_key": parsed.api_key,
            "enabled": True,
        },
    )
    store.set_cloud_model_enabled(parsed.provider_id, parsed.model, True)
    print(ModelManagerStore.gateway_model_id(parsed.provider_id, parsed.model))
    return 0


def main() -> None:
    """Run AI2Apps in the Spark-safe control-plane profile."""

    _configure_spark_profile()
    if len(sys.argv) >= 2 and sys.argv[1] == "doctor":
        raise SystemExit(_doctor(sys.argv[2:]))
    if len(sys.argv) >= 2 and sys.argv[1] == "service":
        raise SystemExit(_service(sys.argv[2:]))
    if len(sys.argv) >= 2 and sys.argv[1] == "models":
        raise SystemExit(_models(sys.argv[2:]))

    _prepare_serve_arguments()

    from ai2apps.cli import main as ai2apps_main

    ai2apps_main()


if __name__ == "__main__":
    main()
