"""Read-only host diagnostics and conservative local-model recommendations.

The checks in this module intentionally avoid importing MLX or model runtimes.  A
broken native dependency must be reported by the environment App, not prevent the
control plane from starting.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import socket
import subprocess
import sys
from contextlib import suppress
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psutil
from packaging.version import InvalidVersion, Version

GIB = 1024**3

_COMPONENTS: tuple[tuple[str, str, str, bool], ...] = (
    ("huggingface_hub", "huggingface-hub", "1.19.0", True),
    ("mlx", "mlx", "0.32.0", True),
    ("mlx_lm", "mlx-lm", "0.31.3", True),
    ("transformers", "transformers", "5.12.1", True),
    ("psutil", "psutil", "5.9.0", True),
    ("modelscope", "modelscope", "1.10.0", False),
)

_CONTROL_PLANE_COMPONENTS: tuple[tuple[str, str, str, bool], ...] = (
    ("huggingface_hub", "huggingface-hub", "1.19.0", True),
    ("fastapi", "fastapi", "0.108.0", True),
    ("uvicorn", "uvicorn", "0.23.0", True),
    ("psutil", "psutil", "5.9.0", True),
    ("modelscope", "modelscope", "1.10.0", False),
)


def _sysctl(name: str) -> str | None:
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-n", name],
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value or None


def _package_check(
    module_name: str, distribution: str, minimum: str, required: bool
) -> dict[str, Any]:
    installed = importlib.util.find_spec(module_name) is not None
    installed_version = None
    if installed:
        with suppress(PackageNotFoundError):
            installed_version = version(distribution)
    compatible = installed
    if installed_version:
        try:
            compatible = Version(installed_version) >= Version(minimum)
        except InvalidVersion:
            compatible = False
    return {
        "id": module_name,
        "name": distribution,
        "required": required,
        "installed": installed,
        "compatible": compatible,
        "version": installed_version,
        "minimum_version": minimum,
        "status": (
            "pass"
            if installed and compatible
            else ("fail" if required else "optional")
        ),
    }


def _path_health(path: Path) -> dict[str, Any]:
    target = path.expanduser()
    probe = target if target.exists() else target.parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    writable = os.access(probe, os.W_OK)
    try:
        usage = shutil.disk_usage(probe)
    except OSError:
        usage = shutil.disk_usage(Path.cwd())
    return {
        "path": str(target),
        "exists": target.exists(),
        "writable": writable,
        "total_bytes": usage.total,
        "free_bytes": usage.free,
        "used_percent": round((usage.used / usage.total) * 100, 1) if usage.total else 0.0,
    }


def _network_check(endpoint: str) -> dict[str, Any]:
    parsed = urlsplit(endpoint)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if parsed.scheme not in {"http", "https"} or not host:
        return {"status": "fail", "message": "Invalid Hugging Face endpoint"}
    try:
        with socket.create_connection((host, port), timeout=2.5):
            pass
    except OSError as error:
        return {"status": "fail", "message": str(error)[:240]}
    return {"status": "pass", "message": f"TCP connection to {host}:{port} succeeded"}


def _metal_check() -> dict[str, Any]:
    """Exercise one tiny MLX allocation in an isolated child process."""
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import mlx.core as mx; x=mx.array([1]); mx.eval(x); print(mx.default_device())",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except subprocess.TimeoutExpired:
        return {"status": "fail", "message": "Metal/MLX probe timed out"}
    except OSError as error:
        return {"status": "fail", "message": str(error)[:240]}
    if result.returncode == 0:
        return {"status": "pass", "message": result.stdout.strip() or "MLX allocation succeeded"}
    detail = (result.stderr or result.stdout).strip().splitlines()
    return {
        "status": "fail",
        "message": detail[-1][:240] if detail else "MLX allocation failed",
    }


def _nvidia_check() -> dict[str, Any]:
    """Probe the NVIDIA driver without importing a CUDA Python framework."""

    executable = shutil.which("nvidia-smi")
    if executable is None:
        return {
            "status": "fail",
            "kind": "cuda",
            "available": False,
            "message": "nvidia-smi is not installed or is not on PATH",
        }
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "fail",
            "kind": "cuda",
            "available": False,
            "message": "nvidia-smi probe timed out",
        }
    except OSError as error:
        return {
            "status": "fail",
            "kind": "cuda",
            "available": False,
            "message": str(error)[:240],
        }
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        return {
            "status": "fail",
            "kind": "cuda",
            "available": False,
            "message": detail[-1][:240] if detail else "NVIDIA driver probe failed",
        }
    first = next((line for line in result.stdout.splitlines() if line.strip()), "")
    fields = [field.strip() for field in first.split(",")]
    name = fields[0] if fields else "NVIDIA GPU"
    driver = fields[1] if len(fields) > 1 else None
    memory_mib: float | None = None
    if len(fields) > 2:
        with suppress(ValueError):
            memory_mib = float(fields[2])
    is_gb10 = "GB10" in name.upper()
    return {
        "status": "pass",
        "kind": "cuda",
        "available": True,
        "name": name,
        "driver_version": driver,
        "device_memory_bytes": int(memory_mib * 1024**2) if memory_mib else None,
        "memory_model": "unified" if is_gb10 else "device-local",
        "message": f"{name}，驱动 {driver or 'unknown'}。",
    }


def _model_recommendation(total_memory: int, free_disk: int) -> dict[str, Any]:
    memory_gib = total_memory / GIB
    if memory_gib < 16:
        tier = ("compact", "1–3B", "4-bit", 8_192, 1, 6)
        notes = "适合轻量聊天、摘要和嵌入；不建议运行大型 MoE。"
    elif memory_gib < 32:
        tier = ("everyday", "7–8B", "4-bit", 16_384, 1, 12)
        notes = "以单并发为主，长上下文时降低最大输出长度。"
    elif memory_gib < 64:
        tier = ("balanced", "14B 或小型 MoE", "4-bit", 32_768, 1, 24)
        notes = "可尝试 30B 级低激活 MoE；保持内存保护为 balanced。"
    elif memory_gib < 96:
        tier = ("performance", "32B 或缓存 MoE", "4-bit", 32_768, 2, 45)
        notes = "缓存 MoE 建议从 Top-80/Top-96 档开始，并实测稳态 TPS。"
    elif memory_gib < 128:
        tier = ("moe", "35B-A3B 缓存 MoE", "2/4-bit", 65_536, 2, 70)
        notes = "优先 Qwen 35B-A3B 的 Top-96/Top-120；大型模型安装前保留回滚空间。"
    else:
        tier = ("research", "35B-A3B / DeepSeek 缓存 MoE", "2/4-bit", 65_536, 2, 100)
        notes = "可运行静态 oracle slot bank 实验；仍需逐模型通过内存和 TPS release gate。"

    key, family, quant, context, concurrency, storage_gib = tier
    fits_disk = free_disk >= max(storage_gib * GIB * 2, 20 * GIB)
    return {
        "tier": key,
        "model_family": family,
        "quantization": quant,
        "max_context_window": context,
        "max_concurrent_requests": concurrency,
        "estimated_model_storage_bytes": storage_gib * GIB,
        "recommended_free_space_bytes": max(storage_gib * GIB * 2, 20 * GIB),
        "disk_ready": fits_disk,
        "notes": notes,
    }


def collect_environment_report(
    *,
    model_dir: Path,
    hf_cache_dir: Path,
    hf_endpoint: str = "https://huggingface.co",
    settings: dict[str, Any] | None = None,
    check_network: bool = False,
) -> dict[str, Any]:
    """Return a JSON-safe snapshot without loading an inference runtime."""

    memory = psutil.virtual_memory()
    try:
        swap = psutil.swap_memory()
        swap_available = True
    except (OSError, RuntimeError):
        # Sandboxed macOS processes may not be allowed to read VM_SWAPUSAGE.
        swap = type(
            "UnavailableSwap",
            (),
            {"total": 0, "used": 0, "percent": 0.0},
        )()
        swap_available = False
    disk = _path_health(model_dir)
    hf_disk = _path_health(hf_cache_dir)
    components = [_package_check(*item) for item in _COMPONENTS]
    machine = platform.machine().lower()
    is_apple_silicon = sys.platform == "darwin" and machine in {"arm64", "aarch64"}
    is_linux = sys.platform.startswith("linux")
    nvidia = _nvidia_check() if is_linux else {
        "status": "skipped",
        "kind": None,
        "available": False,
        "message": "NVIDIA probe is only used on Linux",
    }
    is_nvidia_linux = is_linux and bool(nvidia.get("available"))
    if is_nvidia_linux:
        components = [_package_check(*item) for item in _CONTROL_PLANE_COMPONENTS]
    python_supported = (3, 11) <= sys.version_info[:2] < (3, 14)
    logical_cores = psutil.cpu_count(logical=True) or 1
    try:
        load_1m = os.getloadavg()[0]
        load_percent = (load_1m / logical_cores) * 100
    except (AttributeError, OSError):
        load_1m = None
        load_percent = None

    checks: list[dict[str, Any]] = []

    def add(check_id: str, status: str, title: str, detail: str) -> None:
        checks.append({"id": check_id, "status": status, "title": title, "detail": detail})

    if is_nvidia_linux:
        add(
            "platform",
            "pass",
            "NVIDIA CUDA 主机",
            f"已检测到 {nvidia.get('name', 'NVIDIA GPU')}；模型由托管 CUDA Runtime Service 运行。",
        )
    else:
        add(
            "platform",
            "pass" if is_apple_silicon else "fail",
            "Apple Silicon 与 Metal",
            "已检测到 Apple Silicon，共享内存可供 Metal 使用。"
            if is_apple_silicon
            else "未检测到受支持的 Apple Silicon/Metal 或 Linux/NVIDIA CUDA 主机。",
        )
    add(
        "python",
        "pass" if python_supported else "fail",
        "Python 运行时",
        f"Python {platform.python_version()}（要求 3.11–3.13）。",
    )
    add(
        "cpu",
        "warning" if load_percent is not None and load_percent >= 90 else "pass",
        "CPU 负载",
        f"1 分钟平均负载 {load_1m:.2f}，约占 {load_percent:.0f}% 的逻辑核心容量。"
        if load_percent is not None and load_1m is not None
        else "当前平台未提供平均负载指标。",
    )
    missing = [
        item["name"]
        for item in components
        if item["required"] and item["status"] != "pass"
    ]
    add(
        "dependencies",
        "pass" if not missing else "fail",
        "核心依赖",
        "核心 Python 组件及版本符合要求。"
        if not missing
        else "缺失或版本不兼容：" + "、".join(missing),
    )
    memory_status = "critical" if memory.percent >= 92 else ("warning" if memory.percent >= 82 else "pass")
    add("memory", memory_status, "统一内存", f"已用 {memory.percent:.1f}%，可用 {memory.available / GIB:.1f} GiB。")
    disk_status = "critical" if disk["free_bytes"] < 10 * GIB else ("warning" if disk["free_bytes"] < 30 * GIB else "pass")
    add("disk", disk_status, "模型磁盘", f"可用 {disk['free_bytes'] / GIB:.1f} GiB，路径{'可写' if disk['writable'] else '不可写'}。")
    if not disk["writable"]:
        checks[-1]["status"] = "critical"
    swap_status = "warning" if swap.total and swap.percent >= 50 else "pass"
    add(
        "swap",
        swap_status if swap_available else "skipped",
        "交换空间",
        f"已用 {swap.used / GIB:.1f} GiB（{swap.percent:.1f}%）。"
        if swap_available
        else "当前进程无权读取交换空间指标。",
    )
    network = (
        _network_check(hf_endpoint)
        if check_network
        else {"status": "skipped", "message": "深度检查时验证 Hugging Face 端点连通性"}
    )
    if check_network:
        add("huggingface_network", network["status"], "Hugging Face 网络", network["message"])
        if is_nvidia_linux:
            metal = {"status": "skipped", "message": "CUDA 主机不使用 Metal/MLX"}
            add("cuda_runtime", nvidia["status"], "NVIDIA CUDA 运行时", nvidia["message"])
        else:
            metal = _metal_check()
            add("metal_runtime", metal["status"], "Metal / MLX 运行时", metal["message"])
    else:
        metal = {"status": "skipped", "message": "深度检查时执行隔离的 MLX 分配探针"}

    severity = {"pass": 0, "skipped": 0, "optional": 0, "warning": 1, "fail": 2, "critical": 3}
    worst = max((severity.get(item["status"], 0) for item in checks), default=0)
    overall = "critical" if worst >= 2 else ("warning" if worst == 1 else "healthy")
    recommendation = _model_recommendation(memory.total, disk["free_bytes"])
    current = settings or {}
    actions: list[dict[str, Any]] = []
    if not current.get("prefill_memory_guard", True):
        actions.append({
            "id": "enable_memory_guard",
            "title": "启用预填充内存保护",
            "detail": "降低长上下文预填充导致系统内存耗尽的风险。",
            "risk": "low",
            "restart_required": False,
        })
    desired_guard = "safe" if memory.percent >= 82 or memory.total < 32 * GIB else "balanced"
    if current.get("memory_guard_tier") != desired_guard:
        actions.append({
            "id": f"set_memory_guard_{desired_guard}",
            "title": f"将内存保护设为 {desired_guard}",
            "detail": "依据当前内存容量与压力采用保守上限。",
            "risk": "low",
            "restart_required": False,
        })
    if not current.get("hf_cache_enabled", False) and any(
        item["id"] == "huggingface_hub" and item["status"] == "pass"
        for item in components
    ):
        actions.append({
            "id": "enable_hf_cache",
            "title": "启用 Hugging Face 缓存",
            "detail": "避免重复下载相同的、已固定 revision 的模型文件。",
            "risk": "low",
            "restart_required": False,
        })

    return {
        "schema_version": 1,
        "status": overall,
        "host": {
            "os": platform.system(),
            "os_version": platform.mac_ver()[0] or platform.release(),
            "architecture": platform.machine(),
            "chip": _sysctl("machdep.cpu.brand_string") or platform.processor() or "Unknown",
            "cpu_logical_cores": psutil.cpu_count(logical=True),
            "cpu_physical_cores": psutil.cpu_count(logical=False),
            "cpu_load_1m": load_1m,
            "cpu_load_capacity_percent": load_percent,
            "apple_silicon": is_apple_silicon,
            "metal_memory_is_unified": is_apple_silicon,
            "nvidia_cuda": is_nvidia_linux,
        },
        "memory": {
            "total_bytes": memory.total,
            "available_bytes": memory.available,
            "used_percent": memory.percent,
            "swap_total_bytes": swap.total,
            "swap_used_bytes": swap.used,
            "swap_used_percent": swap.percent,
            "swap_metrics_available": swap_available,
            "recommended_model_budget_bytes": int(memory.total * 0.70),
        },
        "disk": disk,
        "huggingface": {
            "endpoint": hf_endpoint,
            "cache": hf_disk,
            "cli_installed": shutil.which("hf") is not None,
            "token_configured": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")),
            "network": network,
        },
        "components": components,
        "accelerator": nvidia if is_linux else {
            "status": "pass" if is_apple_silicon else "fail",
            "kind": "metal" if is_apple_silicon else None,
            "available": is_apple_silicon,
            "name": _sysctl("machdep.cpu.brand_string") if is_apple_silicon else None,
            "memory_model": "unified" if is_apple_silicon else None,
        },
        "metal": metal,
        "checks": checks,
        "recommendation": recommendation,
        "actions": actions,
    }
