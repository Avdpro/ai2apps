# SPDX-License-Identifier: Apache-2.0
"""Versioned, model-independent continuous audio Worker contract."""
from dataclasses import dataclass
import base64
import binascii
import math
import struct

PROTOCOL = 'ai2apps-audio-duplex/v1'
PATH = '/v1/audio/realtime'
MAX_CONTROL_BYTES = 4 * 1024 * 1024


def validate_pcm(pcm, samples):
    if not isinstance(pcm, bytes) or len(pcm) != samples * 4:
        raise ValueError('Invalid mono f32le PCM frame size')
    if any(not math.isfinite(v[0]) or abs(v[0]) > 1 for v in struct.iter_unpack('<f', pcm)):
        raise ValueError('PCM samples must be finite and within [-1, 1]')


def validate_duplex(value):
    fields = {'protocol', 'mode', 'sample_rate', 'frame_samples', 'text_output', 'text_input',
              'async_result_injection', 'response_cancel', 'voice_reference', 'maximum_session_seconds'}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('An explicit complete duplex declaration is required')
    if value['protocol'] != PROTOCOL or value['mode'] not in ('native', 'pipeline'):
        raise ValueError('Unsupported duplex protocol or mode')
    for key, lower, upper in (('sample_rate', 8000, 48000), ('frame_samples', 80, 48000),
                              ('maximum_session_seconds', 1, 3600)):
        if type(value[key]) is not int or not lower <= value[key] <= upper:
            raise ValueError('Invalid duplex audio geometry or budget')
    if not .01 <= value['frame_samples'] / value['sample_rate'] <= 1:
        raise ValueError('Duplex frames must span 10ms to 1s')
    for key in fields - {'protocol', 'mode', 'sample_rate', 'frame_samples', 'maximum_session_seconds'}:
        if type(value[key]) is not bool:
            raise ValueError('Duplex feature flags must be explicit booleans')
    return dict(value)


def parse_start(message, declaration):
    fields = {'type', 'protocol', 'model', 'system_prompt', 'reference_audio', 'sample_rate', 'seed', 'max_frames'}
    if not isinstance(message, dict) or set(message) - fields:
        raise ValueError('Unknown session start fields')
    if message.get('type') != 'session.start' or message.get('protocol') != PROTOCOL:
        raise ValueError('Unsupported session start protocol')
    if message.get('sample_rate') != declaration['sample_rate']:
        raise ValueError('Input sample rate does not match the selected model')
    prompt = message.get('system_prompt', '')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16000:
        raise ValueError('A bounded character prompt is required')
    seed = message.get('seed', 0)
    maximum = math.floor(declaration['maximum_session_seconds'] * declaration['sample_rate'] / declaration['frame_samples'])
    frames = message.get('max_frames', maximum)
    if type(seed) is not int or not 0 <= seed < 2**32 or type(frames) is not int or not 1 <= frames <= maximum:
        raise ValueError('Invalid session seed or frame budget')
    reference = message.get('reference_audio')
    if declaration['voice_reference']:
        if not isinstance(reference, str) or len(reference) > MAX_CONTROL_BYTES - 32000:
            raise ValueError('A bounded PCM voice reference is required')
        try:
            reference = base64.b64decode(reference, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError('Invalid reference PCM encoding') from None
        if not 3 * declaration['sample_rate'] * 4 <= len(reference) <= 30 * declaration['sample_rate'] * 4 or len(reference) % 4:
            raise ValueError('Voice reference must be 3 to 30 seconds of mono f32le PCM')
    elif reference is not None:
        raise ValueError('Selected model does not accept a voice reference')
    return {'system_prompt': prompt, 'reference_pcm': reference, 'seed': seed, 'max_frames': frames}


@dataclass(frozen=True)
class AudioDuplexFrame:
    session_id: str
    index: int
    sample_start: int
    playback_epoch: int
    pcm: bytes
    text: str = ''
    done: bool = False
    suppressed: bool = False


def frame_event(frame, declaration):
    if not isinstance(frame, AudioDuplexFrame) or len(frame.pcm) != declaration['frame_samples'] * 4:
        raise RuntimeError('Invalid model duplex frame')
    validate_pcm(frame.pcm, declaration['frame_samples'])
    if not isinstance(frame.session_id, str) or not 1 <= len(frame.session_id) <= 200 or type(frame.playback_epoch) is not int or frame.playback_epoch < 0:
        raise RuntimeError('Invalid model session identity')
    if type(frame.index) is not int or frame.index < 0 or frame.sample_start != frame.index * declaration['frame_samples']:
        raise RuntimeError('Invalid model frame alignment')
    if not isinstance(frame.text, str) or len(frame.text) > 4096:
        raise RuntimeError('Invalid model text frame')
    return {'type': 'output.frame', 'session_id': frame.session_id, 'index': frame.index,
            'sample_start': frame.sample_start, 'playback_epoch': frame.playback_epoch,
            'audio': base64.b64encode(frame.pcm).decode('ascii'), 'text': frame.text,
            'done': frame.done, 'suppressed': frame.suppressed}
