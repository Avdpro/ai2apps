# SPDX-License-Identifier: Apache-2.0
"""Admin panel routes for oMLX server configuration.

This module provides HTTP routes for the admin panel including:
- Login/logout with API key authentication
- Dashboard for server monitoring
- Model settings management (per-model sampling parameters, pinning, default)
- Global settings management
"""

import asyncio
import inspect
import json
import logging
import mimetypes
import os
import re
import shutil
import signal
import sys
import time
from collections import deque
from contextlib import suppress
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, Literal, Optional
from urllib.parse import quote, urlsplit

import requests
import httpx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from ai2apps._version import __version__ as _ai2apps_version
from ai2apps.apps import SYSTEM_APP_MANIFESTS
from ai2apps.capabilities import operation_class
from ai2apps.coder import CoderError
from ai2apps.core import EntityIdKind, RepositoryError, new_entity_id
from ai2apps.extensions import ExtensionError
from ai2apps.model_providers import list_package_models
from ai2apps.terminal import TerminalServiceError
from ai2apps.web import I18N_DIR, STATIC_DIR, TEMPLATES_DIR
from omlx._version import __version__ as _omlx_version

from ..api.markitdown import MARKITDOWN_MODEL_ID, markitdown_model_visible
from ..api.openai_models import _coerce_tool_call_arguments
from ..api.utils import _try_parse_json
from ..model_profiles import EXCLUDED_FROM_PROFILES
from ..model_settings import merge_chat_template_kwargs
from ..settings import BURST_DECODE_MODES, SubKeyEntry, burst_decode_env
from .auth import (
    REMEMBER_ME_MAX_AGE,
    SESSION_MAX_AGE,
    compare_keys,
    create_session_token,
    require_admin,
    validate_api_key,
    verify_api_key,
    verify_session,
)

logger = logging.getLogger(__name__)
MOBILE_SESSION_COOKIE = "ai2apps_mobile_session"

PRESET_REMOTE_URL = "https://omlx.ai/assets/omlx_preset.json"


# =============================================================================
# Pydantic Models
# =============================================================================


class LoginRequest(BaseModel):
    """Request model for admin login."""

    api_key: str
    remember: bool = False


class SetupApiKeyRequest(BaseModel):
    """Request model for initial API key setup."""

    api_key: str
    api_key_confirm: str


class CreateSubKeyRequest(BaseModel):
    """Request model for creating a sub API key."""

    key: str
    name: str = ""


class DeleteSubKeyRequest(BaseModel):
    """Request model for deleting a sub API key."""

    key: str


class CreateTerminalSessionRequest(BaseModel):
    """Create one system-owned interactive terminal session."""

    title: str | None = Field(default=None, max_length=80)
    cwd: str | None = Field(default=None, max_length=4096)
    cols: int = Field(default=100, ge=20, le=1000)
    rows: int = Field(default=30, ge=5, le=500)


class CreateCoderProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    root_path: str = Field(min_length=1, max_length=4096)
    kind: Literal["general", "ai2apps"] = "general"
    create_directory: bool = False
    bootstrap: bool = False


class CreateCoderThreadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    agent: Literal["codex", "opencode", "claude"]
    model_source: Literal["default", "ai2apps"] = "default"
    model: str = Field(default="", max_length=500)
    parent_thread_id: str | None = None


class ForkCoderThreadRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)


class StartCoderDevSessionRequest(BaseModel):
    component_id: str = Field(min_length=1, max_length=256)


class SaveCoderFileRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    content: str = Field(max_length=2 * 1024 * 1024)


class CacheProbeRequest(BaseModel):
    """Request model for probing per-prompt cache state.

    Tokenizes a chat message list with the target model's tokenizer, then
    classifies each block's location in the cache hierarchy:
    - Hot SSD (in-RAM copy of SSD cache, ready to mount without disk read)
    - Disk SSD (persisted only, needs disk read to reuse)
    - Cold (fully uncached — would require full prefill)
    """

    model_id: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    chat_template_kwargs: dict[str, Any] | None = None
    thinking_budget: int | None = None


class ModelSettingsRequest(BaseModel):
    """Request model for updating per-model settings."""

    model_alias: str | None = None
    model_type_override: str | None = None
    max_context_window: int | None = None
    cache_moe_memory_tier: str | None = None
    kv_cache_policy: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    repetition_penalty: float | None = None
    min_p: float | None = None
    presence_penalty: float | None = None
    force_sampling: bool | None = None
    max_tool_result_tokens: int | None = None
    chat_template_kwargs: dict[str, Any] | None = None
    forced_ct_kwargs: list[str] | None = None
    ttl_seconds: int | None = None
    index_cache_freq: int | None = None
    enable_thinking: bool | None = None
    thinking_budget_enabled: bool | None = None
    thinking_budget_tokens: int | None = None
    # TurboQuant KV cache (mlx-vlm backend)
    turboquant_kv_enabled: bool | None = None
    turboquant_kv_bits: float | None = None
    # SpecPrefill (experimental)
    specprefill_enabled: bool | None = None
    specprefill_draft_model: str | None = None
    specprefill_keep_pct: float | None = None
    specprefill_threshold: int | None = None
    # DFlash (block diffusion speculative decoding)
    dflash_enabled: bool | None = None
    dflash_draft_model: str | None = None
    dflash_draft_quant_enabled: bool | None = None
    dflash_draft_quant_weight_bits: int | None = None
    dflash_draft_quant_activation_bits: int | None = None
    dflash_draft_quant_group_size: int | None = None
    dflash_max_ctx: int | None = None
    dflash_in_memory_cache: bool | None = None
    dflash_in_memory_cache_max_entries: int | None = None
    dflash_in_memory_cache_max_bytes: int | None = None
    dflash_ssd_cache: bool | None = None
    dflash_ssd_cache_max_bytes: int | None = None
    dflash_draft_window_size: int | None = None
    dflash_draft_sink_size: int | None = None
    dflash_verify_mode: str | None = None
    # Native MTP (mlx-lm PR 990 / PR 15 monkey-patch)
    mtp_enabled: bool | None = None
    # VLM MTP speculative decoding via external assistant drafter (mlx-vlm 191d7c8+)
    vlm_mtp_enabled: bool | None = None
    vlm_mtp_draft_model: str | None = None
    vlm_mtp_draft_block_size: int | None = None
    reasoning_parser: str | None = None
    guided_grammar_enabled: bool | None = None
    guided_grammar: str | None = None
    is_pinned: bool | None = None
    is_default: bool | None = None
    is_hidden: bool | None = None
    is_favorite: bool | None = None
    # Security: per-model opt-in for trust_remote_code (issue #926)
    trust_remote_code: bool | None = None


class CreateProfileRequest(BaseModel):
    """Request body for creating a per-model profile."""

    name: str
    display_name: str
    api_name: str | None = None
    description: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    also_save_as_template: bool = False
    source_template: str | None = None
    expose_as_model: bool = False


class UpdateProfileRequest(BaseModel):
    """Request body for updating/renaming a per-model profile."""

    new_name: str | None = None
    display_name: str | None = None
    api_name: str | None = None
    description: str | None = None
    settings: dict[str, Any] | None = None
    source_template: str | None = None
    expose_as_model: bool | None = None
    also_save_as_template: bool = False


class CreateTemplateRequest(BaseModel):
    """Request body for creating a global template."""

    name: str
    display_name: str
    description: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class UpdateTemplateRequest(BaseModel):
    """Request body for updating/renaming a global template."""

    new_name: str | None = None
    display_name: str | None = None
    description: str | None = None
    settings: dict[str, Any] | None = None


class GlobalSettingsRequest(BaseModel):
    """Request model for updating global server settings."""

    # Server settings
    host: str | None = None
    port: int | None = None
    log_level: str | None = None
    server_aliases: list[str] | None = None
    sse_keepalive_mode: str | None = None
    auto_start_on_launch: bool | None = None
    burst_decode_mode: str | None = None  # "off" / "light" / "balanced" / "aggressive"
    preserve_mid_system_cache: bool | None = None

    # Model settings
    model_dirs: list[str] | None = None
    model_dir: str | None = None  # Deprecated: kept for backward compatibility
    model_fallback: bool | None = None
    hide_helper_models: bool | None = None

    # Memory enforcement
    memory_prefill_memory_guard: bool | None = None
    memory_guard_tier: str | None = (
        None  # "safe" / "balanced" / "aggressive" / "custom"
    )
    memory_guard_custom_ceiling_gb: float | None = (
        None  # only used when tier == "custom"
    )

    # Scheduler settings
    max_concurrent_requests: int | None = None
    embedding_batch_size: int | None = None
    chunked_prefill: bool | None = None
    prefill_priority: str | None = None  # "context" | "speed"

    # Cache settings
    cache_enabled: bool | None = None
    ssd_cache_dir: str | None = None
    ssd_cache_max_size: str | None = None
    hot_cache_only: bool | None = None
    hot_cache_max_size: str | None = None  # "0" = disabled, "8GB", etc.
    initial_cache_blocks: int | None = None  # Starting blocks (requires restart)

    # MCP settings
    mcp_config: str | None = None

    # HuggingFace settings
    hf_endpoint: str | None = None
    hf_cache_enabled: bool | None = None

    # ModelScope settings
    ms_endpoint: str | None = None

    # Network settings
    network_http_proxy: str | None = None
    network_https_proxy: str | None = None
    network_no_proxy: str | None = None
    network_ca_bundle: str | None = None

    # Sampling defaults
    sampling_max_context_window: int | None = None
    sampling_max_context_window_policy: int | None = Field(default=None, ge=1)
    sampling_max_tokens: int | None = None
    sampling_temperature: float | None = None
    sampling_top_p: float | None = None
    sampling_top_k: int | None = None
    sampling_repetition_penalty: float | None = None

    # Claude Code settings
    claude_code_mode: str | None = None
    claude_code_opus_model: str | None = None
    claude_code_sonnet_model: str | None = None
    claude_code_haiku_model: str | None = None

    # Other integrations settings
    integrations_copilot_model: str | None = None
    integrations_codex_model: str | None = None
    integrations_opencode_model: str | None = None
    integrations_openclaw_model: str | None = None
    integrations_hermes_model: str | None = None
    integrations_pi_model: str | None = None
    integrations_openclaw_tools_profile: (
        Literal["minimal", "coding", "messaging", "full"] | None
    ) = None
    markitdown_enabled: bool | None = None
    markitdown_expose_model: bool | None = None
    markitdown_max_file_size_mb: int | None = None
    markitdown_max_files_per_request: int | None = None
    markitdown_pdf_processing_engine: str | None = None

    # UI settings
    ui_language: str | None = None

    # Idle timeout settings. null/0/"" disables the global fallback.
    idle_timeout_seconds: int | None = Field(default=None, ge=60)

    # Auth settings
    api_key: str | None = None
    skip_api_key_verification: bool | None = None

    @field_validator("idle_timeout_seconds", mode="before")
    @classmethod
    def _normalize_idle_timeout(cls, v):
        if v == "":
            return None
        if isinstance(v, int) and not isinstance(v, bool) and v == 0:
            return None
        return v


class HFDownloadRequest(BaseModel):
    """Request model for starting a HuggingFace model download."""

    repo_id: str
    hf_token: str = ""


class HFRetryRequest(BaseModel):
    """Request model for retrying a HuggingFace model download."""

    hf_token: str = ""


class AI2AppsInstallRequest(BaseModel):
    """Start a verified Cache-MoE model installation."""

    model_id: str
    weight_source: str = "huggingface"
    memory_tier: str = "auto"
    token: str = ""


class AI2AppsRetryRequest(BaseModel):
    token: str = ""


class FusionModelRequest(BaseModel):
    fusion: dict[str, Any]


class CloudProviderRequest(BaseModel):
    name: str = ""
    base_url: str = ""
    protocol: Literal["openai", "anthropic"] = "openai"
    models: list[str] | str = Field(default_factory=list)
    enabled: bool = True
    api_key: str | None = None


class CloudModelSelectionRequest(BaseModel):
    model_id: str
    enabled: bool


class DefaultModelRoutesRequest(BaseModel):
    routes: dict[str, str | None]


class MSDownloadRequest(BaseModel):
    """Request model for starting a ModelScope model download."""

    model_id: str
    ms_token: str = ""


class MSRetryRequest(BaseModel):
    """Request model for retrying a ModelScope model download."""

    ms_token: str = ""


class OQStartRequest(BaseModel):
    """Request model for starting an oQ quantization task."""

    model_path: str
    oq_level: float
    group_size: int = 64
    sensitivity_model_path: str = ""
    text_only: bool = False
    dtype: str = "bfloat16"
    preserve_mtp: bool = False
    auto_proxy_sensitivity: bool = True
    enhanced: bool = False
    imatrix_cache_path: str = ""
    imatrix_reuse_cache: bool = True
    imatrix_strict: bool = False
    imatrix_num_samples: int = 128
    imatrix_seq_length: int = 512
    mtp_assistant_model_path: str = ""


class HFUploadRequest(BaseModel):
    """Request model for starting a HuggingFace upload task."""

    model_path: str
    repo_id: str
    hf_token: str
    readme_source_path: str = ""
    auto_readme: bool = True
    redownload_notice: bool = False
    private: bool = False


class HFValidateTokenRequest(BaseModel):
    """Request model for validating a HuggingFace token."""

    hf_token: str


class ShellMountRequest(BaseModel):
    placement: Literal["inline", "sidebar"] = "inline"
    interaction_session_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class ShellSafeModeRequest(BaseModel):
    active: bool
    reason: str = Field(default="user-request", max_length=500)


class ShellPatchResolutionRequest(BaseModel):
    resolution: Literal["disable", "accept-upstream", "preserve-local"]
    candidate_digest: str | None = None


class ShellAgentRunRequest(BaseModel):
    session_id: str
    agent: str = "ai2apps.general-agent"
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    priority: int = Field(default=0, ge=-100, le=100)


class ShellCapabilityRequest(BaseModel):
    session_id: str | None = None
    mount_id: str | None = None
    capabilities: list[str] = Field(min_length=1, max_length=32)
    tool_name: str = Field(default="*", min_length=1, max_length=200)
    effects: list[str] = Field(default_factory=list, max_length=32)
    resource_selector: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=1000)
    timeout_seconds: int = Field(default=600, ge=30, le=3600)


class ShellApprovalDecisionRequest(BaseModel):
    decision: Literal["approve", "deny"]
    scope: Literal["once", "run", "session", "agent", "app"] = "once"
    duration_seconds: int | None = Field(default=None, ge=60, le=86400)
    resource_selector: dict[str, Any] | None = None


class ShellGrantRevokeRequest(BaseModel):
    reason: str = Field(default="user-revoked-from-system-control", min_length=1, max_length=500)


# =============================================================================
# Runtime Settings Application Functions
# =============================================================================


def _format_cache_size(size_bytes: int) -> str:
    """Format cache size in bytes to human-readable string (e.g., '100GB')."""
    gb = size_bytes / (1024**3)
    if gb >= 1:
        return f"{gb:.0f}GB"
    mb = size_bytes / (1024**2)
    return f"{mb:.0f}MB"


def _parse_hot_cache_max_size(value: str) -> int:
    """Parse hot cache max size. Hot cache does not support an auto sentinel."""
    from ..config import parse_size

    normalized = value.strip()
    if normalized.lower() == "auto":
        raise ValueError(
            "Invalid hot_cache_max_size: 'auto' is not supported; "
            "use '0' to disable or a size like '8GB'"
        )

    try:
        size = parse_size(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid hot_cache_max_size: {exc}") from exc

    if size < 0:
        raise ValueError(
            "Invalid hot_cache_max_size: must be '0' to disable "
            "or a non-negative size"
        )
    return size


_PAROQUANT_REASON = "Not supported on paroquant models yet (compatibility not verified)"


def _paroquant_compat_for_model(model_info: dict) -> tuple[bool, str]:
    """Detect whether a model is paroquant-quantized.

    Returns ``(is_paroquant, reason)``. ``is_paroquant`` is True iff
    ``config.json`` declares ``quantization_config.quant_method == "paroquant"``.
    Reason is the user-facing string surfaced as a tooltip/banner on the
    admin model settings modal when paroquant gates an experimental toggle.
    """
    import json
    from pathlib import Path

    model_path = model_info.get("model_path") or ""
    if not model_path:
        return False, ""
    cfg_path = Path(model_path) / "config.json"
    if not cfg_path.exists():
        return False, ""
    try:
        cfg = json.loads(cfg_path.read_text())
    except Exception:
        return False, ""
    qcfg = cfg.get("quantization_config") or {}
    method = (qcfg.get("quant_method") or "").lower()
    if method == "paroquant":
        return True, _PAROQUANT_REASON
    return False, ""


def _dflash_compat_for_model(model_info: dict) -> tuple[bool, str]:
    """Resolve dflash compatibility for an engine_pool model dict.

    Returns ``(False, "")`` when dflash-mlx is not installed so the UI hides
    the compat hint instead of pointing the user at an unrelated reason.
    """
    is_paro, paro_reason = _paroquant_compat_for_model(model_info)
    if is_paro:
        return False, paro_reason
    try:
        from ..engine.dflash import is_dflash_compatible
    except ImportError:
        return False, ""
    model_path = model_info.get("model_path") or ""
    if not model_path:
        return False, "model_path missing"
    return is_dflash_compatible(model_path)


def _entry_is_diffusion_model(entry) -> bool:
    model_type = (getattr(entry, "config_model_type", None) or "").lower()
    return model_type.replace("-", "_") == "diffusion_gemma"


def _sanitize_diffusion_settings_dict(settings: dict) -> None:
    """Clear unsupported diffusion-lane settings before ModelSettings parsing.

    Tool-calling settings (``max_tool_result_tokens``) are intentionally NOT
    cleared: tool calling is prompt-driven plus output parsing and works on
    the diffusion lane when a tool parser matches the chat template.
    """
    unsupported_none_fields = (
        "top_p",
        "top_k",
        "min_p",
        "repetition_penalty",
        "presence_penalty",
        "enable_thinking",
        "preserve_thinking",
        "thinking_budget_tokens",
        "reasoning_parser",
        "guided_grammar",
        "index_cache_freq",
        "specprefill_draft_model",
        "specprefill_keep_pct",
        "specprefill_threshold",
        "dflash_draft_model",
        "dflash_draft_quant_enabled",
        "dflash_draft_quant_weight_bits",
        "dflash_draft_quant_activation_bits",
        "dflash_draft_quant_group_size",
        "dflash_max_ctx",
        "dflash_draft_window_size",
        "dflash_draft_sink_size",
        "dflash_verify_mode",
        "vlm_mtp_draft_model",
        "vlm_mtp_draft_block_size",
    )
    for key in unsupported_none_fields:
        settings[key] = None

    settings["force_sampling"] = False
    settings["thinking_budget_enabled"] = False
    settings["guided_grammar_enabled"] = False
    settings["turboquant_kv_enabled"] = False
    settings["turboquant_kv_bits"] = 4
    settings["turboquant_skip_last"] = True
    settings["specprefill_enabled"] = False
    settings["dflash_enabled"] = False
    settings["dflash_in_memory_cache"] = True
    settings["dflash_in_memory_cache_max_entries"] = 4
    settings["dflash_in_memory_cache_max_bytes"] = 8 * 1024 * 1024 * 1024
    settings["dflash_ssd_cache"] = False
    settings["dflash_ssd_cache_max_bytes"] = 20 * 1024 * 1024 * 1024
    settings["mtp_enabled"] = False
    settings["vlm_mtp_enabled"] = False

    unsupported_ct_kwargs = {
        "enable_thinking",
        "reasoning_effort",
        "preserve_thinking",
    }
    kwargs = settings.get("chat_template_kwargs")
    if kwargs:
        filtered_kwargs = {
            k: v for k, v in kwargs.items() if k not in unsupported_ct_kwargs
        }
        settings["chat_template_kwargs"] = filtered_kwargs or None
    forced = settings.get("forced_ct_kwargs")
    if forced:
        allowed = set(settings.get("chat_template_kwargs") or {})
        filtered_forced = [
            k for k in forced if k not in unsupported_ct_kwargs and k in allowed
        ]
        settings["forced_ct_kwargs"] = filtered_forced or None


def _sanitize_diffusion_model_settings(settings) -> None:
    """Clear settings that the serial diffusion lane does not implement.

    ``max_tool_result_tokens`` is intentionally preserved — tool calling
    works on the diffusion lane (prompt-driven + output parsing).
    """
    settings.top_p = None
    settings.top_k = None
    settings.min_p = None
    settings.repetition_penalty = None
    settings.presence_penalty = None
    settings.force_sampling = False
    settings.enable_thinking = None
    settings.preserve_thinking = None
    settings.thinking_budget_enabled = False
    settings.thinking_budget_tokens = None
    settings.reasoning_parser = None
    settings.guided_grammar_enabled = False
    settings.guided_grammar = None

    unsupported_ct_kwargs = {
        "enable_thinking",
        "reasoning_effort",
        "preserve_thinking",
    }
    if settings.chat_template_kwargs:
        filtered_kwargs = {
            k: v
            for k, v in settings.chat_template_kwargs.items()
            if k not in unsupported_ct_kwargs
        }
        settings.chat_template_kwargs = filtered_kwargs or None
    if settings.forced_ct_kwargs:
        allowed = set(settings.chat_template_kwargs or {})
        filtered_forced = [
            k
            for k in settings.forced_ct_kwargs
            if k not in unsupported_ct_kwargs and k in allowed
        ]
        settings.forced_ct_kwargs = filtered_forced or None

    settings.index_cache_freq = None
    settings.turboquant_kv_enabled = False
    settings.turboquant_kv_bits = 4
    settings.turboquant_skip_last = True
    settings.specprefill_enabled = False
    settings.specprefill_draft_model = None
    settings.specprefill_keep_pct = None
    settings.specprefill_threshold = None
    settings.dflash_enabled = False
    settings.dflash_draft_model = None
    settings.dflash_draft_quant_enabled = None
    settings.dflash_draft_quant_weight_bits = None
    settings.dflash_draft_quant_activation_bits = None
    settings.dflash_draft_quant_group_size = None
    settings.dflash_max_ctx = None
    settings.dflash_in_memory_cache = True
    settings.dflash_in_memory_cache_max_entries = 4
    settings.dflash_in_memory_cache_max_bytes = 8 * 1024 * 1024 * 1024
    settings.dflash_ssd_cache = False
    settings.dflash_ssd_cache_max_bytes = 20 * 1024 * 1024 * 1024
    settings.dflash_draft_window_size = None
    settings.dflash_draft_sink_size = None
    settings.dflash_verify_mode = None
    settings.mtp_enabled = False
    settings.vlm_mtp_enabled = False
    settings.vlm_mtp_draft_model = None
    settings.vlm_mtp_draft_block_size = None


def _mtp_compat_for_model(model_info: dict) -> tuple[bool, str]:
    """Mirror of ``_dflash_compat_for_model`` for the native MTP toggle.

    Returns ``(compatible, reason)``. Reason is empty on success and
    suitable for surfacing to users (admin UI shows it under the toggle).

    The check is conservative: even when the config declares MTP layers
    we also peek at the safetensors weight index to verify that the
    converter actually preserved the MTP tensors, using the loader's
    ``_checkpoint_has_mtp_weights`` so native nextn layouts
    (``model.layers.<num_hidden_layers + i>.*``, e.g. GLM-5.2) count as
    present (issue #2326). Default mlx-lm converters strip ``mtp.*``;
    PR 990 ships a separate path that keeps them.
    """
    import json
    from pathlib import Path

    from ..utils.model_loading import (
        _checkpoint_has_mtp_weights,
        _has_mtp_heads,
        _is_mtp_compatible,
    )

    is_paro, paro_reason = _paroquant_compat_for_model(model_info)
    if is_paro:
        return False, paro_reason

    model_path = model_info.get("model_path") or ""
    if not model_path:
        return False, "model_path missing"
    cfg_path = Path(model_path) / "config.json"
    if not cfg_path.exists():
        return False, "config.json not found"
    try:
        cfg = json.loads(cfg_path.read_text())
    except Exception as e:
        return False, f"failed to read config: {e}"
    model_type = cfg.get("model_type")
    if not _has_mtp_heads(cfg):
        return False, "model has no MTP heads in config"
    if not _is_mtp_compatible(cfg, model_type):
        return False, (
            f"model_type={model_type!r} is not on the MTP whitelist "
            "(supported: qwen3_5*, qwen3_6*, deepseek_v4*, glm_moe_dsa)"
        )
    if not _checkpoint_has_mtp_weights(model_path):
        return False, (
            "Config declares MTP layers but the weight files contain neither "
            "mtp.* tensors nor native nextn layers. Re-convert from HF with a "
            "converter that preserves MTP weights."
        )
    return True, ""


def _apply_log_level_runtime(level: str) -> None:
    """Apply log level change at runtime to all oMLX loggers and handlers."""
    level_name = level.upper()
    log_level = (
        5 if level_name == "TRACE" else getattr(logging, level_name, logging.INFO)
    )

    # Update root logger level and all its handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in root_logger.handlers:
        handler.setLevel(log_level)

    # Update omlx-related loggers
    omlx_loggers = [
        "omlx",
        "omlx.scheduler",
        "omlx.paged_ssd_cache",
        "omlx.memory_monitor",
        "omlx.paged_cache",
        "omlx.prefix_cache",
        "omlx.engine_pool",
        "omlx.model_discovery",
        "omlx.engine_core",
        "omlx.engine",
        "omlx.server",
        "omlx.admin",
    ]

    for logger_name in omlx_loggers:
        logging.getLogger(logger_name).setLevel(log_level)

    # Also update uvicorn logger
    logging.getLogger("uvicorn").setLevel(log_level)
    logging.getLogger("uvicorn.access").setLevel(log_level)


async def _apply_model_dirs_runtime(model_dirs: list[str]) -> tuple[bool, str]:
    """
    Apply model directories change at runtime by re-scanning models.

    This will:
    1. Validate all directories
    2. Unload all currently loaded models
    3. Clear the entries dictionary
    4. Re-discover models from the new directories

    Returns:
        Tuple of (success, message)
    """
    from pathlib import Path

    from ..model_discovery import (
        model_directory_access_error,
        model_directory_write_error,
    )
    from ..server import _server_state

    if _server_state.engine_pool is None:
        return False, "Engine pool not initialized"

    if not model_dirs:
        return False, "At least one model directory is required"

    primary_path = Path(model_dirs[0]).expanduser().resolve()
    write_error = model_directory_write_error(primary_path, create=True)
    if write_error is not None:
        return False, write_error

    active_model_dirs = [str(primary_path)]
    for model_dir in model_dirs[1:]:
        model_path = Path(model_dir).expanduser().resolve()
        access_error = model_directory_access_error(model_path)
        if access_error is not None:
            logger.warning(
                "Skipping inaccessible model directory during runtime reload: %s",
                access_error,
            )
            continue
        active_model_dirs.append(str(model_path))

    pool = _server_state.engine_pool

    # Get pinned models from settings_manager
    pinned_models = []
    if _server_state.settings_manager is not None:
        pinned_models = _server_state.settings_manager.get_pinned_model_ids()

    # Unload all loaded models
    loaded_models = pool.get_loaded_model_ids()
    for model_id in loaded_models:
        try:
            await pool._unload_engine(model_id)
        except Exception as e:
            logger.warning(f"Error unloading {model_id}: {e}")

    # Clear entries
    pool._entries.clear()
    pool._current_model_memory = 0

    # Update downloader model directories
    global _hf_downloader, _ms_downloader, _oq_manager, _hf_uploader
    primary_dir = str(primary_path)
    if _hf_downloader is not None:
        _hf_downloader.update_model_dir(primary_dir)
    if _ms_downloader is not None:
        _ms_downloader.update_model_dir(primary_dir)

    # Update components that scan all model directories
    if _oq_manager is not None:
        _oq_manager.update_model_dirs(active_model_dirs)
    if _hf_uploader is not None:
        _hf_uploader.update_model_dirs(active_model_dirs)

    # Re-discover models from new directories
    try:
        pool.discover_models(active_model_dirs, pinned_models)
        if _server_state.settings_manager is not None:
            pool.apply_settings_overrides(_server_state.settings_manager)
    except Exception as e:
        return False, f"Failed to discover models: {e}"

    dir_count = len(active_model_dirs)
    return True, (
        f"Re-discovered {pool.model_count} models "
        f"from {dir_count} director{'ies' if dir_count > 1 else 'y'}"
    )


async def _reload_models() -> tuple[bool, str]:
    """
    Reload models: re-read model_settings.json, re-scan dirs, re-apply overrides,
    and preload pinned models.

    This does NOT re-read settings.json (global settings). It only refreshes
    the model inventory and per-model settings.

    Returns:
        Tuple of (success, message)
    """
    from ..server import _server_state

    if _server_state.engine_pool is None:
        return False, "Engine pool not initialized"

    global_settings = _get_global_settings()
    if global_settings is None:
        return False, "Global settings not initialized"

    # Re-read model_settings.json from disk
    settings_manager = _get_settings_manager()
    if settings_manager is not None:
        settings_manager._load()

    # Get current effective model dirs from global settings
    model_dirs = [str(d) for d in global_settings.get_effective_model_dirs()]

    # Unload all, re-discover, re-apply overrides
    success, msg = await _apply_model_dirs_runtime(model_dirs)
    if not success:
        return False, msg

    # Preload pinned models
    pool = _server_state.engine_pool
    if pool is not None:
        await pool.preload_pinned_models()

    return True, msg


async def _apply_memory_guard_tier_runtime(
    tier: str | None = None,
    custom_ceiling_gb: float | None = None,
) -> tuple[bool, str]:
    """
    Apply memory_guard_tier (and optionally custom ceiling) at runtime.

    Pushes both values into the running ProcessMemoryEnforcer, which
    recomputes static + dynamic ceilings on its next propagation tick.
    `tier` and `custom_ceiling_gb` can be passed together (Custom tier
    save) or independently.

    Returns:
        Tuple of (success, message)
    """
    from ..server import _server_state
    from ..settings import VALID_MEMORY_GUARD_TIERS

    enforcer = _server_state.process_memory_enforcer
    if enforcer is None:
        return False, "Process memory enforcer not initialized"

    changes = []
    if tier is not None:
        value = tier.strip().lower()
        if value not in VALID_MEMORY_GUARD_TIERS:
            return False, (
                f"Invalid memory_guard_tier: '{tier}' "
                f"(must be one of {sorted(VALID_MEMORY_GUARD_TIERS)})"
            )
        old_tier = enforcer.memory_guard_tier
        enforcer.memory_guard_tier = value
        changes.append(f"tier: {old_tier} -> {value}")
    if custom_ceiling_gb is not None:
        new_bytes = max(0, int(float(custom_ceiling_gb) * 1024**3))
        enforcer.memory_guard_custom_ceiling_bytes = new_bytes
        changes.append(f"custom_ceiling: {custom_ceiling_gb} GB")
    if not changes:
        return True, "(no change)"
    return True, "Memory guard updated — " + ", ".join(changes)


async def _apply_cache_settings_runtime(
    enabled: bool | None,
    ssd_cache_dir: str | None,
    ssd_cache_max_size: str | None,
    global_settings,
    hot_cache_max_size: str | None = None,
) -> tuple[bool, str]:
    """
    Apply cache settings at runtime.

    Updates the scheduler_config and unloads all models so they
    will use the new cache settings when reloaded.

    Returns:
        Tuple of (success, message)
    """
    from ..config import parse_size
    from ..server import _server_state

    if _server_state.engine_pool is None:
        return False, "Engine pool not initialized"

    pool = _server_state.engine_pool

    # Update scheduler config based on cache settings
    if enabled is False or (enabled is None and not global_settings.cache.enabled):
        pool._scheduler_config.paged_ssd_cache_dir = None
        pool._scheduler_config.paged_ssd_cache_max_size = 0
    else:
        # Cache is enabled
        if ssd_cache_dir is not None:
            pool._scheduler_config.paged_ssd_cache_dir = ssd_cache_dir
        elif global_settings.cache.ssd_cache_dir:
            pool._scheduler_config.paged_ssd_cache_dir = (
                global_settings.cache.ssd_cache_dir
            )
        else:
            # Use default cache dir
            pool._scheduler_config.paged_ssd_cache_dir = str(
                global_settings.cache.get_ssd_cache_dir(global_settings.base_path)
            )

        if ssd_cache_max_size is not None:
            # Handle "auto" value
            if ssd_cache_max_size.lower() == "auto":
                pool._scheduler_config.paged_ssd_cache_max_size = (
                    global_settings.cache.get_ssd_cache_max_size_bytes(
                        global_settings.base_path
                    )
                )
            else:
                pool._scheduler_config.paged_ssd_cache_max_size = parse_size(
                    ssd_cache_max_size
                )
        elif global_settings.cache.ssd_cache_max_size:
            # Use settings value (handles "auto")
            pool._scheduler_config.paged_ssd_cache_max_size = (
                global_settings.cache.get_ssd_cache_max_size_bytes(
                    global_settings.base_path
                )
            )
        elif global_settings.cache.ssd_cache_max_size:
            pool._scheduler_config.paged_ssd_cache_max_size = parse_size(
                global_settings.cache.ssd_cache_max_size
            )

    # Apply hot cache max size
    if hot_cache_max_size is not None:
        hot_bytes = _parse_hot_cache_max_size(hot_cache_max_size)
        old_hot = pool._scheduler_config.hot_cache_max_size
        pool._scheduler_config.hot_cache_max_size = hot_bytes
        if hot_bytes != old_hot:
            from ..utils.formatting import format_bytes

            old_str = "Off" if old_hot == 0 else format_bytes(old_hot)
            new_str = "Off" if hot_bytes == 0 else format_bytes(hot_bytes)
            logger.info(f"Hot cache max size changed: {old_str} -> {new_str}")
    elif global_settings.cache.hot_cache_max_size:
        pool._scheduler_config.hot_cache_max_size = (
            global_settings.cache.get_hot_cache_max_size_bytes()
        )
    if hasattr(pool, "configure_hot_cache_budget"):
        pool.configure_hot_cache_budget()

    # Unload all loaded models so they use new config when reloaded
    loaded_models = pool.get_loaded_model_ids()
    for model_id in loaded_models:
        try:
            await pool._unload_engine(model_id)
        except Exception as e:
            logger.warning(f"Error unloading {model_id}: {e}")

    return True, f"Cache settings updated. Unloaded {len(loaded_models)} models."


def _apply_sampling_settings_runtime(
    max_context_window: int | None,
    max_context_window_policy: int | None,
    max_context_window_policy_set: bool,
    max_tokens: int | None,
    temperature: float | None,
    top_p: float | None,
    top_k: int | None,
    repetition_penalty: float | None = None,
) -> tuple[bool, str]:
    """
    Apply sampling default settings at runtime.

    Updates _server_state.sampling which is used for all new API requests.

    Returns:
        Tuple of (success, message)
    """
    from ..server import _server_state

    changes = []

    if max_context_window is not None:
        _server_state.sampling.max_context_window = max_context_window
        changes.append(f"max_context_window={max_context_window}")

    if max_context_window_policy_set:
        _server_state.sampling.max_context_window_policy = max_context_window_policy
        changes.append(f"max_context_window_policy={max_context_window_policy}")

    if max_tokens is not None:
        _server_state.sampling.max_tokens = max_tokens
        changes.append(f"max_tokens={max_tokens}")

    if temperature is not None:
        _server_state.sampling.temperature = temperature
        changes.append(f"temperature={temperature}")

    if top_p is not None:
        _server_state.sampling.top_p = top_p
        changes.append(f"top_p={top_p}")

    if top_k is not None:
        _server_state.sampling.top_k = top_k
        changes.append(f"top_k={top_k}")

    if repetition_penalty is not None:
        _server_state.sampling.repetition_penalty = repetition_penalty
        changes.append(f"repetition_penalty={repetition_penalty}")

    if changes:
        return True, f"Sampling defaults updated: {', '.join(changes)}"
    return True, "No sampling changes"


# =============================================================================
# Router and Templates
# =============================================================================

router = APIRouter(prefix="/admin", tags=["admin"])
shell_router = APIRouter(tags=["apps"])
templates = Jinja2Templates(directory=TEMPLATES_DIR)
static_dir = STATIC_DIR
MOBILE_STATIC_FILES = frozenset({
    "favicon.svg",
    "css/mobile.css",
    "css/mobile_app.css",
    "css/mobile_chat.css",
    "css/tailwind.css",
    "css/dashboard.css",
    "css/account.css",
    "css/agents.css",
    "css/trust_center.css",
    "js/alpine.min.js",
    "js/account.js",
    "js/agent_manager.js",
    "js/dashboard.js",
    "js/lucide.min.js",
    "js/marked.umd.js",
    "js/mobile.js",
    "js/mobile_app.js",
    "js/mobile_chat.js",
    "js/purify.min.js",
    "js/trust_center.js",
    "omlx_preset.json",
    "img/integrations/claude.png",
    "img/integrations/codex.png",
    "img/integrations/copilot.svg",
    "img/integrations/hermes.svg",
    "img/integrations/openclaw.png",
    "img/integrations/opencode.png",
    "img/integrations/pi.svg",
    "fonts/inter/inter.css",
    "fonts/inter/inter-latin-300-normal.woff2",
    "fonts/inter/inter-latin-400-normal.woff2",
    "fonts/inter/inter-latin-500-normal.woff2",
    "fonts/inter/inter-latin-600-normal.woff2",
    "fonts/inter/inter-latin-700-normal.woff2",
    "fonts/inter/inter-latin-800-normal.woff2",
})


SYSTEM_APPS: tuple[dict[str, Any], ...] = tuple(
    {
        "id": manifest["id"],
        "name": manifest["name"],
        "description": manifest["description"],
        "category": manifest["navigation"]["category"],
        "icon": manifest["navigation"]["icon"],
        "entry_url": "",
        "singleton": manifest["instances"]["mode"] == "singleton",
        "presentation": manifest.get("presentation", {}),
    }
    for manifest in SYSTEM_APP_MANIFESTS
)

_SYSTEM_APPS_BY_ID = {app["id"]: app for app in SYSTEM_APPS}
_DASHBOARD_APP_TABS = {
    "ai2apps.dashboard": "status",
    "ai2apps.account": "account",
    "ai2apps.models": "models",
    "ai2apps.discover": "discover",
    "ai2apps.agents": "agents",
    "ai2apps.trust-center": "trust",
    "ai2apps.settings": "settings",
    "ai2apps.logs": "logs",
    "ai2apps.terminal": "terminal",
    "ai2apps.coder": "coder",
    "ai2apps.benchmark": "bench",
}
_DASHBOARD_APP_TEMPLATES = {
    "ai2apps.dashboard": "system_apps/dashboard.html",
    "ai2apps.account": "system_apps/account.html",
    "ai2apps.models": "system_apps/models.html",
    "ai2apps.discover": "system_apps/discover.html",
    "ai2apps.agents": "system_apps/agents.html",
    "ai2apps.trust-center": "system_apps/trust_center.html",
    "ai2apps.settings": "system_apps/settings.html",
    "ai2apps.logs": "system_apps/logs.html",
    "ai2apps.terminal": "system_apps/terminal.html",
    "ai2apps.coder": "system_apps/coder.html",
    "ai2apps.benchmark": "system_apps/benchmark.html",
}
_LEGACY_DASHBOARD_TAB_APPS = {
    tab: app_id for app_id, tab in _DASHBOARD_APP_TABS.items()
}
_HOST_APP_ENTRIES = {
    "ai2apps:system/dashboard": "/admin/app-content/ai2apps.dashboard",
    "ai2apps:system/account": "/admin/app-content/ai2apps.account",
    "ai2apps:system/models": "/admin/app-content/ai2apps.models",
    "ai2apps:system/discover": "/admin/app-content/ai2apps.discover",
    "ai2apps:system/agents": "/admin/app-content/ai2apps.agents",
    "ai2apps:system/trust-center": "/admin/app-content/ai2apps.trust-center",
    "ai2apps:system/settings": "/admin/app-content/ai2apps.settings",
    "ai2apps:system/logs": "/admin/app-content/ai2apps.logs",
    "ai2apps:system/terminal": "/admin/app-content/ai2apps.terminal",
    "ai2apps:system/coder": "/admin/app-content/ai2apps.coder",
    "ai2apps:system/benchmark": "/admin/app-content/ai2apps.benchmark",
    "ai2apps:system/chat": "/admin/chat?embedded=1",
    "ai2apps:mobile/chat": "/mobile/chat",
}


def _static_version(path: str) -> str:
    """Append file mtime as query string for cache busting."""
    file_path = static_dir / path
    if file_path.is_file():
        mtime = int(file_path.stat().st_mtime)
        return f"/admin/static/{path}?v={mtime}"
    return f"/admin/static/{path}"


templates.env.globals["static"] = _static_version


def _mobile_static_version(path: str) -> str:
    """Return a cache-busted URL from the narrow Mobile asset allowlist."""
    if path not in MOBILE_STATIC_FILES:
        raise ValueError("asset is not exposed by the Mobile Gateway")
    file_path = static_dir / path
    suffix = f"?v={int(file_path.stat().st_mtime)}" if file_path.is_file() else ""
    return f"/mobile/static/{path}{suffix}"


templates.env.globals["mobile_static"] = _mobile_static_version

templates.env.globals["version"] = _ai2apps_version
templates.env.globals["runtime_version"] = _omlx_version

# i18n defaults (English) — overridden once set_admin_getters is called
_i18n_dir = I18N_DIR
_en_locale: dict = {}
try:
    _en_locale = json.loads((_i18n_dir / "en.json").read_text(encoding="utf-8"))
except Exception:
    pass
templates.env.globals["t"] = lambda key: _en_locale.get(key, key)
templates.env.globals["locale_json"] = json.dumps(_en_locale, ensure_ascii=False)
templates.env.globals["current_lang"] = "en"


def _load_locale(language: str) -> dict:
    """Load locale dict and fill missing keys from English."""
    fallback = dict(_en_locale)
    path = _i18n_dir / f"{language}.json"
    if language == "en":
        return fallback
    try:
        locale = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            return json.loads((_i18n_dir / "en.json").read_text(encoding="utf-8"))
        except Exception:
            return {}
    fallback.update(locale)
    return fallback


def _make_t(locale: dict):
    """Return a Jinja2-compatible t() function for the given locale dict."""

    def t(key: str) -> str:
        return locale.get(key, key)

    return t


def _refresh_i18n_globals() -> None:
    """Reload i18n globals from current settings. Called on startup and language change."""
    lang = "en"
    try:
        settings = _get_global_settings() if _get_global_settings else None
        if settings:
            lang = settings.ui.language
    except Exception:
        pass
    locale = _load_locale(lang)
    templates.env.globals["t"] = _make_t(locale)
    templates.env.globals["locale_json"] = json.dumps(locale, ensure_ascii=False)
    templates.env.globals["current_lang"] = lang


# =============================================================================
# State Getters (set by server.py)
# =============================================================================

_get_server_state = None
_get_engine_pool = None
_get_settings_manager = None
_get_global_settings = None
_get_platform_runtime = None
_hf_downloader = None
_hf_downloader_error = ""
_ms_downloader = None
_ai2apps_installer = None
_oq_manager = None
_hf_uploader = None


def set_admin_getters(
    state_getter,
    pool_getter,
    settings_manager_getter,
    global_settings_getter,
    platform_runtime_getter=None,
):
    """
    Set the getter functions for accessing server state.

    This function must be called during server initialization to provide
    access to the server state objects.

    Args:
        state_getter: Function that returns the ServerState instance.
        pool_getter: Function that returns the EnginePool instance.
        settings_manager_getter: Function that returns the ModelSettingsManager.
        global_settings_getter: Function that returns the GlobalSettings.
    """
    global _get_server_state, _get_engine_pool, _get_settings_manager
    global _get_global_settings, _get_platform_runtime
    _get_server_state = state_getter
    _get_engine_pool = pool_getter
    _get_settings_manager = settings_manager_getter
    _get_global_settings = global_settings_getter
    _get_platform_runtime = platform_runtime_getter
    _refresh_i18n_globals()


def set_hf_downloader(downloader):
    """Set the HFDownloader instance for admin routes.

    Args:
        downloader: HFDownloader instance created during server initialization.
    """
    global _hf_downloader, _hf_downloader_error
    _hf_downloader = downloader
    _hf_downloader_error = ""


def set_hf_downloader_unavailable(error: str) -> None:
    """Record a recoverable HF dependency/initialization failure."""

    global _hf_downloader, _hf_downloader_error, _ai2apps_installer
    _hf_downloader = None
    _ai2apps_installer = None
    _hf_downloader_error = str(error).strip() or "Downloader initialization failed"


def _version_numbers(value: str) -> tuple[int, int, int]:
    numbers = [int(item) for item in re.findall(r"\d+", value)[:3]]
    return tuple((numbers + [0, 0, 0])[:3])


def _ai2apps_hf_preflight() -> dict[str, Any]:
    """Report dependency, cache and non-secret authentication readiness."""

    minimum = "1.19.0"
    try:
        installed_version = package_version("huggingface-hub")
        dependency_installed = True
    except PackageNotFoundError:
        installed_version = ""
        dependency_installed = False
    dependency_compatible = dependency_installed and (
        _version_numbers(installed_version) >= _version_numbers(minimum)
    )

    hf_home = Path(
        os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")
    ).expanduser()
    cache_path = Path(
        os.environ.get("HF_HUB_CACHE", hf_home / "hub")
    ).expanduser()
    writable_parent = cache_path
    while not writable_parent.exists() and writable_parent.parent != writable_parent:
        writable_parent = writable_parent.parent
    cache_writable = (
        writable_parent.exists()
        and writable_parent.is_dir()
        and os.access(writable_parent, os.W_OK)
    )

    token_path = Path(
        os.environ.get("HF_TOKEN_PATH", hf_home / "token")
    ).expanduser()
    try:
        token_file_configured = token_path.is_file() and token_path.stat().st_size > 0
    except OSError:
        token_file_configured = False
    token_configured = bool(
        os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        or token_file_configured
    )
    downloader_ready = _hf_downloader is not None
    issues = []
    if not dependency_installed:
        issues.append(
            {
                "code": "dependency_missing",
                "message": "Hugging Face support is not installed.",
                "action": (
                    "Install AI2Apps with pip, or run: "
                    "pip install 'huggingface-hub>=1.19.0'"
                ),
            }
        )
    elif not dependency_compatible:
        issues.append(
            {
                "code": "dependency_outdated",
                "message": (
                    f"huggingface-hub {installed_version} is too old; "
                    f"AI2Apps requires {minimum} or newer."
                ),
                "action": "Run: pip install -U 'huggingface-hub>=1.19.0'",
            }
        )
    if not cache_writable:
        issues.append(
            {
                "code": "cache_not_writable",
                "message": f"Hugging Face cache is not writable: {cache_path}",
                "action": "Choose a writable HF_HOME or HF_HUB_CACHE directory.",
            }
        )
    if dependency_compatible and not downloader_ready:
        issues.append(
            {
                "code": "downloader_unavailable",
                "message": (
                    _hf_downloader_error
                    or "Hugging Face downloader is not initialized."
                ),
                "action": "Restart AI2Apps after repairing the Python environment.",
            }
        )

    return {
        "ready": dependency_compatible and cache_writable and downloader_ready,
        "cli_required": False,
        "dependency": {
            "installed": dependency_installed,
            "version": installed_version or None,
            "minimum": minimum,
            "compatible": dependency_compatible,
        },
        "cache": {"path": str(cache_path), "writable": cache_writable},
        "authentication": {
            "status": "configured" if token_configured else "anonymous",
            "token_configured": token_configured,
            "required_for_public_models": False,
        },
        "downloader_initialized": downloader_ready,
        "issues": issues,
    }


def _get_ai2apps_installer():
    global _ai2apps_installer
    if _hf_downloader is None:
        raise HTTPException(status_code=503, detail="Downloader not initialized")
    if _ai2apps_installer is None:
        from ai2apps.model_installer import AI2AppsInstaller

        _ai2apps_installer = AI2AppsInstaller(_hf_downloader)
    return _ai2apps_installer


def set_ms_downloader(downloader):
    """Set the MSDownloader instance for admin routes.

    Args:
        downloader: MSDownloader instance created during server initialization.
    """
    global _ms_downloader
    _ms_downloader = downloader


def set_oq_manager(manager):
    """Set the OQManager instance for admin routes.

    Args:
        manager: OQManager instance created during server initialization.
    """
    global _oq_manager
    _oq_manager = manager


def set_hf_uploader(uploader):
    """Set the HFUploader instance for admin routes.

    Args:
        uploader: HFUploader instance created during server initialization.
    """
    global _hf_uploader
    _hf_uploader = uploader


# =============================================================================
# Helper Functions
# =============================================================================


def format_size(size_bytes: int) -> str:
    """
    Format a byte size as a human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Human-readable string (e.g., "1.5 GB").
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.1f} MB"
    elif size_bytes < 1024**4:
        return f"{size_bytes / 1024**3:.2f} GB"
    else:
        return f"{size_bytes / 1024**4:.2f} TB"


def get_ssd_disk_info(cache_dir: str) -> dict:
    """
    Get disk information for the SSD cache directory.

    Returns:
        Dictionary with total_bytes, total_formatted.
    """
    try:
        check_path = Path(cache_dir).expanduser().resolve()
        while not check_path.exists() and check_path.parent != check_path:
            check_path = check_path.parent
        stat = shutil.disk_usage(check_path)
        return {
            "total_bytes": stat.total,
            "total_formatted": format_size(stat.total),
        }
    except Exception as e:
        logger.warning(f"Failed to get disk info for {cache_dir}: {e}")
        return {
            "total_bytes": 0,
            "total_formatted": "Unknown",
        }


def get_system_memory_info() -> dict:
    """
    Get system memory information.

    Returns:
        Dictionary with total_bytes, total_formatted, auto_limit_bytes,
        and auto_limit_formatted (80% of total).
    """
    try:
        from ..utils import psutil_compat

        total_bytes = int(psutil_compat.get_total_memory())
    except Exception:
        total_bytes = 0

    auto_limit_bytes = int(total_bytes * 0.8)

    # Live values so the admin UI can preview the actual hard ceiling for any
    # tier (static_ceiling + dynamic_ceiling depend on these). Read on each
    # call — never cached.
    try:
        from ..utils import psutil_compat

        available_bytes = int(psutil_compat.virtual_memory().available)
    except Exception:
        available_bytes = 0
    try:
        from ..utils.proc_memory import get_phys_footprint

        omlx_phys_footprint_bytes = int(get_phys_footprint())
    except Exception:
        omlx_phys_footprint_bytes = 0

    # Effective Metal cap = sysctl iogpu.wired_limit_mb when set, else
    # Apple's max_recommended_working_set_size (~75% of RAM). The admin UI
    # compares this against the value oMLX wanted at start (static
    # ceiling) and warns when the cap is below the request.
    try:
        from ..process_memory_enforcer import get_effective_metal_cap_bytes

        iogpu_wired_limit_bytes = int(get_effective_metal_cap_bytes())
    except Exception:
        iogpu_wired_limit_bytes = 0
    omlx_wired_limit_request_bytes = 0
    try:
        from ..server import _server_state

        enforcer = getattr(_server_state, "process_memory_enforcer", None)
        if enforcer is not None:
            omlx_wired_limit_request_bytes = int(
                getattr(enforcer, "_metal_wired_limit_request", 0) or 0
            )
    except Exception:
        pass

    # Live macOS vm_stat layers so the admin dashboard can preview the
    # tier-aware ceiling (free + inactive + active * ratio). Zero on
    # non-macOS / call failure — JS falls back to available_bytes.
    free_memory_bytes = 0
    inactive_memory_bytes = 0
    active_memory_bytes = 0
    try:
        from ..utils import psutil_compat

        vm = psutil_compat.get_macos_vm_stats()
        if vm is not None:
            free_memory_bytes = int(vm.get("free", 0))
            inactive_memory_bytes = int(vm.get("inactive", 0))
            active_memory_bytes = int(vm.get("active", 0))
    except Exception:
        pass

    return {
        "total_bytes": total_bytes,
        "total_formatted": format_size(total_bytes),
        "auto_limit_bytes": auto_limit_bytes,
        "auto_limit_formatted": format_size(auto_limit_bytes),
        "available_bytes": available_bytes,
        "omlx_phys_footprint_bytes": omlx_phys_footprint_bytes,
        "iogpu_wired_limit_bytes": iogpu_wired_limit_bytes,
        "omlx_wired_limit_request_bytes": omlx_wired_limit_request_bytes,
        "free_memory_bytes": free_memory_bytes,
        "inactive_memory_bytes": inactive_memory_bytes,
        "active_memory_bytes": active_memory_bytes,
    }


# =============================================================================
# HTML Page Routes
# =============================================================================


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    Render the admin login page or setup page.

    If no API key is configured, the page will show the initial setup form.
    Otherwise, it shows the standard login form.

    Returns:
        HTML login/setup page.
    """
    # Redirect to dashboard if already authenticated
    from .auth import verify_session

    if verify_session(request):
        return RedirectResponse(url="/admin/dashboard", status_code=302)

    global_settings = _get_global_settings()

    # Skip login page when skip_api_key_verification is enabled
    if global_settings is not None and global_settings.auth.skip_api_key_verification:
        return RedirectResponse(url="/admin/dashboard", status_code=302)

    api_key_configured = bool(global_settings and global_settings.auth.api_key)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"api_key_configured": api_key_configured},
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, is_admin: bool = Depends(require_admin)):
    """Resolve the legacy dashboard URL to its independent system App."""
    requested_tab = request.query_params.get("tab")
    app_id = _LEGACY_DASHBOARD_TAB_APPS.get(
        requested_tab if isinstance(requested_tab, str) else "",
        "ai2apps.dashboard",
    )
    return _shell_response(request, app_id)


def _shell_response(
    request: Request,
    app_id: str,
    instance_id: str | None = None,
):
    """Render the Shell and let its authenticated catalog resolve the App."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,127}", app_id):
        raise HTTPException(status_code=404, detail="App not found")
    return templates.TemplateResponse(
        request,
        "shell.html",
        {
            "system_apps": SYSTEM_APPS,
            "initial_app_id": app_id,
            "initial_instance_id": instance_id,
        },
    )


async def _mobile_access_dependency(request: Request):
    return await _require_mobile_access(request)


@shell_router.get("/mobile", response_class=HTMLResponse)
async def mobile_shell(
    request: Request,
    access=Depends(_mobile_access_dependency),
):
    """Render the Mobile Shell for a local admin or device-scoped session."""
    del access
    return templates.TemplateResponse(request, "mobile.html", {})


@shell_router.get("/mobile/static/{path:path}")
async def mobile_static(path: str):
    """Serve only the assets required by the public Mobile Shell."""
    if path not in MOBILE_STATIC_FILES:
        raise HTTPException(status_code=404, detail="File not found")
    file_path = static_dir / path
    if not file_path.is_file() or not file_path.resolve().is_relative_to(static_dir.resolve()):
        raise HTTPException(status_code=404, detail="File not found")
    media_types = {
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".woff2": "font/woff2",
    }
    return FileResponse(
        file_path,
        media_type=media_types.get(file_path.suffix, "application/octet-stream"),
        headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )


@shell_router.get("/mobile/complete", response_class=HTMLResponse)
async def mobile_handoff_page(request: Request):
    """Render the one-use handoff receiver before a local session exists."""
    return templates.TemplateResponse(request, "mobile.html", {})


@shell_router.get("/apps/{app_id}", response_class=HTMLResponse)
async def system_app_shell(
    request: Request,
    app_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Open or switch to a singleton system App in the shared Shell."""
    return _shell_response(request, app_id)


@shell_router.get(
    "/apps/{app_id}/instances/{instance_id}", response_class=HTMLResponse
)
async def app_instance_shell(
    request: Request,
    app_id: str,
    instance_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Open one exact AppInstance through the shared Shell."""
    return _shell_response(request, app_id, instance_id)


def _shell_manager():
    runtime = _get_platform_runtime() if _get_platform_runtime is not None else None
    manager = None if runtime is None else runtime.extension_manager
    if manager is None:
        raise HTTPException(status_code=503, detail="App Runtime is unavailable")
    return manager


def _remote_manager():
    runtime = _get_platform_runtime() if _get_platform_runtime is not None else None
    manager = None if runtime is None else runtime.remote
    if manager is None:
        raise HTTPException(status_code=503, detail="Remote Access is unavailable")
    return manager


def _local_mobile_admin(request: Request) -> bool:
    settings = _get_global_settings() if _get_global_settings is not None else None
    return bool(settings and settings.auth.skip_api_key_verification) or verify_session(request)


async def _require_mobile_access(request: Request):
    if _local_mobile_admin(request):
        return {"local": True}
    manager = _remote_manager()
    session = await manager.authorize_session(request.cookies.get(MOBILE_SESSION_COOKIE))
    if session is None:
        raise HTTPException(status_code=401, detail="Mobile session is required")
    device = manager.require_device(session.device_id)
    expected = urlsplit(device.public_origin)
    if request.url.hostname != expected.hostname:
        raise HTTPException(status_code=403, detail="Mobile Host is not allowed")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin", "")
        if origin != device.public_origin:
            raise HTTPException(status_code=403, detail="Mobile Origin is not allowed")
    return session


def _mobile_mount_payload(manager, mount: dict[str, Any]) -> dict[str, Any]:
    payload = _shell_mount_payload(manager, mount)
    content_url = str(payload.get("content_url") or "")
    if content_url.startswith("/admin/app-content/"):
        payload["content_url"] = "/mobile/app-content/" + content_url.removeprefix("/admin/app-content/")
    elif content_url.startswith("/admin/chat"):
        payload["content_url"] = "/mobile/chat"
    return payload


def _shell_entry_payload(manager, instance_id: str) -> dict[str, Any]:
    entry = manager.instance_entry(instance_id)
    renderer = entry["renderer"]
    resource = str(entry["resource"])
    if renderer == "host":
        content_url = _HOST_APP_ENTRIES.get(resource)
        if content_url is None:
            raise HTTPException(status_code=422, detail="Unknown host App Entry")
    elif renderer in {"schema", "safe-html"}:
        content_url = f"/admin/app-view/{instance_id}/{renderer}"
    elif renderer == "sandbox":
        content_url = (
            f"/admin/api/shell/app-instances/{instance_id}/resources/"
            f"{quote(resource, safe='/')}"
        )
    else:
        raise HTTPException(status_code=422, detail="Unsupported App renderer")
    return {**entry, "content_url": content_url}


def _shell_mount_payload(manager, mount: dict[str, Any]) -> dict[str, Any]:
    renderer = mount["renderer"]
    resource = str(mount["resource"])
    instance_id = mount["app_instance_id"]
    mount_id = mount["id"]
    if renderer == "host":
        if resource == "ai2apps:generic-launcher":
            content_url = f"/admin/app-mini/{mount_id}/generic"
        elif mount.get("placement") == "mobile":
            content_url = _HOST_APP_ENTRIES.get(resource)
            if content_url is None or mount.get("source") != "builtin":
                raise HTTPException(
                    status_code=422, detail="Unsupported Mobile host renderer"
                )
        else:
            raise HTTPException(status_code=422, detail="Unsupported host mount")
    elif renderer in {"schema", "safe-html"}:
        content_url = (
            f"/admin/app-view/{instance_id}/{renderer}?mount_id="
            f"{quote(mount_id, safe='')}"
        )
    elif renderer == "sandbox":
        content_url = (
            f"/admin/api/shell/app-instances/{instance_id}/resources/"
            f"{quote(resource, safe='/')}?mount_id={quote(mount_id, safe='')}"
        )
    else:
        raise HTTPException(status_code=422, detail="Unsupported Mini-Entry renderer")
    return {**mount, "content_url": content_url}


def _shell_lifecycle_error(error: Exception):
    if isinstance(error, RepositoryError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, ExtensionError):
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "message": str(error)},
        ) from error
    if isinstance(error, ValueError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    if isinstance(error, RuntimeError):
        raise HTTPException(status_code=503, detail=str(error)) from error
    raise error


@router.get("/api/shell/apps")
async def shell_apps(is_admin: bool = Depends(require_admin)):
    """Return the authoritative enabled App catalog and live instances."""
    del is_admin
    return {"items": _shell_manager().list_apps()}


@router.get("/api/shell/account-status")
async def shell_account_status(is_admin: bool = Depends(require_admin)):
    """Return a non-sensitive Cloud account summary for the fixed Dock entry."""
    del is_admin
    runtime = _get_platform_runtime() if _get_platform_runtime is not None else None
    cloud = None if runtime is None else runtime.cloud
    if cloud is None:
        return {"state": "unavailable"}
    try:
        response = await cloud.request("GET", "/v1/auth/me")
    except Exception:
        logger.debug("Unable to refresh the Dock account summary", exc_info=True)
        return {"state": "unavailable"}
    try:
        if response.status_code == 401:
            return {"state": "signed_out"}
        if response.status_code != 200:
            return {"state": "unavailable"}
        payload = response.json()
    except (TypeError, ValueError):
        return {"state": "unavailable"}
    finally:
        await response.aclose()
    user = payload.get("user") if isinstance(payload, dict) else None
    if not isinstance(user, dict):
        return {"state": "unavailable"}
    points = user.get("points") if isinstance(user.get("points"), dict) else {}
    return {
        "state": "signed_in",
        "display_name": str(user.get("displayName") or user.get("email") or "AI2Apps Account"),
        "email": str(user.get("email") or ""),
        "points": str(points.get("total") or points.get("balance") or "0"),
    }


@router.get("/api/shell/app-suggestions")
async def shell_app_suggestions(
    q: str = "",
    is_admin: bool = Depends(require_admin),
):
    """Suggest manifest-declared Apps without granting auto-mount authority."""
    del is_admin
    return {"items": _shell_manager().suggest_apps(q[:2000])}


@router.post("/api/shell/apps/{app_key}/launch")
async def shell_launch_app(
    app_key: str,
    is_admin: bool = Depends(require_admin),
):
    """Launch or restore an App without exposing the model API key."""
    del is_admin
    manager = _shell_manager()
    try:
        instance, home, created = manager.launch_app(app_key)
        entry = _shell_entry_payload(manager, instance.id)
        return {
            **entry,
            "created": created,
            "home_session_id": None if home is None else home.id,
            "route_url": f"/apps/{app_key}/instances/{instance.id}",
        }
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@router.post("/api/shell/app-instances/{instance_id}/focus")
async def shell_focus_app(
    instance_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    manager = _shell_manager()
    try:
        manager.focus_instance(instance_id)
        return _shell_entry_payload(manager, instance_id)
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@router.get("/api/mobile/apps")
async def mobile_app_catalog(is_admin: bool = Depends(require_admin)):
    """Return the fail-closed catalog of explicit Mobile Ready Apps."""
    del is_admin
    return {"items": _shell_manager().list_mobile_apps()}


@router.get("/api/mobile/mounts")
async def mobile_mounts(is_admin: bool = Depends(require_admin)):
    """Restore active Mobile mounts for the authenticated local session."""
    del is_admin
    manager = _shell_manager()
    try:
        return {
            "items": [
                _shell_mount_payload(manager, mount)
                for mount in manager.list_mobile_mounts()
            ]
        }
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@router.post("/api/mobile/apps/{app_key}/open")
async def mobile_open_app(
    app_key: str,
    is_admin: bool = Depends(require_admin),
):
    """Launch or focus one App and return its durable Mobile mount."""
    del is_admin
    manager = _shell_manager()
    try:
        instance, home, created = manager.launch_app(app_key)
        mount = manager.mount_mobile(
            instance.id,
            context={"surface": "mobile", "requested_by": "mobile-shell"},
        )
        return {
            **_shell_mount_payload(manager, mount),
            "created": created,
            "home_session_id": None if home is None else home.id,
        }
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@router.post("/api/mobile/app-instances/{instance_id}/focus")
async def mobile_focus_app(
    instance_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Resume an existing Mobile Ready AppInstance and its Mobile mount."""
    del is_admin
    manager = _shell_manager()
    try:
        manager.focus_instance(instance_id)
        return _shell_mount_payload(manager, manager.mount_mobile(instance_id))
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@shell_router.post("/v1/mobile/session/exchange")
async def remote_mobile_session_exchange(request: Request, payload: dict[str, Any]):
    """Exchange a fragment-delivered handoff without exposing the Cloud JWT."""
    handoff = payload.get("handoff")
    if not isinstance(handoff, str) or not 24 <= len(handoff) <= 200:
        raise HTTPException(status_code=422, detail="Invalid mobile handoff")
    manager = _remote_manager()
    host = request.url.hostname
    device = next(
        (item for item in manager.repository.list() if urlsplit(item.public_origin).hostname == host),
        None,
    )
    if device is None:
        raise HTTPException(status_code=404, detail="Mobile device is unavailable")
    try:
        token, session = await manager.exchange_handoff(
            device_id=device.device_id, handoff=handoff
        )
    except Exception as error:
        from ai2apps.remote import RemoteAccessError, RemoteTokenError
        if isinstance(error, RemoteAccessError):
            raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": str(error)}) from error
        if isinstance(error, RemoteTokenError):
            raise HTTPException(status_code=401, detail="Mobile handoff was rejected") from error
        raise
    response = JSONResponse({"connected": True, "expiresAt": session.expires_at.isoformat()})
    response.set_cookie(
        MOBILE_SESSION_COOKIE, token, max_age=15 * 60, httponly=True,
        secure=True, samesite="strict", path="/",
    )
    return response


@shell_router.get("/v1/mobile/apps")
async def remote_mobile_app_catalog(access=Depends(_mobile_access_dependency)):
    del access
    return {"items": _shell_manager().list_mobile_apps()}


@shell_router.get("/v1/mobile/mounts")
async def remote_mobile_mounts(access=Depends(_mobile_access_dependency)):
    del access
    manager = _shell_manager()
    try:
        return {"items": [_mobile_mount_payload(manager, item) for item in manager.list_mobile_mounts()]}
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@shell_router.post("/v1/mobile/apps/{app_key}/open")
async def remote_mobile_open_app(app_key: str, access=Depends(_mobile_access_dependency)):
    del access
    manager = _shell_manager()
    try:
        instance, home, created = manager.launch_app(app_key)
        mount = manager.mount_mobile(instance.id, context={"surface": "mobile", "requested_by": "mobile-shell"})
        return {**_mobile_mount_payload(manager, mount), "created": created,
                "home_session_id": None if home is None else home.id}
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@shell_router.post("/v1/mobile/app-instances/{instance_id}/focus")
async def remote_mobile_focus_app(instance_id: str, access=Depends(_mobile_access_dependency)):
    del access
    manager = _shell_manager()
    try:
        manager.focus_instance(instance_id)
        return _mobile_mount_payload(manager, manager.mount_mobile(instance_id))
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@shell_router.delete("/v1/mobile/mounts/{mount_id}")
async def remote_mobile_unmount(mount_id: str, access=Depends(_mobile_access_dependency)):
    del access
    try:
        return _shell_manager().unmount(mount_id)
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@shell_router.get("/mobile/app-content/{app_id}", response_class=HTMLResponse)
async def remote_mobile_app_content(
    request: Request, app_id: str, access=Depends(_mobile_access_dependency)
):
    del access
    return _system_app_content_response(
        request, app_id, include_api_key=False, mobile_surface=True
    )


@shell_router.get("/mobile/chat", response_class=HTMLResponse)
async def remote_mobile_chat(
    request: Request, access=Depends(_mobile_access_dependency)
):
    del access
    return templates.TemplateResponse(
        request,
        "mobile_chat.html",
        {},
        headers={
            "Content-Security-Policy": (
                "default-src 'self'; frame-ancestors 'self'; object-src 'none'; "
                "base-uri 'none'; form-action 'none'"
            )
        },
    )


def _mobile_internal_headers() -> dict[str, str]:
    state = _get_server_state() if _get_server_state is not None else None
    key = None if state is None else state.api_key
    return {} if key is None else {"Authorization": f"Bearer {key}"}


async def _mobile_platform_proxy(
    request: Request,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    """Call one allowlisted Platform API from the cookie-authenticated gateway."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=request.app),
        base_url="http://ai2apps.mobile.internal",
        headers={**_mobile_internal_headers(), **(headers or {})},
        timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10),
    ) as client:
        response = await client.request(method, f"/v1/platform{path}", json=payload)
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("content-type", "application/json"),
        headers={"Cache-Control": "no-store"},
    )


@shell_router.get("/v1/mobile/chat/state")
async def remote_mobile_chat_state(
    request: Request, access=Depends(_mobile_access_dependency)
):
    del access
    return await _mobile_platform_proxy(request, "GET", "/chat")


@shell_router.get("/v1/mobile/chat/threads")
async def remote_mobile_chat_threads(
    request: Request, access=Depends(_mobile_access_dependency)
):
    del access
    return await _mobile_platform_proxy(request, "GET", "/chat/threads")


@shell_router.post("/v1/mobile/chat/threads")
async def remote_mobile_create_chat_thread(
    request: Request,
    payload: dict[str, Any],
    access=Depends(_mobile_access_dependency),
):
    del access
    safe = {
        "title": str(payload.get("title", ""))[:160],
        "session_metadata": {"surface": "mobile"},
    }
    return await _mobile_platform_proxy(request, "POST", "/chat/threads", payload=safe)


@shell_router.get("/v1/mobile/chat/threads/{thread_id}/content")
async def remote_mobile_chat_thread_content(
    request: Request, thread_id: str, access=Depends(_mobile_access_dependency)
):
    del access
    return await _mobile_platform_proxy(
        request, "GET", f"/chat/threads/{quote(thread_id, safe='')}/content"
    )


@shell_router.put("/v1/mobile/chat/threads/{thread_id}/content")
async def remote_mobile_replace_chat_thread_content(
    request: Request,
    thread_id: str,
    payload: dict[str, Any],
    access=Depends(_mobile_access_dependency),
):
    del access
    messages = payload.get("messages")
    if not isinstance(messages, list) or len(messages) > 1000:
        raise HTTPException(status_code=422, detail="Mobile chat messages are invalid")
    if (
        len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        > 40 * 1024 * 1024
    ):
        raise HTTPException(status_code=413, detail="Mobile chat content is too large")
    forwarded = {
        "expected_revision": payload.get("expected_revision"),
        "title": None if payload.get("title") is None else str(payload["title"])[:160],
        "session_metadata": payload.get("session_metadata", {}),
        "messages": messages,
    }
    return await _mobile_platform_proxy(
        request,
        "PUT",
        f"/chat/threads/{quote(thread_id, safe='')}/content",
        payload=forwarded,
    )


@shell_router.post("/v1/mobile/chat/threads/{thread_id}/attachments")
async def remote_mobile_chat_attachment(
    request: Request,
    thread_id: str,
    payload: dict[str, Any],
    access=Depends(_mobile_access_dependency),
):
    del access
    data = payload.get("data")
    if not isinstance(data, str) or len(data) > 35 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Mobile attachment is too large")
    forwarded = {
        "filename": str(payload.get("filename", ""))[:512],
        "media_type": str(payload.get("media_type", "application/octet-stream"))[:255],
        "data": data,
        "metadata": {"surface": "mobile"},
    }
    return await _mobile_platform_proxy(
        request,
        "POST",
        f"/sessions/{quote(thread_id, safe='')}/attachments",
        payload=forwarded,
    )


@shell_router.get("/v1/mobile/agents")
async def remote_mobile_agents(
    request: Request, access=Depends(_mobile_access_dependency)
):
    del access
    return await _mobile_platform_proxy(request, "GET", "/agents")


@shell_router.post("/v1/mobile/chat/threads/{thread_id}/agent-runs")
async def remote_mobile_create_agent_run(
    request: Request,
    thread_id: str,
    payload: dict[str, Any],
    access=Depends(_mobile_access_dependency),
):
    del access
    agent = payload.get("agent", "ai2apps.general-agent")
    run_input = payload.get("input")
    if not isinstance(agent, str) or not isinstance(run_input, dict):
        raise HTTPException(status_code=422, detail="Mobile Agent request is invalid")
    return await _mobile_platform_proxy(
        request,
        "POST",
        f"/sessions/{quote(thread_id, safe='')}/agent-runs",
        payload={"agent": agent, "input": run_input},
        headers={"Idempotency-Key": f"mobile:{thread_id}:{time.time_ns()}"},
    )


@shell_router.get("/v1/mobile/agent-runs/{run_id}")
async def remote_mobile_agent_run(
    request: Request, run_id: str, access=Depends(_mobile_access_dependency)
):
    del access
    return await _mobile_platform_proxy(
        request, "GET", f"/agent-runs/{quote(run_id, safe='')}"
    )


@shell_router.get("/v1/mobile/models")
async def remote_mobile_models(
    request: Request, access=Depends(_mobile_access_dependency)
):
    del access
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=request.app),
        base_url="http://ai2apps.mobile.internal",
        headers=_mobile_internal_headers(),
    ) as client:
        response = await client.get("/v1/models")
    return Response(
        content=response.content, status_code=response.status_code,
        media_type=response.headers.get("content-type", "application/json"),
    )


@shell_router.post("/v1/mobile/chat/completions")
async def remote_mobile_chat_completions(
    request: Request,
    payload: dict[str, Any],
    access=Depends(_mobile_access_dependency),
):
    """Forward a bounded chat request without exposing the local API key."""
    del access
    messages = payload.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 100:
        raise HTTPException(status_code=422, detail="Mobile chat messages are invalid")
    model = payload.get("model")
    if not isinstance(model, str) or not model.strip():
        raise HTTPException(status_code=422, detail="Mobile chat model is required")
    try:
        max_tokens = int(payload.get("max_tokens", 4096))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Mobile chat max_tokens is invalid")
    if max_tokens <= 0:
        raise HTTPException(status_code=422, detail="Mobile chat max_tokens is invalid")
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > 1024 * 1024:
        raise HTTPException(status_code=413, detail="Mobile chat request is too large")
    forwarded = {
        "model": model.strip(), "messages": messages, "stream": True,
        "temperature": payload.get("temperature", 0.7),
        "max_tokens": min(max_tokens, 8192),
    }
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=request.app),
        base_url="http://ai2apps.mobile.internal",
        headers={**_mobile_internal_headers(), "Accept": "text/event-stream"},
        timeout=httpx.Timeout(connect=10, read=3600, write=30, pool=10),
    )
    upstream = await client.send(
        client.build_request("POST", "/v1/chat/completions", json=forwarded),
        stream=True,
    )
    if upstream.status_code >= 400:
        body = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        return Response(content=body, status_code=upstream.status_code,
                        media_type=upstream.headers.get("content-type", "application/json"))

    async def stream_body():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_body(), media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/api/shell/app-instances/{instance_id}/suspend")
async def shell_suspend_app(
    instance_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        instance = _shell_manager().suspend_instance(instance_id)
        return {"instance_id": instance.id, "status": instance.status.value}
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@router.delete("/api/shell/app-instances/{instance_id}")
async def shell_close_app(
    instance_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        instance = _shell_manager().close_instance(instance_id)
        return {"instance_id": instance.id, "status": instance.status.value}
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@router.get("/api/shell/app-instances/{instance_id}/entry")
async def shell_instance_entry(
    instance_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return _shell_entry_payload(_shell_manager(), instance_id)
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@router.post("/api/shell/app-instances/{instance_id}/mounts")
async def shell_mount_app(
    instance_id: str,
    request: ShellMountRequest,
    is_admin: bool = Depends(require_admin),
):
    """Create a durable Mini-Entry mount for a conversation surface."""
    del is_admin
    manager = _shell_manager()
    try:
        mount = manager.mount(
            instance_id,
            mini=True,
            placement=request.placement,
            interaction_session_id=request.interaction_session_id,
            context=request.context,
        )
        return _shell_mount_payload(manager, mount)
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@router.get("/api/shell/sessions/{session_id}/mounts")
async def shell_session_mounts(
    session_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    manager = _shell_manager()
    try:
        return {
            "items": [
                _shell_mount_payload(manager, mount)
                for mount in manager.list_mounts(session_id)
            ]
        }
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@router.delete("/api/shell/app-mounts/{mount_id}")
async def shell_unmount_app(
    mount_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return _shell_manager().unmount(mount_id)
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@router.post("/api/shell/app-instances/{instance_id}/agent-runs")
async def shell_create_agent_run(
    instance_id: str,
    request: ShellAgentRunRequest,
    is_admin: bool = Depends(require_admin),
):
    """Create an AgentRun only for a Session owned or mounted by this App."""
    del is_admin
    runtime = _get_platform_runtime() if _get_platform_runtime is not None else None
    manager = _shell_manager()
    if runtime is None or runtime.agents is None or runtime.agent_runtime is None:
        raise HTTPException(status_code=503, detail="Agent Runtime is unavailable")
    try:
        if not manager.instance_can_use_session(instance_id, request.session_id):
            raise HTTPException(status_code=403, detail="Session is outside App scope")
        run, created = runtime.agents.create_run(
            session_id=request.session_id,
            agent_key=request.agent,
            input={
                **request.input,
                "_invoking_app_instance_id": instance_id,
            },
            idempotency_key=request.idempotency_key,
            priority=request.priority,
        )
        runtime.agent_runtime.wake()
        return {
            "id": run.id,
            "created": created,
            "status": run.status.value,
            "session_id": run.session_id,
            "agent_definition_id": run.agent_definition_id,
            "event_stream_url": f"/v1/platform/agent-runs/{run.id}/events",
        }
    except RepositoryError as error:
        _shell_lifecycle_error(error)


@router.get("/api/shell/control")
async def shell_control_snapshot(is_admin: bool = Depends(require_admin)):
    del is_admin
    return _shell_manager().control_snapshot()


def _grant_payload(item) -> dict[str, Any]:
    return {
        "id": item.id,
        "scope": item.scope.value,
        "scope_id": item.scope_id,
        "agent_definition_id": item.agent_definition_id,
        "session_id": item.session_id,
        "app_instance_id": item.app_instance_id,
        "capabilities": list(item.capabilities),
        "tool_pattern": item.tool_pattern,
        "resource_selector": item.resource_selector,
        "issued_by": item.issued_by,
        "evidence": item.evidence,
        "expires_at": item.expires_at,
        "revoked_at": item.revoked_at,
        "revoke_reason": item.revoke_reason,
        "created_at": item.created_at,
        "active": item.active,
    }


def _capability_request_payload(item, *, app_name: str | None = None) -> dict[str, Any]:
    return {
        "id": item.id,
        "source_kind": item.subject_kind,
        "app_instance_id": item.app_instance_id,
        "session_id": item.session_id,
        "run_id": item.run_id,
        "title": app_name or "App capability request",
        "prompt": item.reason,
        "capabilities": list(item.capabilities),
        "tool_name": item.tool_name,
        "effects": list(item.effects),
        "resource_selector": item.resource_selector,
        "risk_level": item.risk_level,
        "operation_class": operation_class(item.effects),
        "status": item.status.value,
        "requested_by": item.requested_by,
        "decision_scope": item.decision_scope,
        "decision_evidence": item.decision_evidence,
        "grant_lease_id": item.grant_lease_id,
        "deadline_at": item.deadline_at,
        "created_at": item.created_at,
        "resolved_at": item.resolved_at,
    }


def _shell_approval_items(runtime, *, include_resolved: bool) -> list[dict[str, Any]]:
    assert runtime.database is not None and runtime.capabilities is not None
    direct = runtime.capabilities.list_requests(include_resolved=include_resolved)
    app_names: dict[str, str] = {}
    with runtime.database.transaction() as connection:
        rows = connection.execute(
            """SELECT i.*, r.session_id, r.agent_definition_id,
                      s.app_instance_id, a.display_name AS agent_name,
                      d.display_name AS app_name
               FROM agent_interactions i
               JOIN agent_runs r ON r.id = i.run_id
               JOIN sessions s ON s.id = r.session_id
               JOIN agent_definitions a ON a.id = r.agent_definition_id
               JOIN app_instances ai ON ai.id = s.app_instance_id
               JOIN app_definitions d ON d.id = ai.app_definition_id
               WHERE i.kind = 'approval'
                 AND (? OR i.status = 'pending')
               ORDER BY i.created_at DESC""",
            (int(include_resolved),),
        ).fetchall()
        for request in direct:
            name = connection.execute(
                """SELECT d.display_name FROM app_instances i
                   JOIN app_definitions d ON d.id=i.app_definition_id
                   WHERE i.id=?""",
                (request.app_instance_id,),
            ).fetchone()
            app_names[request.app_instance_id] = (
                request.app_instance_id if name is None else name["display_name"]
            )
    items = [
        _capability_request_payload(
            request, app_name=app_names.get(request.app_instance_id)
        )
        for request in direct
    ]
    for row in rows:
        request = json.loads(row["request_json"])
        effects = tuple(request.get("effects", []))
        items.append(
            {
                "id": row["id"],
                "source_kind": "agent_run",
                "app_instance_id": row["app_instance_id"],
                "session_id": row["session_id"],
                "run_id": row["run_id"],
                "title": row["agent_name"],
                "app_name": row["app_name"],
                "prompt": row["prompt"],
                "capabilities": request.get("capabilities", []),
                "tool_name": request.get("tool_name", "*"),
                "effects": list(effects),
                "resource_selector": request.get("resource_selector", {}),
                "risk_level": runtime.capabilities.risk_level(effects),
                "operation_class": operation_class(effects),
                "action_preview": request.get("action_preview", {}),
                "status": row["status"],
                "requested_by": "agent-runtime",
                "decision_scope": (
                    None
                    if row["response_json"] is None
                    else json.loads(row["response_json"]).get("scope")
                ),
                "decision_evidence": {},
                "grant_lease_id": None,
                "deadline_at": row["deadline_at"],
                "created_at": row["created_at"],
                "resolved_at": row["resolved_at"],
            }
        )
    return sorted(items, key=lambda item: str(item["created_at"]), reverse=True)


@router.post("/api/shell/app-instances/{instance_id}/capability-requests")
async def shell_create_capability_request(
    instance_id: str,
    request: ShellCapabilityRequest,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    runtime = _get_platform_runtime() if _get_platform_runtime is not None else None
    if runtime is None or runtime.capabilities is None or runtime.database is None:
        raise HTTPException(status_code=503, detail="Capability Runtime is unavailable")
    try:
        session_id = request.session_id
        if session_id is None and request.mount_id is not None:
            mount = _shell_manager().mount_entry(request.mount_id)
            if mount["app_instance_id"] != instance_id:
                raise HTTPException(status_code=403, detail="Mount is outside App scope")
            session_id = mount["interaction_session_id"]
        if session_id is None:
            with runtime.database.transaction() as connection:
                home = connection.execute(
                    """SELECT id FROM sessions WHERE app_instance_id=?
                       AND status='active' ORDER BY created_at LIMIT 1""",
                    (instance_id,),
                ).fetchone()
            session_id = None if home is None else home["id"]
        if session_id is None:
            raise HTTPException(status_code=409, detail="App has no active Session")
        item = runtime.capabilities.create_app_request(
            app_instance_id=instance_id,
            session_id=session_id,
            capabilities=tuple(request.capabilities),
            tool_name=request.tool_name,
            effects=tuple(request.effects),
            resource_selector=request.resource_selector,
            reason=request.reason,
            timeout_seconds=request.timeout_seconds,
        )
        return _capability_request_payload(item)
    except (RepositoryError, ValueError) as error:
        _shell_lifecycle_error(error)


@router.get("/api/shell/approvals")
async def shell_approval_inbox(
    include_resolved: bool = False,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    runtime = _get_platform_runtime() if _get_platform_runtime is not None else None
    if runtime is None or runtime.capabilities is None or runtime.database is None:
        raise HTTPException(status_code=503, detail="Capability Runtime is unavailable")
    return {"items": _shell_approval_items(runtime, include_resolved=include_resolved)}


@router.post("/api/shell/approvals/{approval_id}/decide")
async def shell_decide_approval(
    approval_id: str,
    request: ShellApprovalDecisionRequest,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    runtime = _get_platform_runtime() if _get_platform_runtime is not None else None
    if (
        runtime is None
        or runtime.capabilities is None
        or runtime.agents is None
        or runtime.agent_runtime is None
        or runtime.database is None
    ):
        raise HTTPException(status_code=503, detail="Capability Runtime is unavailable")
    try:
        if approval_id.startswith(EntityIdKind.CAPABILITY_REQUEST.prefix):
            item, lease = runtime.capabilities.decide_app_request(
                approval_id,
                decision=request.decision,
                scope=request.scope,
                duration_seconds=request.duration_seconds,
                resource_selector=request.resource_selector,
            )
            return {
                "request": _capability_request_payload(item),
                "grant": None if lease is None else _grant_payload(lease),
            }
        with runtime.database.transaction() as connection:
            interaction = connection.execute(
                """SELECT i.run_id,i.kind,i.status FROM agent_interactions i
                   WHERE i.id=?""",
                (approval_id,),
            ).fetchone()
        if interaction is None or interaction["kind"] != "approval":
            raise HTTPException(status_code=404, detail="Approval request not found")
        scope = request.scope
        runtime.agents.respond_interaction(
            interaction["run_id"],
            approval_id,
            response={
                "decision": request.decision,
                **({"scope": scope} if request.decision == "approve" else {}),
            },
            response_id=new_entity_id(EntityIdKind.CAPABILITY_DECISION),
        )
        runtime.agent_runtime.wake()
        run = runtime.agents.get_run(interaction["run_id"])
        return {
            "request": {
                "id": approval_id,
                "source_kind": "agent_run",
                "run_id": run.id,
                "status": "approved" if request.decision == "approve" else "denied",
                "decision_scope": scope if request.decision == "approve" else None,
            },
            "grant": None,
            "run_status": run.status.value,
        }
    except (RepositoryError, ValueError) as error:
        _shell_lifecycle_error(error)


@router.get("/api/shell/grant-leases")
async def shell_grant_leases(
    include_inactive: bool = False,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    runtime = _get_platform_runtime() if _get_platform_runtime is not None else None
    if runtime is None or runtime.capabilities is None:
        raise HTTPException(status_code=503, detail="Capability Runtime is unavailable")
    return {
        "items": [
            _grant_payload(item)
            for item in runtime.capabilities.list_leases(
                include_inactive=include_inactive
            )
        ]
    }


@router.post("/api/shell/grant-leases/{lease_id}/revoke")
async def shell_revoke_grant(
    lease_id: str,
    request: ShellGrantRevokeRequest,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    runtime = _get_platform_runtime() if _get_platform_runtime is not None else None
    if runtime is None or runtime.capabilities is None:
        raise HTTPException(status_code=503, detail="Capability Runtime is unavailable")
    try:
        return _grant_payload(
            runtime.capabilities.revoke_lease(lease_id, reason=request.reason)
        )
    except RepositoryError as error:
        _shell_lifecycle_error(error)


@router.post("/api/shell/safe-mode")
async def shell_safe_mode(
    request: ShellSafeModeRequest,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        runtime = _get_platform_runtime() if _get_platform_runtime is not None else None
        if runtime is None:
            raise HTTPException(status_code=503, detail="Platform Runtime is unavailable")
        return await runtime.set_safe_mode(request.active, request.reason)
    except (ExtensionError, RuntimeError) as error:
        _shell_lifecycle_error(error)


@router.post("/api/shell/local-patches/{patch_id}/resolve")
async def shell_resolve_patch(
    patch_id: str,
    request: ShellPatchResolutionRequest,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        result = _shell_manager().resolve_patch_and_activate(
            patch_id,
            request.resolution,
            candidate_digest=request.candidate_digest,
        )
        item = result["patch"]
        package = result["package"]
        return {
            "id": item.id,
            "status": item.status.value,
            "base_digest": item.base_digest,
            "activated": result["activated"],
            "package_digest": package.digest,
            "package_status": package.status.value,
            "pending_conflicts": result["pending_conflicts"],
        }
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)


@router.get("/api/shell/app-instances/{instance_id}/resources/{resource:path}")
async def shell_app_resource(
    request: Request,
    instance_id: str,
    resource: str,
    mount_id: str | None = None,
    is_admin: bool = Depends(require_admin),
):
    """Serve one digest-verified resource from an active installed App."""
    del is_admin
    manager = _shell_manager()
    try:
        entry = (
            manager.mount_entry(mount_id)
            if mount_id is not None
            else manager.instance_entry(instance_id)
        )
        if mount_id is not None and entry["app_instance_id"] != instance_id:
            raise HTTPException(status_code=409, detail="Mount instance changed")
        path = manager.resolve_app_resource(instance_id, resource)
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if entry["renderer"] == "sandbox" and resource == entry["resource"]:
        origin = str(request.base_url).rstrip("/")
        headers["Content-Security-Policy"] = (
            "sandbox allow-scripts allow-forms allow-downloads; "
            f"default-src 'none'; script-src {origin} 'unsafe-inline'; "
            f"style-src {origin} 'unsafe-inline'; "
            f"img-src {origin} data: blob:; font-src {origin}; connect-src 'none'; "
            "form-action 'none'; base-uri 'none'"
        )
    return FileResponse(path, media_type=media_type, headers=headers)


@router.get("/app-view/{instance_id}/{renderer}", response_class=HTMLResponse)
async def shell_constrained_view(
    request: Request,
    instance_id: str,
    renderer: Literal["schema", "safe-html"],
    mount_id: str | None = None,
    is_admin: bool = Depends(require_admin),
):
    """Render trusted host wrappers around constrained package resources."""
    del is_admin
    manager = _shell_manager()
    try:
        entry = (
            manager.mount_entry(mount_id)
            if mount_id is not None
            else manager.instance_entry(instance_id)
        )
        if mount_id is not None and entry["app_instance_id"] != instance_id:
            raise HTTPException(status_code=409, detail="Mount instance changed")
        if entry["renderer"] != renderer:
            raise HTTPException(status_code=409, detail="Entry renderer changed")
        manager.resolve_app_resource(instance_id, str(entry["resource"]))
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)
    resource_url = (
        f"/admin/api/shell/app-instances/{instance_id}/resources/"
        f"{quote(str(entry['resource']), safe='/')}"
    )
    return templates.TemplateResponse(
        request,
        f"app_views/{renderer.replace('-', '_')}.html",
        {
            "app_name": entry["display_name"],
            "resource_url": resource_url,
            "mount_id": mount_id,
        },
        headers={
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "connect-src 'self'; img-src 'self' data: blob:; base-uri 'none'; "
                "form-action 'none'; frame-ancestors 'self'"
            )
        },
    )


@router.get("/app-mini/{mount_id}/generic", response_class=HTMLResponse)
async def shell_generic_mini_entry(
    request: Request,
    mount_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        entry = _shell_manager().mount_entry(mount_id)
    except (RepositoryError, ExtensionError) as error:
        _shell_lifecycle_error(error)
    if entry["resource"] != "ai2apps:generic-launcher":
        raise HTTPException(status_code=409, detail="Mini-Entry resource changed")
    return templates.TemplateResponse(
        request,
        "app_views/mini_launcher.html",
        {
            "app_name": entry["display_name"],
            "app_key": entry["app_key"],
            "instance_id": entry["app_instance_id"],
            "mount_id": mount_id,
        },
    )


def _terminal_manager():
    runtime = _get_platform_runtime() if _get_platform_runtime is not None else None
    manager = None if runtime is None else runtime.terminal
    if manager is None:
        raise HTTPException(status_code=503, detail="Terminal Service is unavailable")
    return manager


def _terminal_http_error(error: Exception) -> None:
    if not isinstance(error, TerminalServiceError):
        raise error
    status = {
        "not_found": 404,
        "session_limit": 409,
        "invalid_cwd": 422,
        "invalid_size": 422,
        "input_too_large": 413,
    }.get(error.code, 409)
    raise HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    ) from error


@router.get("/api/terminal/sessions")
async def terminal_sessions(is_admin: bool = Depends(require_admin)):
    """List Terminal App sessions without leaking internal Coder PTYs."""
    del is_admin
    return {"items": _terminal_manager().list(owner="terminal")}


@router.post("/api/terminal/sessions", status_code=201)
async def terminal_create_session(
    request: CreateTerminalSessionRequest,
    is_admin: bool = Depends(require_admin),
):
    """Create a PTY-backed login shell owned by the Terminal Service."""
    del is_admin
    try:
        session = await _terminal_manager().create(
            title=request.title,
            cwd=request.cwd,
            cols=request.cols,
            rows=request.rows,
            owner="terminal",
        )
    except Exception as error:
        _terminal_http_error(error)
    return session.public()


@router.delete("/api/terminal/sessions/{session_id}", status_code=204)
async def terminal_close_session(
    session_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Close the PTY, its process group, and all browser attachments."""
    del is_admin
    try:
        await _terminal_manager().close(session_id)
    except Exception as error:
        _terminal_http_error(error)
    return Response(status_code=204)


def _terminal_websocket_authorized(websocket: WebSocket) -> bool:
    settings = _get_global_settings() if _get_global_settings is not None else None
    if settings is not None and settings.auth.skip_api_key_verification:
        return True
    return verify_session(websocket)  # WebSocket and Request both expose cookies.


def _terminal_websocket_same_origin(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    host = websocket.headers.get("host")
    if not origin or not host:
        return False
    try:
        return urlsplit(origin).netloc.lower() == host.lower()
    except ValueError:
        return False


@router.websocket("/api/terminal/sessions/{session_id}/stream")
async def terminal_session_stream(websocket: WebSocket, session_id: str):
    """Attach one authenticated browser to a terminal byte stream."""
    if not _terminal_websocket_authorized(websocket):
        await websocket.close(code=4401, reason="Admin authentication required")
        return
    if not _terminal_websocket_same_origin(websocket):
        await websocket.close(code=4403, reason="WebSocket origin denied")
        return
    try:
        manager = _terminal_manager()
        subscriber_id, queue, backlog = manager.subscribe(session_id)
        session = manager.get(session_id)
    except HTTPException:
        await websocket.close(code=1013, reason="Terminal Service unavailable")
        return
    except Exception:
        await websocket.close(code=4404, reason="Terminal session not found")
        return

    await websocket.accept()

    async def send_output() -> None:
        await websocket.send_json({"type": "ready", "session": session.public()})
        if backlog:
            await websocket.send_bytes(backlog)
        while True:
            item = await queue.get()
            if isinstance(item, bytes):
                await websocket.send_bytes(item)
            else:
                await websocket.send_json(item)

    async def receive_input() -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))
            if message.get("bytes") is not None:
                try:
                    manager.write(session_id, message["bytes"])
                except TerminalServiceError as error:
                    await websocket.send_json(
                        {"type": "error", "code": error.code, "message": str(error)}
                    )
                continue
            raw = message.get("text")
            if raw is None or len(raw) > 70_000:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = payload.get("type")
            if kind == "input" and isinstance(payload.get("data"), str):
                try:
                    manager.write(session_id, payload["data"])
                except TerminalServiceError as error:
                    await websocket.send_json(
                        {"type": "error", "code": error.code, "message": str(error)}
                    )
            elif kind == "resize":
                try:
                    manager.resize(
                        session_id, int(payload.get("cols")), int(payload.get("rows"))
                    )
                except (TypeError, ValueError):
                    continue
                except TerminalServiceError as error:
                    await websocket.send_json(
                        {"type": "error", "code": error.code, "message": str(error)}
                    )

    sender = asyncio.create_task(send_output())
    receiver = asyncio.create_task(receive_input())
    try:
        done, pending = await asyncio.wait(
            (sender, receiver), return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            with suppress(WebSocketDisconnect, RuntimeError):
                task.result()
    finally:
        manager.unsubscribe(session_id, subscriber_id)


def _coder_manager():
    runtime = _get_platform_runtime() if _get_platform_runtime is not None else None
    manager = None if runtime is None else runtime.coder
    if manager is None:
        raise HTTPException(status_code=503, detail="Coder Service is unavailable")
    return manager


def _coder_http_error(error: CoderError) -> None:
    status = {
        "project_not_found": 404,
        "thread_not_found": 404,
        "component_not_found": 404,
        "dev_session_not_found": 404,
        "resource_not_found": 404,
        "file_not_found": 404,
        "parent_not_found": 404,
        "project_exists": 409,
        "agent_not_installed": 409,
        "session_limit": 409,
    }.get(error.code, 422)
    raise HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    ) from error


@router.get("/api/coder")
async def coder_snapshot(is_admin: bool = Depends(require_admin)):
    del is_admin
    return _coder_manager().snapshot()


@router.post("/api/coder/projects", status_code=201)
async def coder_create_project(
    request: CreateCoderProjectRequest,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return _coder_manager().create_project(**request.model_dump())
    except CoderError as error:
        _coder_http_error(error)


@router.post("/api/coder/projects/{project_id}/threads", status_code=201)
async def coder_create_thread(
    project_id: str,
    request: CreateCoderThreadRequest,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return _coder_manager().create_thread(
            project_id=project_id, **request.model_dump()
        )
    except CoderError as error:
        _coder_http_error(error)


@router.post("/api/coder/threads/{thread_id}/fork", status_code=201)
async def coder_fork_thread(
    thread_id: str,
    request: ForkCoderThreadRequest,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return _coder_manager().fork_thread(thread_id, title=request.title)
    except CoderError as error:
        _coder_http_error(error)


@router.post("/api/coder/threads/{thread_id}/start")
async def coder_start_thread(
    thread_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return await _coder_manager().start_thread(thread_id)
    except CoderError as error:
        _coder_http_error(error)


@router.post("/api/coder/threads/{thread_id}/stop")
async def coder_stop_thread(
    thread_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return await _coder_manager().stop_thread(thread_id)
    except CoderError as error:
        _coder_http_error(error)


@router.delete("/api/coder/threads/{thread_id}")
async def coder_delete_thread(
    thread_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return await _coder_manager().delete_thread(thread_id)
    except CoderError as error:
        _coder_http_error(error)


@router.post("/api/coder/projects/{project_id}/validate")
async def coder_validate_project(
    project_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return _coder_manager().validate_project(project_id)
    except CoderError as error:
        _coder_http_error(error)


@router.delete("/api/coder/projects/{project_id}")
async def coder_remove_project(
    project_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return await _coder_manager().remove_project(project_id)
    except CoderError as error:
        _coder_http_error(error)


@router.get("/api/coder/projects/{project_id}/files")
async def coder_list_project_files(
    project_id: str,
    path: str = ".",
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return _coder_manager().list_project_files(project_id, path)
    except CoderError as error:
        _coder_http_error(error)


@router.get("/api/coder/projects/{project_id}/file")
async def coder_read_project_file(
    project_id: str,
    path: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return _coder_manager().read_project_file(project_id, path)
    except CoderError as error:
        _coder_http_error(error)


@router.put("/api/coder/projects/{project_id}/file")
async def coder_write_project_file(
    project_id: str,
    request: SaveCoderFileRequest,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return _coder_manager().write_project_file(
            project_id, request.path, request.content
        )
    except CoderError as error:
        _coder_http_error(error)


@router.post("/api/coder/projects/{project_id}/test")
async def coder_test_project(
    project_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return await _coder_manager().test_project(project_id)
    except CoderError as error:
        _coder_http_error(error)


@router.post("/api/coder/projects/{project_id}/build")
async def coder_build_project(
    project_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return _coder_manager().build_project(project_id)
    except CoderError as error:
        _coder_http_error(error)


@router.post("/api/coder/projects/{project_id}/testflight")
async def coder_submit_testflight(
    project_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return _coder_manager().submit_project_testflight(project_id)
    except CoderError as error:
        _coder_http_error(error)


@router.post("/api/coder/projects/{project_id}/dev-sessions", status_code=201)
async def coder_start_dev_session(
    project_id: str,
    request: StartCoderDevSessionRequest,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return _coder_manager().start_dev_session(project_id, request.component_id)
    except CoderError as error:
        _coder_http_error(error)


@router.delete("/api/coder/dev-sessions/{session_id}")
async def coder_stop_dev_session(
    session_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        return _coder_manager().stop_dev_session(session_id)
    except CoderError as error:
        _coder_http_error(error)


def _coder_dev_headers(entry: bool = False) -> dict[str, str]:
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    if entry:
        headers["Content-Security-Policy"] = (
            "sandbox allow-scripts allow-forms allow-downloads; "
            "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
            "font-src 'self' data:; connect-src 'none'; form-action 'none'; base-uri 'none'"
        )
    return headers


@router.get("/coder-dev/{session_id}/preview")
async def coder_dev_preview(
    session_id: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        session = _coder_manager().dev_session(session_id)
        entry = session.component.manifest.get("entry", {})
        if not isinstance(entry, dict):
            raise CoderError("invalid_dev_entry", "Component has no previewable Entry")
        resource = entry.get("resource")
        if entry.get("kind") not in {"sandbox", "safe-html"} or not isinstance(resource, str):
            raise CoderError("invalid_dev_entry", "Component has no previewable Entry")
        _coder_manager().resolve_dev_resource(session_id, resource)
    except CoderError as error:
        _coder_http_error(error)
    return RedirectResponse(
        f"/admin/coder-dev/{quote(session_id, safe='')}/{quote(resource, safe='/')}",
        status_code=307,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/coder-dev/{session_id}/{resource:path}")
async def coder_dev_resource(
    session_id: str,
    resource: str,
    is_admin: bool = Depends(require_admin),
):
    del is_admin
    try:
        session = _coder_manager().dev_session(session_id)
        path, media = _coder_manager().resolve_dev_resource(session_id, resource)
        entry = session.component.manifest.get("entry")
        is_entry = isinstance(entry, dict) and entry.get("resource") == resource
    except CoderError as error:
        _coder_http_error(error)
    return FileResponse(path, media_type=media, headers=_coder_dev_headers(entry=is_entry))


def _system_app_content_response(
    request: Request,
    app_id: str,
    *,
    include_api_key: bool,
    mobile_surface: bool = False,
):
    tab = _DASHBOARD_APP_TABS.get(app_id)
    template_name = _DASHBOARD_APP_TEMPLATES.get(app_id)
    app = _SYSTEM_APPS_BY_ID.get(app_id)
    if tab is None or template_name is None or app is None:
        raise HTTPException(status_code=404, detail="App content not found")
    context = {
        "system_app": {
            "id": app_id,
            "name": app["name"],
            "tab": tab,
        }
    }
    if mobile_surface:
        context.update(
            {
                "app_base_template": "mobile_app_base.html",
                "mobile_surface": True,
                "static": _mobile_static_version,
            }
        )
    if app.get("presentation", {}).get("dock_reveal") is False:
        context["show_dock_reveal"] = False
    if include_api_key and app_id in {
        "ai2apps.account",
        "ai2apps.discover",
        "ai2apps.agents",
        "ai2apps.general-chat",
        "ai2apps.trust-center",
    }:
        settings = _get_global_settings()
        context["api_key"] = settings.auth.api_key if settings else ""
    return templates.TemplateResponse(
        request,
        template_name,
        context,
    )


@router.get("/app-content/{app_id}", response_class=HTMLResponse)
async def system_app_content(
    request: Request,
    app_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Render one built-in system App through its independent Host Entry."""
    del is_admin
    return _system_app_content_response(request, app_id, include_api_key=True)


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, is_admin: bool = Depends(require_admin)):
    """
    Render the chat page for interacting with models.

    Requires admin authentication via session cookie.
    The API key is injected into the template context so that
    the chat page can auto-set it in localStorage, bypassing
    the manual API key entry modal.

    Returns:
        HTML chat page.
    """
    global_settings = _get_global_settings()
    api_key = global_settings.auth.api_key if global_settings else ""
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "api_key": api_key or "",
            "terminal_assistant": request.query_params.get("terminal_assistant")
            == "1",
        },
    )


@router.get("/static/{path:path}")
async def admin_static(path: str):
    """Serve static files for admin panel (CSS, JS, fonts, logos, etc.)."""
    file_path = static_dir / path
    if not file_path.is_file() or not file_path.resolve().is_relative_to(
        static_dir.resolve()
    ):
        raise HTTPException(status_code=404, detail="File not found")
    media_types = {
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".ico": "image/x-icon",
        ".css": "text/css",
        ".js": "application/javascript",
        ".woff2": "font/woff2",
        ".woff": "font/woff",
        ".ttf": "font/ttf",
    }
    media_type = media_types.get(file_path.suffix, "application/octet-stream")
    return FileResponse(file_path, media_type=media_type)


# =============================================================================
# Authentication API Routes
# =============================================================================


@router.post("/api/login")
async def login(request: LoginRequest, response: Response):
    """
    Authenticate with API key and create session.

    Requires an API key to be configured on the server. If no API key
    is configured, returns 400 directing the user to set one up first.

    Args:
        request: LoginRequest containing the API key.
        response: FastAPI response object for setting cookies.

    Returns:
        JSON response with success status.

    Raises:
        HTTPException: 400 if no API key configured, 401 if invalid.
    """
    global_settings = _get_global_settings()
    server_api_key = global_settings.auth.api_key if global_settings else None

    # Reject login if no API key is configured (must use setup first)
    if not server_api_key:
        raise HTTPException(
            status_code=400,
            detail="No API key configured. Please set up an API key first.",
        )

    # Main key only — sub keys must not grant admin login
    if not verify_api_key(request.api_key, server_api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )

    # Create session token and set cookie
    token = create_session_token(remember=request.remember)
    cookie_max_age = REMEMBER_ME_MAX_AGE if request.remember else SESSION_MAX_AGE
    response.set_cookie(
        key="omlx_admin_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=cookie_max_age,
    )

    return {"success": True}


@router.post("/api/setup-api-key")
async def setup_api_key(request: SetupApiKeyRequest, response: Response):
    """
    Set up the initial API key when none is configured.

    This endpoint is only available when no API key is currently set.
    After successful setup, a session is created so the user is
    immediately logged in.

    Args:
        request: SetupApiKeyRequest with api_key and api_key_confirm.
        response: FastAPI response object for setting cookies.

    Returns:
        JSON response with success status.

    Raises:
        HTTPException: 400 if key already configured, validation fails,
                      or keys don't match.
    """
    from ..server import _server_state

    global_settings = _get_global_settings()

    # Only allow setup if no API key is currently configured
    if global_settings and global_settings.auth.api_key:
        raise HTTPException(
            status_code=400,
            detail="API key is already configured. Use settings to change it.",
        )

    # Validate confirmation match
    if request.api_key != request.api_key_confirm:
        raise HTTPException(status_code=400, detail="API keys do not match")

    # Validate key format
    is_valid, error_msg = validate_api_key(request.api_key)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Apply to settings and runtime
    global_settings.auth.api_key = request.api_key
    _server_state.api_key = request.api_key

    # Persist to file
    try:
        global_settings.save()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {e}")

    logger.info("API key configured via initial setup")

    # Create session token and set cookie (auto-login after setup)
    token = create_session_token()
    response.set_cookie(
        key="omlx_admin_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,  # 24 hours
    )

    return {"success": True, "message": "API key configured successfully"}


@router.post("/api/logout")
async def logout(response: Response):
    """
    Clear session cookie and logout.

    Args:
        response: FastAPI response object for clearing cookies.

    Returns:
        JSON response with success status.
    """
    response.delete_cookie(key="omlx_admin_session")
    return {"success": True}


@router.get("/auto-login")
async def auto_login(key: str = "", redirect: str = "/admin/dashboard"):
    """
    Auto-login using API key and redirect to the target admin page.

    Used by the macOS menubar app to open admin pages with automatic
    authentication, bypassing the manual login form.

    Args:
        key: The API key for authentication.
        redirect: The path to redirect to after login. Must start with /admin.

    Returns:
        HTTP 302 redirect with session cookie set.
    """
    if not redirect.startswith("/admin"):
        raise HTTPException(status_code=400, detail="Invalid redirect path")

    global_settings = _get_global_settings()
    server_api_key = global_settings.auth.api_key if global_settings else None

    # Main key only — sub keys must not grant admin login
    if not key or not server_api_key or not verify_api_key(key, server_api_key):
        return RedirectResponse(url="/admin", status_code=302)

    token = create_session_token()
    response = RedirectResponse(url=redirect, status_code=302)
    response.set_cookie(
        key="omlx_admin_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return response


# =============================================================================
# Sub Key Management Routes
# =============================================================================


@router.post("/api/sub-keys")
async def create_sub_key(
    request: CreateSubKeyRequest, is_admin: bool = Depends(require_admin)
):
    """Create a new sub API key.

    Sub keys can only be used for API authentication, not admin login.

    Args:
        request: CreateSubKeyRequest with key and optional name.

    Returns:
        JSON with the created sub key entry.

    Raises:
        HTTPException: 400 if validation fails or key already exists.
    """
    global_settings = _get_global_settings()
    if global_settings is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    # Validate key format
    is_valid, error_msg = validate_api_key(request.key)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Check for duplicate (against main key and existing sub keys)
    if global_settings.auth.api_key and compare_keys(
        request.key, global_settings.auth.api_key
    ):
        raise HTTPException(
            status_code=400, detail="Sub key cannot be the same as the main key"
        )

    for sk in global_settings.auth.sub_keys:
        if sk.key and compare_keys(request.key, sk.key):
            raise HTTPException(status_code=400, detail="This key already exists")

    entry = SubKeyEntry(
        key=request.key,
        name=request.name or "",
        created_at=datetime.now(UTC).isoformat(),
    )
    global_settings.auth.sub_keys.append(entry)

    try:
        global_settings.save()
    except Exception as e:
        # Rollback
        global_settings.auth.sub_keys.pop()
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {e}")

    logger.info(f"Sub key created: {request.name or '(unnamed)'}")
    return {"success": True, "sub_key": entry.to_dict()}


@router.delete("/api/sub-keys")
async def delete_sub_key(
    request: DeleteSubKeyRequest, is_admin: bool = Depends(require_admin)
):
    """Delete a sub API key.

    Args:
        request: DeleteSubKeyRequest with the key to delete.

    Returns:
        JSON with success status.

    Raises:
        HTTPException: 404 if key not found.
    """
    global_settings = _get_global_settings()
    if global_settings is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    # Find and remove the key
    for i, sk in enumerate(global_settings.auth.sub_keys):
        if sk.key and compare_keys(request.key, sk.key):
            removed = global_settings.auth.sub_keys.pop(i)
            try:
                global_settings.save()
            except Exception as e:
                global_settings.auth.sub_keys.insert(i, removed)
                raise HTTPException(
                    status_code=500, detail=f"Failed to save settings: {e}"
                )
            logger.info(f"Sub key deleted: {sk.name or '(unnamed)'}")
            return {"success": True}

    raise HTTPException(status_code=404, detail="Sub key not found")


# =============================================================================
# Grammar API Routes
# =============================================================================


_SUPPORTED_MODELS_DOC_RE = re.compile(
    r"Supported models:\s*\n((?:\s*-\s*\S.*\n?)+)",
)


def _models_from_docstring(fn) -> list[str]:
    """Extract the ``Supported models:`` bullet list from an xgrammar 0.1.34+
    structural-tag function's docstring. Returns ``[]`` if the section is
    absent or unparseable."""
    doc = inspect.getdoc(fn) or ""
    match = _SUPPORTED_MODELS_DOC_RE.search(doc)
    if not match:
        return []
    return [
        line.strip().lstrip("-").strip()
        for line in match.group(1).splitlines()
        if line.strip().startswith("-")
    ]


@router.get("/api/grammar/parsers")
async def list_grammar_parsers(is_admin: bool = Depends(require_admin)):
    """Return available reasoning parser names from xgrammar.

    Supports both API generations:

    - **xgrammar 0.1.34+** exposes a per-model registry at
      ``xgrammar.builtin_structural_tag._structural_tag_registry``; supported
      model names are pulled from each function's docstring.
    - **xgrammar 0.1.32–0.1.33** exposes the now-removed helper
      ``get_builtin_structural_tag_supported_models()``.

    Returns ``[]`` if xgrammar is missing, fails to load (e.g. broken native
    binding on macOS arm64), or has neither API available.
    """
    # Install the torch stub BEFORE any xgrammar import. If this lives
    # inside the first try-block, a failure on the 0.1.34+ path can leave
    # the fallback try-block importing xgrammar without the stub, which
    # is guaranteed ImportError on stub-only (DMG) deployments.
    try:
        from omlx._torch_stub import install as _install_torch_stub

        _install_torch_stub()
    except Exception as e:  # pragma: no cover — defensive
        logger.debug("torch stub install failed: %s", e)

    # Prefer the 0.1.34+ registry so newer parsers (qwen3_6, gemma4,
    # deepseek_v4, ...) are exposed.
    try:
        from xgrammar.builtin_structural_tag import _structural_tag_registry

        return [
            {"value": style, "label": style, "models": _models_from_docstring(fn)}
            for style, fn in _structural_tag_registry.items()
        ]
    except Exception as e:
        logger.debug("xgrammar 0.1.34+ registry unavailable: %s", e)

    # Fall back to the pre-0.1.34 helper.
    try:
        from xgrammar import get_builtin_structural_tag_supported_models

        supported = get_builtin_structural_tag_supported_models()
        return [
            {"value": style, "label": style, "models": models}
            for style, models in supported.items()
        ]
    except Exception as e:
        logger.warning("xgrammar parser discovery unavailable: %s", e)
        return []


# =============================================================================
# Models API Routes
# =============================================================================


def _model_display_name(
    model_id: str,
    model_path: str | Path | None,
    model_dirs: list[Path],
    *,
    source_repo_id: str | None = None,
) -> str:
    """Return the UI-only display name for a discovered local model."""
    repo_id = (source_repo_id or "").strip()
    if "/" in repo_id:
        return repo_id

    if not model_path:
        return model_id

    path_text = str(model_path)
    if "://" in path_text:
        return model_id

    try:
        path = Path(path_text).expanduser().resolve()
    except (OSError, RuntimeError):
        path = Path(path_text).expanduser()

    for model_dir in model_dirs:
        try:
            rel = path.relative_to(model_dir.expanduser().resolve())
        except (OSError, RuntimeError, ValueError):
            continue

        parts = rel.parts
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        return model_id

    return model_id


def _model_dirs_for_display(global_settings: Any | None) -> list[Path]:
    if global_settings is None:
        return []
    try:
        return global_settings.model.get_model_dirs(global_settings.base_path)
    except Exception as e:  # pragma: no cover - defensive for partial test doubles
        logger.debug("Could not resolve model dirs for display names: %s", e)
        return []


def _cloud_model_capabilities(model: dict[str, Any]) -> set[str]:
    """Normalize provider metadata and conservative name hints for routing."""

    raw = model.get("capabilities")
    capabilities = {
        re.sub(r"(?<!^)(?=[A-Z])", "_", str(key)).lower().replace("-", "_")
        for key, enabled in (raw.items() if isinstance(raw, dict) else [])
        if enabled
    }
    if isinstance(raw, dict) and raw.get("imageInput"):
        capabilities.add("image_recognition")
    text = " ".join(
        str(model.get(key) or "").lower() for key in ("id", "name")
    )
    if any(token in text for token in ("gpt-image", "dall-e", "imagen", "flux")):
        capabilities.add("image_generation")
    if any(token in text for token in ("sora", "veo", "video-generation", "video_gen")):
        capabilities.add("video_generation")
    if any(token in text for token in ("whisper", "transcribe", "speech-to-text", "asr")):
        capabilities.add("speech_recognition")
    if any(
        token in text
        for token in ("vision", "-vl", "gemini", "claude", "gpt-4", "gpt-5")
    ):
        capabilities.add("image_recognition")
    if not capabilities.intersection(
        {"image_generation", "video_generation", "speech_recognition"}
    ):
        capabilities.add("work")
    return capabilities


async def _ai2apps_cloud_provider() -> dict[str, Any]:
    """Build the managed Model App provider from the current Cloud account."""

    runtime = _get_platform_runtime() if _get_platform_runtime is not None else None
    cloud = None if runtime is None else runtime.cloud
    base = {
        "id": "ai2apps",
        "name": "AI2Apps Cloud",
        "base_url": getattr(cloud, "base_url", "https://coder.ai2apps.com"),
        "protocol": "ai2apps-responses",
        "models": [],
        "model_count": 0,
        "enabled_model_count": 0,
        "models_error": "",
        "enabled": True,
        "configured": False,
        "builtin": True,
        "managed": True,
        "connection_state": "unavailable" if cloud is None else "signed_out",
    }
    if cloud is None:
        base["models_error"] = "Cloud connection is not ready; local models remain available."
        return base
    try:
        response = await cloud.request("GET", "/v1/ai/models")
    except Exception:
        logger.debug("Unable to load the AI2Apps Cloud model catalog", exc_info=True)
        base["models_error"] = "AI2Apps Cloud is unavailable; local models remain available."
        return base
    try:
        if response.status_code == 401:
            return base
        if response.status_code != 200:
            base["connection_state"] = "unavailable"
            base["models_error"] = f"AI2Apps Cloud returned HTTP {response.status_code}."
            return base
        payload = response.json()
    except (TypeError, ValueError):
        base["connection_state"] = "unavailable"
        base["models_error"] = "AI2Apps Cloud returned an invalid model catalog."
        return base
    finally:
        await response.aclose()
    items = payload.get("items", []) if isinstance(payload, dict) else []
    models = [
        {
            "id": str(item["id"]),
            "name": str(item.get("displayName") or item["id"]),
            "owned_by": str(item.get("provider") or "AI2Apps"),
            "capabilities": item.get("capabilities") or {},
            "context_window": item.get("contextWindow"),
            "max_output_tokens": item.get("maxOutputTokens"),
            "pricing_version": item.get("pricingVersion"),
            "rates": item.get("rates") or {},
            "enabled": True,
        }
        for item in items
        if isinstance(item, dict) and item.get("id")
    ]
    base.update(
        {
            "models": models,
            "model_count": len(models),
            "enabled_model_count": len(models),
            "configured": True,
            "connection_state": "signed_in",
        }
    )
    return base


@router.get("/api/models")
async def list_models(is_admin: bool = Depends(require_admin)):
    """
    List all models with their settings.

    Returns model information from the engine pool combined with
    per-model settings from the settings manager.

    Returns:
        JSON list of models with their status and settings.

    Raises:
        HTTPException: 401 if not authenticated, 503 if server not initialized.
    """
    engine_pool = _get_engine_pool()
    settings_manager = _get_settings_manager()
    server_state = _get_server_state()
    global_settings = _get_global_settings() if _get_global_settings else None
    model_dirs = _model_dirs_for_display(global_settings)

    if engine_pool is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    # Get engine pool status
    status = engine_pool.get_status()
    models_status = status.get("models", [])

    # Get all model settings
    all_settings = settings_manager.get_all_settings() if settings_manager else {}

    # Draft-model references pointed at by other models' speculative settings —
    # used to badge "helper" drafters that only differ by being referenced.
    referenced_drafts: set[str] = set()
    for _ms in all_settings.values():
        for ref in (
            _ms.specprefill_draft_model,
            _ms.dflash_draft_model,
            _ms.vlm_mtp_draft_model,
        ):
            if ref:
                referenced_drafts.add(ref)

    # SSD cache dir is set on the scheduler_config when the user enables paged
    # SSD caching; admin UI consumes it to gate the dflash SSD toggle.
    ssd_cache_dir = getattr(
        getattr(engine_pool, "_scheduler_config", None),
        "paged_ssd_cache_dir",
        None,
    )
    dflash_ssd_cache_available = bool(ssd_cache_dir)

    # Combine model info with settings
    models = []
    for model_info in models_status:
        model_id = model_info["id"]
        settings = all_settings.get(model_id)

        is_paroquant, paroquant_reason = _paroquant_compat_for_model(model_info)
        compat_ok, compat_reason = _dflash_compat_for_model(model_info)
        mtp_compat_ok, mtp_compat_reason = _mtp_compat_for_model(model_info)

        model_data = {
            "id": model_id,
            "model_path": model_info.get("model_path", ""),
            "display_name": _model_display_name(
                model_id,
                model_info.get("model_path", ""),
                model_dirs,
                source_repo_id=model_info.get("source_repo_id"),
            ),
            "loaded": model_info.get("loaded", False),
            "is_loading": model_info.get("is_loading", False),
            "estimated_size": model_info.get("estimated_size", 0),
            "estimated_size_formatted": format_size(
                model_info.get("estimated_size", 0)
            ),
            "actual_size": model_info.get("actual_size") or 0,
            "actual_size_formatted": (
                format_size(model_info.get("actual_size", 0))
                if model_info.get("actual_size")
                else None
            ),
            "pinned": model_info.get("pinned", False),
            "is_default": (
                server_state.default_model == model_id if server_state else False
            ),
            "is_hidden": bool(settings and settings.is_hidden),
            "is_favorite": bool(settings and settings.is_favorite),
            "is_helper": (
                bool(model_info.get("is_helper"))
                or model_id in referenced_drafts
                or model_info.get("model_path") in referenced_drafts
                or model_info.get("source_repo_id") in referenced_drafts
            ),
            "engine_type": model_info.get("engine_type", "batched"),
            "model_type": model_info.get("model_type", "llm"),
            "config_model_type": model_info.get("config_model_type", ""),
            "cache_moe": bool(model_info.get("cache_moe", False)),
            # Native context window from the model's config.json — used by
            # the context bench UI to hide targets the model cannot reach.
            "model_context_length": model_info.get("model_context_length"),
            "thinking_default": model_info.get("thinking_default"),
            "preserve_thinking_default": model_info.get("preserve_thinking_default"),
            "source_type": model_info.get("source_type", "local"),
            "source_repo_id": model_info.get("source_repo_id"),
            "last_access": model_info.get("last_access"),
            "dflash_compatible": compat_ok,
            "dflash_compatibility_reason": compat_reason,
            "dflash_ssd_cache_available": dflash_ssd_cache_available,
            "mtp_compatible": mtp_compat_ok,
            "mtp_compatibility_reason": mtp_compat_reason,
            "is_paroquant": is_paroquant,
            "paroquant_reason": paroquant_reason,
        }

        if model_data["cache_moe"]:
            from ..model_discovery import (
                deepseek_cache_moe_memory_profile,
                qwen36_cache_moe_memory_profile,
            )

            cache_config = getattr(
                engine_pool._entries.get(model_id), "cache_moe_config", None
            )
            profile_fn = (
                qwen36_cache_moe_memory_profile
                if model_data["config_model_type"] == "qwen3_5_moe"
                and (cache_config or {}).get("engine")
                in ("qwen3.6-flesh", "qwen3.6-arena", "qwen3.6-tiered")
                else deepseek_cache_moe_memory_profile
            )
            model_data["cache_moe_memory"] = profile_fn(
                model_info.get("model_path", ""), cache_config
            )

        # Add settings if available
        if settings:
            model_data["settings"] = asdict(settings)
        if settings_manager:
            model_data["exposed_profiles"] = [
                profile
                for profile in settings_manager.list_profiles(model_id)
                if profile.get("expose_as_model")
            ]

        models.append(model_data)

    if markitdown_model_visible(global_settings) and not any(
        m.get("id") == MARKITDOWN_MODEL_ID for m in models
    ):
        models.append(
            {
                "id": MARKITDOWN_MODEL_ID,
                "model_path": "builtin://markitdown",
                "display_name": MARKITDOWN_MODEL_ID,
                "loaded": True,
                "is_loading": False,
                "estimated_size": 0,
                "estimated_size_formatted": format_size(0),
                "actual_size": 0,
                "actual_size_formatted": None,
                "pinned": False,
                "is_default": False,
                "engine_type": "markitdown",
                "model_type": "markitdown",
                "config_model_type": "markitdown",
                "thinking_default": None,
                "preserve_thinking_default": None,
                "source_type": "builtin",
                "source_repo_id": None,
                "last_access": None,
                "dflash_compatible": False,
                "dflash_compatibility_reason": "",
                "dflash_ssd_cache_available": False,
                "mtp_compatible": False,
                "mtp_compatibility_reason": "",
                "is_paroquant": False,
                "paroquant_reason": "",
                "virtual": True,
            }
        )

    if global_settings is not None:
        cloud_models = _model_manager_store().enabled_cloud_models()
        ai2apps_provider = await _ai2apps_cloud_provider()
        local_gateway_ids = {model["gateway_id"] for model in cloud_models}
        configured_local_providers = {
            provider["id"]
            for provider in _model_manager_store().list_cloud()
            if provider["configured"]
        }
        if ai2apps_provider["configured"]:
            cloud_models.extend(
                {
                    **model,
                    "gateway_id": f"cloud/{model['id']}",
                    "provider_id": "ai2apps",
                    "provider_name": "AI2Apps Cloud",
                    "protocol": "ai2apps-responses",
                }
                for model in ai2apps_provider["models"]
                if f"cloud/{model['id']}" not in local_gateway_ids
                and str(model["id"]).split("/", 1)[0]
                not in configured_local_providers
            )
        for cloud_model in cloud_models:
            cloud_capabilities = _cloud_model_capabilities(cloud_model)
            cloud_model_type = (
                "image_generation"
                if "image_generation" in cloud_capabilities
                else (
                    "video_generation"
                    if "video_generation" in cloud_capabilities
                    else (
                        "audio_stt"
                        if "speech_recognition" in cloud_capabilities
                        else "llm"
                    )
                )
            )
            models.append(
                {
                    "id": cloud_model["gateway_id"],
                    "model_path": f"cloud://{cloud_model['provider_id']}/{cloud_model['id']}",
                    "display_name": cloud_model.get("name") or cloud_model["id"],
                    "loaded": True,
                    "is_loading": False,
                    "estimated_size": 0,
                    "estimated_size_formatted": format_size(0),
                    "actual_size": 0,
                    "actual_size_formatted": None,
                    "pinned": False,
                    "is_default": False,
                    "is_hidden": False,
                    "is_favorite": False,
                    "is_helper": False,
                    "engine_type": "cloud",
                    "model_type": cloud_model_type,
                    "config_model_type": "cloud",
                    "capabilities": sorted(cloud_capabilities),
                    "cache_moe": False,
                    "thinking_default": None,
                    "preserve_thinking_default": None,
                    "source_type": "cloud",
                    "source_repo_id": None,
                    "last_access": None,
                    "dflash_compatible": False,
                    "dflash_compatibility_reason": "",
                    "dflash_ssd_cache_available": False,
                    "mtp_compatible": False,
                    "mtp_compatibility_reason": "",
                    "is_paroquant": False,
                    "paroquant_reason": "",
                    "virtual": True,
                    "cloud_provider": cloud_model["provider_id"],
                    "cloud_protocol": cloud_model.get("protocol", "openai"),
                    "external_model_id": cloud_model["id"],
                }
            )

        existing_ids = {model["id"] for model in models}
        for fusion in _model_manager_store().list_fusion():
            if not fusion.get("valid") or fusion["id"] in existing_ids:
                continue
            def role_is_cached_moe(role_model_id: str) -> bool:
                return any(
                    model.get("cache_moe")
                    and role_model_id
                    in {
                        model["id"],
                        model.get("display_name"),
                        model.get("settings", {}).get("model_alias"),
                    }
                    for model in models
                )

            cached_role_ids = []
            if role_is_cached_moe(fusion["generator"]["model"]):
                cached_role_ids.append("generator")
            if fusion["reviewer"].get("backend") == "local" and role_is_cached_moe(
                fusion["reviewer"]["model"]
            ):
                cached_role_ids.append("reviewer")
            models.append(
                {
                    "id": fusion["id"],
                    "model_path": f"fusion://{fusion['id']}",
                    "display_name": fusion.get("name") or fusion["id"],
                    "loaded": True,
                    "is_loading": False,
                    "estimated_size": 0,
                    "estimated_size_formatted": format_size(0),
                    "actual_size": 0,
                    "actual_size_formatted": None,
                    "pinned": False,
                    "is_default": False,
                    "is_hidden": False,
                    "is_favorite": False,
                    "is_helper": False,
                    "engine_type": "fusion",
                    "model_type": "llm",
                    "config_model_type": "ai2apps_fusion",
                    "cache_moe": bool(cached_role_ids),
                    "thinking_default": None,
                    "preserve_thinking_default": None,
                    "source_type": "fusion",
                    "source_repo_id": None,
                    "last_access": None,
                    "dflash_compatible": False,
                    "dflash_compatibility_reason": "",
                    "dflash_ssd_cache_available": False,
                    "mtp_compatible": False,
                    "mtp_compatibility_reason": "",
                    "is_paroquant": False,
                    "paroquant_reason": "",
                    "virtual": True,
                    "fusion_generator": fusion["generator"]["model"],
                    "fusion_reviewer": fusion["reviewer"]["model"],
                    "fusion_cached_moe_roles": cached_role_ids,
                    "fusion_config": {
                        "gate": fusion.get("gate", {}),
                        "cache_moe": fusion.get("cache_moe", {}),
                        "resolver": fusion.get("resolver", {}),
                    },
                }
            )
            existing_ids.add(fusion["id"])

    platform_runtime = _get_platform_runtime() if _get_platform_runtime else None
    existing_ids = {model["id"] for model in models}
    for package_model in list_package_models(platform_runtime):
        if package_model.id in existing_ids:
            continue
        models.append(package_model.public_catalog_entry())
        existing_ids.add(package_model.id)

    return {"models": models}


def _model_manager_store():
    from ai2apps.model_manager import ModelManagerStore

    settings = _get_global_settings()
    if settings is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    return ModelManagerStore(settings.base_path)


def _supports_default_model_purpose(model: dict[str, Any], purpose: str) -> bool:
    """Keep UI filtering and the persisted routing contract fail-closed."""

    if model.get("is_hidden") or model.get("is_helper"):
        return False
    model_type = str(model.get("model_type") or "").lower()
    config_type = str(model.get("config_model_type") or "").lower()
    capabilities = {str(item) for item in model.get("capabilities", [])}
    is_diffusion = model_type == "image_generation" or "diffusion" in config_type
    if purpose.startswith("work_"):
        return (
            model_type in {"llm", "vlm"}
            and not is_diffusion
            and (not capabilities or "work" in capabilities)
        )
    if purpose == "speech_recognition":
        return model_type == "audio_stt" or purpose in capabilities
    if purpose == "speech_generation":
        return model_type == "audio_tts" or purpose in capabilities
    if purpose == "audio_processing":
        return model_type == "audio_processing" or purpose in capabilities
    if purpose == "image_recognition":
        return (model_type == "vlm" and not is_diffusion) or purpose in capabilities
    if purpose == "image_generation":
        return is_diffusion or purpose in capabilities
    if purpose == "video_generation":
        return (
            model_type == "video_generation"
            or "video" in config_type
            or purpose in capabilities
        )
    return False


@router.get("/api/model-manager")
async def get_model_manager(is_admin: bool = Depends(require_admin)):
    """Return models grouped by their serving contract, not disk location."""

    from ai2apps.model_installer import AI2AppsInstaller

    catalog = AI2AppsInstaller.catalog()
    cached_repo_ids = {
        source["repo_id"]
        for recipe in catalog
        for source in recipe.get("sources", [])
    }
    runtime_models = (await list_models(is_admin=is_admin))["models"]
    cache_runtime = [model for model in runtime_models if model.get("cache_moe")]
    ordinary_runtime = [
        model
        for model in runtime_models
        if not model.get("cache_moe")
        and not model.get("virtual")
        and model.get("source_repo_id") not in cached_repo_ids
        and model.get("id") not in cached_repo_ids
    ]
    package_runtime = [
        model for model in runtime_models if model.get("source_type") == "package"
    ]
    try:
        tasks = _get_ai2apps_installer().get_tasks()
    except HTTPException:
        tasks = []
    latest_tasks: dict[str, dict[str, Any]] = {}
    for task in tasks:
        latest_tasks[task["model_id"]] = task

    cached_moe = []
    for recipe in catalog:
        repo_ids = {source["repo_id"] for source in recipe.get("sources", [])}
        installed = next(
            (
                model
                for model in cache_runtime
                if model.get("source_repo_id") in repo_ids
                or model.get("id") in repo_ids
                or any(str(model.get("model_path", "")).rstrip("/").endswith(repo) for repo in repo_ids)
            ),
            None,
        )
        cached_moe.append(
            {
                **recipe,
                "installed": installed is not None,
                "runtime_model": installed,
                "task": latest_tasks.get(recipe["id"]),
            }
        )

    store = _model_manager_store()
    ai2apps_provider = await _ai2apps_cloud_provider()
    configured_local_providers = {
        provider["id"]: provider["name"]
        for provider in store.list_cloud()
        if provider["configured"]
    }
    for model in ai2apps_provider["models"]:
        local_provider_id = str(model["id"]).split("/", 1)[0]
        local_provider_name = configured_local_providers.get(local_provider_id)
        model["enabled"] = local_provider_name is None
        model["disabled_reason"] = (
            ""
            if local_provider_name is None
            else f"Using local {local_provider_name} API key (local provider takes priority)."
        )
    ai2apps_provider["enabled_model_count"] = sum(
        1 for model in ai2apps_provider["models"] if model["enabled"]
    )
    return {
        "cached_moe": cached_moe,
        "omlx": ordinary_runtime,
        "packages": package_runtime,
        "fusion": store.list_fusion(),
        "cloud": [
            ai2apps_provider,
            *(provider for provider in store.list_cloud() if provider["id"] != "ai2apps"),
        ],
        "defaults": store.default_models(),
    }


@router.put("/api/model-manager/defaults")
async def put_default_model_routes(
    request: DefaultModelRoutesRequest,
    is_admin: bool = Depends(require_admin),
):
    """Persist purpose-specific system model defaults from the live catalog."""

    runtime_models = (await list_models(is_admin=is_admin))["models"]
    catalog = {str(model["id"]): model for model in runtime_models}
    for purpose, selected in request.routes.items():
        model_id = str(selected or "").strip()
        if not model_id:
            continue
        model = catalog.get(model_id)
        if model is None:
            raise HTTPException(status_code=400, detail=f"Model is not available: {model_id}")
        if not _supports_default_model_purpose(model, purpose):
            raise HTTPException(
                status_code=400,
                detail=f"Model {model_id} is not compatible with {purpose}",
            )
    try:
        routes = _model_manager_store().put_default_models(
            request.routes,
            available_model_ids=set(catalog),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"defaults": routes}


@router.put("/api/model-manager/fusion/{model_id}")
async def put_fusion_model(
    model_id: str,
    request: FusionModelRequest,
    is_admin: bool = Depends(require_admin),
):
    try:
        return {"model": _model_manager_store().put_fusion(model_id, request.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/model-manager/fusion/{model_id}")
async def delete_fusion_model(model_id: str, is_admin: bool = Depends(require_admin)):
    try:
        if not _model_manager_store().delete_fusion(model_id):
            raise HTTPException(status_code=404, detail="Fusion model not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True}


@router.put("/api/model-manager/cloud/{provider_id}")
async def put_cloud_provider(
    provider_id: str,
    request: CloudProviderRequest,
    is_admin: bool = Depends(require_admin),
):
    if provider_id == "ai2apps":
        raise HTTPException(status_code=409, detail="AI2Apps Cloud is managed by Account App")
    store = _model_manager_store()
    try:
        provider = store.put_cloud(provider_id, request.model_dump())
        if request.api_key:
            try:
                provider = await asyncio.to_thread(store.sync_cloud, provider_id)
            except ValueError:
                # The credential/configuration remains saved. Surface the
                # sanitized sync error on the Provider card for correction.
                provider = next(
                    item for item in store.list_cloud() if item["id"] == provider_id
                )
        return {"provider": provider}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/model-manager/cloud/{provider_id}/refresh")
async def refresh_cloud_provider_models(
    provider_id: str, is_admin: bool = Depends(require_admin)
):
    if provider_id == "ai2apps":
        raise HTTPException(status_code=409, detail="AI2Apps Cloud refreshes from Account App")
    try:
        provider = await asyncio.to_thread(
            _model_manager_store().sync_cloud, provider_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"provider": provider}


@router.put("/api/model-manager/cloud/{provider_id}/model-selection")
async def set_cloud_provider_model_selection(
    provider_id: str,
    request: CloudModelSelectionRequest,
    is_admin: bool = Depends(require_admin),
):
    if provider_id == "ai2apps":
        raise HTTPException(status_code=409, detail="AI2Apps Cloud models are managed by the service")
    try:
        provider = _model_manager_store().set_cloud_model_enabled(
            provider_id, request.model_id, request.enabled
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"provider": provider}


@router.delete("/api/model-manager/cloud/{provider_id}")
async def delete_cloud_provider(
    provider_id: str, is_admin: bool = Depends(require_admin)
):
    if provider_id == "ai2apps":
        raise HTTPException(status_code=409, detail="Sign out from Account App to disconnect AI2Apps Cloud")
    try:
        _model_manager_store().delete_cloud(provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True}


@router.post("/api/models/{model_id}/unload")
async def unload_model(
    model_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Manually unload a model from memory."""
    engine_pool = _get_engine_pool()
    if engine_pool is None:
        raise HTTPException(status_code=503, detail="Engine pool not initialized")

    entry = engine_pool.get_entry(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
    if entry.engine is None:
        raise HTTPException(status_code=400, detail=f"Model not loaded: {model_id}")

    await engine_pool._unload_engine(model_id)
    logger.info(f"Manually unloaded model: {model_id}")
    return {"status": "ok", "model_id": model_id, "message": f"Unloaded {model_id}"}


async def _require_admin_or_bearer(request: Request) -> bool:
    """Allow admin session OR a valid Bearer API key (for CLI use)."""
    gs = _get_global_settings() if _get_global_settings else None

    # No-auth mode: always allow
    if gs is not None and gs.auth.skip_api_key_verification:
        return True

    # Valid admin session cookie
    if verify_session(request):
        return True

    # Bearer token matching the configured API key
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and gs is not None:
        token = auth_header[7:]
        server_key = gs.auth.api_key or ""
        sub_keys = gs.auth.sub_keys or []
        if verify_api_key(token, server_key):
            return True
        for sk in sub_keys:
            if verify_api_key(token, getattr(sk, "key", "")):
                return True

    raise HTTPException(
        status_code=401,
        detail="Admin authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/api/models/{model_id}/load")
async def load_model(
    model_id: str,
    is_admin: bool = Depends(_require_admin_or_bearer),
):
    """Manually load a model into memory."""
    engine_pool = _get_engine_pool()
    if engine_pool is None:
        raise HTTPException(status_code=503, detail="Engine pool not initialized")

    entry = engine_pool.get_entry(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
    if entry.engine is not None:
        return {
            "status": "ok",
            "model_id": model_id,
            "message": f"Already loaded: {model_id}",
        }
    if entry.is_loading:
        raise HTTPException(
            status_code=409, detail=f"Model is already loading: {model_id}"
        )

    try:
        await engine_pool.get_engine(model_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    logger.info(f"Manually loaded model: {model_id}")
    return {"status": "ok", "model_id": model_id, "message": f"Loaded {model_id}"}


@router.post("/api/reload")
async def reload_models(is_admin: bool = Depends(require_admin)):
    """Reload models: re-read model settings, re-discover models, preload pinned."""
    success, message = await _reload_models()
    if success:
        return {"status": "ok", "message": message}
    raise HTTPException(status_code=500, detail=message)


@router.put("/api/models/{model_id}/settings")
async def update_model_settings(
    model_id: str,
    request: ModelSettingsRequest,
    is_admin: bool = Depends(require_admin),
):
    """
    Update settings for a specific model.

    Updates are persisted to the settings file and applied immediately
    to the engine pool where applicable (e.g., pinned status).

    Args:
        model_id: The model identifier.
        request: ModelSettingsRequest with the new settings.

    Returns:
        JSON response with success status and updated settings.

    Raises:
        HTTPException: 401 if not authenticated, 404 if model not found.
    """
    engine_pool = _get_engine_pool()
    settings_manager = _get_settings_manager()
    server_state = _get_server_state()

    if engine_pool is None or settings_manager is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    # Check if model exists
    entry = engine_pool.get_entry(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")

    # Get current settings
    current_settings = settings_manager.get_settings(model_id)

    # Apply updates — use model_fields_set to distinguish "sent as null"
    # (clear to default) from "not sent" (don't touch).
    sent = request.model_fields_set
    prev_engine_type = entry.engine_type  # Track for requires_reload check
    prev_load_signature = engine_pool._engine_runtime_signature(
        model_id, current_settings
    )
    is_diffusion_model = _entry_is_diffusion_model(entry)
    if "model_alias" in sent:
        alias_value = request.model_alias.strip() if request.model_alias else None
        if alias_value == "":
            alias_value = None
        if alias_value is not None:
            all_settings = settings_manager.get_all_settings()
            for mid, ms in all_settings.items():
                if mid != model_id and ms.model_alias == alias_value:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Alias '{alias_value}' is already used by model '{mid}'",
                    )
            for mid in engine_pool._entries:
                if mid != model_id and mid == alias_value:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Alias '{alias_value}' conflicts with model directory name '{mid}'",
                    )
            _raise_if_alias_conflicts_exposed_profiles(
                alias_value=alias_value,
                model_id=model_id,
                settings_manager=settings_manager,
                engine_pool=engine_pool,
            )
        current_settings.model_alias = alias_value
    if "model_type_override" in sent:
        valid_types = {
            "llm",
            "vlm",
            "embedding",
            "reranker",
            "audio_stt",
            "audio_tts",
            "audio_sts",
        }
        # Treat empty string as None (auto-detect)
        override_value = request.model_type_override or None
        if override_value is not None and override_value not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model_type_override: {request.model_type_override}",
            )
        current_settings.model_type_override = override_value
        # Update engine pool entry type immediately
        type_to_engine = {
            "llm": "batched",
            "vlm": "vlm",
            "embedding": "embedding",
            "reranker": "reranker",
            "audio_stt": "audio_stt",
            "audio_tts": "audio_tts",
            "audio_sts": "audio_sts",
        }
        if override_value:
            entry.model_type = override_value
            entry.engine_type = type_to_engine.get(override_value, "batched")
        else:
            # Reset to auto-detected type
            from pathlib import Path

            from ..model_discovery import detect_model_type

            detected_type = detect_model_type(Path(entry.model_path))
            entry.model_type = detected_type
            entry.engine_type = type_to_engine.get(detected_type, "batched")
    if "max_context_window" in sent:
        current_settings.max_context_window = request.max_context_window
    if "cache_moe_memory_tier" in sent:
        memory_tier = (request.cache_moe_memory_tier or "auto").strip().lower()
        if memory_tier not in {"auto", "lean", "compact", "optimal"}:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid Cache-MoE memory tier: {memory_tier}",
            )
        current_tier = current_settings.cache_moe_memory_tier or "auto"
        if memory_tier != current_tier and engine_pool._entry_is_busy(entry):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Cache-MoE memory profile cannot be changed while the "
                    "model has active requests"
                ),
            )
        current_settings.cache_moe_memory_tier = (
            None if memory_tier == "auto" else memory_tier
        )
    if "kv_cache_policy" in sent:
        kv_policy = (request.kv_cache_policy or "session").strip().lower()
        if kv_policy not in {"strict", "session", "persistent"}:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid KV continuity policy: {kv_policy}",
            )
        current_settings.kv_cache_policy = kv_policy
    if "max_tokens" in sent:
        current_settings.max_tokens = request.max_tokens
    if "temperature" in sent:
        current_settings.temperature = request.temperature
    if "top_p" in sent:
        current_settings.top_p = request.top_p
    if "top_k" in sent:
        current_settings.top_k = request.top_k
    if "repetition_penalty" in sent:
        current_settings.repetition_penalty = request.repetition_penalty
    if "min_p" in sent:
        current_settings.min_p = request.min_p
    if "presence_penalty" in sent:
        current_settings.presence_penalty = request.presence_penalty
    if "force_sampling" in sent:
        current_settings.force_sampling = request.force_sampling
    if "max_tool_result_tokens" in sent:
        # 0 means disable (reset to None)
        current_settings.max_tool_result_tokens = (
            request.max_tool_result_tokens
            if request.max_tool_result_tokens and request.max_tool_result_tokens > 0
            else None
        )
    if "enable_thinking" in sent:
        current_settings.enable_thinking = request.enable_thinking
    if "thinking_budget_enabled" in sent:
        current_settings.thinking_budget_enabled = (
            request.thinking_budget_enabled or False
        )
    if "thinking_budget_tokens" in sent:
        current_settings.thinking_budget_tokens = (
            request.thinking_budget_tokens
            if request.thinking_budget_tokens and request.thinking_budget_tokens > 0
            else None
        )
    if "chat_template_kwargs" in sent:
        current_settings.chat_template_kwargs = request.chat_template_kwargs
    if "forced_ct_kwargs" in sent:
        current_settings.forced_ct_kwargs = request.forced_ct_kwargs
    if "ttl_seconds" in sent:
        current_settings.ttl_seconds = request.ttl_seconds
    if "index_cache_freq" in sent:
        # 0 means disable (reset to None)
        current_settings.index_cache_freq = (
            request.index_cache_freq
            if request.index_cache_freq and request.index_cache_freq >= 2
            else None
        )
    # TurboQuant KV cache settings
    if "turboquant_kv_enabled" in sent:
        current_settings.turboquant_kv_enabled = request.turboquant_kv_enabled or False
    if "turboquant_kv_bits" in sent:
        current_settings.turboquant_kv_bits = request.turboquant_kv_bits or 4
    # SpecPrefill settings
    if "specprefill_enabled" in sent:
        current_settings.specprefill_enabled = request.specprefill_enabled or False
    if "specprefill_draft_model" in sent:
        current_settings.specprefill_draft_model = (
            request.specprefill_draft_model or None
        )
    if "specprefill_keep_pct" in sent:
        current_settings.specprefill_keep_pct = request.specprefill_keep_pct or None
    if "specprefill_threshold" in sent:
        current_settings.specprefill_threshold = request.specprefill_threshold or None
    # DFlash settings
    if "dflash_enabled" in sent:
        new_dflash_enabled = (
            False if is_diffusion_model else bool(request.dflash_enabled)
        )
        if new_dflash_enabled:
            from ..engine.dflash import is_dflash_compatible

            compat_ok, compat_reason = is_dflash_compatible(entry.model_path)
            if not compat_ok:
                raise HTTPException(status_code=400, detail=compat_reason)
        current_settings.dflash_enabled = new_dflash_enabled
    if "dflash_draft_model" in sent:
        current_settings.dflash_draft_model = request.dflash_draft_model or None
    if "dflash_draft_quant_enabled" in sent:
        current_settings.dflash_draft_quant_enabled = (
            bool(request.dflash_draft_quant_enabled)
            if request.dflash_draft_quant_enabled is not None
            else None
        )
    if "dflash_draft_quant_weight_bits" in sent:
        current_settings.dflash_draft_quant_weight_bits = (
            int(request.dflash_draft_quant_weight_bits)
            if request.dflash_draft_quant_weight_bits is not None
            else None
        )
    if "dflash_draft_quant_activation_bits" in sent:
        current_settings.dflash_draft_quant_activation_bits = (
            int(request.dflash_draft_quant_activation_bits)
            if request.dflash_draft_quant_activation_bits is not None
            else None
        )
    if "dflash_draft_quant_group_size" in sent:
        current_settings.dflash_draft_quant_group_size = (
            int(request.dflash_draft_quant_group_size)
            if request.dflash_draft_quant_group_size is not None
            else None
        )
    if "dflash_max_ctx" in sent:
        # 0/None means "unlimited" — the engine treats None as no fallback threshold
        value = request.dflash_max_ctx
        current_settings.dflash_max_ctx = value if value and value > 0 else None
    if "dflash_in_memory_cache" in sent:
        current_settings.dflash_in_memory_cache = bool(request.dflash_in_memory_cache)
    if "dflash_in_memory_cache_max_entries" in sent:
        value = request.dflash_in_memory_cache_max_entries
        current_settings.dflash_in_memory_cache_max_entries = (
            int(value) if value and value > 0 else 4
        )
    if (
        "dflash_in_memory_cache_max_bytes" in sent
        and request.dflash_in_memory_cache_max_bytes
    ):
        current_settings.dflash_in_memory_cache_max_bytes = int(
            request.dflash_in_memory_cache_max_bytes
        )
    if "dflash_ssd_cache" in sent:
        ssd_requested = bool(request.dflash_ssd_cache)
        if is_diffusion_model:
            ssd_requested = False
        elif ssd_requested:
            in_mem_after = (
                bool(request.dflash_in_memory_cache)
                if "dflash_in_memory_cache" in sent
                else current_settings.dflash_in_memory_cache
            )
            if not in_mem_after:
                raise HTTPException(
                    status_code=400,
                    detail="DFlash SSD cache requires the in-memory cache to be enabled.",
                )
            ssd_dir = getattr(
                getattr(_get_engine_pool(), "_scheduler_config", None),
                "paged_ssd_cache_dir",
                None,
            )
            if not ssd_dir:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "DFlash SSD cache requires oMLX paged SSD cache to be enabled "
                        "(set --paged-ssd-cache-dir or configure it in settings)."
                    ),
                )
        current_settings.dflash_ssd_cache = ssd_requested
    if "dflash_ssd_cache_max_bytes" in sent and request.dflash_ssd_cache_max_bytes:
        current_settings.dflash_ssd_cache_max_bytes = int(
            request.dflash_ssd_cache_max_bytes
        )
    if "dflash_draft_window_size" in sent:
        # 0 / None / negative → fall back to dflash-mlx internal default (1024).
        value = request.dflash_draft_window_size
        current_settings.dflash_draft_window_size = (
            int(value) if value and value > 0 else None
        )
    if "dflash_draft_sink_size" in sent:
        # Negative is invalid; 0 is a legal sink-size (no sink tokens).
        value = request.dflash_draft_sink_size
        current_settings.dflash_draft_sink_size = (
            int(value) if value is not None and value >= 0 else None
        )
    if "dflash_verify_mode" in sent:
        value = request.dflash_verify_mode
        # dflash-mlx accepts: dflash | adaptive | ddtree | off.
        # Anything else (including empty string) → revert to dflash default.
        current_settings.dflash_verify_mode = (
            value if value in ("dflash", "adaptive", "ddtree", "off") else None
        )

    # Native MTP (mlx-lm PR 990 / PR 15 monkey-patch)
    if "mtp_enabled" in sent:
        new_mtp_enabled = False if is_diffusion_model else bool(request.mtp_enabled)
        if new_mtp_enabled:
            # Compatibility check: the model needs MTP heads in config.json AND
            # the model_type must be one PR 990 / PR 15 covers AND the weight
            # files must actually contain MTP tensors (mtp.* or the native
            # nextn layers). The last check is the one that catches
            # mlx-community converted weights where the default sanitize
            # path stripped the MTP heads.
            import json
            from pathlib import Path

            from ..utils.model_loading import (
                _checkpoint_has_mtp_weights,
                _is_mtp_compatible,
            )

            cfg_path = Path(entry.model_path) / "config.json"
            if not cfg_path.exists():
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"MTP enabled but config.json missing at {cfg_path}; "
                        "cannot verify MTP compatibility."
                    ),
                )
            try:
                cfg = json.loads(cfg_path.read_text())
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"MTP enabled but failed to read model config: {e}",
                )
            model_type = cfg.get("model_type")
            if not _is_mtp_compatible(cfg, model_type):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Model is not MTP-compatible (model_type={model_type!r}, "
                        f"mtp_num_hidden_layers={cfg.get('mtp_num_hidden_layers', 0)}). "
                        "Lightning MTP requires a Qwen3.5/3.6, DeepSeek-V4 or "
                        "GLM-5.2 checkpoint with MTP heads."
                    ),
                )
            if not _checkpoint_has_mtp_weights(entry.model_path):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Config declares MTP layers but the weight files contain "
                        "neither mtp.* tensors nor native nextn layers. Re-convert "
                        "from HF with a converter that preserves MTP weights. The "
                        "default mlx-lm sanitize() path strips them."
                    ),
                )
            # Mutual exclusion with DFlash — ModelSettings.__post_init__
            # also enforces this, but we surface a clearer error here.
            dflash_after = (
                bool(request.dflash_enabled)
                if "dflash_enabled" in sent
                else current_settings.dflash_enabled
            )
            if dflash_after:
                raise HTTPException(
                    status_code=400,
                    detail="MTP and DFlash cannot both be enabled; choose one speculative-decoding path.",
                )
        current_settings.mtp_enabled = new_mtp_enabled

    # VLM MTP (mlx-vlm f96138e+, gemma4_assistant drafter)
    if "vlm_mtp_enabled" in sent:
        new_vlm_mtp = False if is_diffusion_model else bool(request.vlm_mtp_enabled)
        if new_vlm_mtp:
            drafter_after = (
                request.vlm_mtp_draft_model
                if "vlm_mtp_draft_model" in sent
                else current_settings.vlm_mtp_draft_model
            )
            if not drafter_after:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "vlm_mtp_enabled requires vlm_mtp_draft_model "
                        "(path to a gemma4_assistant drafter, "
                        "e.g. 'gemma-4-26B-A4B-it-assistant')."
                    ),
                )
            # Mutex enforced again at ModelSettings.__post_init__ for
            # last-mile safety, but surface a clearer error here.
            for other_field, other_label in (
                ("dflash_enabled", "DFlash"),
                ("specprefill_enabled", "SpecPrefill"),
                ("mtp_enabled", "MTP"),
                ("turboquant_kv_enabled", "TurboQuant KV"),
            ):
                other_after = (
                    bool(getattr(request, other_field))
                    if other_field in sent
                    else getattr(current_settings, other_field)
                )
                if other_after:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"vlm_mtp_enabled and {other_label} cannot both be "
                            "enabled; choose one speculative-decoding path."
                        ),
                    )
        current_settings.vlm_mtp_enabled = new_vlm_mtp
    if "vlm_mtp_draft_model" in sent:
        current_settings.vlm_mtp_draft_model = request.vlm_mtp_draft_model or None
    if "vlm_mtp_draft_block_size" in sent:
        current_settings.vlm_mtp_draft_block_size = request.vlm_mtp_draft_block_size

    if "reasoning_parser" in sent:
        current_settings.reasoning_parser = request.reasoning_parser or None
    if "guided_grammar_enabled" in sent:
        current_settings.guided_grammar_enabled = (
            request.guided_grammar_enabled or False
        )
    if "guided_grammar" in sent:
        grammar = request.guided_grammar.strip() if request.guided_grammar else None
        current_settings.guided_grammar = grammar or None
    if request.is_pinned is not None:
        current_settings.is_pinned = request.is_pinned
        # Also update the engine pool entry
        entry.is_pinned = request.is_pinned
    if request.is_default is not None:
        current_settings.is_default = request.is_default
        # Update server_state.default_model if setting as default
        if request.is_default and server_state:
            server_state.default_model = model_id
    if request.is_hidden is not None:
        current_settings.is_hidden = request.is_hidden
    if request.is_favorite is not None:
        current_settings.is_favorite = request.is_favorite
    if "trust_remote_code" in sent:
        current_settings.trust_remote_code = bool(request.trust_remote_code)

    if is_diffusion_model:
        _sanitize_diffusion_model_settings(current_settings)

    # If an active profile was set, clear it when the user's save diverges
    # from the profile's stored values.  Only compare fields present in
    # both the profile and the current settings — new fields in the model
    # settings that the profile doesn't have are silently merged in, and
    # removed fields (no longer in the profile) are skipped.
    if current_settings.active_profile_name:
        profile = settings_manager.get_profile(
            model_id, current_settings.active_profile_name
        )
        if profile is None:
            current_settings.active_profile_name = None
        else:
            profile_settings = profile.get("settings", {}) or {}
            candidate = current_settings.to_dict()
            diverged = False
            for key, expected in profile_settings.items():
                # Profile None means "unconstrained" — candidate.to_dict()
                # drops None, so treat profile None as no constraint to
                # keep the comparison symmetric.
                if expected is None:
                    continue
                if key not in candidate:
                    diverged = True
                    break
                if candidate[key] != expected:
                    diverged = True
                    break
            if diverged:
                current_settings.active_profile_name = None
            else:
                new_fields = {
                    k: v
                    for k, v in candidate.items()
                    if k not in profile_settings and k not in EXCLUDED_FROM_PROFILES
                }
                if new_fields:
                    profile_settings.update(new_fields)
                    profile["settings"] = profile_settings
                    settings_manager.update_profile(
                        model_id,
                        current_settings.active_profile_name,
                        settings=profile_settings,
                    )

    # Persist settings
    settings_manager.set_settings(model_id, current_settings)

    # A failed load is cached to prevent clients from retrying the same broken
    # configuration on every request. Clear that cache only when the effective
    # load-time configuration changed so the next request can try the new
    # configuration without requiring a full model rescan.
    current_load_signature = engine_pool._engine_runtime_signature(
        model_id, current_settings
    )
    if entry.load_failed and (
        prev_engine_type != entry.engine_type
        or prev_load_signature != current_load_signature
    ):
        engine_pool._clear_load_failure(entry)
        logger.info(
            "Cleared cached load failure for %s after load-time settings changed.",
            model_id,
        )

    # Auto-unload (and re-load if pinned) when a setting that only takes
    # effect at engine construction time is changed on a loaded model.
    requires_reload = entry.engine is not None and (
        ("model_type_override" in sent and entry.engine_type != prev_engine_type)
        or "index_cache_freq" in sent
        or "cache_moe_memory_tier" in sent
        or "dflash_enabled" in sent
        or "dflash_draft_model" in sent
        or "dflash_draft_quant_enabled" in sent
        or "dflash_draft_quant_weight_bits" in sent
        or "dflash_draft_quant_activation_bits" in sent
        or "dflash_draft_quant_group_size" in sent
        or "dflash_max_ctx" in sent
        or "dflash_in_memory_cache" in sent
        or "dflash_in_memory_cache_max_entries" in sent
        or "dflash_in_memory_cache_max_bytes" in sent
        or "dflash_ssd_cache" in sent
        or "dflash_ssd_cache_max_bytes" in sent
        # trust_remote_code is plumbed at model load time; toggling it on
        # an already-loaded engine has no effect until reload.
        or "trust_remote_code" in sent
    )
    auto_unloaded = False
    auto_reloaded = False
    if requires_reload:
        was_pinned = entry.is_pinned
        try:
            logger.info(
                f"Settings changed for loaded model {model_id}, auto-unloading."
            )
            await engine_pool._unload_engine(model_id)
            auto_unloaded = True
        except Exception as e:
            logger.warning(f"Auto-unload failed for {model_id}: {e}")
        if auto_unloaded and was_pinned:
            try:
                await engine_pool._load_engine(model_id)
                auto_reloaded = True
                logger.info(f"Auto-reloaded pinned model {model_id} with new settings.")
            except Exception as e:
                logger.warning(f"Auto-reload failed for pinned model {model_id}: {e}")

    return {
        "success": True,
        "model_id": model_id,
        "settings": current_settings.to_dict(),
        "model_type": entry.model_type,
        "engine_type": entry.engine_type,
        "requires_reload": requires_reload,
        "auto_unloaded": auto_unloaded,
        "auto_reloaded": auto_reloaded,
    }


# =============================================================================
# Profile & Template endpoints
# =============================================================================


def _require_settings_manager():
    mgr = _get_settings_manager()
    if mgr is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    return mgr


def _require_model(model_id: str):
    pool = _get_engine_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Engine pool not initialized")
    entry = pool.get_entry(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
    return entry


def _model_aliases(
    settings_manager, *, exclude_model_id: str | None = None
) -> dict[str, str]:
    return {
        ms.model_alias: mid
        for mid, ms in settings_manager.get_all_settings().items()
        if mid != exclude_model_id and ms.model_alias
    }


def _raise_if_profile_id_conflicts_model_id(
    candidate_id: str,
    *,
    model_id: str,
    engine_pool,
):
    for existing_id in engine_pool.get_model_ids():
        if existing_id != model_id and existing_id == candidate_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Exposed profile model ID '{candidate_id}' conflicts with "
                    f"model directory name '{existing_id}'"
                ),
            )


def _raise_if_alias_conflicts_exposed_profiles(
    *,
    alias_value: str,
    model_id: str,
    settings_manager,
    engine_pool,
):
    exposed_ids = settings_manager.get_exposed_profile_model_ids()
    if alias_value in exposed_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Alias '{alias_value}' conflicts with an exposed profile model ID",
        )

    aliases = _model_aliases(settings_manager, exclude_model_id=model_id)
    for profile in settings_manager.list_profiles(model_id):
        if not profile.get("expose_as_model"):
            continue
        api_name = profile.get("api_name") or profile["name"]
        candidate_id = f"{alias_value}:{api_name}"
        _raise_if_profile_id_conflicts_model_id(
            candidate_id,
            model_id=model_id,
            engine_pool=engine_pool,
        )
        if candidate_id in aliases:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Alias '{alias_value}' would expose profile model ID "
                    f"'{candidate_id}', which conflicts with model alias "
                    f"for '{aliases[candidate_id]}'"
                ),
            )
        other_exposed_ids = settings_manager.get_exposed_profile_model_ids(
            exclude_model_id=model_id,
            exclude_profile_name=profile["name"],
        )
        if candidate_id in other_exposed_ids:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Alias '{alias_value}' would expose duplicate profile "
                    f"model ID '{candidate_id}'"
                ),
            )


@router.get("/api/models/{model_id}/profiles")
async def list_model_profiles(
    model_id: str,
    is_admin: bool = Depends(require_admin),
):
    mgr = _require_settings_manager()
    _require_model(model_id)
    return {"profiles": mgr.list_profiles(model_id)}


@router.post("/api/models/{model_id}/profiles")
async def create_model_profile(
    model_id: str,
    request: CreateProfileRequest,
    is_admin: bool = Depends(require_admin),
):
    from ..model_profiles import InvalidProfileNameError, filter_universal_fields

    mgr = _require_settings_manager()
    _require_model(model_id)
    engine_pool = _get_engine_pool()
    try:
        profile = mgr.save_profile(
            model_id=model_id,
            name=request.name,
            display_name=request.display_name,
            description=request.description,
            settings=request.settings or {},
            source_template=request.source_template,
            expose_as_model=request.expose_as_model,
            api_name=request.api_name,
            reserved_model_ids=(
                set(engine_pool.get_model_ids()) if engine_pool is not None else None
            ),
        )
    except InvalidProfileNameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if request.also_save_as_template:
        try:
            mgr.upsert_template(
                name=request.name,
                display_name=request.display_name,
                description=request.description,
                settings=filter_universal_fields(request.settings or {}),
            )
        except InvalidProfileNameError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"profile": profile}


@router.put("/api/models/{model_id}/profiles/{name}")
async def update_model_profile(
    model_id: str,
    name: str,
    request: UpdateProfileRequest,
    is_admin: bool = Depends(require_admin),
):
    from ..model_profiles import InvalidProfileNameError, filter_universal_fields

    mgr = _require_settings_manager()
    _require_model(model_id)
    engine_pool = _get_engine_pool()
    try:
        updated = mgr.update_profile(
            model_id=model_id,
            name=name,
            new_name=request.new_name,
            display_name=request.display_name,
            description=request.description,
            settings=request.settings,
            source_template=request.source_template,
            expose_as_model=request.expose_as_model,
            api_name=request.api_name,
            reserved_model_ids=(
                set(engine_pool.get_model_ids()) if engine_pool is not None else None
            ),
        )
    except InvalidProfileNameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Profile not found: {name}")

    if request.also_save_as_template and request.settings is not None:
        try:
            mgr.upsert_template(
                name=updated["name"],
                display_name=updated["display_name"],
                description=updated.get("description"),
                settings=filter_universal_fields(request.settings),
            )
        except InvalidProfileNameError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"profile": updated}


@router.delete("/api/models/{model_id}/profiles/{name}")
async def delete_model_profile(
    model_id: str,
    name: str,
    is_admin: bool = Depends(require_admin),
):
    mgr = _require_settings_manager()
    _require_model(model_id)
    if not mgr.delete_profile(model_id, name):
        raise HTTPException(status_code=404, detail=f"Profile not found: {name}")
    return {"deleted": True, "name": name}


@router.post("/api/models/{model_id}/profiles/{name}/apply")
async def apply_model_profile(
    model_id: str,
    name: str,
    is_admin: bool = Depends(require_admin),
):
    mgr = _require_settings_manager()
    entry = _require_model(model_id)
    is_diffusion_model = _entry_is_diffusion_model(entry)
    sanitizer = _sanitize_diffusion_settings_dict if is_diffusion_model else None
    applied = mgr.apply_profile(model_id, name, settings_sanitizer=sanitizer)
    if applied is None:
        raise HTTPException(status_code=404, detail=f"Profile not found: {name}")
    if is_diffusion_model:
        _sanitize_diffusion_model_settings(applied)
        mgr.set_settings(model_id, applied)
    return {"model_id": model_id, "settings": applied.to_dict()}


@router.get("/api/profile-fields")
async def get_profile_fields(is_admin: bool = Depends(require_admin)):
    from ..model_profiles import (
        MODEL_SPECIFIC_PROFILE_FIELDS,
        UNIVERSAL_PROFILE_FIELDS,
    )

    return {
        "universal": list(UNIVERSAL_PROFILE_FIELDS),
        "model_specific": list(MODEL_SPECIFIC_PROFILE_FIELDS),
    }


@router.get("/api/profile-templates")
async def list_templates(is_admin: bool = Depends(require_admin)):
    mgr = _require_settings_manager()
    return {"templates": mgr.list_templates()}


@router.post("/api/profile-templates")
async def create_template(
    request: CreateTemplateRequest,
    is_admin: bool = Depends(require_admin),
):
    from ..model_profiles import InvalidProfileNameError

    mgr = _require_settings_manager()
    try:
        tmpl = mgr.save_template(
            name=request.name,
            display_name=request.display_name,
            description=request.description,
            settings=request.settings or {},
        )
    except InvalidProfileNameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"template": tmpl}


@router.put("/api/profile-templates/{name}")
async def update_template(
    name: str,
    request: UpdateTemplateRequest,
    is_admin: bool = Depends(require_admin),
):
    from ..model_profiles import InvalidProfileNameError

    mgr = _require_settings_manager()
    try:
        updated = mgr.update_template(
            name=name,
            new_name=request.new_name,
            display_name=request.display_name,
            description=request.description,
            settings=request.settings,
        )
    except InvalidProfileNameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Template not found: {name}")
    return {"template": updated}


@router.delete("/api/profile-templates/{name}")
async def delete_template(
    name: str,
    is_admin: bool = Depends(require_admin),
):
    mgr = _require_settings_manager()
    if not mgr.delete_template(name):
        raise HTTPException(status_code=404, detail=f"Template not found: {name}")
    return {"deleted": True, "name": name}


# =============================================================================
# Preset refresh (proxy to omlx.ai to avoid CORS)
# =============================================================================


@router.post("/api/presets/refresh")
async def refresh_presets(is_admin: bool = Depends(require_admin)):
    """Fetch the latest preset bundle from omlx.ai and return it.

    The client uses this instead of fetching omlx.ai directly so we do not
    depend on CORS headers on the remote host. Any failure is surfaced as 502
    so the client can silently fall back to the bundled presets.
    """
    try:
        resp = await asyncio.to_thread(
            requests.get,
            PRESET_REMOTE_URL,
            timeout=10,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {e}")
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Remote returned {resp.status_code}",
        )
    try:
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Invalid JSON: {e}")


@router.get("/api/models/{model_id}/generation_config")
async def get_generation_config(
    model_id: str,
    is_admin: bool = Depends(require_admin),
):
    """
    Read model config files and return recommended defaults.

    Reads generation_config.json for sampling parameters and config.json
    for max_context_window (max_position_embeddings).

    Args:
        model_id: The model identifier.

    Returns:
        JSON with recommended parameters from the model's config files.

    Raises:
        HTTPException: 404 if model not found or no config files exist.
    """
    import json as json_module

    engine_pool = _get_engine_pool()
    if engine_pool is None:
        raise HTTPException(status_code=503, detail="Engine pool not initialized")

    entry = engine_pool.get_entry(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")

    model_path = Path(entry.model_path)
    result = {}

    # Read generation_config.json for sampling parameters
    gen_config_path = model_path / "generation_config.json"
    if gen_config_path.exists():
        try:
            with open(gen_config_path, encoding="utf-8") as f:
                gen_config = json_module.load(f)

            # Temperature: if do_sample is false, effective temperature is 0
            do_sample = gen_config.get("do_sample", True)
            if "temperature" in gen_config:
                result["temperature"] = (
                    0.0 if not do_sample else gen_config["temperature"]
                )

            if "top_p" in gen_config:
                result["top_p"] = gen_config["top_p"]

            if "top_k" in gen_config:
                result["top_k"] = gen_config["top_k"]

            if "repetition_penalty" in gen_config:
                result["repetition_penalty"] = gen_config["repetition_penalty"]

        except (json_module.JSONDecodeError, OSError) as e:
            logger.warning(
                f"Failed to parse generation_config.json for {model_id}: {e}"
            )

    # Read config.json for max_position_embeddings → max_context_window
    config_path = model_path / "config.json"
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                model_config = json_module.load(f)

            max_pos = (
                model_config.get("max_position_embeddings")
                or model_config.get("max_seq_len")
                or model_config.get("seq_length")
                or model_config.get("n_positions")
            )

            # Nested config fallback (VLM, MoE models like Qwen3.5, GLM-4V)
            if not max_pos:
                text_config = model_config.get("text_config", {})
                if isinstance(text_config, dict):
                    max_pos = (
                        text_config.get("max_position_embeddings")
                        or text_config.get("max_seq_len")
                        or text_config.get("seq_length")
                        or text_config.get("n_positions")
                    )

            if max_pos and isinstance(max_pos, int):
                result["max_context_window"] = max_pos

        except (json_module.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to parse config.json for {model_id}: {e}")

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No config files with defaults found for {model_id}",
        )

    return result


# =============================================================================
# Global Settings API Routes
# =============================================================================


@router.get("/api/server-info")
async def get_server_info(is_admin: bool = Depends(require_admin)):
    """Return server connectivity metadata for the dashboard.

    Provides the configured host, port, and the list of user-facing
    aliases (hostnames/IPs) that the dashboard can use to render
    selectable API URL hints.

    Returns:
        JSON object with ``host``, ``port``, and ``aliases``.

    Raises:
        HTTPException: 401 if not authenticated, 503 if server not initialized.
    """
    from ..utils.network import detect_server_aliases

    global_settings = _get_global_settings()
    if global_settings is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    configured = list(global_settings.server.server_aliases)
    if configured:
        aliases = configured
    else:
        # Fall back to live detection if persisted list is empty.
        aliases = detect_server_aliases(host=global_settings.server.host)

    return {
        "host": global_settings.server.host,
        "port": global_settings.server.port,
        "aliases": aliases,
    }


def _schedule_self_terminate(delay: float = 0.5) -> None:
    """Schedule ``os.kill(getpid(), SIGTERM)`` on the running loop.

    Extracted from the restart handler so tests can patch this seam
    instead of mocking ``asyncio.get_running_loop`` globally (which
    interferes with FastAPI's TestClient portal).
    """
    pid = os.getpid()

    def _kill() -> None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            # Already exited (e.g. concurrent SIGTERM) — nothing to do.
            pass
        except Exception:  # pragma: no cover — best-effort signal.
            logger.exception("Failed to self-terminate for restart")

    asyncio.get_running_loop().call_later(delay, _kill)


@router.post("/api/server/restart")
async def restart_server(is_admin: bool = Depends(require_admin)):
    """Trigger a server restart via the menubar supervisor.

    The handler does not perform the restart itself — it returns 202 and
    schedules ``os.kill(os.getpid(), SIGTERM)`` 500ms after the response
    is queued. The menubar app's ``ServerManager._health_check_loop``
    detects the process exit and respawns the server with a short
    backoff (~5s).

    Gated by the ``OMLX_SUPERVISED`` environment variable so plain
    ``omlx serve`` (no supervisor) returns 503 rather than killing the
    server with no respawn path.
    """
    supervisor = os.environ.get("OMLX_SUPERVISED")
    if not supervisor:
        raise HTTPException(
            status_code=503,
            detail=(
                "Server is not running under a supervisor that can "
                "respawn it. Restart unavailable — use the menu bar "
                "app's Restart, or restart from your shell."
            ),
        )

    _schedule_self_terminate(0.5)
    logger.warning("Server restart requested (supervisor=%s)", supervisor)

    # 5s backoff in ServerManager + ~1-2s startup = ~7s downtime budget.
    return JSONResponse(
        status_code=202,
        content={
            "status": "restarting",
            "supervisor": supervisor,
            "expected_downtime_seconds": 7,
        },
    )


@router.get("/api/global-settings")
async def get_global_settings(is_admin: bool = Depends(require_admin)):
    """
    Get current global server settings.

    Returns the full global settings including server, model, scheduler,
    cache, and MCP configurations.

    Returns:
        JSON object with global settings.

    Raises:
        HTTPException: 401 if not authenticated, 503 if server not initialized.
    """
    global_settings = _get_global_settings()

    if global_settings is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    # Get system memory info for auto calculation
    memory_info = get_system_memory_info()

    # Get SSD disk info for cache directory
    cache_dir = global_settings.cache.ssd_cache_dir or str(
        global_settings.cache.get_ssd_cache_dir(global_settings.base_path)
    )
    disk_info = get_ssd_disk_info(cache_dir)

    return {
        "base_path": str(global_settings.base_path),
        "server": {
            "host": global_settings.server.host,
            "port": global_settings.server.port,
            "log_level": global_settings.server.log_level,
            "server_aliases": list(global_settings.server.server_aliases),
            "sse_keepalive_mode": global_settings.server.sse_keepalive_mode,
            "auto_start_on_launch": global_settings.server.auto_start_on_launch,
            "burst_decode_mode": global_settings.server.burst_decode_mode,
            "preserve_mid_system_cache": getattr(
                global_settings.server,
                "preserve_mid_system_cache",
                True,
            ),
        },
        "model": {
            "model_dirs": [
                str(d)
                for d in global_settings.model.get_model_dirs(global_settings.base_path)
            ],
            "model_dir": str(
                global_settings.model.get_model_dir(global_settings.base_path)
            ),
            "effective_model_dirs": [
                str(d) for d in global_settings.get_effective_model_dirs()
            ],
            "model_fallback": global_settings.model.model_fallback,
            "hide_helper_models": global_settings.model.hide_helper_models,
        },
        "memory": {
            "prefill_memory_guard": global_settings.memory.prefill_memory_guard,
            "memory_guard_tier": global_settings.memory.memory_guard_tier,
            "memory_guard_custom_ceiling_gb": global_settings.memory.memory_guard_custom_ceiling_gb,
        },
        "scheduler": {
            "max_concurrent_requests": global_settings.scheduler.max_concurrent_requests,
            "embedding_batch_size": global_settings.scheduler.embedding_batch_size,
            "chunked_prefill": global_settings.scheduler.chunked_prefill,
            "prefill_priority": global_settings.scheduler.prefill_priority,
        },
        "cache": {
            "enabled": global_settings.cache.enabled,
            "ssd_cache_dir": cache_dir,
            # Resolve "auto" to actual value (10% of SSD capacity)
            "ssd_cache_max_size": _format_cache_size(
                global_settings.cache.get_ssd_cache_max_size_bytes(
                    global_settings.base_path
                )
            ),
            "hot_cache_only": global_settings.cache.hot_cache_only,
            "hot_cache_max_size": global_settings.cache.hot_cache_max_size,
            "initial_cache_blocks": global_settings.cache.initial_cache_blocks,
        },
        "mcp": {
            "config_path": global_settings.mcp.config_path,
        },
        "huggingface": {
            "endpoint": global_settings.huggingface.endpoint,
            "hf_cache_enabled": global_settings.huggingface.hf_cache_enabled,
            "hf_cache_path": str(global_settings.get_hf_cache_dir()),
        },
        "modelscope": {
            "endpoint": global_settings.modelscope.endpoint,
        },
        "network": {
            "http_proxy": global_settings.network.http_proxy,
            "https_proxy": global_settings.network.https_proxy,
            "no_proxy": global_settings.network.no_proxy,
            "ca_bundle": global_settings.network.ca_bundle,
        },
        "sampling": {
            "max_context_window": global_settings.sampling.max_context_window,
            "max_context_window_policy": (
                global_settings.sampling.max_context_window_policy
            ),
            "max_tokens": global_settings.sampling.max_tokens,
            "temperature": global_settings.sampling.temperature,
            "top_p": global_settings.sampling.top_p,
            "top_k": global_settings.sampling.top_k,
            "repetition_penalty": global_settings.sampling.repetition_penalty,
        },
        "auth": {
            "api_key_set": bool(global_settings.auth.api_key),
            "api_key": global_settings.auth.api_key or "",
            "skip_api_key_verification": global_settings.auth.skip_api_key_verification,
            "sub_keys": [sk.to_dict() for sk in global_settings.auth.sub_keys],
        },
        "claude_code": {
            "mode": global_settings.claude_code.mode,
            "opus_model": global_settings.claude_code.opus_model,
            "sonnet_model": global_settings.claude_code.sonnet_model,
            "haiku_model": global_settings.claude_code.haiku_model,
        },
        "integrations": {
            "codex_model": global_settings.integrations.codex_model,
            "opencode_model": global_settings.integrations.opencode_model,
            "openclaw_model": global_settings.integrations.openclaw_model,
            "hermes_model": global_settings.integrations.hermes_model,
            "pi_model": global_settings.integrations.pi_model,
            "copilot_model": global_settings.integrations.copilot_model,
            "openclaw_tools_profile": global_settings.integrations.openclaw_tools_profile,
            "markitdown_enabled": global_settings.integrations.markitdown_enabled,
            "markitdown_expose_model": global_settings.integrations.markitdown_expose_model,
            "markitdown_max_file_size_mb": global_settings.integrations.markitdown_max_file_size_mb,
            "markitdown_max_files_per_request": global_settings.integrations.markitdown_max_files_per_request,
            "markitdown_pdf_processing_engine": global_settings.integrations.markitdown_pdf_processing_engine,
        },
        "system": {
            "total_memory_bytes": memory_info["total_bytes"],
            "total_memory": memory_info["total_formatted"],
            "auto_model_memory": memory_info["auto_limit_formatted"],
            "available_memory_bytes": memory_info["available_bytes"],
            "omlx_phys_footprint_bytes": memory_info["omlx_phys_footprint_bytes"],
            "free_memory_bytes": memory_info["free_memory_bytes"],
            "inactive_memory_bytes": memory_info["inactive_memory_bytes"],
            "active_memory_bytes": memory_info["active_memory_bytes"],
            "iogpu_wired_limit_bytes": memory_info["iogpu_wired_limit_bytes"],
            "omlx_wired_limit_request_bytes": memory_info[
                "omlx_wired_limit_request_bytes"
            ],
            "ssd_total_bytes": disk_info["total_bytes"],
            "ssd_total": disk_info["total_formatted"],
        },
        "ui": {
            "language": global_settings.ui.language,
        },
        "idle_timeout": {
            "idle_timeout_seconds": global_settings.idle_timeout.idle_timeout_seconds,
        },
    }


@router.post("/api/global-settings")
async def update_global_settings(
    request: GlobalSettingsRequest,
    is_admin: bool = Depends(require_admin),
):
    """
    Update global server settings.

    Updates are persisted to the global settings file. Some settings
    (log_level, model_dir, memory_guard_tier, cache) are applied immediately,
    while others (host, port, scheduler, mcp) require server restart.

    Args:
        request: GlobalSettingsRequest with the new settings.

    Returns:
        JSON response with success status, message, and list of runtime-applied settings.

    Raises:
        HTTPException: 401 if not authenticated, 503 if server not initialized,
                      400 if validation fails.
    """
    global_settings = _get_global_settings()

    if global_settings is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    # Track which settings were applied at runtime
    runtime_applied: list[str] = []
    pending_embedding_batch_size: int | None = None
    previous_embedding_batch_size: int | None = None

    # Apply server settings
    if request.host is not None:
        from ..utils.network import is_valid_bind_host

        parts = [h.strip() for h in request.host.split(",") if h.strip()]
        if not parts:
            raise HTTPException(status_code=400, detail="Host cannot be empty")
        for part in parts:
            if not is_valid_bind_host(part):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid host: {part!r} (must be a hostname or IP address)",
                )
        global_settings.server.host = request.host
    if request.port is not None:
        global_settings.server.port = request.port
    if request.log_level is not None:
        global_settings.server.log_level = request.log_level
        # Apply log level at runtime
        _apply_log_level_runtime(request.log_level)
        runtime_applied.append("log_level")
    if request.sse_keepalive_mode is not None:
        valid_modes = {"chunk", "comment", "off"}
        if request.sse_keepalive_mode not in valid_modes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sse_keepalive_mode: {request.sse_keepalive_mode} "
                f"(must be one of {sorted(valid_modes)})",
            )
        global_settings.server.sse_keepalive_mode = request.sse_keepalive_mode
        runtime_applied.append("sse_keepalive_mode")
    if request.burst_decode_mode is not None:
        if request.burst_decode_mode not in BURST_DECODE_MODES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid burst_decode_mode: {request.burst_decode_mode} "
                f"(must be one of {sorted(BURST_DECODE_MODES)})",
            )
        mode = request.burst_decode_mode
        global_settings.server.burst_decode_mode = mode
        # Seed env so models loaded later pick up the mode without a restart.
        for _key, _value in burst_decode_env(mode).items():
            os.environ[_key] = _value
        # Hot-apply to every loaded engine. EngineConfig is a mutable dataclass
        # and its burst fields are read fresh each decode burst
        # (EngineCore._step_burst), so this takes effect on the next token.
        max_steps, single_s = BURST_DECODE_MODES[mode]
        from ..server import _server_state

        pool = _server_state.engine_pool
        if pool is not None:
            for _mid, entry in pool._entries.items():
                if entry is None or entry.engine is None:
                    continue
                async_core = getattr(entry.engine, "_engine", None)
                core = (
                    getattr(async_core, "engine", None)
                    if async_core is not None
                    else None
                )
                cfg = getattr(core, "config", None) if core is not None else None
                if cfg is not None and hasattr(cfg, "decode_burst_budget_single_s"):
                    cfg.decode_burst_max_steps = max_steps
                    cfg.decode_burst_budget_single_s = single_s
        runtime_applied.append("burst_decode_mode")
        logger.info(f"Burst Decode mode set to '{mode}'")
    if request.auto_start_on_launch is not None:
        global_settings.server.auto_start_on_launch = request.auto_start_on_launch
        runtime_applied.append("auto_start_on_launch")
    if request.preserve_mid_system_cache is not None:
        global_settings.server.preserve_mid_system_cache = (
            request.preserve_mid_system_cache
        )
        runtime_applied.append("preserve_mid_system_cache")

    if request.server_aliases is not None:
        from ..utils.network import is_valid_alias

        cleaned: list[str] = []
        seen: set[str] = set()
        for alias in request.server_aliases:
            if not isinstance(alias, str):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid server alias: each alias must be a string",
                )
            value = alias.strip()
            if not value or value in seen:
                continue
            if not is_valid_alias(value):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid server alias: {value!r} (must be a hostname or IP address)",
                )
            seen.add(value)
            cleaned.append(value)
        global_settings.server.server_aliases = cleaned
        runtime_applied.append("server_aliases")

    # Apply model settings
    new_dirs = None
    if request.model_dirs is not None:
        new_dirs = [d for d in request.model_dirs if d.strip()]
    elif request.model_dir is not None:
        new_dirs = [request.model_dir]

    if new_dirs is not None:
        old_dirs = global_settings.model.model_dirs
        if new_dirs != old_dirs:
            effective_dirs = [
                str(d) for d in global_settings.get_effective_model_dirs(new_dirs)
            ]
            success, msg = await _apply_model_dirs_runtime(effective_dirs)
            if success:
                global_settings.model.model_dirs = new_dirs
                global_settings.model.model_dir = new_dirs[0] if new_dirs else None
                runtime_applied.append("model_dirs")
                logger.info(msg)
            else:
                raise HTTPException(
                    status_code=400, detail=f"Failed to change model directories: {msg}"
                )

    if request.model_fallback is not None:
        global_settings.model.model_fallback = request.model_fallback
        runtime_applied.append("model_fallback")
    if request.hide_helper_models is not None:
        global_settings.model.hide_helper_models = request.hide_helper_models
        runtime_applied.append("hide_helper_models")

    # Apply memory guard tier + custom ceiling change (Live)
    if (
        request.memory_guard_tier is not None
        or request.memory_guard_custom_ceiling_gb is not None
    ):
        if request.memory_guard_tier is not None:
            global_settings.memory.memory_guard_tier = request.memory_guard_tier
        if request.memory_guard_custom_ceiling_gb is not None:
            global_settings.memory.memory_guard_custom_ceiling_gb = float(
                request.memory_guard_custom_ceiling_gb
            )
        try:
            success, msg = await _apply_memory_guard_tier_runtime(
                tier=request.memory_guard_tier,
                custom_ceiling_gb=request.memory_guard_custom_ceiling_gb,
            )
            if success:
                runtime_applied.append("memory_guard_tier")
                logger.info(msg)
            else:
                logger.warning(f"Failed to apply memory_guard_tier: {msg}")
        except Exception as e:
            logger.warning(f"Error applying memory_guard_tier: {e}")

    # Apply prefill memory guard setting (Live)
    if request.memory_prefill_memory_guard is not None:
        global_settings.memory.prefill_memory_guard = (
            request.memory_prefill_memory_guard
        )
        from ..server import _server_state

        if _server_state.process_memory_enforcer is not None:
            _server_state.process_memory_enforcer.prefill_memory_guard = (
                request.memory_prefill_memory_guard
            )
        runtime_applied.append("prefill_memory_guard")
        logger.info(
            f"Prefill memory guard "
            f"{'enabled' if request.memory_prefill_memory_guard else 'disabled'}"
        )

    # Apply scheduler settings (restart required)
    if request.max_concurrent_requests is not None:
        global_settings.scheduler.max_concurrent_requests = (
            request.max_concurrent_requests
        )

    # Apply embedding batch size setting (Live for loaded embedding engines)
    if request.embedding_batch_size is not None:
        if request.embedding_batch_size <= 0:
            raise HTTPException(
                status_code=400,
                detail="Invalid embedding_batch_size: must be > 0",
            )
        pending_embedding_batch_size = request.embedding_batch_size

    # Apply chunked prefill setting (Live)
    if request.chunked_prefill is not None:
        global_settings.scheduler.chunked_prefill = request.chunked_prefill
        from ..server import _server_state

        pool = _server_state.engine_pool
        if pool is not None:
            for mid, entry in pool._entries.items():
                if entry is None or entry.engine is None:
                    continue
                async_core = getattr(entry.engine, "_engine", None)
                core = (
                    getattr(async_core, "engine", None)
                    if async_core is not None
                    else None
                )
                scheduler = (
                    getattr(core, "scheduler", None) if core is not None else None
                )
                if scheduler is not None and hasattr(scheduler, "config"):
                    scheduler.config.chunked_prefill = request.chunked_prefill
        runtime_applied.append("chunked_prefill")
        logger.info(
            f"Chunked prefill {'enabled' if request.chunked_prefill else 'disabled'}"
        )

    # Apply prefill priority setting (Live)
    if request.prefill_priority is not None:
        value = request.prefill_priority.strip().lower()
        if value not in ("context", "speed"):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid prefill_priority: '{request.prefill_priority}' "
                    f"(must be 'context' or 'speed')"
                ),
            )
        global_settings.scheduler.prefill_priority = value
        from ..server import _server_state

        pool = _server_state.engine_pool
        if pool is not None:
            # Engines loaded from now on build their Scheduler from the
            # pool's stored config — without this, a bench/reload after the
            # toggle would silently revert to the boot-time mode.
            pool_config = getattr(pool, "_scheduler_config", None)
            if pool_config is not None:
                pool_config.prefill_speed_priority = value == "speed"
            for mid, entry in pool._entries.items():
                if entry is None or entry.engine is None:
                    continue
                async_core = getattr(entry.engine, "_engine", None)
                core = (
                    getattr(async_core, "engine", None)
                    if async_core is not None
                    else None
                )
                scheduler = (
                    getattr(core, "scheduler", None) if core is not None else None
                )
                if scheduler is not None:
                    scheduler._prefill_speed_priority = value == "speed"
                    if hasattr(scheduler, "config"):
                        scheduler.config.prefill_speed_priority = value == "speed"
        runtime_applied.append("prefill_priority")
        logger.info(f"Prefill priority set to '{value}'")

    if request.hot_cache_max_size is not None:
        try:
            _parse_hot_cache_max_size(request.hot_cache_max_size)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Apply cache settings
    cache_changed = False
    if request.cache_enabled is not None:
        global_settings.cache.enabled = request.cache_enabled
        cache_changed = True
    if request.ssd_cache_dir is not None:
        global_settings.cache.ssd_cache_dir = request.ssd_cache_dir
        cache_changed = True
    if request.ssd_cache_max_size is not None:
        global_settings.cache.ssd_cache_max_size = request.ssd_cache_max_size
        cache_changed = True
    if request.hot_cache_only is not None:
        global_settings.cache.hot_cache_only = request.hot_cache_only
    if request.hot_cache_max_size is not None:
        global_settings.cache.hot_cache_max_size = request.hot_cache_max_size
        cache_changed = True
    if request.initial_cache_blocks is not None:
        global_settings.cache.initial_cache_blocks = request.initial_cache_blocks

    if cache_changed:
        success, msg = await _apply_cache_settings_runtime(
            request.cache_enabled,
            request.ssd_cache_dir,
            request.ssd_cache_max_size,
            global_settings,
            hot_cache_max_size=request.hot_cache_max_size,
        )
        if success:
            runtime_applied.append("cache")
            logger.info(msg)
        else:
            logger.warning(f"Failed to apply cache settings runtime: {msg}")

    # Apply MCP settings (restart required)
    if request.mcp_config is not None:
        global_settings.mcp.config_path = (
            request.mcp_config if request.mcp_config else None
        )

    # Apply HuggingFace settings (Live - immediately applied via env var)
    if request.hf_endpoint is not None:
        global_settings.huggingface.endpoint = request.hf_endpoint
        if request.hf_endpoint:
            os.environ["HF_ENDPOINT"] = request.hf_endpoint
        elif "HF_ENDPOINT" in os.environ:
            del os.environ["HF_ENDPOINT"]
        runtime_applied.append("hf_endpoint")
        logger.info(
            f"HuggingFace endpoint updated to: " f"{request.hf_endpoint or '(default)'}"
        )
    if request.hf_cache_enabled is not None:
        if global_settings.huggingface.hf_cache_enabled != request.hf_cache_enabled:
            global_settings.huggingface.hf_cache_enabled = request.hf_cache_enabled
            effective_dirs = [
                str(d) for d in global_settings.get_effective_model_dirs()
            ]
            success, msg = await _apply_model_dirs_runtime(effective_dirs)
            if not success:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to change HuggingFace cache discovery: {msg}",
                )
            runtime_applied.append("hf_cache_enabled")
            logger.info(msg)

    # Apply ModelScope settings (Live - immediately applied via env var)
    if request.ms_endpoint is not None:
        global_settings.modelscope.endpoint = request.ms_endpoint
        if request.ms_endpoint:
            os.environ["MODELSCOPE_DOMAIN"] = request.ms_endpoint
        elif "MODELSCOPE_DOMAIN" in os.environ:
            del os.environ["MODELSCOPE_DOMAIN"]
        runtime_applied.append("ms_endpoint")
        logger.info(
            f"ModelScope endpoint updated to: " f"{request.ms_endpoint or '(default)'}"
        )

    # Apply network settings (Live - immediately applied via env vars)
    network_changed = False
    if request.network_http_proxy is not None:
        global_settings.network.http_proxy = request.network_http_proxy
        if request.network_http_proxy:
            os.environ["HTTP_PROXY"] = request.network_http_proxy
            os.environ["http_proxy"] = request.network_http_proxy
        else:
            os.environ.pop("HTTP_PROXY", None)
            os.environ.pop("http_proxy", None)
        network_changed = True

    if request.network_https_proxy is not None:
        global_settings.network.https_proxy = request.network_https_proxy
        if request.network_https_proxy:
            os.environ["HTTPS_PROXY"] = request.network_https_proxy
            os.environ["https_proxy"] = request.network_https_proxy
        else:
            os.environ.pop("HTTPS_PROXY", None)
            os.environ.pop("https_proxy", None)
        network_changed = True

    if request.network_no_proxy is not None:
        global_settings.network.no_proxy = request.network_no_proxy
        if request.network_no_proxy:
            os.environ["NO_PROXY"] = request.network_no_proxy
            os.environ["no_proxy"] = request.network_no_proxy
        else:
            os.environ.pop("NO_PROXY", None)
            os.environ.pop("no_proxy", None)
        network_changed = True

    if request.network_ca_bundle is not None:
        global_settings.network.ca_bundle = request.network_ca_bundle
        if request.network_ca_bundle:
            os.environ["REQUESTS_CA_BUNDLE"] = request.network_ca_bundle
            os.environ["SSL_CERT_FILE"] = request.network_ca_bundle
        else:
            os.environ.pop("REQUESTS_CA_BUNDLE", None)
            os.environ.pop("SSL_CERT_FILE", None)
        network_changed = True

    if network_changed:
        runtime_applied.append("network")
        logger.info("Network settings updated")

    # Apply sampling settings (Live - immediately applied)
    sampling_changed = False
    if request.sampling_max_context_window is not None:
        global_settings.sampling.max_context_window = (
            request.sampling_max_context_window
        )
        sampling_changed = True
    if "sampling_max_context_window_policy" in request.model_fields_set:
        global_settings.sampling.max_context_window_policy = (
            request.sampling_max_context_window_policy
        )
        sampling_changed = True
    if request.sampling_max_tokens is not None:
        global_settings.sampling.max_tokens = request.sampling_max_tokens
        sampling_changed = True
    if request.sampling_temperature is not None:
        global_settings.sampling.temperature = request.sampling_temperature
        sampling_changed = True
    if request.sampling_top_p is not None:
        global_settings.sampling.top_p = request.sampling_top_p
        sampling_changed = True
    if request.sampling_top_k is not None:
        global_settings.sampling.top_k = request.sampling_top_k
        sampling_changed = True
    if request.sampling_repetition_penalty is not None:
        global_settings.sampling.repetition_penalty = (
            request.sampling_repetition_penalty
        )
        sampling_changed = True

    if sampling_changed:
        success, msg = _apply_sampling_settings_runtime(
            request.sampling_max_context_window,
            request.sampling_max_context_window_policy,
            "sampling_max_context_window_policy" in request.model_fields_set,
            request.sampling_max_tokens,
            request.sampling_temperature,
            request.sampling_top_p,
            request.sampling_top_k,
            request.sampling_repetition_penalty,
        )
        if success:
            runtime_applied.append("sampling")
            logger.info(msg)

    # Apply Claude Code settings (Live - immediately applied)
    claude_code_changed = False
    # mode: standard is-not-None check is correct — mode must never be null
    if request.claude_code_mode is not None:
        global_settings.claude_code.mode = request.claude_code_mode
        claude_code_changed = True
    # model fields: use model_fields_set to distinguish "field absent from POST body"
    # from "field explicitly sent as null" — null must clear the field to None.
    # DO NOT use `is not None` here: that would prevent clearing a model field to null.
    if "claude_code_opus_model" in request.model_fields_set:
        global_settings.claude_code.opus_model = request.claude_code_opus_model
        claude_code_changed = True
    if "claude_code_sonnet_model" in request.model_fields_set:
        global_settings.claude_code.sonnet_model = request.claude_code_sonnet_model
        claude_code_changed = True
    if "claude_code_haiku_model" in request.model_fields_set:
        global_settings.claude_code.haiku_model = request.claude_code_haiku_model
        claude_code_changed = True

    if claude_code_changed:
        runtime_applied.append("claude_code")
        logger.info(
            f"Claude Code settings updated: "
            f"mode={global_settings.claude_code.mode}, "
            f"opus={global_settings.claude_code.opus_model}, "
            f"sonnet={global_settings.claude_code.sonnet_model}, "
            f"haiku={global_settings.claude_code.haiku_model}"
        )

    # Apply integrations settings (Live - immediately applied)
    integrations_changed = False
    if "integrations_copilot_model" in request.model_fields_set:
        global_settings.integrations.copilot_model = request.integrations_copilot_model
        integrations_changed = True
    if "integrations_codex_model" in request.model_fields_set:
        global_settings.integrations.codex_model = request.integrations_codex_model
        integrations_changed = True
    if "integrations_opencode_model" in request.model_fields_set:
        global_settings.integrations.opencode_model = (
            request.integrations_opencode_model
        )
        integrations_changed = True
    if "integrations_openclaw_model" in request.model_fields_set:
        global_settings.integrations.openclaw_model = (
            request.integrations_openclaw_model
        )
        integrations_changed = True
    if "integrations_hermes_model" in request.model_fields_set:
        global_settings.integrations.hermes_model = request.integrations_hermes_model
        integrations_changed = True
    if "integrations_pi_model" in request.model_fields_set:
        global_settings.integrations.pi_model = request.integrations_pi_model
        integrations_changed = True
    if "integrations_openclaw_tools_profile" in request.model_fields_set:
        global_settings.integrations.openclaw_tools_profile = (
            request.integrations_openclaw_tools_profile
        )
        integrations_changed = True
    if "markitdown_enabled" in request.model_fields_set:
        global_settings.integrations.markitdown_enabled = bool(
            request.markitdown_enabled
        )
        integrations_changed = True
    if "markitdown_expose_model" in request.model_fields_set:
        global_settings.integrations.markitdown_expose_model = bool(
            request.markitdown_expose_model
        )
        integrations_changed = True
    if "markitdown_max_file_size_mb" in request.model_fields_set:
        if (
            request.markitdown_max_file_size_mb is None
            or request.markitdown_max_file_size_mb <= 0
        ):
            raise HTTPException(
                status_code=400,
                detail="markitdown_max_file_size_mb must be > 0",
            )
        global_settings.integrations.markitdown_max_file_size_mb = (
            request.markitdown_max_file_size_mb
        )
        integrations_changed = True
    if "markitdown_max_files_per_request" in request.model_fields_set:
        if (
            request.markitdown_max_files_per_request is None
            or request.markitdown_max_files_per_request <= 0
        ):
            raise HTTPException(
                status_code=400,
                detail="markitdown_max_files_per_request must be > 0",
            )
        global_settings.integrations.markitdown_max_files_per_request = (
            request.markitdown_max_files_per_request
        )
        integrations_changed = True
    if "markitdown_pdf_processing_engine" in request.model_fields_set:
        engine = (request.markitdown_pdf_processing_engine or "").strip()
        if not engine:
            raise HTTPException(
                status_code=400,
                detail="markitdown_pdf_processing_engine must not be empty",
            )
        global_settings.integrations.markitdown_pdf_processing_engine = engine
        integrations_changed = True

    if integrations_changed:
        runtime_applied.append("integrations")
        logger.info(
            f"Integration settings updated: "
            f"copilot={global_settings.integrations.copilot_model}, "
            f"codex={global_settings.integrations.codex_model}, "
            f"opencode={global_settings.integrations.opencode_model}, "
            f"openclaw={global_settings.integrations.openclaw_model}, "
            f"hermes={global_settings.integrations.hermes_model}, "
            f"pi={global_settings.integrations.pi_model}, "
            f"markitdown_enabled={global_settings.integrations.markitdown_enabled}, "
            f"markitdown_expose_model={global_settings.integrations.markitdown_expose_model}, "
            f"markitdown_pdf_processing_engine={global_settings.integrations.markitdown_pdf_processing_engine}"
        )

    # Apply UI settings
    if request.ui_language is not None:
        global_settings.ui.language = request.ui_language
        runtime_applied.append("ui_language")
        _refresh_i18n_globals()
        logger.info(f"UI language changed to: {request.ui_language}")

    # Apply idle timeout settings (Live)
    # Use model_fields_set to distinguish "explicitly sent as null" (disable)
    # from "not sent" (don't touch).
    if "idle_timeout_seconds" in request.model_fields_set:
        global_settings.idle_timeout.idle_timeout_seconds = request.idle_timeout_seconds
        runtime_applied.append("idle_timeout_seconds")
        if request.idle_timeout_seconds:
            logger.info(f"Idle timeout set to: {request.idle_timeout_seconds}s")
        else:
            logger.info("Idle timeout disabled")

    # Apply auth settings (API key change)
    if request.api_key is not None:
        from ..server import _server_state

        is_valid, error_msg = validate_api_key(request.api_key)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        global_settings.auth.api_key = request.api_key
        _server_state.api_key = request.api_key
        runtime_applied.append("api_key")
        logger.info("API key updated via admin settings")

    if request.skip_api_key_verification is not None:
        global_settings.auth.skip_api_key_verification = (
            request.skip_api_key_verification
        )
        runtime_applied.append("skip_api_key_verification")

    if pending_embedding_batch_size is not None:
        previous_embedding_batch_size = global_settings.scheduler.embedding_batch_size
        global_settings.scheduler.embedding_batch_size = pending_embedding_batch_size

    # Validate settings
    errors = global_settings.validate()
    if errors:
        if previous_embedding_batch_size is not None:
            global_settings.scheduler.embedding_batch_size = (
                previous_embedding_batch_size
            )
        raise HTTPException(status_code=400, detail=errors)

    # Persist to file
    try:
        global_settings.save()
    except Exception as e:
        if previous_embedding_batch_size is not None:
            global_settings.scheduler.embedding_batch_size = (
                previous_embedding_batch_size
            )
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {e}")

    if pending_embedding_batch_size is not None:
        from ..server import _server_state

        pool = _server_state.engine_pool
        if pool is not None:
            await pool.apply_embedding_batch_size(pending_embedding_batch_size)
        runtime_applied.append("embedding_batch_size")
        logger.info(f"Embedding batch size set to {pending_embedding_batch_size}")

    # Build response message
    message = "Settings saved successfully."

    return {
        "success": True,
        "message": message,
        "runtime_applied": runtime_applied,
    }


# =============================================================================
# Logs API Routes
# =============================================================================


def _tail_file(file_path: Path, num_lines: int) -> tuple[str, int]:
    """
    Read the last N lines of a file efficiently.

    Uses a deque to efficiently keep only the last N lines in memory.

    Args:
        file_path: Path to the log file.
        num_lines: Number of lines to return.

    Returns:
        Tuple of (content_string, total_line_count)
    """
    if not file_path.exists():
        return "", 0

    # Use deque for efficient tail operation
    lines = deque(maxlen=num_lines)
    total_lines = 0

    with open(file_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            lines.append(line)
            total_lines += 1

    return "".join(lines), total_lines


def _get_available_log_files(log_dir: Path) -> list[str]:
    """
    Get list of available log files sorted by modification time.

    Args:
        log_dir: Directory containing log files.

    Returns:
        List of log file names, newest first.
    """
    if not log_dir.exists():
        return []

    files = []
    for f in log_dir.iterdir():
        # Match server.log and server.log.YYYY-MM-DD patterns
        if f.name.startswith("server") and (f.suffix == ".log" or ".log." in f.name):
            files.append(f.name)

    # Sort by modification time (newest first)
    files.sort(key=lambda x: (log_dir / x).stat().st_mtime, reverse=True)
    return files


@router.get("/api/logs")
async def get_logs(
    lines: int = 100,
    file: str | None = None,
    is_admin: bool = Depends(require_admin),
):
    """
    Get server logs.

    Returns the last N lines of the specified log file (or current log).
    Supports viewing historical rotated log files.

    Args:
        lines: Number of lines to return (default: 100, max: 10000).
        file: Optional specific log file name. If not specified, uses current log.

    Returns:
        JSON response with log content and metadata:
        - logs: The log content string
        - total_lines: Total number of lines in the file
        - log_file: Name of the log file being read
        - available_files: List of available log files

    Raises:
        HTTPException: 401 if not authenticated, 503 if server not initialized,
                      400 if invalid file name, 404 if log file not found.
    """
    global_settings = _get_global_settings()

    if global_settings is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    # Limit lines to prevent memory issues
    lines = min(max(1, lines), 10000)

    log_dir = global_settings.logging.get_log_dir(global_settings.base_path)

    # Get available log files
    available_files = _get_available_log_files(log_dir)

    # Determine which file to read
    if file:
        # Validate file name (prevent path traversal)
        if "/" in file or "\\" in file or ".." in file:
            raise HTTPException(status_code=400, detail="Invalid file name")
        log_file = log_dir / file
        if not log_file.exists():
            raise HTTPException(status_code=404, detail=f"Log file not found: {file}")
    else:
        # Default to current log file
        log_file = log_dir / "server.log"

    # Read log content
    if log_file.exists():
        content, total_lines = _tail_file(log_file, lines)
    else:
        content = ""
        total_lines = 0

    return {
        "logs": content,
        "total_lines": total_lines,
        "log_file": log_file.name,
        "available_files": available_files,
    }


# =============================================================================
# Stats API Routes
# =============================================================================


def _get_engine_info() -> dict:
    """Get commit SHA and GitHub URL for engine packages.

    Fallback chain:
    1. PEP 610 direct_url.json (pip install git+https://...)
    2. _engine_commits.json (generated by build.py for app bundle)
    3. Parse pyproject.toml at runtime (dev environment)
    """
    import importlib.metadata

    engines = {}
    packages = {
        "mlx-lm": "https://github.com/ml-explore/mlx-lm",
        "mlx-vlm": "https://github.com/Blaizzy/mlx-vlm",
        "mlx-embeddings": "https://github.com/Blaizzy/mlx-embeddings",
        "mlx-audio": "https://github.com/Blaizzy/mlx-audio",
    }

    fallback_commits = _load_fallback_commits(packages)

    for pkg_name, default_url in packages.items():
        info = {"name": pkg_name, "version": None, "commit": None, "url": None}
        try:
            dist = importlib.metadata.distribution(pkg_name)
            info["version"] = dist.version

            # Method 1: PEP 610 direct_url.json
            commit_info = _get_commit_from_direct_url(dist, default_url)
            if not commit_info:
                # Methods 2+3: _engine_commits.json or pyproject.toml
                commit_info = fallback_commits.get(pkg_name)

            if commit_info:
                info["commit"] = commit_info["commit"]
                info["url"] = commit_info["url"]
        except Exception:
            pass
        engines[pkg_name] = info

    return engines


def _get_commit_from_direct_url(dist, default_url: str) -> dict | None:
    """Extract commit SHA from PEP 610 direct_url.json."""
    import json

    try:
        direct_url_text = dist.read_text("direct_url.json")
        if direct_url_text:
            direct_url = json.loads(direct_url_text)
            vcs_info = direct_url.get("vcs_info", {})
            commit = vcs_info.get("commit_id")
            if commit:
                repo_url = direct_url.get("url", default_url).rstrip("/")
                if repo_url.endswith(".git"):
                    repo_url = repo_url[:-4]
                return {"commit": commit, "url": f"{repo_url}/commit/{commit}"}
    except Exception:
        pass
    return None


def _load_fallback_commits(packages: dict[str, str]) -> dict:
    """Load commit SHAs from fallback sources.

    Tries in order:
    1. _engine_commits.json (generated by build.py, lives in omlx package dir)
    2. pyproject.toml (dev environment, lives one level above package dir)
    """
    import json
    from pathlib import Path

    # This file is at omlx/admin/routes.py → package dir is omlx/
    pkg_dir = Path(__file__).resolve().parent.parent

    # Method 2: _engine_commits.json (written by build.py for app bundle)
    commits_file = pkg_dir / "_engine_commits.json"
    if commits_file.is_file():
        try:
            data = json.loads(commits_file.read_text())
            result = {}
            for pkg_name, entry in data.items():
                if isinstance(entry, dict) and "commit" in entry:
                    commit = entry["commit"]
                    repo_url = entry.get("url", packages.get(pkg_name, ""))
                    if "/commit/" not in repo_url:
                        repo_url = f"{repo_url}/commit/{commit}"
                    result[pkg_name] = {"commit": commit, "url": repo_url}
            if result:
                return result
        except Exception:
            pass

    # Method 3: Parse pyproject.toml (dev environment)
    pyproject = pkg_dir.parent / "pyproject.toml"
    if pyproject.is_file():
        try:
            return _parse_commits_from_pyproject(pyproject, packages)
        except Exception:
            pass

    return {}


def _parse_commits_from_pyproject(pyproject_path, packages: dict[str, str]) -> dict:
    """Extract commit SHAs from git+https:// URLs in pyproject.toml."""
    import re
    from pathlib import Path

    content = Path(pyproject_path).read_text()
    commits = {}
    # Match: "mlx-lm @ git+https://github.com/.../mlx-lm@<sha>"
    pattern = r'"(\S+)\s*@\s*git\+https://[^@"]+@([0-9a-f]{7,40})"'
    for match in re.finditer(pattern, content):
        pkg_name = match.group(1).strip().lower().split("[", 1)[0]
        sha = match.group(2)
        if pkg_name in packages:
            repo_url = packages[pkg_name]
            commits[pkg_name] = {
                "commit": sha,
                "url": f"{repo_url}/commit/{sha}",
            }
    return commits


def _build_runtime_cache_observability(
    global_settings,
    model_filter: str = "",
) -> dict:
    """Build runtime cache observability payload for dashboard.

    Includes the effective runtime paths and per-model SSD cache runtime stats
    from loaded schedulers, so users can verify real cache state without manual
    process inspection.
    """
    if global_settings is None:
        return {
            "base_path": "",
            "ssd_cache_dir": "",
            "response_state_dir": "",
            "models": [],
            "total_num_files": 0,
            "total_size_bytes": 0,
            "effective_block_sizes": [],
        }

    cache_dir = global_settings.cache.get_ssd_cache_dir(global_settings.base_path)
    cache_cfg = global_settings.cache
    try:
        cfg_disk_max = cache_cfg.get_ssd_cache_max_size_bytes(global_settings.base_path)
    except (ValueError, OSError, TypeError) as exc:
        logger.warning("Could not read SSD cache max size from config: %s", exc)
        cfg_disk_max = 0

    payload = {
        "base_path": str(global_settings.base_path),
        "ssd_cache_dir": str(cache_dir),
        "response_state_dir": str(cache_dir / "response-state"),
        "models": [],
        "total_num_files": 0,
        "total_size_bytes": 0,
        "effective_block_sizes": [],
        "disk_max_bytes": cfg_disk_max,
        "hot_cache_max_bytes": 0,
        "hot_cache_size_bytes": 0,
        "hot_cache_entries": 0,
    }

    try:
        engine_pool = _get_engine_pool()
    except Exception:  # Server startup has not initialized the pool yet.
        engine_pool = None
    if engine_pool is None:
        return payload

    block_sizes = set()

    for model_info in engine_pool.get_status().get("models", []):
        model_id = model_info.get("id")
        if not model_id:
            continue
        if model_filter and model_id != model_filter:
            continue
        if not model_info.get("loaded"):
            continue

        entry = engine_pool._entries.get(model_id)
        if entry is None or entry.engine is None:
            continue

        async_core = getattr(entry.engine, "_engine", None)
        core = getattr(async_core, "engine", None) if async_core is not None else None
        scheduler = getattr(core, "scheduler", None) if core is not None else None
        if scheduler is None and async_core is None:
            # Engines without an AsyncEngineCore (DFlash) expose a scheduler
            # through their fallback engine once it is active.
            scheduler = getattr(entry.engine, "scheduler", None)

        runtime_stats = None
        if scheduler is not None and hasattr(scheduler, "get_ssd_cache_stats"):
            try:
                runtime_stats = scheduler.get_ssd_cache_stats()
            except Exception as exc:
                logger.warning(
                    "Failed to collect runtime cache stats for model '%s': %s",
                    model_id,
                    exc,
                )
                continue
        elif hasattr(entry.engine, "get_runtime_cache_stats"):
            # DFlash primary mode: the engine adapts its dflash-mlx runtime
            # cache (L1 in-memory + L2 snapshot dir) to the same shape.
            try:
                runtime_stats = entry.engine.get_runtime_cache_stats()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to collect runtime cache stats for model '%s': %s",
                    model_id,
                    exc,
                )
                continue

        if not runtime_stats:
            continue

        block_size = runtime_stats.get("block_size")
        indexed_blocks = runtime_stats.get("indexed_blocks")

        ssd_stats = runtime_stats.get("ssd_cache")
        if is_dataclass(ssd_stats):
            ssd_stats = asdict(ssd_stats)
        elif hasattr(ssd_stats, "to_dict"):
            ssd_stats = ssd_stats.to_dict()
        elif not isinstance(ssd_stats, dict):
            ssd_stats = {}

        ssd_manager = getattr(scheduler, "paged_ssd_cache_manager", None)
        scheduler_model_name = getattr(
            getattr(scheduler, "config", None), "model_name", ""
        )
        if ssd_manager is not None and hasattr(ssd_manager, "get_stats_for_model"):
            try:
                scoped_ssd_stats = ssd_manager.get_stats_for_model(
                    scheduler_model_name or model_id
                )
                if is_dataclass(scoped_ssd_stats):
                    ssd_stats = asdict(scoped_ssd_stats)
                elif isinstance(scoped_ssd_stats, dict):
                    ssd_stats = scoped_ssd_stats
            except Exception as exc:
                logger.warning(
                    "Failed to collect model-scoped SSD cache stats for model '%s': %s",
                    model_id,
                    exc,
                )

        prefix_stats = runtime_stats.get("prefix_cache")
        if is_dataclass(prefix_stats):
            prefix_stats = asdict(prefix_stats)
        elif hasattr(prefix_stats, "to_dict"):
            prefix_stats = prefix_stats.to_dict()
        elif not isinstance(prefix_stats, dict):
            prefix_stats = {}

        indexed_blocks_value = indexed_blocks if isinstance(indexed_blocks, int) else 0
        if not isinstance(block_size, int) or block_size <= 0:
            block_size = int(prefix_stats.get("block_size", 0) or 0)

        partial_block_skips = int(prefix_stats.get("partial_block_skips", 0) or 0)
        partial_tokens_skipped = int(prefix_stats.get("partial_tokens_skipped", 0) or 0)
        last_partial_tokens_skipped = int(
            prefix_stats.get("last_partial_tokens_skipped", 0) or 0
        )
        last_tokens_to_next_block = int(
            prefix_stats.get("last_tokens_to_next_block", 0) or 0
        )

        has_sub_block_cache = (
            indexed_blocks_value == 0
            and isinstance(block_size, int)
            and block_size > 0
            and partial_block_skips > 0
        )

        model_payload = {
            "id": model_id,
            "block_size": block_size,
            "indexed_blocks": indexed_blocks_value,
            "indexed_blocks_display": (
                f"<{block_size}" if has_sub_block_cache else str(indexed_blocks_value)
            ),
            "has_sub_block_cache": has_sub_block_cache,
            "partial_block_skips": partial_block_skips,
            "partial_tokens_skipped": partial_tokens_skipped,
            "last_partial_tokens_skipped": last_partial_tokens_skipped,
            "last_tokens_to_next_block": last_tokens_to_next_block,
            "num_files": int(ssd_stats.get("num_files", 0) or 0),
            "total_size_bytes": int(ssd_stats.get("total_size_bytes", 0) or 0),
            "max_size_bytes": int(ssd_stats.get("max_size_bytes", 0) or 0),
            "hot_cache_max_bytes": int(ssd_stats.get("hot_cache_max_bytes", 0) or 0),
            "hot_cache_size_bytes": int(ssd_stats.get("hot_cache_size_bytes", 0) or 0),
            "hot_cache_entries": int(ssd_stats.get("hot_cache_entries", 0) or 0),
        }

        cache_rates = runtime_stats.get("cache_rates")
        if cache_rates:
            model_payload["cache_rates"] = cache_rates

        payload["models"].append(model_payload)
        payload["total_num_files"] += model_payload["num_files"]
        payload["total_size_bytes"] += model_payload["total_size_bytes"]

        if isinstance(block_size, int) and block_size > 0:
            block_sizes.add(block_size)

    payload["effective_block_sizes"] = sorted(block_sizes)

    # Aggregate hot-cache and disk-max across models. Hot cache max is a single
    # process-wide budget shared by all loaded model managers, so keep the
    # largest reported cap instead of summing per-model rows. Disk max also
    # keeps the config fallback via max() because a single SSD cache directory
    # is shared — the effective cap is the largest configured limit, not a
    # per-model sum.
    hot_cache_max = 0
    disk_max = payload["disk_max_bytes"]
    hot_cache_size_total = 0
    hot_cache_entries_total = 0
    for m in payload["models"]:
        hot_cache_size_total += m.get("hot_cache_size_bytes", 0)
        hot_cache_entries_total += m.get("hot_cache_entries", 0)
        hot_cache_max = max(hot_cache_max, m.get("hot_cache_max_bytes", 0))
        disk_max = max(disk_max, m.get("max_size_bytes", 0))
    payload["hot_cache_max_bytes"] = hot_cache_max
    payload["hot_cache_size_bytes"] = hot_cache_size_total
    payload["hot_cache_entries"] = hot_cache_entries_total
    payload["disk_max_bytes"] = disk_max

    # Fallback: if no loaded models contributed stats, scan the cache
    # directory directly so the dashboard still shows real disk usage.
    if payload["total_num_files"] == 0 and cache_dir.exists():
        try:
            num_files = 0
            total_bytes = 0
            for subdir in "0123456789abcdef":
                subdir_path = cache_dir / subdir
                if not subdir_path.exists():
                    continue
                for f in subdir_path.glob("*.safetensors"):
                    num_files += 1
                    total_bytes += f.stat().st_size
            payload["total_num_files"] = num_files
            payload["total_size_bytes"] = total_bytes
        except Exception as exc:
            logger.warning("Failed to scan SSD cache directory: %s", exc)

    return payload


def _build_ai2apps_observability(model_filter: str = "") -> dict:
    """Return product-specific scope/cache state without synchronizing Metal."""
    raw_probe_depth = os.environ.get(
        "OMLX_DEEPSEEK_V4_SCOPE_PROBE_DEPTH", "16"
    ).strip()
    try:
        probe_depth = int(raw_probe_depth)
    except ValueError:
        probe_depth = 16
    payload = {
        "version": _ai2apps_version,
        "runtime": {"name": "oMLX", "version": _omlx_version},
        "scope_configured": bool(
            os.environ.get("OMLX_DEEPSEEK_V4_SCOPE_PROFILE", "").strip()
        ),
        "initial_scope": os.environ.get(
            "OMLX_DEEPSEEK_V4_SCOPE_NAME", ""
        ).strip(),
        "probe_depth": probe_depth,
        "lossy_mode": os.environ.get(
            "OMLX_DEEPSEEK_V4_SCOPE_LOSSY_MODE", "exact"
        ).strip()
        or "exact",
        "models": [],
    }
    try:
        engine_pool = _get_engine_pool()
    except Exception:  # Server startup has not initialized the pool yet.
        engine_pool = None
    if engine_pool is None:
        return payload
    for model_id, entry in engine_pool._entries.items():
        if model_filter and model_id != model_filter:
            continue
        engine = entry.engine
        if engine is None or not hasattr(engine, "get_stats"):
            continue
        try:
            flesh = engine.get_stats().get("flesh")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not collect AI2Apps stats for %s: %s", model_id, exc)
            continue
        if flesh:
            payload["models"].append({"id": model_id, **flesh})
    return payload


@router.get("/api/stats")
async def get_server_stats(
    model: str = "",
    scope: str = "session",
    is_admin: bool = Depends(require_admin),
):
    """Get server serving stats for the Status dashboard.

    Args:
        model: Filter by model ID. Empty string returns global aggregate.
        scope: "session" for current session, "alltime" for persisted totals.
    """
    from ..server import resolve_model_id
    from ..server_metrics import get_server_metrics

    metrics = get_server_metrics()
    resolved_model = resolve_model_id(model) or model if model else ""
    snapshot = metrics.get_snapshot(model_id=resolved_model, scope=scope)

    global_settings = _get_global_settings()
    host = global_settings.server.host if global_settings else "127.0.0.1"
    port = global_settings.server.port if global_settings else 8000
    api_key = global_settings.auth.api_key if global_settings else ""

    from ..utils.install import get_cli_prefix

    # Build active_models data for the dashboard card.
    active_models_data = _build_active_models_data()
    runtime_cache_data = _build_runtime_cache_observability(
        global_settings,
        model_filter=model,
    )

    return {
        **snapshot,
        "host": host,
        "port": port,
        "api_key": api_key or "",
        "cli_prefix": get_cli_prefix(),
        "engines": _get_engine_info(),
        "active_models": active_models_data,
        "runtime_cache": runtime_cache_data,
        "ai2apps": _build_ai2apps_observability(model_filter=model),
    }


@router.get("/api/activity")
async def get_server_activity(is_admin: bool = Depends(require_admin)):
    """Return lightweight current model and request activity for live displays."""
    return {"active_models": _build_active_models_data()}


def _build_active_models_data() -> dict:
    """Build active models status for the dashboard Active Models card."""
    from ..model_discovery import format_size
    from ..prefill_progress import get_prefill_tracker

    engine_pool = _get_engine_pool()
    server_state = _get_server_state()
    if engine_pool is None:
        return {
            "models": [],
            "model_memory_used": 0,
            "model_memory_max": 0,
            "memory_pressure": {
                "enabled": False,
                "current_bytes": 0,
                "soft_bytes": 0,
                "hard_bytes": 0,
                "current_formatted": "0.0GB",
                "soft_formatted": "0.0GB",
                "hard_formatted": "0.0GB",
                "pressure_level": "ok",
            },
            "total_active_requests": 0,
            "total_waiting_requests": 0,
        }

    now = time.monotonic()
    tracker = get_prefill_tracker()
    status = engine_pool.get_status()
    enforcer = (
        getattr(server_state, "process_memory_enforcer", None)
        if server_state is not None
        else None
    )
    enforcer_status = None
    if enforcer is not None:
        try:
            enforcer_status = enforcer.get_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Memory enforcer status unavailable: %s", exc)
    models = []
    total_active = 0
    total_waiting = 0

    for model_info in status.get("models", []):
        if not model_info.get("loaded") and not model_info.get("is_loading"):
            continue

        model_id = model_info["id"]
        active_requests = 0
        waiting_requests = 0
        running_by_id = {}
        has_scheduler_snapshot = False
        waiting_ids = set()
        waiting = []
        activities = []

        # Get per-model active/waiting request counts.
        # Follow the same pattern as server.py /api/status endpoint.
        collector_request_ids: set = set()
        active_request_ids: set = set()
        activity_requests = 0
        entry = engine_pool._entries.get(model_id)
        if entry and entry.engine is not None:
            sched = None
            async_core = getattr(entry.engine, "_engine", None)
            if async_core is not None:
                core = getattr(async_core, "engine", None)
                if core is not None:
                    collectors = getattr(core, "_output_collectors", {})
                    try:
                        collector_request_ids = set(collectors.keys())
                    except RuntimeError:
                        # Scheduler state is mutated from the engine executor;
                        # keep the dashboard endpoint best-effort rather than
                        # failing on a concurrent dict resize.
                        collector_request_ids = set()

                    sched = getattr(core, "scheduler", None)
            else:
                # Engines without an AsyncEngineCore (DFlash) still expose a
                # scheduler once their fallback engine is active.
                sched = getattr(entry.engine, "scheduler", None)
            if sched is not None and hasattr(sched, "snapshot_for_admin"):
                snap = sched.snapshot_for_admin()
                has_scheduler_snapshot = True
                running_by_id = snap["running_by_id"]
                waiting_queue = snap["waiting"]
                waiting_requests = len(waiting_queue)
                waiting_ids = {req.request_id for req in waiting_queue}
                waiting = [
                    {
                        "request_id": req.request_id,
                        "queue_position": idx,
                        "elapsed_seconds": max(0.0, now - req.arrival_time),
                        "prompt_tokens": getattr(req, "num_prompt_tokens", 0),
                    }
                    for idx, req in enumerate(waiting_queue, start=1)
                ]
            if hasattr(entry.engine, "get_activity_snapshot"):
                # Requests the engine tracks itself (non-streaming engines,
                # DFlash primary mode). Counted on top of any scheduler
                # snapshot; the two sources never overlap.
                snapshot = entry.engine.get_activity_snapshot()
                activity_requests = snapshot.get("active_requests", 0)
                activities = snapshot.get("activities", [])

        prefilling = tracker.get_model_progress(model_id)
        prefilling_ids = {p["request_id"] for p in prefilling}
        if has_scheduler_snapshot:
            active_request_ids = set(running_by_id) | prefilling_ids
        elif collector_request_ids:
            active_request_ids = collector_request_ids - waiting_ids
        if has_scheduler_snapshot or collector_request_ids:
            active_requests = len(active_request_ids)
        active_requests += activity_requests

        # Generating = active requests that finished prefill.
        generating = []
        for rid in sorted(active_request_ids - prefilling_ids - waiting_ids):
            req = running_by_id.get(rid)
            generated_tokens = getattr(req, "num_output_tokens", 0) if req else 0
            started_at = getattr(req, "generation_started_at", None) if req else None
            last_activity_at = getattr(req, "last_activity_at", None) if req else None
            elapsed = max(0.0, now - started_at) if started_at else None
            last_activity_age = (
                max(0.0, now - last_activity_at) if last_activity_at else None
            )
            tokens_per_second = (
                generated_tokens / elapsed if elapsed and elapsed > 0 else 0.0
            )
            generating.append(
                {
                    "request_id": rid,
                    "elapsed_seconds": elapsed,
                    "generated_tokens": generated_tokens,
                    "tokens_per_second": tokens_per_second,
                    "last_activity_age_seconds": last_activity_age,
                    "prompt_tokens": getattr(req, "num_prompt_tokens", 0) if req else 0,
                    "max_tokens": getattr(req, "max_tokens", None) if req else None,
                }
            )

        loading_started_at = model_info.get("loading_started_at")
        loading_elapsed_seconds = (
            max(0.0, now - loading_started_at) if loading_started_at else None
        )
        loading_estimated_seconds = None
        loading_remaining_seconds_estimate = None
        if loading_elapsed_seconds is not None:
            estimated_size_gb = model_info.get("estimated_size", 0) / (1024**3)
            # Model loaders do not expose byte-level progress, so use a
            # deliberately conservative elapsed-time estimate and cap below
            # complete until the model is actually loaded.
            observed_seconds_per_gb = status.get("load_seconds_per_gb_estimate")
            observations = status.get("load_time_observations", 0)
            if observed_seconds_per_gb and observations >= 2:
                # Adapt to this machine/session once we have more than a
                # single potentially-misleading sample.
                loading_estimated_seconds = max(
                    3.0,
                    1.0 + estimated_size_gb * float(observed_seconds_per_gb),
                )
                if loading_elapsed_seconds < loading_estimated_seconds:
                    loading_remaining_seconds_estimate = max(
                        0.0, loading_estimated_seconds - loading_elapsed_seconds
                    )

        # Compute idle time and TTL remaining for loaded models.
        is_loaded = (
            model_info.get("loaded") and entry is not None and entry.engine is not None
        )
        last_access = model_info.get("last_access")
        idle_seconds: float | None = None
        ttl_remaining_seconds: float | None = None

        if is_loaded and last_access is not None and last_access > 0:
            idle_seconds = max(0.0, time.time() - last_access)

        # Determine effective TTL: per-model ttl_seconds first, then global idle_timeout.
        effective_ttl: int | None = None
        settings_manager = _get_settings_manager()
        if is_loaded and settings_manager is not None:
            model_settings = settings_manager.get_settings(model_id)
            if (
                model_settings is not None
                and getattr(model_settings, "ttl_seconds", None) is not None
            ):
                effective_ttl = model_settings.ttl_seconds
        if effective_ttl is None:
            global_settings = _get_global_settings()
            if global_settings is not None:
                gt = getattr(global_settings, "idle_timeout", None)
                if gt is not None:
                    effective_ttl = getattr(gt, "idle_timeout_seconds", None)

        if is_loaded and effective_ttl is not None and idle_seconds is not None:
            ttl_remaining_seconds = max(0.0, effective_ttl - idle_seconds)

        # DFlash observability (issue #2398): session speculation counters and
        # the load-time precision pairing warning. None on non-DFlash engines.
        dflash_info = None
        if entry is not None and entry.engine is not None:
            pairing = getattr(entry.engine, "pairing_warning", None)
            speculation = None
            get_speculation = getattr(entry.engine, "get_speculation_stats", None)
            if callable(get_speculation):
                try:
                    speculation = get_speculation()
                except Exception:
                    logger.debug("get_speculation_stats failed", exc_info=True)
            if speculation is not None or pairing:
                dflash_info = {
                    "speculation": speculation,
                    "pairing_warning": pairing,
                }

        models.append(
            {
                "id": model_id,
                "estimated_size": model_info.get("estimated_size", 0),
                "estimated_size_formatted": format_size(
                    model_info.get("estimated_size", 0)
                ),
                "actual_size": model_info.get("actual_size") or 0,
                "actual_size_formatted": (
                    format_size(model_info.get("actual_size", 0))
                    if model_info.get("actual_size")
                    else None
                ),
                "pinned": model_info.get("pinned", False),
                "is_loading": model_info.get("is_loading", False),
                "loading_elapsed_seconds": loading_elapsed_seconds,
                "loading_estimated_seconds": loading_estimated_seconds,
                "loading_remaining_seconds_estimate": loading_remaining_seconds_estimate,
                "active_requests": active_requests,
                "waiting_requests": waiting_requests,
                "waiting": waiting,
                "activities": activities,
                "prefilling": prefilling,
                "generating": generating,
                "idle_seconds": idle_seconds,
                "ttl_remaining_seconds": ttl_remaining_seconds,
                "dflash": dflash_info,
            }
        )

        total_active += active_requests
        total_waiting += waiting_requests

    # model_memory_used reports phys_footprint (whole process) when the
    # enforcer is running so the UI's usage bar matches the value used to
    # drive eviction. model_memory_max is the final_ceiling from
    # enforcer.get_final_ceiling().
    if enforcer_status is not None and enforcer_status.get("enabled"):
        memory_used = enforcer_status.get("current_bytes", 0)
        memory_max = enforcer_status.get("ceiling_bytes", 0)
    else:
        memory_used = status.get("current_model_memory", 0)
        memory_max = status.get("final_ceiling", 0)
    return {
        "models": models,
        "model_memory_used": memory_used,
        "model_memory_max": memory_max,
        "memory_pressure": {
            "enabled": bool(enforcer_status and enforcer_status.get("enabled")),
            "current_bytes": (
                enforcer_status.get("current_bytes", 0)
                if enforcer_status is not None
                else 0
            ),
            "soft_bytes": (
                enforcer_status.get("soft_bytes", 0)
                if enforcer_status is not None
                else 0
            ),
            "hard_bytes": (
                enforcer_status.get("hard_bytes", 0)
                if enforcer_status is not None
                else 0
            ),
            "current_formatted": (
                enforcer_status.get("current_formatted", "0.0GB")
                if enforcer_status is not None
                else "0.0GB"
            ),
            "soft_formatted": (
                enforcer_status.get("soft_formatted", "0.0GB")
                if enforcer_status is not None
                else "0.0GB"
            ),
            "hard_formatted": (
                enforcer_status.get("hard_formatted", "0.0GB")
                if enforcer_status is not None
                else "0.0GB"
            ),
            "pressure_level": (
                enforcer_status.get("pressure_level", "ok")
                if enforcer_status is not None
                else "ok"
            ),
        },
        "total_active_requests": total_active,
        "total_waiting_requests": total_waiting,
    }


@router.post("/api/stats/clear")
async def clear_server_stats(is_admin: bool = Depends(require_admin)):
    """Clear session server metrics."""
    from ..server_metrics import get_server_metrics

    get_server_metrics().clear_metrics()
    return {"status": "ok"}


@router.post("/api/stats/clear-alltime")
async def clear_alltime_stats(is_admin: bool = Depends(require_admin)):
    """Clear all-time server metrics and delete persisted stats file."""
    from ..server_metrics import get_server_metrics

    get_server_metrics().clear_alltime_metrics()
    return {"status": "ok"}


def _iter_loaded_scheduler_records():
    """Yield (model_id, scheduler, core) for each loaded model.

    Traverses the internal engine hierarchy: pool entry → async engine →
    core engine → scheduler.
    """
    engine_pool = _get_engine_pool()
    if engine_pool is None:
        return
    for model_info in engine_pool.get_status().get("models", []):
        model_id = model_info.get("id")
        if not model_id or not model_info.get("loaded"):
            continue
        entry = engine_pool._entries.get(model_id)
        if entry is None or entry.engine is None:
            continue
        async_core = getattr(entry.engine, "_engine", None)
        core = getattr(async_core, "engine", None) if async_core is not None else None
        scheduler = getattr(core, "scheduler", None) if core is not None else None
        if scheduler is not None:
            yield model_id, scheduler, core


def _iter_loaded_schedulers():
    """Yield (model_id, scheduler) for each loaded model.

    Both ``clear_ssd_cache`` and ``clear_hot_cache`` share this traversal.
    """
    for model_id, scheduler, _core in _iter_loaded_scheduler_records():
        yield model_id, scheduler


@router.post("/api/ssd-cache/clear")
async def clear_ssd_cache(is_admin: bool = Depends(require_admin)):
    """Clear all SSD cache files for all loaded models.

    Uses loaded models' SSD cache managers when available.  Falls back to
    direct filesystem deletion so caches can be wiped even when no model
    is loaded.
    """
    total_deleted = 0

    for model_id, scheduler in _iter_loaded_schedulers():
        ssd_manager = getattr(scheduler, "paged_ssd_cache_manager", None)
        if ssd_manager is not None:
            try:
                total_deleted += ssd_manager.clear()
            except Exception as exc:
                logger.warning(
                    "Failed to clear SSD cache for model '%s': %s",
                    model_id,
                    exc,
                )

    # Phase 2: remove any remaining files on disk (covers unloaded models)
    global_settings = _get_global_settings()
    if global_settings is not None:
        cache_dir = global_settings.cache.get_ssd_cache_dir(
            global_settings.base_path,
        )
        if cache_dir.exists():
            try:
                for subdir in "0123456789abcdef":
                    subdir_path = cache_dir / subdir
                    if not subdir_path.exists():
                        continue
                    for f in subdir_path.glob("*.safetensors"):
                        try:
                            f.unlink()
                            total_deleted += 1
                        except OSError:
                            pass
            except Exception as exc:
                logger.warning("Failed to clean SSD cache directory: %s", exc)

    return {"status": "ok", "total_deleted": total_deleted}


@router.post("/api/hot-cache/clear")
async def clear_hot_cache(is_admin: bool = Depends(require_admin)):
    """Clear the in-memory hot cache and release the buffers it held.

    Dropping hot cache entries releases Python references, but MLX may keep
    now-unused buffers in its allocator pool. Reclaim through the scheduler's
    synchronized clear path so active engine streams and async store-cache
    workers keep the same Metal safety barriers used by generation.
    """
    import gc

    from ..engine_core import get_mlx_executor
    from ..scheduler import _sync_and_clear_cache
    from ..utils.proc_memory import get_phys_footprint

    footprint_before = get_phys_footprint()
    total_cleared = 0
    reclaim_targets = []
    for model_id, scheduler, core in _iter_loaded_scheduler_records():
        ssd_manager = getattr(scheduler, "paged_ssd_cache_manager", None)
        if ssd_manager is not None and hasattr(ssd_manager, "clear_hot_cache"):
            try:
                total_cleared += ssd_manager.clear_hot_cache()
            except Exception as exc:
                logger.warning(
                    "Failed to clear hot cache for model '%s': %s",
                    model_id,
                    exc,
                )
        rate_tracker = getattr(scheduler, "_cache_rate_tracker", None)
        if rate_tracker is not None:
            rate_tracker.clear()
        executor = getattr(core, "_mlx_executor", None)
        if executor is not None:
            reclaim_targets.append(
                (model_id, executor, getattr(scheduler, "_stream", None))
            )

    # Also clear managers orphaned by an abnormal teardown: they hold live
    # hot cache but are no longer attached to a loaded scheduler, so the loop
    # above cannot reach them. The shared budget still references them.
    pool = _get_engine_pool()
    budget = getattr(getattr(pool, "_scheduler_config", None), "hot_cache_budget", None)
    if budget is not None and hasattr(budget, "clear_all_owners"):
        try:
            total_cleared += budget.clear_all_owners()
        except Exception as exc:
            logger.warning("Failed to clear orphaned hot caches: %s", exc)

    # Return pooled buffers to the OS using scheduler._sync_and_clear_cache(),
    # the same lock/synchronize/clear helper used by generation. Run on each
    # loaded engine's executor so its thread-local stream is present. If every
    # model has been unloaded, still run one reclaim on the fallback executor so
    # orphaned/no-loaded hot cache cleanup can release MLX's allocator pool.
    gc.collect()
    loop = asyncio.get_running_loop()
    if reclaim_targets:
        for model_id, executor, stream in reclaim_targets:
            try:
                await loop.run_in_executor(executor, _sync_and_clear_cache, stream)
            except RuntimeError as exc:
                if "cannot schedule new futures after shutdown" not in str(exc):
                    raise
                logger.warning(
                    "Engine executor unavailable while reclaiming MLX buffers "
                    "for model '%s': %s",
                    model_id,
                    exc,
                )
                await loop.run_in_executor(get_mlx_executor(), _sync_and_clear_cache)
    else:
        await loop.run_in_executor(get_mlx_executor(), _sync_and_clear_cache)
    bytes_reclaimed = max(0, footprint_before - get_phys_footprint())

    return {
        "status": "ok",
        "total_cleared": total_cleared,
        "bytes_reclaimed": bytes_reclaimed,
    }


def _normalize_probe_tool_calls(messages: list[dict]) -> list[dict]:
    """Parse echoed tool_call arguments (JSON string -> object) for templating.

    Native tool-calling chat templates (GLM, Qwen3.x, MiniMax) iterate
    ``tool_call.function.arguments.items()``, but the OpenAI wire form sends
    ``arguments`` as a JSON string. Rendering the string form raises
    ``'str object' has no attribute 'items'`` and the probe 400s, so any
    conversation that used tools reports an error (hollow cache dot) instead
    of a real hit/miss. The chat path parses these before rendering; mirror
    that here so (a) tool conversations tokenize and (b) the probe's block
    hashes line up with what a real prefill produced. Returns shallow copies
    so the caller's message dicts are left untouched.
    """
    normalized: list[dict] = []
    for msg in messages:
        tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else None
        if not tool_calls:
            normalized.append(msg)
            continue
        new_calls = []
        for tc in tool_calls:
            fn = tc.get("function") if isinstance(tc, dict) else None
            if isinstance(fn, dict) and "arguments" in fn:
                arguments = _coerce_tool_call_arguments(fn["arguments"])
                tc = {
                    **tc,
                    "function": {**fn, "arguments": _try_parse_json(arguments)},
                }
            new_calls.append(tc)
        normalized.append({**msg, "tool_calls": new_calls})
    return normalized


def _probe_chat_template_kwargs(
    request: "CacheProbeRequest",
    *,
    preserve_thinking_default: bool | None = None,
) -> dict | None:
    """Chat-template kwargs the scheduler would actually prefill this with.

    The probe answers "is this prompt cached", so it has to render byte-for
    byte what a real turn renders. Rendering with the caller's kwargs alone
    ignores the model's own settings — a model with enable_thinking set (or
    any forced/persisted chat_template_kwargs) then hashes a prompt that is
    never prefilled, and since the block walk stops at the first miss, every
    block reports cold.
    """
    settings = None
    if _get_settings_manager is not None:
        try:
            manager = _get_settings_manager()
            if manager is not None:
                settings = manager.get_settings_for_request(
                    request.model_id,
                    resolved_model_id=request.model_id,
                )
        except Exception:
            # A settings lookup failure must not break probing outright —
            # fall back to the caller's kwargs (pre-fix behaviour).
            logger.warning(
                "cache probe: model settings lookup failed for %s; "
                "rendering with request kwargs only",
                request.model_id,
                exc_info=True,
            )
            settings = None
    return (
        merge_chat_template_kwargs(
            settings,
            request.chat_template_kwargs,
            thinking_budget=request.thinking_budget,
            preserve_thinking_default=preserve_thinking_default,
        )
        or None
    )


@router.post("/api/cache/probe")
async def probe_cache(
    request: CacheProbeRequest,
    is_admin: bool = Depends(require_admin),
):
    """Probe cache state for a chat message list.

    Classifies each block of the rendered prompt into one of three buckets:
    - ``blocks_ssd_hot``: in the SSD manager's hot cache (RAM copy of cold
      blocks, ready to mount without disk read)
    - ``blocks_ssd_disk``: only in the SSD index on disk
    - ``blocks_cold``: not cached anywhere (requires full prefill)

    The split is computed via a walk of the chain-hashed block sequence — the
    same hashing the scheduler uses at prefill time. The model must be loaded
    for the probe to run; unloaded models return ``model_loaded: false``.
    """
    engine_pool = _get_engine_pool()
    if engine_pool is None:
        raise HTTPException(status_code=503, detail="Engine pool not initialized")

    entry = engine_pool._entries.get(request.model_id)
    if entry is None:
        raise HTTPException(
            status_code=404, detail=f"Model not found: {request.model_id}"
        )
    if entry.engine is None:
        return {
            "model_id": request.model_id,
            "model_loaded": False,
            "reason": "Model is not loaded — load it to enable cache probing.",
        }

    engine = entry.engine
    tokenizer = getattr(engine, "_tokenizer", None)
    if tokenizer is None or not hasattr(tokenizer, "apply_chat_template"):
        raise HTTPException(
            status_code=400,
            detail="Model tokenizer does not support chat templating.",
        )

    # Reach into the scheduler to access the prefix index and SSD manager.
    async_core = getattr(engine, "_engine", None)
    core = getattr(async_core, "engine", None) if async_core is not None else None
    scheduler = getattr(core, "scheduler", None) if core is not None else None
    if scheduler is None:
        raise HTTPException(
            status_code=500, detail="Scheduler unavailable for loaded model."
        )

    prefix_cache = getattr(scheduler, "block_aware_cache", None)
    ssd_manager = getattr(scheduler, "paged_ssd_cache_manager", None)
    paged_cache = getattr(scheduler, "paged_cache_manager", None)
    block_size = getattr(
        getattr(scheduler, "config", None), "paged_cache_block_size", 0
    )
    if not block_size and prefix_cache is not None:
        block_size = getattr(prefix_cache, "block_size", 0)
    if not block_size:
        raise HTTPException(
            status_code=500,
            detail="Cache block size unavailable — cache may not be enabled.",
        )

    # Render + tokenize the prompt using the same path as generation so the
    # hashes line up with what the scheduler would produce at prefill.
    try:
        messages = _normalize_probe_tool_calls(request.messages)
        if hasattr(engine, "_preprocess_messages"):
            messages = engine._preprocess_messages(messages)
        try:
            from ..api.tool_calling import convert_tools_for_template  # type: ignore

            template_tools = (
                convert_tools_for_template(request.tools) if request.tools else None
            )
        except Exception:
            template_tools = request.tools or None
        if hasattr(engine, "_apply_chat_template"):
            prompt = engine._apply_chat_template(
                messages,
                template_tools,
                chat_template_kwargs=_probe_chat_template_kwargs(
                    request,
                    preserve_thinking_default=getattr(
                        entry, "preserve_thinking_default", None
                    ),
                ),
            )
        else:
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        token_ids = list(tokenizer.encode(prompt))
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to tokenize messages: {exc}"
        )

    total_tokens = len(token_ids)
    if total_tokens == 0:
        return {
            "model_id": request.model_id,
            "model_loaded": True,
            "total_tokens": 0,
            "block_size": block_size,
            "total_blocks": 0,
            "blocks_ssd_hot": 0,
            "blocks_ssd_disk": 0,
            "blocks_cold": 0,
            "ssd_hit_tokens": 0,
            "cold_tokens": 0,
        }

    # Compute chain-hashed block sequence.
    from ..cache.paged_cache import compute_block_hash

    model_name = getattr(paged_cache, "model_name", None) if paged_cache else None
    ssd_index = getattr(ssd_manager, "_index", None) if ssd_manager else None
    ssd_hot = getattr(ssd_manager, "_hot_cache", None) if ssd_manager else None

    # The cache is a contiguous prefix (each block chain-hashed from the
    # previous), so we walk block-by-block until the first retrievability
    # miss — after that, every subsequent block is necessarily cold.
    #
    # Ground truth for "cached" in paged-SSD mode is retrievability:
    # hot_cache (RAM copy) OR ssd_index (on disk). BlockAwarePrefixCache's
    # internal prefix index is deliberately NOT consulted — it tracks every
    # hash the scheduler has seen and isn't cleared by clear_ssd_cache(),
    # so relying on it would report false positives after a manual wipe.
    blocks_ssd_hot = 0
    blocks_ssd_disk = 0
    ssd_hit_tokens = 0

    parent_hash = b""
    total_blocks = (total_tokens + block_size - 1) // block_size

    for start in range(0, total_tokens, block_size):
        end = min(start + block_size, total_tokens)
        block_tokens = token_ids[start:end]
        if not block_tokens:
            break

        block_hash = compute_block_hash(
            parent_hash,
            block_tokens,
            extra_keys=None,
            model_name=model_name,
        )
        parent_hash = block_hash

        in_ssd_hot = ssd_hot is not None and block_hash in ssd_hot
        in_ssd_disk = False
        if ssd_index is not None:
            try:
                in_ssd_disk = ssd_index.contains(block_hash)
            except Exception:
                in_ssd_disk = False

        if not (in_ssd_hot or in_ssd_disk):
            break

        if in_ssd_hot:
            blocks_ssd_hot += 1
        else:
            blocks_ssd_disk += 1
        ssd_hit_tokens += len(block_tokens)

    cached_blocks = blocks_ssd_hot + blocks_ssd_disk
    blocks_cold = max(total_blocks - cached_blocks, 0)

    return {
        "model_id": request.model_id,
        "model_loaded": True,
        "total_tokens": total_tokens,
        "block_size": block_size,
        "total_blocks": total_blocks,
        "blocks_ssd_hot": blocks_ssd_hot,
        "blocks_ssd_disk": blocks_ssd_disk,
        "blocks_cold": blocks_cold,
        "ssd_hit_tokens": ssd_hit_tokens,
        "cold_tokens": max(total_tokens - ssd_hit_tokens, 0),
    }


# =============================================================================
# HuggingFace Downloader API Routes
# =============================================================================


@router.get("/api/dynamoe/catalog", include_in_schema=False)
@router.get("/api/ai2apps/catalog")
async def get_ai2apps_catalog(is_admin: bool = Depends(require_admin)):
    """List AI2Apps-verified Cache-MoE installation recipes."""

    from ai2apps.model_installer import AI2AppsInstaller

    return {"models": AI2AppsInstaller.catalog()}


@router.get("/api/dynamoe/preflight", include_in_schema=False)
@router.get("/api/ai2apps/preflight")
async def get_ai2apps_preflight(is_admin: bool = Depends(require_admin)):
    """Return actionable Hugging Face environment readiness."""

    return _ai2apps_hf_preflight()


@router.post("/api/dynamoe/install", include_in_schema=False)
@router.post("/api/ai2apps/install")
async def start_ai2apps_install(
    request: AI2AppsInstallRequest,
    is_admin: bool = Depends(require_admin),
):
    preflight = _ai2apps_hf_preflight()
    if not preflight["ready"]:
        issue = preflight["issues"][0]
        raise HTTPException(
            status_code=503,
            detail=f"{issue['message']} {issue['action']}",
        )
    try:
        task = await _get_ai2apps_installer().start(
            request.model_id,
            request.weight_source,
            request.memory_tier,
            request.token,
        )
        return {"success": True, "task": task.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/dynamoe/tasks", include_in_schema=False)
@router.get("/api/ai2apps/tasks")
async def list_ai2apps_tasks(is_admin: bool = Depends(require_admin)):
    return {"tasks": _get_ai2apps_installer().get_tasks()}


@router.post("/api/dynamoe/tasks/{task_id}/cancel", include_in_schema=False)
@router.post("/api/ai2apps/tasks/{task_id}/cancel")
async def cancel_ai2apps_install(
    task_id: str,
    is_admin: bool = Depends(require_admin),
):
    if not await _get_ai2apps_installer().cancel(task_id):
        raise HTTPException(status_code=404, detail="Task not found or not cancellable")
    return {"success": True}


@router.post("/api/dynamoe/tasks/{task_id}/retry", include_in_schema=False)
@router.post("/api/ai2apps/tasks/{task_id}/retry")
async def retry_ai2apps_install(
    task_id: str,
    request: AI2AppsRetryRequest = AI2AppsRetryRequest(),
    is_admin: bool = Depends(require_admin),
):
    try:
        task = await _get_ai2apps_installer().retry(task_id, request.token)
        return {"success": True, "task": task.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/hf/download")
async def start_hf_download(
    request: HFDownloadRequest,
    is_admin: bool = Depends(require_admin),
):
    """Start downloading a model from HuggingFace."""
    if _hf_downloader is None:
        raise HTTPException(status_code=503, detail="Downloader not initialized")

    try:
        task = await _hf_downloader.start_download(request.repo_id, request.hf_token)
        return {"success": True, "task": task.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/hf/tasks")
async def list_hf_tasks(is_admin: bool = Depends(require_admin)):
    """List all download tasks."""
    if _hf_downloader is None:
        raise HTTPException(status_code=503, detail="Downloader not initialized")

    return {"tasks": _hf_downloader.get_tasks()}


@router.post("/api/hf/cancel/{task_id}")
async def cancel_hf_download(
    task_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Cancel an active download."""
    if _hf_downloader is None:
        raise HTTPException(status_code=503, detail="Downloader not initialized")

    success = await _hf_downloader.cancel_download(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or not cancellable")
    return {"success": True}


@router.post("/api/hf/retry/{task_id}")
async def retry_hf_download(
    task_id: str,
    request: HFRetryRequest = HFRetryRequest(),
    is_admin: bool = Depends(require_admin),
):
    """Retry a failed or cancelled download, resuming from existing files."""
    if _hf_downloader is None:
        raise HTTPException(status_code=503, detail="Downloader not initialized")

    try:
        task = await _hf_downloader.retry_download(task_id, request.hf_token)
        return {"success": True, "task": task.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/hf/task/{task_id}")
async def remove_hf_task(
    task_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Remove a completed, failed, or cancelled task."""
    if _hf_downloader is None:
        raise HTTPException(status_code=503, detail="Downloader not initialized")

    success = _hf_downloader.remove_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or still active")
    return {"success": True}


@router.get("/api/hf/recommended")
async def get_recommended_models(
    mlx_only: bool = True,
    is_admin: bool = Depends(require_admin),
):
    """Get recommended models filtered by system memory."""
    if _hf_downloader is None:
        raise HTTPException(status_code=503, detail="Downloader not initialized")

    memory_info = get_system_memory_info()
    max_memory = memory_info["total_bytes"] or 16 * 1024**3

    from .hf_downloader import HFDownloader

    try:
        result = await HFDownloader.get_recommended_models(
            max_memory_bytes=max_memory, result_limit=50, mlx_only=mlx_only
        )
        return result
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="HuggingFace API request timed out. The service may be temporarily unavailable.",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/api/hf/search")
async def search_hf_models(
    q: str = "",
    sort: str = "trending",
    limit: int = 100,
    mlx_only: bool = True,
    # Filtering
    min_params: Optional[int] = None,
    max_params: Optional[int] = None,
    min_size: Optional[int] = None,  # bytes
    max_size: Optional[int] = None,  # bytes
    # Sorting
    sort_by_size: bool = False,
    sort_ascending: bool = False,
    is_admin: bool = Depends(require_admin),
):
    """Search HuggingFace models by query with filtering and sorting.

    Query Parameters:
        q: Search query string (required)
        sort: Sort order - trending/downloads/created/updated/most_params/least_params/largest/smallest
        limit: Maximum results (max 100)
        mlx_only: Restrict to MLX library models
        min_params: Minimum parameter count
        max_params: Maximum parameter count
        min_size: Minimum model size in bytes
        max_size: Maximum model size in bytes
        sort_by_size: Sort results by size instead of default sort
        sort_ascending: Sort in ascending order
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    from .hf_downloader import HFDownloader

    try:
        result = await HFDownloader.search_models(
            query=q.strip(),
            sort=sort,
            limit=min(limit, 100),
            mlx_only=mlx_only,
            min_params=min_params,
            max_params=max_params,
            min_size=min_size,
            max_size=max_size,
            sort_by_size=sort_by_size,
            sort_ascending=sort_ascending,
        )
        return result
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="HuggingFace API request timed out. The service may be temporarily unavailable.",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/api/hf/model-info")
async def get_hf_model_info(
    repo_id: str = "",
    is_admin: bool = Depends(require_admin),
):
    """Get detailed model information from HuggingFace."""
    if not repo_id.strip():
        raise HTTPException(
            status_code=400, detail="Query parameter 'repo_id' is required"
        )

    from huggingface_hub.utils import RepositoryNotFoundError

    from .hf_downloader import HFDownloader

    try:
        result = await HFDownloader.get_model_info(repo_id=repo_id.strip())
        return result
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="HuggingFace API request timed out. The service may be temporarily unavailable.",
        )
    except RepositoryNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Model '{repo_id.strip()}' not found"
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/api/hf/models")
async def list_hf_models(is_admin: bool = Depends(require_admin)):
    """List models in every directory used by runtime discovery."""
    global_settings = _get_global_settings()
    if global_settings is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    # Runtime discovery also includes the shared Hugging Face cache when it is
    # enabled.  Keeping the Manager on only the explicitly configured model
    # directories made models available to serving and Chat disappear from the
    # management UI.
    model_dirs = global_settings.get_effective_model_dirs()

    from ..model_discovery import _resolve_hf_cache_entry

    def _add_model(
        model_path: Path,
        model_name: str,
        *,
        source_repo_id: str | None = None,
    ) -> None:
        if model_name in seen_names:
            return
        seen_names.add(model_name)
        total_size = sum(f.stat().st_size for f in model_path.rglob("*") if f.is_file())
        models.append(
            {
                "name": model_name,
                "path": str(model_path),
                "display_name": _model_display_name(
                    model_name,
                    model_path,
                    model_dirs,
                    source_repo_id=source_repo_id,
                ),
                "size": total_size,
                "size_formatted": format_size(total_size),
            }
        )

    models = []
    seen_names: set[str] = set()
    for model_dir in model_dirs:
        if not model_dir.exists():
            continue
        for subdir in sorted(model_dir.iterdir()):
            if not subdir.is_dir() or subdir.name.startswith("."):
                continue

            if (subdir / "config.json").exists():
                # Level 1: direct model folder
                _add_model(subdir, subdir.name)
            else:
                # HF Hub cache entry: models--Org--Name/snapshots/<hash>/
                hf_resolved = _resolve_hf_cache_entry(subdir)
                if hf_resolved is not None:
                    if (hf_resolved.snapshot_path / "config.json").exists():
                        _add_model(
                            hf_resolved.snapshot_path,
                            hf_resolved.model_id,
                            source_repo_id=hf_resolved.source_repo_id,
                        )
                    continue

                # Level 2: organization folder — scan children
                for child in sorted(subdir.iterdir()):
                    if not child.is_dir() or child.name.startswith("."):
                        continue
                    if (child / "config.json").exists():
                        _add_model(child, child.name)

    # Sort by the UI display name so organization prefixes group together.
    models.sort(key=lambda m: m["display_name"].lower())
    return {"models": models}


@router.delete("/api/hf/models/{model_name}")
async def delete_hf_model(
    model_name: str,
    is_admin: bool = Depends(require_admin),
):
    """Delete a downloaded model from disk and refresh the model pool."""
    global_settings = _get_global_settings()
    engine_pool = _get_engine_pool()

    if global_settings is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    model_dirs = global_settings.model.get_model_dirs(global_settings.base_path)

    # Search for model across all directories in both flat and org-folder layouts
    model_path = None
    parent_model_dir = None
    for model_dir in model_dirs:
        if not model_dir.exists():
            continue
        candidate = model_dir / model_name
        if candidate.is_dir() and (candidate / "config.json").exists():
            model_path = candidate
            parent_model_dir = model_dir
            break
        # Try two-level: search inside organization folders
        for subdir in model_dir.iterdir():
            if not subdir.is_dir() or subdir.name.startswith("."):
                continue
            candidate = subdir / model_name
            if candidate.is_dir() and (candidate / "config.json").exists():
                model_path = candidate
                parent_model_dir = model_dir
                break
        if model_path is not None:
            break

    if model_path is None:
        raise HTTPException(status_code=404, detail="Model not found")

    # Validate path traversal against parent model directory
    try:
        if not model_path.resolve().is_relative_to(parent_model_dir.resolve()):
            raise HTTPException(status_code=400, detail="Invalid model name")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model name")

    if not model_path.is_dir():
        raise HTTPException(status_code=400, detail="Not a model directory")

    # Unload model if loaded
    if engine_pool is not None:
        loaded_ids = engine_pool.get_loaded_model_ids()
        if model_name in loaded_ids:
            try:
                await engine_pool._unload_engine(model_name)
                logger.info(f"Unloaded model '{model_name}' before deletion")
            except Exception as e:
                logger.warning(f"Failed to unload model '{model_name}': {e}")

    # Delete from disk
    # Handle macOS resource fork files (._*) that may disappear on non-native
    # filesystems (exFAT, NTFS). Use onexc (Python 3.12+) to avoid
    # DeprecationWarning, with onerror fallback for older versions.
    def _handle_onexc(func, path, exc):
        if isinstance(exc, FileNotFoundError) and Path(path).name.startswith("._"):
            logger.debug(f"Ignoring missing resource fork file: {path}")
            return
        raise exc

    def _handle_onerror(func, path, exc_info):
        if exc_info[0] == FileNotFoundError and Path(path).name.startswith("._"):
            logger.debug(f"Ignoring missing resource fork file: {path}")
            return
        raise exc_info[1].with_traceback(exc_info[2])

    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(model_path, onexc=_handle_onexc)
        else:
            shutil.rmtree(model_path, onerror=_handle_onerror)
        logger.info(f"Deleted model directory: {model_path}")
    except Exception as e:
        logger.error(f"Failed to delete model directory {model_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete model: {e}")

    # If the model was inside an org folder (organized layout) and that
    # folder is now empty, drop it so the listing stays tidy.
    parent = model_path.parent
    if parent != parent_model_dir and parent.exists() and not any(parent.iterdir()):
        try:
            parent.rmdir()
            logger.info(f"Removed empty org folder: {parent}")
        except OSError as e:
            logger.debug(f"Could not remove empty org folder {parent}: {e}")

    # Re-discover models
    if engine_pool is not None:
        settings_manager = _get_settings_manager()
        pinned_models = []
        if settings_manager:
            pinned_models = settings_manager.get_pinned_model_ids()

        engine_pool._entries.pop(model_name, None)
        # Release the deleted model's persisted settings (including its alias)
        # so they can be reused by another model.
        if settings_manager:
            settings_manager.delete_settings(model_name)
        engine_pool.discover_models(
            [str(d) for d in global_settings.get_effective_model_dirs()],
            pinned_models,
        )
        if settings_manager:
            engine_pool.apply_settings_overrides(settings_manager)
        logger.info("Model pool refreshed after deletion")

    return {"success": True, "message": f"Model '{model_name}' deleted"}


# =============================================================================
# ModelScope Downloader API Routes
# =============================================================================


@router.get("/api/ms/status")
async def ms_status(is_admin: bool = Depends(require_admin)):
    """Check if ModelScope downloader is available."""
    return {"available": _ms_downloader is not None}


@router.post("/api/ms/download")
async def start_ms_download(
    request: MSDownloadRequest,
    is_admin: bool = Depends(require_admin),
):
    """Start downloading a model from ModelScope."""
    if _ms_downloader is None:
        raise HTTPException(
            status_code=503, detail="ModelScope downloader not initialized"
        )

    try:
        task = await _ms_downloader.start_download(request.model_id, request.ms_token)
        return {"success": True, "task": task.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/api/ms/tasks")
async def list_ms_tasks(is_admin: bool = Depends(require_admin)):
    """List all ModelScope download tasks."""
    if _ms_downloader is None:
        raise HTTPException(
            status_code=503, detail="ModelScope downloader not initialized"
        )

    return {"tasks": _ms_downloader.get_tasks()}


@router.post("/api/ms/cancel/{task_id}")
async def cancel_ms_download(
    task_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Cancel an active ModelScope download."""
    if _ms_downloader is None:
        raise HTTPException(
            status_code=503, detail="ModelScope downloader not initialized"
        )

    success = await _ms_downloader.cancel_download(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or not cancellable")
    return {"success": True}


@router.post("/api/ms/retry/{task_id}")
async def retry_ms_download(
    task_id: str,
    request: MSRetryRequest = MSRetryRequest(),
    is_admin: bool = Depends(require_admin),
):
    """Retry a failed or cancelled ModelScope download."""
    if _ms_downloader is None:
        raise HTTPException(
            status_code=503, detail="ModelScope downloader not initialized"
        )

    try:
        task = await _ms_downloader.retry_download(task_id, request.ms_token)
        return {"success": True, "task": task.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/ms/task/{task_id}")
async def remove_ms_task(
    task_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Remove a completed, failed, or cancelled ModelScope task."""
    if _ms_downloader is None:
        raise HTTPException(
            status_code=503, detail="ModelScope downloader not initialized"
        )

    success = _ms_downloader.remove_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or still active")
    return {"success": True}


@router.get("/api/ms/recommended")
async def get_ms_recommended_models(
    mlx_only: bool = True,
    is_admin: bool = Depends(require_admin),
):
    """Get recommended models from ModelScope filtered by system memory."""
    if _ms_downloader is None:
        raise HTTPException(
            status_code=503, detail="ModelScope downloader not initialized"
        )

    memory_info = get_system_memory_info()
    max_memory = memory_info["total_bytes"] or 16 * 1024**3

    from .ms_downloader import MSDownloader

    try:
        result = await MSDownloader.get_recommended_models(
            max_memory_bytes=max_memory, result_limit=50, mlx_only=mlx_only
        )
        return result
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="ModelScope API request timed out. The service may be temporarily unavailable.",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/api/ms/search")
async def search_ms_models(
    q: str = "",
    sort: str = "trending",
    limit: int = 100,
    mlx_only: bool = True,
    is_admin: bool = Depends(require_admin),
):
    """Search ModelScope models by query."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    from .ms_downloader import MSDownloader

    try:
        result = await MSDownloader.search_models(
            query=q.strip(),
            sort=sort,
            limit=min(limit, 100),
            mlx_only=mlx_only,
        )
        return result
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="ModelScope API request timed out. The service may be temporarily unavailable.",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/api/ms/model-info")
async def get_ms_model_info(
    model_id: str = "",
    is_admin: bool = Depends(require_admin),
):
    """Get detailed model information from ModelScope."""
    if not model_id.strip():
        raise HTTPException(
            status_code=400, detail="Query parameter 'model_id' is required"
        )

    from .ms_downloader import MSDownloader

    try:
        result = await MSDownloader.get_model_info(model_id=model_id.strip())
        return result
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="ModelScope API request timed out. The service may be temporarily unavailable.",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        if "NotExistError" in type(e).__name__ or "404" in str(e):
            raise HTTPException(
                status_code=404, detail=f"Model '{model_id.strip()}' not found"
            )
        raise HTTPException(status_code=502, detail=str(e))


# =============================================================================
# Accuracy Benchmark API Routes (MUST be before throughput {bench_id} routes)
# =============================================================================


@router.post("/api/bench/accuracy/queue/add")
async def add_to_accuracy_queue(
    request: Request,
    is_admin: bool = Depends(require_admin),
):
    """Add a model to the accuracy benchmark queue and start if idle."""
    from .accuracy_benchmark import (
        AccuracyBenchmarkRequest,
        add_to_queue,
        get_queue_status,
        start_next_from_queue,
    )

    engine_pool = _get_engine_pool()
    if engine_pool is None:
        raise HTTPException(status_code=503, detail="Engine pool not initialized")

    from .context_benchmark import get_active_run as get_active_context_run

    context_active = get_active_context_run()
    if context_active is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A context benchmark is already running "
                f"(bench_id={context_active.bench_id}, "
                f"model_id={context_active.request.model_id})."
            ),
        )

    body = await request.json()
    try:
        bench_request = AccuracyBenchmarkRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # External runs target a remote model — nothing to validate locally.
    if bench_request.external is None:
        entry = engine_pool.get_entry(bench_request.model_id)
        if entry is None:
            raise HTTPException(
                status_code=404, detail=f"Model not found: {bench_request.model_id}"
            )
        if entry.model_type not in ("llm", "vlm", None):
            raise HTTPException(
                status_code=400,
                detail=f"Model {bench_request.model_id} is not a supported model (type: {entry.model_type})",
            )

    add_to_queue(bench_request)

    logger.info(
        f"Accuracy queue: added {bench_request.model_id} "
        f"benchmarks={list(bench_request.benchmarks.keys())}"
    )

    # Start processing if not already running (synchronous — sets bench_id immediately)
    start_next_from_queue(engine_pool)

    return get_queue_status()


@router.get("/api/bench/accuracy/queue/status")
async def get_accuracy_queue_status(
    is_admin: bool = Depends(require_admin),
):
    """Get accuracy benchmark queue status."""
    from .accuracy_benchmark import get_queue_status

    return get_queue_status()


@router.delete("/api/bench/accuracy/queue/{idx}")
async def remove_from_accuracy_queue(
    idx: int,
    is_admin: bool = Depends(require_admin),
):
    """Remove an item from the accuracy benchmark queue."""
    from .accuracy_benchmark import get_queue_status, remove_from_queue

    if not remove_from_queue(idx):
        raise HTTPException(status_code=404, detail=f"Queue index {idx} not found")

    return get_queue_status()


@router.get("/api/bench/accuracy/results")
async def get_accumulated_accuracy_results(
    is_admin: bool = Depends(require_admin),
):
    """Get all accumulated accuracy benchmark results."""
    from .accuracy_benchmark import get_accumulated_results, get_queue_status

    status = get_queue_status()
    return {
        "results": get_accumulated_results(),
        "running": status["running"],
        "current_model": status["current_model"],
        "current_bench_id": status["current_bench_id"],
    }


@router.post("/api/bench/accuracy/results/reset")
async def reset_accuracy_results(
    is_admin: bool = Depends(require_admin),
):
    """Clear all accumulated accuracy benchmark results."""
    from .accuracy_benchmark import reset_accumulated_results

    reset_accumulated_results()
    return {"status": "reset"}


@router.post("/api/bench/accuracy/cancel")
async def cancel_accuracy_queue(
    is_admin: bool = Depends(require_admin),
):
    """Cancel the current run and clear the queue."""
    from .accuracy_benchmark import cancel_queue

    await cancel_queue()
    return {"status": "cancelled"}


@router.get("/api/bench/accuracy/{bench_id}/stream")
async def stream_accuracy_benchmark(
    bench_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Stream accuracy benchmark progress via Server-Sent Events."""
    import json

    from fastapi.responses import StreamingResponse

    from .accuracy_benchmark import get_run

    run = get_run(bench_id)
    if run is None:
        raise HTTPException(
            status_code=404, detail=f"Accuracy benchmark not found: {bench_id}"
        )

    async def event_generator():
        # Replay-then-attach: every subscriber starts at offset 0 of the
        # run's event log and follows along live. Lets the HTML dashboard
        # recover its view on page refresh and lets multiple consumers
        # (e.g. browser + Swift app) share the same run.
        seen = 0
        try:
            while True:
                async with run.cond:
                    while seen >= len(run.events) and not run.terminal:
                        try:
                            await asyncio.wait_for(run.cond.wait(), timeout=60.0)
                        except TimeoutError:
                            break
                    new = list(run.events[seen:])
                    seen = len(run.events)
                    done = run.terminal

                for ev in new:
                    yield f"data: {json.dumps(ev)}\n\n"
                if not new and not done:
                    yield ": keepalive\n\n"
                if done:
                    break
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# Context Benchmark API Routes (MUST be before throughput {bench_id} routes)
# =============================================================================


@router.get("/api/bench/context/active")
async def get_active_context_benchmark(is_admin: bool = Depends(require_admin)):
    """Return the currently-running context benchmark, if any."""
    from .context_benchmark import get_active_run

    run = get_active_run()
    if run is None:
        return {"running": False, "bench_id": None, "model_id": None}
    return {
        "running": True,
        "bench_id": run.bench_id,
        "model_id": run.request.model_id,
        "target_tokens": run.request.target_tokens,
    }


@router.post("/api/bench/context/start")
async def start_context_benchmark(
    request: Request,
    is_admin: bool = Depends(require_admin),
):
    """Start a context window benchmark run.

    Rejects with 409 while any benchmark (context, throughput, accuracy)
    is running — they all unload/load models and would corrupt each
    other. Rejects with 400 when the memory guard is off: there is no
    admission boundary to measure and an unguarded probe prefill can
    genuinely exhaust the machine.
    """
    from .accuracy_benchmark import get_queue_status
    from .benchmark import get_active_run as get_active_throughput_run
    from .context_benchmark import (
        ContextBenchmarkRequest,
        cleanup_old_runs,
        create_run,
        get_active_run,
        run_context_benchmark,
    )

    engine_pool = _get_engine_pool()
    if engine_pool is None:
        raise HTTPException(status_code=503, detail="Engine pool not initialized")

    active = get_active_run()
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A context benchmark is already running "
                f"(bench_id={active.bench_id}, "
                f"model_id={active.request.model_id})."
            ),
        )
    throughput_active = get_active_throughput_run()
    if throughput_active is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A throughput benchmark is already running "
                f"(bench_id={throughput_active.bench_id}, "
                f"model_id={throughput_active.request.model_id})."
            ),
        )
    accuracy_status = get_queue_status()
    if accuracy_status.get("running"):
        raise HTTPException(
            status_code=409,
            detail=(
                f"An accuracy benchmark is already running "
                f"(model_id={accuracy_status.get('current_model')})."
            ),
        )

    from ..server import _server_state

    enforcer = getattr(_server_state, "process_memory_enforcer", None)
    final_ceiling = 0
    if enforcer is not None:
        try:
            final_ceiling = int(enforcer.get_final_ceiling())
        except Exception:
            final_ceiling = 0
    if final_ceiling <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Memory Guard is disabled. The context benchmark measures "
                "the guard's admission boundary, and probing without it can "
                "exhaust system memory. Enable Memory Guard and retry."
            ),
        )

    body = await request.json()
    try:
        bench_request = ContextBenchmarkRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    entry = engine_pool.get_entry(bench_request.model_id)
    if entry is None:
        raise HTTPException(
            status_code=404, detail=f"Model not found: {bench_request.model_id}"
        )
    if entry.model_type not in ("llm", "vlm", None):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Model {bench_request.model_id} is not a supported model "
                f"(type: {entry.model_type})"
            ),
        )

    cleanup_old_runs()
    run = create_run(bench_request)
    run.task = asyncio.create_task(run_context_benchmark(run, engine_pool))

    logger.info(
        f"Context benchmark started: {run.bench_id} "
        f"model={bench_request.model_id} target={bench_request.target_tokens}"
    )

    return {
        "bench_id": run.bench_id,
        "status": "started",
        "target_tokens": bench_request.target_tokens,
    }


@router.get("/api/bench/context/{bench_id}/stream")
async def stream_context_benchmark(
    bench_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Stream context benchmark progress via Server-Sent Events."""
    import json

    from fastapi.responses import StreamingResponse

    from .context_benchmark import get_run

    run = get_run(bench_id)
    if run is None:
        raise HTTPException(
            status_code=404, detail=f"Benchmark not found: {bench_id}"
        )

    async def event_generator():
        # Replay-then-attach, same shape as the throughput bench stream.
        # Terminal events here are `done` and `error`.
        seen = 0
        try:
            while True:
                async with run.cond:
                    while seen >= len(run.events) and not run.terminal:
                        try:
                            await asyncio.wait_for(run.cond.wait(), timeout=60.0)
                        except TimeoutError:
                            break
                    new = list(run.events[seen:])
                    seen = len(run.events)
                    done = run.terminal

                for ev in new:
                    yield f"data: {json.dumps(ev)}\n\n"
                if not new and not done:
                    yield ": keepalive\n\n"
                if done:
                    break
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/bench/context/{bench_id}/cancel")
async def cancel_context_benchmark(
    bench_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Cancel a running context benchmark."""
    from .context_benchmark import get_run

    run = get_run(bench_id)
    if run is None:
        raise HTTPException(
            status_code=404, detail=f"Benchmark not found: {bench_id}"
        )

    if run.status != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Benchmark is not running (status: {run.status})",
        )

    if run.task and not run.task.done():
        run.task.cancel()

    return {"status": "cancelled", "bench_id": bench_id}


@router.get("/api/bench/context/{bench_id}/results")
async def get_context_benchmark_results(
    bench_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Get status and result of a context benchmark (REST poll surface)."""
    from .context_benchmark import get_run

    run = get_run(bench_id)
    if run is None:
        raise HTTPException(
            status_code=404, detail=f"Benchmark not found: {bench_id}"
        )

    return {
        "bench_id": run.bench_id,
        "status": run.status,
        "phase": run.phase,
        "progress": run.progress,
        "message": run.message,
        "result": run.result,
        "error": run.error_message if run.error_message else None,
    }


# =============================================================================
# Benchmark API Routes (Throughput)
# =============================================================================


@router.get("/api/bench/active")
async def get_active_benchmark(is_admin: bool = Depends(require_admin)):
    """Return the currently-running throughput benchmark, if any.

    Symmetric to `/api/bench/accuracy/queue/status` — lets a fresh page
    load or a second tab discover an in-flight run so it can attach to
    the SSE stream. Combined with the replay-on-subscribe stream this
    is what makes the multi-tab + page-refresh story actually work.
    """
    from .benchmark import get_active_run

    run = get_active_run()
    if run is None:
        return {
            "running": False,
            "bench_id": None,
            "model_id": None,
            "context_profile": None,
        }
    return {
        "running": True,
        "bench_id": run.bench_id,
        "model_id": run.request.model_id,
        "context_profile": run.request.context_profile.value,
        "force_lm_engine": run.request.force_lm_engine,
        # Reconnecting tabs need this to restore the disabled-dropdown UI
        # state. Never expose base_url/api_key here — model_id already
        # carries the external model name.
        "external": run.request.external is not None,
    }


@router.post("/api/bench/start")
async def start_benchmark(
    request: Request,
    is_admin: bool = Depends(require_admin),
):
    """Start a benchmark run.

    Validates the model, creates a benchmark run, and starts it
    as an asyncio background task. Rejects with 409 if another
    throughput bench is already running — two concurrent runs on
    the same engine produce mutually-corrupted measurements.
    """
    from .benchmark import (
        BenchmarkRequest,
        cleanup_old_runs,
        create_run,
        get_active_run,
        run_benchmark,
    )

    engine_pool = _get_engine_pool()
    if engine_pool is None:
        raise HTTPException(status_code=503, detail="Engine pool not initialized")

    # One throughput bench at a time. The replay-on-subscribe stream lets
    # clients attach to the already-running one if that's what they want.
    active = get_active_run()
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A throughput benchmark is already running "
                f"(bench_id={active.bench_id}, model_id={active.request.model_id})."
            ),
        )

    from .context_benchmark import get_active_run as get_active_context_run

    context_active = get_active_context_run()
    if context_active is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A context benchmark is already running "
                f"(bench_id={context_active.bench_id}, "
                f"model_id={context_active.request.model_id})."
            ),
        )

    body = await request.json()
    try:
        bench_request = BenchmarkRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validate model exists and is an LLM. External runs target a remote
    # model — nothing to validate locally.
    if bench_request.external is None:
        entry = engine_pool.get_entry(bench_request.model_id)
        if entry is None:
            raise HTTPException(
                status_code=404, detail=f"Model not found: {bench_request.model_id}"
            )
        if entry.model_type not in ("llm", "vlm", None):
            raise HTTPException(
                status_code=400,
                detail=f"Model {bench_request.model_id} is not a supported model (type: {entry.model_type})",
            )

    # Cleanup old runs
    cleanup_old_runs()

    # Create and start the benchmark
    run = create_run(bench_request)
    total_tests = len(bench_request.prompt_lengths) + len(bench_request.batch_sizes) * 2

    run.task = asyncio.create_task(run_benchmark(run, engine_pool))

    logger.info(
        f"Benchmark started: {run.bench_id} model={bench_request.model_id} "
        f"tests={total_tests}"
    )

    return {
        "bench_id": run.bench_id,
        "status": "started",
        "total_tests": total_tests,
    }


@router.get("/api/bench/{bench_id}/stream")
async def stream_benchmark(
    bench_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Stream benchmark progress via Server-Sent Events."""
    import json

    from fastapi.responses import StreamingResponse

    from .benchmark import get_run

    run = get_run(bench_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Benchmark not found: {bench_id}")

    async def event_generator():
        # Replay-then-attach: see /api/bench/accuracy/{id}/stream for the
        # full rationale. The bench stream's terminal events are
        # `upload_done` and `error` — `done` only marks the boundary
        # between tests and upload.
        seen = 0
        try:
            while True:
                async with run.cond:
                    while seen >= len(run.events) and not run.terminal:
                        try:
                            await asyncio.wait_for(run.cond.wait(), timeout=60.0)
                        except TimeoutError:
                            break
                    new = list(run.events[seen:])
                    seen = len(run.events)
                    done = run.terminal

                for ev in new:
                    yield f"data: {json.dumps(ev)}\n\n"
                if not new and not done:
                    yield ": keepalive\n\n"
                if done:
                    break
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/bench/{bench_id}/cancel")
async def cancel_benchmark(
    bench_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Cancel a running benchmark."""
    from .benchmark import get_run

    run = get_run(bench_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Benchmark not found: {bench_id}")

    if run.status != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Benchmark is not running (status: {run.status})",
        )

    if run.task and not run.task.done():
        run.task.cancel()

    return {"status": "cancelled", "bench_id": bench_id}


@router.get("/api/bench/{bench_id}/results")
async def get_benchmark_results(
    bench_id: str,
    is_admin: bool = Depends(require_admin),
):
    """Get results from a completed benchmark."""
    from .benchmark import get_run

    run = get_run(bench_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Benchmark not found: {bench_id}")

    return {
        "bench_id": run.bench_id,
        "status": run.status,
        "context_profile": run.request.context_profile.value,
        "results": run.results,
        "error": run.error_message if run.error_message else None,
        "upload_state": run.upload_state,
    }


@router.get("/api/device-info")
async def get_device_info(
    is_admin: bool = Depends(require_admin),
):
    """Get device hardware info and owner_hash for omlx.ai integration."""
    from ..utils.hardware import (
        compute_owner_hash,
        get_chip_name,
        get_gpu_core_count,
        get_io_platform_uuid,
        get_total_memory_gb,
        parse_chip_info,
    )

    chip_string = get_chip_name()
    chip_name, chip_variant = parse_chip_info(chip_string)
    memory_gb = round(get_total_memory_gb())
    gpu_cores = get_gpu_core_count()

    owner_hash = None
    io_uuid = get_io_platform_uuid()
    if io_uuid:
        full_hash = compute_owner_hash(io_uuid, chip_name, gpu_cores, memory_gb)
        owner_hash = full_hash[:-1]  # Strip verify character for URL

    return {
        "chip_name": chip_name,
        "chip_variant": chip_variant,
        "memory_gb": memory_gb,
        "gpu_cores": gpu_cores,
        "owner_hash": owner_hash,
    }


# =============================================================================
# Update Check
# =============================================================================

@router.get("/api/update-check")
async def check_update(
    is_admin: bool = Depends(require_admin),
):
    """Return the independent AI2Apps update state.

    Upstream oMLX releases must not be presented as AI2Apps product updates.
    """
    return {
        "update_available": False,
        "latest_version": None,
        "release_url": None,
        "update_channel": "ai2apps",
    }


# =============================================================================
# oQ Quantization API Routes
# =============================================================================


@router.get("/api/oq/models")
async def list_oq_models(is_admin: bool = Depends(require_admin)):
    """List non-quantized models available for oQ quantization."""
    if _oq_manager is None:
        raise HTTPException(status_code=503, detail="oQ quantizer not initialized")
    source_models, all_models = await _oq_manager.list_quantizable_models()
    return {"models": source_models, "all_models": all_models}


@router.get("/api/oq/estimate")
async def estimate_oq(
    model_path: str,
    oq_level: float,
    preserve_mtp: bool = False,
    is_admin: bool = Depends(require_admin),
):
    """Estimate effective bpw and output size for a model at given oQ level."""
    from ..oq import estimate_bpw_and_size

    try:
        result = await asyncio.to_thread(
            estimate_bpw_and_size,
            model_path,
            oq_level,
            64,  # group_size (default)
            preserve_mtp,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/oq/start")
async def start_oq_quantization(
    request: OQStartRequest,
    is_admin: bool = Depends(require_admin),
):
    """Start an oQ quantization task."""
    from ..oq import OQ_LEVELS

    if _oq_manager is None:
        raise HTTPException(status_code=503, detail="oQ quantizer not initialized")
    if request.oq_level not in OQ_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid oQ level. Must be one of {sorted(OQ_LEVELS)}",
        )
    if request.dtype not in ("bfloat16", "float16"):
        raise HTTPException(
            status_code=400,
            detail="Invalid dtype. Must be 'bfloat16' or 'float16'",
        )
    if request.enhanced:
        if not 1 <= request.imatrix_num_samples <= 4096:
            raise HTTPException(
                status_code=400,
                detail="Invalid imatrix_num_samples. Must be between 1 and 4096.",
            )
        if not 64 <= request.imatrix_seq_length <= 8192:
            raise HTTPException(
                status_code=400,
                detail="Invalid imatrix_seq_length. Must be between 64 and 8192.",
            )
    is_paro, _ = _paroquant_compat_for_model({"model_path": request.model_path})
    if is_paro:
        raise HTTPException(
            status_code=400,
            detail=(
                "Model is already quantized with paroquant; "
                "oQ re-quantization is not supported"
            ),
        )
    try:
        task = await _oq_manager.start_quantization(
            model_path=request.model_path,
            oq_level=request.oq_level,
            group_size=request.group_size,
            sensitivity_model_path=request.sensitivity_model_path,
            text_only=request.text_only,
            dtype=request.dtype,
            preserve_mtp=request.preserve_mtp,
            auto_proxy_sensitivity=request.auto_proxy_sensitivity,
            enhanced=request.enhanced,
            imatrix_cache_path=request.imatrix_cache_path,
            imatrix_reuse_cache=request.imatrix_reuse_cache,
            imatrix_strict=request.imatrix_strict,
            imatrix_num_samples=request.imatrix_num_samples,
            imatrix_seq_length=request.imatrix_seq_length,
            mtp_assistant_model_path=request.mtp_assistant_model_path,
        )
        return {"success": True, "task": task.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/oq/tasks")
async def list_oq_tasks(is_admin: bool = Depends(require_admin)):
    """List all quantization tasks."""
    if _oq_manager is None:
        raise HTTPException(status_code=503, detail="oQ quantizer not initialized")
    return {"tasks": _oq_manager.get_tasks()}


@router.post("/api/oq/cancel/{task_id}")
async def cancel_oq_task(task_id: str, is_admin: bool = Depends(require_admin)):
    """Cancel an active quantization task."""
    if _oq_manager is None:
        raise HTTPException(status_code=503, detail="oQ quantizer not initialized")
    success = await _oq_manager.cancel_quantization(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or not cancellable")
    return {"success": True}


@router.delete("/api/oq/task/{task_id}")
async def remove_oq_task(task_id: str, is_admin: bool = Depends(require_admin)):
    """Remove a completed/failed/cancelled task."""
    if _oq_manager is None:
        raise HTTPException(status_code=503, detail="oQ quantizer not initialized")
    success = _oq_manager.remove_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or still active")
    return {"success": True}


# =============================================================================
# HuggingFace Upload Endpoints
# =============================================================================


@router.post("/api/upload/validate-token")
async def validate_upload_token(
    request: HFValidateTokenRequest,
    is_admin: bool = Depends(require_admin),
):
    """Validate a HuggingFace token and return user info."""
    if _hf_uploader is None:
        raise HTTPException(status_code=503, detail="HF Uploader not initialized")
    try:
        result = await _hf_uploader.validate_token(request.hf_token)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/upload/oq-models")
async def list_upload_oq_models(is_admin: bool = Depends(require_admin)):
    """List local oQ models available for upload."""
    if _hf_uploader is None:
        raise HTTPException(status_code=503, detail="HF Uploader not initialized")
    oq_models = await _hf_uploader.list_oq_models()
    all_models = await _hf_uploader.list_all_models()
    return {"oq_models": oq_models, "all_models": all_models}


@router.post("/api/upload/start")
async def start_upload(
    request: HFUploadRequest,
    is_admin: bool = Depends(require_admin),
):
    """Start an upload task to HuggingFace Hub."""
    if _hf_uploader is None:
        raise HTTPException(status_code=503, detail="HF Uploader not initialized")
    try:
        task = await _hf_uploader.start_upload(
            model_path=request.model_path,
            repo_id=request.repo_id,
            token=request.hf_token,
            readme_source_path=request.readme_source_path,
            auto_readme=request.auto_readme,
            redownload_notice=request.redownload_notice,
            private=request.private,
        )
        return {"success": True, "task": task.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/upload/tasks")
async def list_upload_tasks(is_admin: bool = Depends(require_admin)):
    """List all upload tasks."""
    if _hf_uploader is None:
        raise HTTPException(status_code=503, detail="HF Uploader not initialized")
    return {"tasks": _hf_uploader.get_tasks()}


@router.post("/api/upload/cancel/{task_id}")
async def cancel_upload_task(task_id: str, is_admin: bool = Depends(require_admin)):
    """Cancel an active or pending upload task."""
    if _hf_uploader is None:
        raise HTTPException(status_code=503, detail="HF Uploader not initialized")
    success = await _hf_uploader.cancel_upload(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or not cancellable")
    return {"success": True}


@router.delete("/api/upload/task/{task_id}")
async def remove_upload_task(task_id: str, is_admin: bool = Depends(require_admin)):
    """Remove a completed/failed/cancelled upload task."""
    if _hf_uploader is None:
        raise HTTPException(status_code=503, detail="HF Uploader not initialized")
    success = _hf_uploader.remove_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or still active")
    return {"success": True}
