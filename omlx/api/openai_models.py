# SPDX-License-Identifier: Apache-2.0
# Adapted from vllm-mlx (https://github.com/vllm-project/vllm-mlx).
"""
Pydantic models for OpenAI-compatible API.

These models define the request and response schemas for:
- Chat completions
- Text completions
- Tool calling
- MCP (Model Context Protocol) integration
"""

import json
from typing import Any, Dict, List, Optional, Union

from pydantic import AliasChoices, BaseModel, Field, field_validator

from omlx.api.shared_models import (
    BaseUsage,
    IDPrefix,
    generate_id,
    get_unix_timestamp,
)

# =============================================================================
# Content Types
# =============================================================================


class ImageURL(BaseModel):
    """Base64 data URI for vision model input."""

    url: str  # "data:image/jpeg;base64,..."
    detail: Optional[str] = "auto"  # "low", "high", "auto"


class InputAudio(BaseModel):
    """Audio input data for multimodal models (OpenAI format)."""

    data: str  # Base64-encoded audio or data URI
    format: str = "wav"  # Audio format: wav, mp3, etc.


class FileContent(BaseModel):
    """File input for attachment preprocessing.

    ``file_data`` matches OpenAI Chat Completions file content parts.
    ``data`` is accepted as an oMLX legacy alias for dashboard clients.
    """

    filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_data: Optional[str] = None
    data: Optional[str] = None
    file_id: Optional[str] = None


class ContentPart(BaseModel):
    """
    A part of a message content array.

    Supports:
    - text: Plain text content
    - image_url: Image input for vision models
    - input_audio: Audio input for multimodal audio models
    - file: Document or text input for attachment preprocessing
    """

    type: str  # "text", "image_url", "input_audio", or "file"
    text: Optional[str] = None
    image_url: Optional[ImageURL] = None
    input_audio: Optional[InputAudio] = None
    file: Optional[FileContent] = None


# =============================================================================
# Messages
# =============================================================================


class Message(BaseModel):
    """
    A message in a chat conversation.

    Supports:
    - Simple text messages (role + content string)
    - Content array messages (role + content list with text parts)
    - Tool call messages (assistant with tool_calls)
    - Tool response messages (role="tool" with tool_call_id)
    """

    role: str
    content: Optional[Union[str, List[ContentPart], List[dict]]] = None
    # Reasoning/thinking content from <think> blocks (OpenAI reasoning_content field)
    reasoning_content: Optional[str] = None
    # For assistant messages with tool calls
    tool_calls: Optional[List[dict]] = None
    # For tool response messages (role="tool")
    tool_call_id: Optional[str] = None
    # Participant name, rendered into chat template (e.g. Kimi K2/K2.5 named assistants)
    name: Optional[str] = None
    # Continue from this message instead of starting a new turn (prefill / partial mode)
    partial: bool = False

    @field_validator("tool_calls", mode="before")
    @classmethod
    def _validate_tool_call_arguments(cls, v: Any) -> Any:
        """Validate arguments on each tool_call before the raw dict is stored.

        tool_calls is typed as List[dict] for flexibility, which bypasses
        FunctionCall's own validator. Re-run the same coercion here so
        malformed arguments surface as 422 instead of crashing the chat
        template on the next turn.
        """
        if not isinstance(v, list):
            return v
        for tc in v:
            if not isinstance(tc, dict):
                continue
            func = tc.get("function")
            if not isinstance(func, dict) or "arguments" not in func:
                continue
            func["arguments"] = _coerce_tool_call_arguments(func["arguments"])
        return v


# =============================================================================
# Tool Calling
# =============================================================================


def _coerce_tool_call_arguments(v: Any) -> str:
    """Normalize a tool_call.arguments value to a JSON-object string.

    Native tool-calling chat templates (Qwen3.5/3.6, GLM-4.x, MiniMax)
    iterate `arguments.items()`, which requires the echoed value to parse
    back into a dict. Rejecting malformed inputs here turns the silent 500
    in downstream template rendering into a clear 422 that tells the client
    what to fix. Dict inputs (non-spec but common) are coerced to JSON
    strings, empty/whitespace strings normalize to ``"{}"``, and any value
    that can't round-trip into a JSON object raises ValueError.
    """
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    if not isinstance(v, str):
        raise ValueError(
            f"arguments must be a JSON-encoded string, got {type(v).__name__}. "
            "Per the OpenAI spec tool_call.arguments is a string containing JSON, "
            'not a dict/list/number. Example: \'{"location": "Tokyo"}\'.'
        )
    stripped = v.strip()
    if not stripped:
        return "{}"
    try:
        parsed = json.loads(stripped)
    except (json.JSONDecodeError, ValueError) as e:
        snippet = stripped if len(stripped) <= 120 else stripped[:117] + "..."
        raise ValueError(
            f"arguments must be valid JSON, got parse error: {e}. "
            "This usually means the client echoed a previous tool call "
            "with a malformed arguments value. Send arguments as a "
            'JSON-encoded object string like \'{"location": "Tokyo"}\'. '
            f"Received: {snippet!r}"
        ) from e
    if not isinstance(parsed, dict):
        raise ValueError(
            f"arguments must be a JSON object, got {type(parsed).__name__}. "
            "Tool-call arguments cannot be a list, number, or bare string. "
            'Example: \'{"location": "Tokyo"}\'.'
        )
    return v


class FunctionCall(BaseModel):
    """A function call with name and arguments."""

    name: str
    arguments: str  # JSON string

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, v: Any) -> str:
        return v.strip() if isinstance(v, str) else v

    @field_validator("arguments", mode="before")
    @classmethod
    def _validate_arguments_json(cls, v: Any) -> str:
        return _coerce_tool_call_arguments(v)


class ToolCall(BaseModel):
    """A tool call from the model."""

    id: str
    type: str = "function"
    function: FunctionCall


class ToolDefinition(BaseModel):
    """Definition of a tool that can be called by the model."""

    type: str = "function"
    function: dict


# =============================================================================
# Structured Output (JSON Schema)
# =============================================================================


class ResponseFormatJsonSchema(BaseModel):
    """JSON Schema definition for structured output."""

    name: str
    description: Optional[str] = None
    schema_: dict = Field(alias="schema")  # JSON Schema specification
    strict: Optional[bool] = False

    class Config:
        populate_by_name = True


class ResponseFormat(BaseModel):
    """
    Response format specification for structured output.

    Supports:
    - "text": Default text output (no structure enforcement)
    - "json_object": Forces valid JSON output
    - "json_schema": Forces JSON matching a specific schema
    """

    type: str = "text"  # "text", "json_object", "json_schema"
    json_schema: Optional[ResponseFormatJsonSchema] = None


class StructuredOutputOptions(BaseModel):
    """vLLM-compatible structured output options.

    Exactly one field should be set. When passed via ``extra_body`` in the
    OpenAI client, the key is ``structured_outputs``.

    Supports:
    - json: JSON schema (dict or string) for logit-level enforcement
    - regex: Regular expression the output must match
    - choice: List of allowed string values (output will be exactly one)
    - grammar: EBNF/GBNF context-free grammar string
    """

    model_config = {"populate_by_name": True}

    json_schema: Optional[Union[str, dict]] = Field(None, alias="json")
    regex: Optional[str] = None
    choice: Optional[List[str]] = None
    grammar: Optional[str] = None


# =============================================================================
# Chat Completion
# =============================================================================


class StreamOptions(BaseModel):
    """Options for streaming responses."""

    include_usage: bool = False


class ChatCompletionRequest(BaseModel):
    """Request for chat completion."""

    model: str
    messages: List[Message]
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    repetition_penalty: float | None = None
    max_tokens: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("max_tokens", "max_completion_tokens"),
    )
    stream: bool = False
    stream_options: Optional[StreamOptions] = None
    stop: Optional[List[str]] = None
    min_p: float | None = None
    xtc_probability: float | None = None
    xtc_threshold: float | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    # Tool calling
    tools: Optional[List[ToolDefinition]] = None
    tool_choice: Optional[Union[str, dict]] = None  # "auto", "none", or specific tool
    # Structured output
    response_format: Optional[Union[ResponseFormat, dict]] = None
    # vLLM-compatible structured output (grammar, regex, choice, json)
    structured_outputs: Optional[Union[StructuredOutputOptions, dict]] = None
    # vLLM/OpenAI-compatible grammar alias, normalized to structured_outputs
    guided_grammar: Optional[str] = None
    # Chat template kwargs (e.g. enable_thinking, reasoning_effort)
    chat_template_kwargs: Optional[Dict[str, Any]] = None
    # OpenAI-compatible shorthand forwarded to the model chat template.
    reasoning_effort: Optional[str] = None
    # Thinking budget (max thinking tokens, None = unlimited)
    thinking_budget: Optional[int] = Field(default=None, ge=0)
    # SpecPrefill: per-request enable/disable (None = use model setting)
    specprefill: Optional[bool] = None
    # SpecPrefill: per-request keep percentage (0.1-0.5, None = use model setting)
    specprefill_keep_pct: Optional[float] = None
    # SpecPrefill: per-request threshold override (min tokens to trigger, None = use model setting)
    specprefill_threshold: Optional[int] = None
    # Seed for reproducible generation (best-effort)
    seed: Optional[int] = None
    # AI2Apps extension: stable logical conversation ownership for adaptive L1.
    # Ignored by engines that do not implement a session-owned expert cache.
    ai2apps_session_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    # AI2Apps Cloud logical request identity. The local gateway forwards this
    # value only to AI2Apps Cloud; local/provider-direct requests ignore it.
    ai2apps_idempotency_key: Optional[str] = Field(
        default=None, min_length=8, max_length=160
    )
    # AI2Apps extension: per-Session adaptive L1 policy. ``trigger`` is an
    # action exposed by /v1/ai2apps/l1/optimize, not a request mode.
    ai2apps_l1_mode: Optional[str] = None
    # AI2Apps extension: per-request routed-expert acceleration policy.
    # auto selects a Prefill policy by context length and returns Decode to
    # exact; natural=exact, turbo=Head3 Prefill/Tail2 Decode, blast=head2.
    ai2apps_engine_boost: Optional[str] = None
    # Prefix-KV continuity: strict uses canonical visible history, session
    # retains full KV for this process, persistent also permits SSD reuse after
    # a server restart. Non-strict modes require ai2apps_session_id.
    ai2apps_kv_policy: Optional[str] = None
    # AI2Apps Fusion stream capability negotiation.
    ai2apps_stream_mode: Optional[str] = None
    # Per-request Fusion review overrides. None inherits the saved profile.
    ai2apps_fusion_gate_policy: Optional[str] = None
    ai2apps_fusion_mid_generation_review: Optional[bool] = None
    ai2apps_fusion_thinking_audit: Optional[bool] = None
    ai2apps_fusion_reviewer_guidance: Optional[str] = None
    ai2apps_fusion_checkpoint_tokens: Optional[int] = Field(default=None, ge=1)
    ai2apps_fusion_generator_l1_mode: Optional[str] = None
    ai2apps_fusion_generator_engine_boost: Optional[str] = None
    ai2apps_fusion_reviewer_l1_mode: Optional[str] = None
    ai2apps_fusion_reviewer_engine_boost: Optional[str] = None
    # Read-only compatibility fields for pre-rename local clients. New API
    # responses and documentation expose only the AI2Apps names.
    dynamoe_session_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    dynamoe_l1_mode: Optional[str] = None
    dynamoe_engine_boost: Optional[str] = None
    dynamoe_kv_policy: Optional[str] = None
    dynamoe_stream_mode: Optional[str] = None

    @field_validator(
        "ai2apps_l1_mode",
        "dynamoe_l1_mode",
        "ai2apps_fusion_generator_l1_mode",
        "ai2apps_fusion_reviewer_l1_mode",
    )
    @classmethod
    def validate_ai2apps_l1_mode(cls, value):
        if value is not None and value not in ("auto", "off"):
            raise ValueError("ai2apps_l1_mode must be auto or off")
        return value

    @field_validator(
        "ai2apps_engine_boost",
        "dynamoe_engine_boost",
        "ai2apps_fusion_generator_engine_boost",
        "ai2apps_fusion_reviewer_engine_boost",
    )
    @classmethod
    def validate_ai2apps_engine_boost(cls, value):
        if value is not None and value not in ("auto", "natural", "turbo", "blast"):
            raise ValueError(
                "ai2apps_engine_boost must be auto, natural, turbo, or blast"
            )
        return value

    @field_validator("ai2apps_kv_policy", "dynamoe_kv_policy")
    @classmethod
    def validate_ai2apps_kv_policy(cls, value):
        if value is not None and value not in ("strict", "session", "persistent"):
            raise ValueError(
                "ai2apps_kv_policy must be strict, session, or persistent"
            )
        return value

    @field_validator("ai2apps_stream_mode", "dynamoe_stream_mode")
    @classmethod
    def validate_ai2apps_stream_mode(cls, value):
        if value is not None and value not in ("draft", "reasoning", "final"):
            raise ValueError("ai2apps_stream_mode must be draft, reasoning, or final")
        return value

    @field_validator("ai2apps_fusion_gate_policy")
    @classmethod
    def validate_ai2apps_fusion_gate_policy(cls, value):
        if value is not None and value not in ("off", "always", "adaptive"):
            raise ValueError("ai2apps_fusion_gate_policy must be off, always, or adaptive")
        return value

    @field_validator("ai2apps_fusion_reviewer_guidance")
    @classmethod
    def validate_ai2apps_fusion_reviewer_guidance(cls, value):
        if value is not None and value not in ("off", "reasoning_handoff"):
            raise ValueError(
                "ai2apps_fusion_reviewer_guidance must be off or reasoning_handoff"
            )
        return value

    @field_validator("stop", mode="before")
    @classmethod
    def coerce_stop(cls, v):
        """Accept stop as a single string (OpenAI compat) and wrap in a list."""
        if isinstance(v, str):
            return [v]
        return v


class AI2AppsL1OptimizeRequest(BaseModel):
    """AI2Apps extension for a non-blocking adaptive-L1 control request."""

    model: str
    session_id: str = Field(min_length=1, max_length=128)


class AI2AppsEngineBoostRequest(BaseModel):
    """Queue an Engine Boost change at the next safe Decode boundary."""

    model: str
    session_id: str = Field(min_length=1, max_length=128)
    mode: str

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value):
        if value not in ("auto", "natural", "turbo", "blast"):
            raise ValueError("mode must be auto, natural, turbo, or blast")
        return value


class AI2AppsFusionSkipReviewRequest(BaseModel):
    """Skip the reviewer for one currently running Fusion session."""

    model: str
    session_id: str = Field(min_length=1, max_length=128)


class AI2AppsExternalReviewRequest(BaseModel):
    """Explicitly review one completed Fusion answer with a cloud model."""

    fusion_model: str
    external_model: str
    session_id: str = Field(min_length=1, max_length=128)
    messages: List[Dict[str, Any]]
    draft: str = Field(min_length=1)


# Import compatibility for integrations built against development checkouts.
DynaMoeL1OptimizeRequest = AI2AppsL1OptimizeRequest
DynaMoeEngineBoostRequest = AI2AppsEngineBoostRequest


class AssistantMessage(BaseModel):
    """Response message from the assistant."""

    role: str = "assistant"
    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class ChatCompletionChoice(BaseModel):
    """A single choice in chat completion response."""

    index: int = 0
    message: AssistantMessage
    finish_reason: Optional[str] = "stop"


class PromptTokensDetails(BaseModel):
    """Breakdown of prompt tokens used."""

    cached_tokens: Optional[int] = None
    audio_tokens: Optional[int] = None


class Usage(BaseUsage):
    """Token usage statistics for OpenAI API.

    Extends BaseUsage with optional timing metrics (oMLX extension).
    When present, timing values are in seconds.
    """

    prompt_tokens_details: Optional[PromptTokensDetails] = None
    # Timing metrics (oMLX extension, seconds)
    model_load_duration: Optional[float] = None
    time_to_first_token: Optional[float] = None
    total_time: Optional[float] = None
    prompt_eval_duration: Optional[float] = None
    generation_duration: Optional[float] = None
    prompt_tokens_per_second: Optional[float] = None
    generation_tokens_per_second: Optional[float] = None


class ChatCompletionResponse(BaseModel):
    """Response for chat completion."""

    id: str = Field(default_factory=lambda: generate_id(IDPrefix.CHAT_COMPLETION))
    object: str = "chat.completion"
    created: int = Field(default_factory=get_unix_timestamp)
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage = Field(default_factory=Usage)


# =============================================================================
# Text Completion
# =============================================================================


class CompletionRequest(BaseModel):
    """Request for text completion."""

    model: str
    prompt: Union[str, List[str]]
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    repetition_penalty: float | None = None
    max_tokens: Optional[int] = None
    stream: bool = False
    stream_options: Optional[StreamOptions] = None
    stop: Optional[List[str]] = None
    min_p: float | None = None
    xtc_probability: float | None = None
    xtc_threshold: float | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    # Seed for reproducible generation (best-effort)
    seed: Optional[int] = None
    # Cap reasoning/thinking tokens (parity with /v1/chat/completions)
    thinking_budget: Optional[int] = Field(default=None, ge=0)

    @field_validator("stop", mode="before")
    @classmethod
    def coerce_stop(cls, v):
        """Accept stop as a single string (OpenAI compat) and wrap in a list."""
        if isinstance(v, str):
            return [v]
        return v


class CompletionChoice(BaseModel):
    """A single choice in text completion response."""

    index: int = 0
    text: str
    finish_reason: Optional[str] = "stop"


class CompletionResponse(BaseModel):
    """Response for text completion."""

    id: str = Field(default_factory=lambda: generate_id(IDPrefix.COMPLETION))
    object: str = "text_completion"
    created: int = Field(default_factory=get_unix_timestamp)
    model: str
    choices: List[CompletionChoice]
    usage: Usage = Field(default_factory=Usage)


# =============================================================================
# Models List
# =============================================================================


class ModelInfo(BaseModel):
    """Information about an available model."""

    id: str
    object: str = "model"
    created: int = Field(default_factory=get_unix_timestamp)
    owned_by: str = "omlx"
    # vLLM-compatible extension: lets OpenAI-style clients discover the
    # effective context window from the listing without a separate call
    # to /v1/models/status (see #1308).
    max_model_len: int | None = None
    # AI2Apps extension: execution/billing authority is explicit rather than
    # inferred by clients from a legacy public model-id prefix.
    source: str | None = None
    shareable: bool | None = None
    usage_notice: str | None = None
    # AI2Apps discovery extensions. Clients use these explicit declarations
    # instead of guessing multimodal support from a model name.
    model_type: str | None = None
    capabilities: list[str] | dict[str, Any] | None = None


class ModelsResponse(BaseModel):
    """Response for listing models."""

    object: str = "list"
    data: List[ModelInfo]


# =============================================================================
# MCP (Model Context Protocol)
# =============================================================================


class MCPToolInfo(BaseModel):
    """Information about an MCP tool."""

    name: str
    description: str
    server: str
    parameters: dict = Field(default_factory=dict)


class MCPToolsResponse(BaseModel):
    """Response for listing MCP tools."""

    tools: List[MCPToolInfo]
    count: int


class MCPServerInfo(BaseModel):
    """Information about an MCP server."""

    name: str
    state: str
    transport: str
    tools_count: int
    error: Optional[str] = None


class MCPServersResponse(BaseModel):
    """Response for listing MCP servers."""

    servers: List[MCPServerInfo]


class MCPExecuteRequest(BaseModel):
    """Request to execute an MCP tool."""

    model_config = {"populate_by_name": True}

    tool_name: str = Field(validation_alias=AliasChoices("tool_name", "tool"))
    arguments: dict = Field(default_factory=dict)


class MCPExecuteResponse(BaseModel):
    """Response from executing an MCP tool."""

    tool_name: str
    content: Optional[Union[str, list, dict]] = None
    is_error: bool = False
    error_message: Optional[str] = None


# =============================================================================
# Streaming (for SSE responses)
# =============================================================================


class ChatCompletionChunkDelta(BaseModel):
    """Delta content in a streaming chunk."""

    role: Optional[str] = None
    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    tool_calls: Optional[List[dict]] = None
    # Native AI2Apps Fusion phase event. OpenAI-compatible clients ignore it;
    # AI2Apps-aware clients can commit, patch, or supersede a streamed draft.
    ai2apps: Optional[dict] = None


class ChatCompletionChunkChoice(BaseModel):
    """A single choice in a streaming chunk."""

    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """A streaming chunk for chat completion."""

    id: str = Field(default_factory=lambda: generate_id(IDPrefix.CHAT_COMPLETION))
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=get_unix_timestamp)
    model: str
    choices: List[ChatCompletionChunkChoice]
    usage: Optional[Usage] = None  # Present on last chunk when include_usage=true
