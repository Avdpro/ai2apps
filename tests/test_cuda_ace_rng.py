"""Request seed governs planning without consuming the caller's RNG stream."""
import sys
from pathlib import Path
import pytest
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_ace_engine import planner_rng

@pytest.mark.parametrize('fail',[False,True])
def test_planner_rng_repeatability_and_restoration(fail):
    before=torch.random.get_rng_state().clone()
    outputs=[]
    for _ in range(2):
        try:
            with planner_rng(42):
                outputs.append(torch.multinomial(torch.ones(100),20))
                if fail:raise RuntimeError('cancelled')
        except RuntimeError as exc:assert str(exc)=='cancelled'
        assert torch.equal(before,torch.random.get_rng_state())
    assert torch.equal(*outputs)
    with planner_rng(43):other=torch.multinomial(torch.ones(100),20)
    assert not torch.equal(other,outputs[0])


@pytest.mark.parametrize('fail',[False,True])
def test_deterministic_inference_restores_backend_flags(fail):
    from cuda_ace_engine import deterministic_inference
    def flags():return (torch.are_deterministic_algorithms_enabled(),torch.is_deterministic_algorithms_warn_only_enabled(),torch.backends.cudnn.benchmark,torch.backends.cudnn.deterministic)
    before=flags();rng=torch.random.get_rng_state().clone()
    try:
        with deterministic_inference(42):
            assert flags()==(True,False,False,True)
            torch.rand(3)
            if fail:raise RuntimeError('cancelled')
    except RuntimeError as exc:assert str(exc)=='cancelled'
    assert flags()==before and torch.equal(rng,torch.random.get_rng_state())
