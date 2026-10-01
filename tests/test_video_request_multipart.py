from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

SERVER_SOURCE = Path(__file__).parents[1] / "omlx" / "server.py"


def test_video_create_request_keeps_multipart_uploads():
    app = FastAPI()

    @app.post("/probe")
    async def probe(request: Request):
        payload = None
        uploads = {}
        async with request.form() as form:
            for name, value in form.multi_items():
                if isinstance(value, UploadFile):
                    uploads[name] = (
                        value.filename,
                        await value.read(),
                        value.content_type,
                    )
                elif name == "request":
                    payload = json.loads(str(value))
        return {
            "payload": payload,
            "uploads": {
                name: {
                    "filename": upload[0],
                    "content": upload[1].decode(),
                    "mediaType": upload[2],
                }
                for name, upload in uploads.items()
            },
        }

    payload = {
        "model": "example/image-to-video",
        "content": [
            {"type": "text", "role": "prompt", "text": "animate"},
            {
                "type": "image_url",
                "role": "first_frame",
                "image_url": {"url": "multipart://first_frame"},
            },
        ],
    }
    response = TestClient(app).post(
        "/probe",
        files={
            "request": (None, json.dumps(payload), "application/json"),
            "first_frame": ("start.png", b"image-bytes", "image/png"),
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "payload": payload,
        "uploads": {
            "first_frame": {
                "filename": "start.png",
                "content": "image-bytes",
                "mediaType": "image/png",
            }
        },
    }


def test_video_host_checks_the_starlette_upload_type():
    source = SERVER_SOURCE.read_text()

    assert "from starlette.datastructures import UploadFile" in source
    assert "    UploadFile,\n" not in source.split("from fastapi import (", 1)[1].split(")", 1)[0]
