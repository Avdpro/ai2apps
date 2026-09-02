"""Frozen Model Share v1 manifests, RFC 8785 digests, and schema checks."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

try:
    import rfc8785
except ModuleNotFoundError:  # Development source trees may not be re-synced yet.
    rfc8785 = None

from ai2apps.peer.identity import b64url_encode

REQUEST_SCHEMA_VERSION = "ai2apps.compute.request.v1"
RESULT_SCHEMA_VERSION = "ai2apps.compute.result.v1"
AUDIO_TTS_REQUEST_SCHEMA_VERSION = "ai2apps.compute.request.audio-tts.v2"
AUDIO_TTS_RESULT_SCHEMA_VERSION = "ai2apps.compute.result.audio-tts.v2"
MULTIMODAL_REQUEST_SCHEMA_VERSION = "ai2apps.compute.request.multimodal-pricing.v1"
MULTIMODAL_RESULT_SCHEMA_VERSION = "ai2apps.compute.result.multimodal-pricing.v1"
REQUEST_DIGEST_DOMAIN = "ai2apps.compute.request.v1"
RESULT_DIGEST_DOMAIN = "ai2apps.compute.result.v1"
MULTIMODAL_CALCULATORS = frozenset({"tts_v1", "image_v1", "video_v1"})

_REQUEST_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["schemaVersion", "requestId", "requesterId", "model", "payment", "prompt", "systemPrompt", "parameters", "attachments", "nonce"],
    "properties": {
        "schemaVersion": {"const": REQUEST_SCHEMA_VERSION},
        "requestId": {"type": "string", "format": "uuid"},
        "requesterId": {"type": "string", "format": "uuid"},
        "model": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "revision", "runtime"],
            "properties": {
                "id": {"type": "string", "minLength": 1, "maxLength": 200},
                "revision": {"type": "string", "minLength": 1, "maxLength": 160},
                "runtime": {"type": "string", "minLength": 1, "maxLength": 120},
            },
        },
        "payment": {
            "type": "object", "additionalProperties": False,
            "required": ["assetCode", "floatingPrice", "maximumAmountMinor"],
            "properties": {
                "assetCode": {"const": "PROMO_POINTS"},
                "floatingPrice": {"type": "boolean"},
                "maximumAmountMinor": {"type": "string", "pattern": "^[1-9][0-9]*$"},
            },
        },
        "prompt": {"type": "string", "maxLength": 1_000_000},
        "systemPrompt": {"type": ["string", "null"], "maxLength": 1_000_000},
        "parameters": {
            "type": "object", "additionalProperties": False,
            "required": ["temperature", "maxTokens"],
            "properties": {
                "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                "maxTokens": {"type": "integer", "minimum": 1, "maximum": 65_536},
            },
        },
        "attachments": {"type": "array", "maxItems": 0},
        "nonce": {"type": "string", "pattern": "^[A-Za-z0-9_-]{22,128}$"},
    },
}

_RESULT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object", "additionalProperties": False,
    "required": ["schemaVersion", "contractId", "requestDigest", "parts", "finishReason", "nonce"],
    "properties": {
        "schemaVersion": {"const": RESULT_SCHEMA_VERSION},
        "contractId": {"type": "string", "format": "uuid"},
        "requestDigest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "parts": {
            "type": "array", "minItems": 1, "maxItems": 256,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["type", "text"],
                "properties": {
                    "type": {"const": "text"},
                    "text": {"type": "string", "maxLength": 4_000_000},
                },
            },
        },
        "finishReason": {"type": "string", "minLength": 1, "maxLength": 80},
        "nonce": {"type": "string", "pattern": "^[A-Za-z0-9_-]{22,128}$"},
    },
}

_AUDIO_TTS_REQUEST_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object", "additionalProperties": False,
    "required": ["schemaVersion", "requestId", "requesterId", "model", "payment", "text", "voice", "language", "instructions", "speed", "responseFormat", "nonce"],
    "properties": {
        "schemaVersion": {"const": AUDIO_TTS_REQUEST_SCHEMA_VERSION},
        "requestId": {"type": "string", "format": "uuid"},
        "requesterId": {"type": "string", "format": "uuid"},
        "model": _REQUEST_SCHEMA["properties"]["model"],
        "payment": _REQUEST_SCHEMA["properties"]["payment"],
        "text": {"type": "string", "minLength": 1, "maxLength": 100_000},
        "voice": {"type": "string", "minLength": 1, "maxLength": 120, "pattern": "^[A-Za-z0-9._-]+$"},
        "language": {"type": ["string", "null"], "maxLength": 40, "pattern": "^[A-Za-z0-9._-]+$"},
        "instructions": {"type": ["string", "null"], "maxLength": 2_000},
        "speed": {"type": "number", "minimum": 0.5, "maximum": 2.0},
        "responseFormat": {"const": "wav"},
        "nonce": _REQUEST_SCHEMA["properties"]["nonce"],
    },
}

_AUDIO_TTS_RESULT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object", "additionalProperties": False,
    "required": ["schemaVersion", "contractId", "requestDigest", "parts", "usage", "finishReason", "nonce"],
    "properties": {
        "schemaVersion": {"const": AUDIO_TTS_RESULT_SCHEMA_VERSION},
        "contractId": {"type": "string", "format": "uuid"},
        "requestDigest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "parts": {
            "type": "array", "minItems": 1, "maxItems": 1,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["type", "artifactId", "mediaType", "sizeBytes", "contentDigest", "chunkManifestDigest"],
                "properties": {
                    "type": {"const": "artifact"}, "artifactId": {"const": "audio-0"},
                    "mediaType": {"const": "audio/wav"},
                    "sizeBytes": {"type": "integer", "minimum": 44, "maximum": 67_108_864},
                    "contentDigest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "chunkManifestDigest": {"type": "null"},
                },
            },
        },
        "usage": {
            "type": "object", "additionalProperties": False,
            "required": ["inputUnit", "inputUnits", "outputUnit", "outputUnits"],
            "properties": {
                "inputUnit": {"const": "unicode_scalar"},
                "inputUnits": {"type": "integer", "minimum": 1, "maximum": 100_000},
                "outputUnit": {"const": "audio_millisecond"},
                "outputUnits": {"type": "integer", "minimum": 1, "maximum": 86_400_000},
            },
        },
        "finishReason": {"const": "stop"},
        "nonce": _RESULT_SCHEMA["properties"]["nonce"],
    },
}

_MULTIMODAL_REQUEST_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object", "additionalProperties": False,
    "required": ["schemaVersion", "requestId", "contractId", "quoteId", "calculatorType",
                 "modelId", "modelRevision", "runtime", "requestPayloadDigest"],
    "properties": {
        "schemaVersion": {"const": MULTIMODAL_REQUEST_SCHEMA_VERSION},
        "requestId": {"type": "string", "format": "uuid"},
        "contractId": {"type": "string", "format": "uuid"},
        "quoteId": {"type": "string", "format": "uuid"},
        "calculatorType": {"enum": sorted(MULTIMODAL_CALCULATORS)},
        "modelId": {"type": "string", "minLength": 1, "maxLength": 200},
        "modelRevision": {"type": "string", "minLength": 1, "maxLength": 160},
        "runtime": {"type": "string", "minLength": 1, "maxLength": 120},
        "requestPayloadDigest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    },
}

_MULTIMODAL_RESULT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object", "additionalProperties": False,
    "required": ["schemaVersion", "contractId", "calculatorType", "actualUsage", "artifacts"],
    "properties": {
        "schemaVersion": {"const": MULTIMODAL_RESULT_SCHEMA_VERSION},
        "contractId": {"type": "string", "format": "uuid"},
        "calculatorType": {"enum": sorted(MULTIMODAL_CALCULATORS)},
        "actualUsage": {"type": "object"},
        "artifacts": {
            "type": "array", "minItems": 1, "maxItems": 256,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["sha256", "contentType", "byteSize"],
                "properties": {
                    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "contentType": {"type": "string", "minLength": 1, "maxLength": 200},
                    "byteSize": {"type": "string", "pattern": "^[1-9][0-9]*$"},
                },
            },
        },
    },
}

_FORMATS = FormatChecker()
_REQUEST_VALIDATOR = Draft202012Validator(_REQUEST_SCHEMA, format_checker=_FORMATS)
_RESULT_VALIDATOR = Draft202012Validator(_RESULT_SCHEMA, format_checker=_FORMATS)
_AUDIO_TTS_REQUEST_VALIDATOR = Draft202012Validator(_AUDIO_TTS_REQUEST_SCHEMA, format_checker=_FORMATS)
_AUDIO_TTS_RESULT_VALIDATOR = Draft202012Validator(_AUDIO_TTS_RESULT_SCHEMA, format_checker=_FORMATS)
_MULTIMODAL_REQUEST_VALIDATOR = Draft202012Validator(_MULTIMODAL_REQUEST_SCHEMA, format_checker=_FORMATS)
_MULTIMODAL_RESULT_VALIDATOR = Draft202012Validator(_MULTIMODAL_RESULT_SCHEMA, format_checker=_FORMATS)


def canonical_json(value: Mapping[str, Any]) -> bytes:
    """Return RFC 8785 bytes; approximations based on sorted JSON are forbidden."""

    if rfc8785 is None:
        raise RuntimeError(
            "Model Share requires the declared rfc8785 runtime dependency"
        )
    try:
        return rfc8785.dumps(value)
    except (TypeError, ValueError, rfc8785.CanonicalizationError) as error:
        raise ValueError("manifest is not RFC 8785 canonicalizable") from error


def manifest_digest(value: Mapping[str, Any], schema_version: str) -> str:
    if value.get("schemaVersion") != schema_version:
        raise ValueError("manifest schema version does not match its digest domain")
    return hashlib.sha256(schema_version.encode("utf-8") + b"\x00" + canonical_json(value)).hexdigest()


def compute_content_digest(kind: str, value: Mapping[str, Any]) -> str:
    if kind not in {"request", "result"}:
        raise ValueError("compute content digest kind is invalid")
    domain = REQUEST_DIGEST_DOMAIN if kind == "request" else RESULT_DIGEST_DOMAIN
    return hashlib.sha256(domain.encode("utf-8") + b"\x00" + canonical_json(value)).hexdigest()


def request_payload_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _validate(validator: Draft202012Validator, value: Mapping[str, Any]) -> None:
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    if errors:
        location = ".".join(str(item) for item in errors[0].absolute_path) or "$"
        raise ValueError(f"manifest field {location} is invalid")


@dataclass(frozen=True, slots=True)
class ComputeRequestManifest:
    value: dict[str, Any]

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> ComputeRequestManifest:
        if not isinstance(value, Mapping):
            raise ValueError("request manifest must be an object")
        materialized = dict(value)
        _validate(_REQUEST_VALIDATOR, materialized)
        canonical_json(materialized)
        return cls(materialized)

    @property
    def digest(self) -> str:
        return manifest_digest(self.value, REQUEST_SCHEMA_VERSION)

    @classmethod
    def create(
        cls, *, request_id: str, requester_id: str, model_id: str,
        revision: str, runtime: str, maximum_amount_minor: str,
        prompt: str, system_prompt: str | None, temperature: int | float,
        max_tokens: int, floating_price: bool = False,
    ) -> ComputeRequestManifest:
        return cls.parse({
            "schemaVersion": REQUEST_SCHEMA_VERSION,
            "requestId": request_id,
            "requesterId": requester_id,
            "model": {"id": model_id, "revision": revision, "runtime": runtime},
            "payment": {"assetCode": "PROMO_POINTS", "floatingPrice": floating_price, "maximumAmountMinor": maximum_amount_minor},
            "prompt": prompt,
            "systemPrompt": system_prompt,
            "parameters": {"temperature": temperature, "maxTokens": max_tokens},
            "attachments": [],
            "nonce": b64url_encode(secrets.token_bytes(16)),
        })


@dataclass(frozen=True, slots=True)
class ComputeResultManifest:
    value: dict[str, Any]

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> ComputeResultManifest:
        if not isinstance(value, Mapping):
            raise ValueError("result manifest must be an object")
        materialized = dict(value)
        _validate(_RESULT_VALIDATOR, materialized)
        canonical_json(materialized)
        return cls(materialized)

    @property
    def digest(self) -> str:
        return manifest_digest(self.value, RESULT_SCHEMA_VERSION)

    @classmethod
    def create(cls, *, contract_id: str, request_digest: str, text: str, finish_reason: str) -> ComputeResultManifest:
        return cls.parse({
            "schemaVersion": RESULT_SCHEMA_VERSION,
            "contractId": contract_id,
            "requestDigest": request_digest,
            "parts": [{"type": "text", "text": text}],
            "finishReason": finish_reason,
            "nonce": b64url_encode(secrets.token_bytes(16)),
        })


@dataclass(frozen=True, slots=True)
class AudioTTSRequestManifest:
    value: dict[str, Any]

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> AudioTTSRequestManifest:
        if not isinstance(value, Mapping):
            raise ValueError("audio TTS request manifest must be an object")
        materialized = dict(value)
        _validate(_AUDIO_TTS_REQUEST_VALIDATOR, materialized)
        if any(0xD800 <= ord(character) <= 0xDFFF for character in materialized["text"]):
            raise ValueError("audio TTS text must contain Unicode scalar values only")
        canonical_json(materialized)
        return cls(materialized)

    @property
    def digest(self) -> str:
        return manifest_digest(self.value, AUDIO_TTS_REQUEST_SCHEMA_VERSION)

    @classmethod
    def create(
        cls, *, request_id: str, requester_id: str, model_id: str,
        revision: str, runtime: str, maximum_amount_minor: str, text: str,
        voice: str, language: str | None = None,
        instructions: str | None = None, speed: int | float = 1.0,
    ) -> AudioTTSRequestManifest:
        return cls.parse({
            "schemaVersion": AUDIO_TTS_REQUEST_SCHEMA_VERSION,
            "requestId": request_id,
            "requesterId": requester_id,
            "model": {"id": model_id, "revision": revision, "runtime": runtime},
            "payment": {"assetCode": "PROMO_POINTS", "floatingPrice": False, "maximumAmountMinor": maximum_amount_minor},
            "text": text, "voice": voice, "language": language,
            "instructions": instructions, "speed": speed, "responseFormat": "wav",
            "nonce": b64url_encode(secrets.token_bytes(16)),
        })


@dataclass(frozen=True, slots=True)
class AudioTTSResultManifest:
    value: dict[str, Any]

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> AudioTTSResultManifest:
        if not isinstance(value, Mapping):
            raise ValueError("audio TTS result manifest must be an object")
        materialized = dict(value)
        _validate(_AUDIO_TTS_RESULT_VALIDATOR, materialized)
        canonical_json(materialized)
        return cls(materialized)

    @property
    def digest(self) -> str:
        return manifest_digest(self.value, AUDIO_TTS_RESULT_SCHEMA_VERSION)

    @classmethod
    def create(
        cls, *, contract_id: str, request_digest: str, size_bytes: int,
        content_digest: str, input_units: int, output_units: int,
    ) -> AudioTTSResultManifest:
        return cls.parse({
            "schemaVersion": AUDIO_TTS_RESULT_SCHEMA_VERSION,
            "contractId": contract_id, "requestDigest": request_digest,
            "parts": [{"type": "artifact", "artifactId": "audio-0", "mediaType": "audio/wav",
                       "sizeBytes": size_bytes, "contentDigest": content_digest, "chunkManifestDigest": None}],
            "usage": {"inputUnit": "unicode_scalar", "inputUnits": input_units,
                      "outputUnit": "audio_millisecond", "outputUnits": output_units},
            "finishReason": "stop", "nonce": b64url_encode(secrets.token_bytes(16)),
        })


@dataclass(frozen=True, slots=True)
class MultimodalRequestManifest:
    value: dict[str, Any]

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> "MultimodalRequestManifest":
        if not isinstance(value, Mapping):
            raise ValueError("multimodal request manifest must be an object")
        materialized = dict(value)
        _validate(_MULTIMODAL_REQUEST_VALIDATOR, materialized)
        canonical_json(materialized)
        return cls(materialized)

    @property
    def digest(self) -> str:
        return compute_content_digest("request", self.value)

    @classmethod
    def create(cls, *, request_id: str, contract_id: str, quote_id: str,
               calculator_type: str, model_id: str, model_revision: str,
               runtime: str, request_payload: Mapping[str, Any]) -> "MultimodalRequestManifest":
        return cls.parse({
            "schemaVersion": MULTIMODAL_REQUEST_SCHEMA_VERSION,
            "requestId": request_id, "contractId": contract_id,
            "quoteId": quote_id, "calculatorType": calculator_type,
            "modelId": model_id, "modelRevision": model_revision,
            "runtime": runtime,
            "requestPayloadDigest": request_payload_digest(request_payload),
        })


@dataclass(frozen=True, slots=True)
class MultimodalResultManifest:
    value: dict[str, Any]

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> "MultimodalResultManifest":
        if not isinstance(value, Mapping):
            raise ValueError("multimodal result manifest must be an object")
        materialized = dict(value)
        _validate(_MULTIMODAL_RESULT_VALIDATOR, materialized)
        canonical_json(materialized)
        return cls(materialized)

    @property
    def digest(self) -> str:
        return compute_content_digest("result", self.value)

    @classmethod
    def create(cls, *, contract_id: str, calculator_type: str,
               actual_usage: Mapping[str, Any], artifacts: list[Mapping[str, Any]]) -> "MultimodalResultManifest":
        return cls.parse({
            "schemaVersion": MULTIMODAL_RESULT_SCHEMA_VERSION,
            "contractId": contract_id, "calculatorType": calculator_type,
            "actualUsage": dict(actual_usage),
            "artifacts": [dict(item) for item in artifacts],
        })
