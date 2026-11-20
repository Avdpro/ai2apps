"""VGGT-Omega 1B 512 single-image geometry, not multi-view reconstruction."""
from package_adapter import DepthAdapter


class Adapter(DepthAdapter):
    family = "vggt"
    filename = "vggt.safetensors"


def create_adapter(context):
    return Adapter(context)
