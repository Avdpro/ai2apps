"""Compare the CUDA bridge against the actual checked-in Mac schedule source."""
import ast
from pathlib import Path
import sys
import textwrap

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'spark'))
from cuda_ace_schedule import mac_timesteps
from patch_ace_step_schedule import patch_model


def test_all_public_step_counts_match_mac_source():
    source = (ROOT/'packages/ai2apps-model-ace-step-mlx/src/vendor/mlx_audio/tts/models/ace_step/ace_step.py').read_text()
    start = source.index('        SHIFT_TIMESTEPS = {')
    end = source.index('        if attention_mask is None:', start)
    code = compile(textwrap.dedent(source[start:end]), '<Mac schedule>', 'exec')
    for steps in range(1, 101):
        namespace = {'fix_nfe': steps, 'shift': 3.0}
        exec(code, namespace)
        assert np.array_equal(mac_timesteps(steps), namespace['t_schedule_list'])


def test_patched_cuda_branch_preserves_count_and_values():
    source = (ROOT/'experiments/music_mlx/vendor/ACE-Step-1.5/acestep/models/turbo/modeling_acestep_v15_turbo.py').read_bytes()
    patched = patch_model(source).decode()
    ast.parse(patched)
    start = patched.index('        if timesteps is not None:', patched.index('# Determine the timestep schedule'))
    end = patched.index('        # Variable-step schedule:', start)
    code = compile(textwrap.dedent(patched[start:end]), '<patched CUDA schedule>', 'exec')
    class Torch:
        Tensor = type(None)
    for steps in (1, 8, 16, 100):
        values = mac_timesteps(steps)
        namespace = {'timesteps': values, 'torch': Torch}
        exec(code, namespace)
        assert namespace['t_schedule_list'] == values
    with pytest.raises(ValueError):
        patch_model(source + b'\n')


@pytest.mark.parametrize('value', [0, 101, True, 8.0, '8'])
def test_invalid_steps_rejected(value):
    with pytest.raises(ValueError):
        mac_timesteps(value)


def test_official_schedule_matches_pinned_default_branch():
    from cuda_ace_schedule import official_timesteps
    source=(ROOT/'experiments/music_mlx/vendor/ACE-Step-1.5/acestep/models/turbo/modeling_acestep_v15_turbo.py').read_text()
    start=source.index('        if t_schedule_list is None and infer_steps is not None')
    end=source.index('\n        if t_schedule_list is None:',start)
    code=compile(textwrap.dedent(source[start:end]),'<official variable schedule>','exec')
    for steps in range(1,21):
        namespace={'t_schedule_list':None,'infer_steps':steps,'shift':1.0}
        exec(code,namespace)
        assert official_timesteps(steps)==namespace['t_schedule_list']
    for steps in (21,100):
        values=official_timesteps(steps)
        assert len(values)==steps and values[0]==1 and values[-1]>0
        assert all(a>b for a,b in zip(values,values[1:]))
    for value in (0,101,True,8.0,'8'):
        with pytest.raises(ValueError):official_timesteps(value)
