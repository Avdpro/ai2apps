"""Public package surface for EchoMimicV3 MLX."""

from .config import GenerationRequest, ReferenceConfiguration
from .memory_profiles import MemoryProfile, select_memory_profile
from .pipeline import (
    AvatarPipeline,
    CancellationToken,
    EncodedConditions,
    GenerationCancelled,
    GenerationResult,
    PipelineModelPaths,
)
from .service import AvatarJobRequest, AvatarJobService, JobSnapshot, JobStatus

__all__ = [
    "AvatarJobRequest",
    "AvatarJobService",
    "AvatarPipeline",
    "CancellationToken",
    "EncodedConditions",
    "GenerationCancelled",
    "GenerationRequest",
    "GenerationResult",
    "JobSnapshot",
    "JobStatus",
    "MemoryProfile",
    "PipelineModelPaths",
    "ReferenceConfiguration",
    "select_memory_profile",
]
__version__ = "0.0.1"
