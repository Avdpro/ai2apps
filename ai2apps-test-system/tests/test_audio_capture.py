import json
import pytest

from ai2apps_test import audio_capture
from ai2apps_test.audio_check import check_audio


def test_capture_id_and_path_boundary(tmp_path):
    with pytest.raises(ValueError):
        audio_capture.capture_dir(tmp_path, '../escape')
    outside = tmp_path / 'outside'
    outside.mkdir()
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'evidence').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='escapes'):
        audio_capture.capture_dir(run, 'a' * 32)


def test_start_rejects_terminal_and_invalid_duration(tmp_path):
    (tmp_path / 'state.json').write_text(json.dumps({'status': 'cancelled'}))
    with pytest.raises(ValueError, match='ended'):
        audio_capture.start(tmp_path, tmp_path, 'case')
    with pytest.raises(ValueError, match='duration'):
        audio_capture.start(tmp_path, tmp_path, 'case', 181)


def test_stop_completed_capture_is_idempotent(tmp_path):
    directory = audio_capture.capture_dir(tmp_path, 'a' * 32)
    directory.mkdir(parents=True)
    (directory / 'capture.json').write_text(json.dumps({'status': 'captured'}))
    result = audio_capture.stop(tmp_path, 'a' * 32)
    assert result['status'] == 'captured'
    assert not (directory / 'stop').exists()


def test_asr_rejects_incomplete_capture_before_loading_model(tmp_path):
    wav = tmp_path / 'output.wav'
    wav.write_bytes(b'not yet closed')
    (tmp_path / 'capture.json').write_text(json.dumps({'status': 'recording'}))
    with pytest.raises(ValueError, match='incomplete'):
        check_audio(tmp_path, wav, tmp_path, 'hello')
