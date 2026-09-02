"""AI2Apps Z-Image pipeline with guarded Metal block fusions."""

from __future__ import annotations

from mflux.models.z_image.variants.z_image import ZImage

from z_image_fused_rms import install


class OptimizedZImage(ZImage):
    """Install the audited Metal path before constructing the mflux graph."""

    def __init__(self, *args, **kwargs) -> None:
        self._ai2apps_metal_fusions_enabled = install()
        super().__init__(*args, **kwargs)

    def ai2apps_optimization_stats(self) -> dict[str, bool | str]:
        return {
            "metal_rms_adaln_fusions_enabled": self._ai2apps_metal_fusions_enabled,
            "step_synchronization": "every-step",
            "quantization_group_size": "64",
        }
