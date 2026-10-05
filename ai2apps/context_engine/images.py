"""Immutable, explicit image omission projection, ported from DeepSeek image-offload.

OpenAI image_url blocks are replaced by visible source references, never deleted
from durable records. Input user/tool images only; assistant output stays intact.
"""

import hashlib

from .core import Node, canonical


def image_indexes(node):
    body = node.body
    if body.get("role") not in {"user", "tool"} or not isinstance(
        body.get("content"), list
    ):
        return ()
    return tuple(
        i for i, part in enumerate(body["content"]) if part.get("type") == "image_url"
    )


def offload_images(node, indexes, reference):
    if not indexes or tuple(sorted(set(indexes))) != tuple(indexes):
        raise ValueError("Image indexes must be nonempty, unique and increasing")
    eligible = image_indexes(node)
    if any(i not in eligible for i in indexes):
        raise ValueError("Image is missing, already offloaded, or not an input image")
    body = node.body
    for index in indexes:
        image = body["content"][index]
        body["content"][index] = {
            "type": "text",
            "text": canonical(
                {
                    "type": "ai2apps.image-offload/v1",
                    "notice": "This original image is omitted from this request. Do not infer unseen image content.",
                    "source": reference,
                    "part_index": index,
                    "sha256": hashlib.sha256(canonical(image).encode()).hexdigest(),
                }
            ),
        }
    return Node.message(node.id, body, pinned=node.pinned)


def oldest_images(surface, count=1):
    if type(count) is not int or count <= 0:
        raise ValueError("Positive image count required")
    selected = []
    for node in surface.nodes:
        if node.pinned:
            continue
        indexes = image_indexes(node)[:count]
        if indexes:
            selected.append((node, indexes))
            count -= len(indexes)
        if not count:
            break
    return tuple(selected)
