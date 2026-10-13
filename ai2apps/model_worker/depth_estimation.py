"""Depth estimation v1 transport contract; no inference dependencies."""

from collections.abc import Mapping

from .protocol import ModelWorkerError


def validate_depth_estimation(payload, *, parts, models):
    """Only uploaded images and declared depth models; never arbitrary paths/URLs."""
    def invalid(message):
        raise ModelWorkerError(message, code="invalid_depth_request", status_code=400)

    if not isinstance(payload, Mapping):
        invalid("Depth request must be an object")
    allowed = {"schema", "model", "input_size", "output_format", "image"}
    if set(payload) - allowed:
        invalid("Unsupported depth request fields")
    if payload.get("schema") != "ai2apps.depth-estimation/v1":
        invalid("Unsupported depth estimation schema")
    model_id = payload.get("model")
    model = next((m for m in models if model_id == m.get("id")), None)
    if model is None or model.get("model_type") != "depth_estimation":
        invalid("A declared depth-estimation model is required")
    if "depth_estimation" not in model.get("capabilities", ()):
        invalid("Model does not declare depth estimation")
    if set(parts) != {"image"}:
        invalid("Exactly one image upload is required")
    if payload.get("image") != {"part": "image"}:
        invalid("Image must reference the uploaded request part")
    if parts["image"].media_type not in {"image/png", "image/jpeg", "image/webp"}:
        invalid("Unsupported depth input image format")
    size = payload.get("input_size")
    if isinstance(size, str) and size.isascii() and size.isdecimal() and len(size) <= 4:
        size = int(size)
    if size is not None and (type(size) is not int or not 128 <= size <= 2048):
        invalid("input_size must be an integer between 128 and 2048")
    if payload.get("output_format", "npz") != "npz":
        invalid("Depth output format must be npz")
    result = {**payload, "output_format": "npz"}
    if size is not None:
        result["input_size"] = size
    return result
