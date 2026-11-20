from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from patch_yue2_cuda_stream import patch_source


def test_only_pinned_graph_source_can_be_patched():
    source=(Path(__file__).resolve().parents[1]/'experiments/yue2_mlx/upstream/src/yue2/cuda_graph.py').read_bytes()
    patched=patch_source(source)
    compile(patched,'patched_graph','exec')
    assert b'warmup = _warmup_stream(self.device)' in patched
    with pytest.raises(ValueError):patch_source(source+b'\n')
    with pytest.raises(ValueError):patch_source(patched)
