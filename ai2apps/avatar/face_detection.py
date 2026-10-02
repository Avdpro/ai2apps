"""Use macOS Vision for Host portrait framing without a checkpoint download."""

import ctypes as c
import io
import sys

from PIL import Image


class _Point(c.Structure):
    _fields_ = [("x", c.c_double), ("y", c.c_double)]


class _Size(c.Structure):
    _fields_ = [("width", c.c_double), ("height", c.c_double)]


class _Rect(c.Structure):
    _fields_ = [("origin", _Point), ("size", _Size)]


def detect_faces(rgb):
    """Return pixel rectangles (left, top, width, height), largest face first."""
    if sys.platform != "darwin":
        raise ValueError("Automatic portrait framing currently requires macOS")
    objc = c.CDLL("/usr/lib/libobjc.A.dylib")
    for name in ("Foundation", "Vision"):
        c.CDLL(f"/System/Library/Frameworks/{name}.framework/{name}")
    objc.objc_getClass.argtypes = [c.c_char_p]
    objc.objc_getClass.restype = c.c_void_p
    objc.sel_registerName.argtypes = [c.c_char_p]
    objc.sel_registerName.restype = c.c_void_p

    def cls(name):
        return objc.objc_getClass(name.encode())

    def send(obj, selector, result=c.c_void_p, types=(), values=()):
        function = c.CFUNCTYPE(result, c.c_void_p, c.c_void_p, *types)(
            ("objc_msgSend", objc)
        )
        return function(obj, objc.sel_registerName(selector.encode()), *values)

    pool = send(send(cls("NSAutoreleasePool"), "alloc"), "init")
    handler = request = None
    try:
        buffer = io.BytesIO()
        Image.fromarray(rgb).save(buffer, format="PNG")
        content = buffer.getvalue()
        data = send(
            cls("NSData"),
            "dataWithBytes:length:",
            types=(c.c_char_p, c.c_ulong),
            values=(content, len(content)),
        )
        handler = send(
            send(cls("VNImageRequestHandler"), "alloc"),
            "initWithData:options:",
            types=(c.c_void_p, c.c_void_p),
            values=(data, send(cls("NSDictionary"), "dictionary")),
        )
        request = send(send(cls("VNDetectFaceRectanglesRequest"), "alloc"), "init")
        requests = send(
            cls("NSArray"), "arrayWithObject:", types=(c.c_void_p,), values=(request,)
        )
        error = c.c_void_p()
        if not send(
            handler,
            "performRequests:error:",
            c.c_bool,
            (c.c_void_p, c.POINTER(c.c_void_p)),
            (requests, c.byref(error)),
        ):
            raise ValueError(
                "System face detection failed; try a clear front-facing portrait"
            )
        observations = send(request, "results")
        count = send(observations, "count", c.c_ulong) if observations else 0
        height, width = rgb.shape[:2]
        faces = []
        for index in range(count):
            observation = send(
                observations, "objectAtIndex:", types=(c.c_ulong,), values=(index,)
            )
            box = send(observation, "boundingBox", _Rect)
            faces.append(
                (
                    box.origin.x * width,
                    (1 - box.origin.y - box.size.height) * height,
                    box.size.width * width,
                    box.size.height * height,
                )
            )
        return sorted(faces, key=lambda b: b[2] * b[3], reverse=True)
    finally:
        if request:
            send(request, "release", None)
        if handler:
            send(handler, "release", None)
        send(pool, "drain", None)
