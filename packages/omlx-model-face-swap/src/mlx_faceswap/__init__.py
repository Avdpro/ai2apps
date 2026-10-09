"""Shared face media helpers; accelerator modules load only when requested."""
__all__ = ["MLXOnnxGraph"]

def __getattr__(name):
    if name == "MLXOnnxGraph":
        from .onnx_mlx import MLXOnnxGraph
        return MLXOnnxGraph
    raise AttributeError(name)
