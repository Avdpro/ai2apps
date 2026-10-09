"""Music protocol bounds and authenticated Worker transport regression."""
import pytest
from fastapi.testclient import TestClient

from ai2apps.model_worker.audio_generation import validate_audio_generation
from ai2apps.model_worker.protocol import ModelWorkerError
from ai2apps.model_worker.server import create_app
from ai2apps.packages.supervisor import ManagedServiceSupervisor
from test_ai2apps_model_worker import _manifest, _worker_files

BASE = {"model": "example.worker/chat", "task": "music", "prompt": "Piano", "duration": 30}

@pytest.mark.parametrize("change", [
    {"task": []}, {"model": []}, {"prompt": " "}, {"duration": float("nan")},
    {"duration": True}, {"duration": 601}, {"seed": -1}, {"steps": 0},
    {"stream": True}, {"output_format": "mp3"}, {"task": "sound_effects", "lyrics": "Hi"},
    {"output_path": "/tmp/file"}, {"language": "../../etc"},
])
def test_invalid_generation(change):
    with pytest.raises(ModelWorkerError):
        validate_audio_generation(BASE | change)

def test_defaults_and_reference_rejection():
    result = validate_audio_generation(BASE)
    assert result["seed"] == 42 and result["output_format"] == "wav"
    with pytest.raises(ModelWorkerError):
        validate_audio_generation(BASE, has_parts=True)

def test_authenticated_route(tmp_path):
    package, data = _worker_files(tmp_path)
    _, config = ManagedServiceSupervisor._model_worker_command(package, data, _manifest(), 9123)
    with TestClient(create_app(config, token="music-test-token")) as client:
        route = "/v1/audio/generations"
        assert client.post(route, json=BASE).status_code == 401
        headers = {"Authorization": "Bearer music-test-token"}
        result = client.post(route, headers=headers, json=BASE)
        assert result.status_code == 200
        assert result.json()["operation"] == "audio_generate"
        assert client.post(route, headers=headers, json=BASE | {"duration": -1}).status_code == 400
        # Existing TTS transport remains independent of the new contract.
        assert client.post("/v1/audio/speech", headers=headers, json={"model": "example.worker/chat", "input": "Hello"}).status_code == 200


def test_generation_wav_artifact_progress_and_cleanup(tmp_path):
    import io
    import wave

    package, data = _worker_files(tmp_path)
    adapter = package / 'src/adapter.py'
    source = adapter.read_text().replace('if request.payload.get("artifact"):', 'if request.operation == "audio_generate":').replace('output = request.output_root / "avatar.mp4"', 'output = request.output_root / "music.wav"').replace('output.write_bytes(b"fake-mp4")', '''import wave
            with wave.open(str(output), "wb") as wav:
                wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                wav.writeframes(b"\\x01\\x00" * 8000)''').replace('ModelWorkerArtifact(output, "video/mp4", "avatar.mp4")', 'ModelWorkerArtifact(output, "audio/wav", "music.wav")')
    adapter.write_text(source)
    _, config = ManagedServiceSupervisor._model_worker_command(package, data, _manifest(), 9123)
    headers = {"Authorization": "Bearer music-test-token", "X-Request-ID": "generation-artifact"}
    with TestClient(create_app(config, token="music-test-token")) as client:
        result = client.post('/v1/audio/generations', headers=headers, json=BASE)
        assert result.status_code == 200
        assert result.headers['content-type'] == 'audio/wav'
        with wave.open(io.BytesIO(result.content)) as wav:
            assert wav.getnframes() == 8000
        status = client.get('/v1/requests/generation-artifact', headers=headers).json()
        assert status['status'] == 'succeeded'
        assert status['progress']['phase'] == 'encode'
        assert not list(data.rglob('music.wav'))


WORKFLOW = {"schema": "ai2apps.audio-generation/v2", "model": "example.worker/chat",
            "task": "music", "prompt": "Piano", "duration_mode": "auto"}

@pytest.mark.parametrize("change", [
    {"schema": []}, {"schema": "unknown"}, {"duration_mode": []},
    {"duration_mode": "unknown"}, {"duration": 30}, {"task": "sound_effects"},
    {"generation": []}, {"generation": {"path": "/tmp/score"}},
    {"generation": {"planning_mode": []}}, {"generation": {"planning_mode": "other"}},
    {"generation": {"abc": ""}}, {"generation": {"abc": "a" * 131073}},
    {"generation": {"abc": "X:1", "planning_mode": "off"}},
    {"generation": {"max_semantic_tokens": True}},
    {"generation": {"max_semantic_tokens": 15001}},
    {"generation": {"max_abc_tokens": 0}},
    {"generation": {"guidance_scale": float("inf")}},
    {"generation": {"guidance_scale": True}},
])
def test_invalid_workflow(change):
    with pytest.raises(ModelWorkerError):
        validate_audio_generation(WORKFLOW | change)


def test_versioned_workflow_roundtrip(tmp_path):
    payload = WORKFLOW | {"generation": {"planning_mode": "melody", "abc": "X:1\nK:C\nCDEF|",
                                       "max_semantic_tokens": 3000, "guidance_scale": 1.01}}
    checked = validate_audio_generation(payload)
    assert "duration" not in checked and checked["steps"] == 32
    assert checked["generation"] == payload["generation"]
    assert validate_audio_generation(BASE)["steps"] == 8
    with pytest.raises(ModelWorkerError):
        validate_audio_generation(BASE | {"generation": {}})
    package, data = _worker_files(tmp_path)
    _, config = ManagedServiceSupervisor._model_worker_command(package, data, _manifest(), 9123)
    with TestClient(create_app(config, token="workflow-test")) as client:
        response = client.post("/v1/audio/generations", json=payload,
                               headers={"Authorization": "Bearer workflow-test"})
        assert response.status_code == 200
        assert response.json()["operation"] == "audio_generate"
