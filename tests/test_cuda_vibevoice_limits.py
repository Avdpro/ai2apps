import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('vibevoice_limits',Path(__file__).resolve().parents[1]/'spark/cuda_vibevoice_limits.py')
limits=importlib.util.module_from_spec(spec);spec.loader.exec_module(limits)

def test_official_default_uses_remaining_context_not_4096():
    assert limits.generation_budget(2000,316)==7876

def test_text_is_not_counted_twice_in_shared_new_token_budget():
    assert limits.generation_budget(2000,316,6000)==6000

@pytest.mark.parametrize('text,prefix,budget',[(6000,316,6000),(1,8192,None),(1,316,7877),(1,316,True),(0,316,None)])
def test_impossible_or_invalid_context_is_rejected(text,prefix,budget):
    with pytest.raises(ValueError):limits.generation_budget(text,prefix,budget)
