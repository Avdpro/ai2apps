"""Depth Anything V2 Large: relative inverse depth, not Img2Img."""
from package_adapter import DepthAdapter


class Adapter(DepthAdapter):
    family = "da"
    filename = "da-large.safetensors"


def create_adapter(context):
    return Adapter(context)
