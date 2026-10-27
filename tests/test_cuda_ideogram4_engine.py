import importlib.util,sys,types
from pathlib import Path
import pytest
import torch
from PIL import Image
spec=importlib.util.spec_from_file_location('ideogram_engine',Path(__file__).resolve().parents[1]/'spark/cuda_ideogram4_engine.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
@pytest.fixture
def engine(monkeypatch):
 verifier=types.ModuleType('ideogram4.caption_verifier');verifier.CaptionVerifier=lambda:types.SimpleNamespace(verify=lambda _:[]);monkeypatch.setitem(sys.modules,'ideogram4.caption_verifier',verifier)
 class Pipeline:
  def __init__(self):
   self.conditional_transformer=torch.nn.Identity();self.unconditional_transformer=torch.nn.Identity();self.autoencoder=types.SimpleNamespace(decoder=torch.nn.Identity());self.text_encoder=types.SimpleNamespace(language_model=types.SimpleNamespace(layers=[torch.nn.Identity()]))
  def __call__(self,prompt,**kw):
   x=torch.ones(1)
   for _ in range(kw['num_steps']):x=self.unconditional_transformer(self.conditional_transformer(x))
   return [Image.new('RGB',(kw['width'],kw['height']))]
 e=module.CudaIdeogram4Engine('/unused','/unused');e.pipeline=Pipeline();return e

def test_cancel_removes_all_hooks_and_never_publishes_partial(engine,tmp_path):
 def fail(*_):raise RuntimeError('cancel at native boundary')
 with pytest.raises(RuntimeError,match='cancel at native boundary') as held:engine.generate('{}',tmp_path/'out.png',width=256,height=256,steps=2,progress=fail)
 assert not list(tmp_path.iterdir())
 modules=[engine.pipeline.conditional_transformer,engine.pipeline.unconditional_transformer,engine.pipeline.autoencoder.decoder,*engine.pipeline.text_encoder.language_model.layers]
 assert all(not m._forward_pre_hooks and not m._forward_hooks for m in modules)
 assert held.value.__notes__
 # Same engine can generate after a cancelled request.
 result=engine.generate('{}',tmp_path/'recovered.png',width=256,height=256,steps=2)
 assert result['steps']==2 and (tmp_path/'recovered.png').exists()

def test_existing_output_is_never_overwritten(engine,tmp_path):
 target=tmp_path/'out.png';target.write_bytes(b'preserve')
 with pytest.raises(FileExistsError):engine.generate('{}',target,width=256,height=256)
 assert target.read_bytes()==b'preserve'


def test_named_sampler_uses_pinned_official_settings(monkeypatch):
 import ast
 # Load the exact pinned upstream constants, without its GPU package initializer.
 source=Path(__file__).resolve().parent/'fixtures/ideogram4/sampler_configs.py'
 tree=ast.parse(source.read_text());ns={'SamplerParameters':types.SimpleNamespace}
 exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.AnnAssign)],type_ignores=[]),str(source),'exec'),ns)
 presets=types.ModuleType('ideogram4.sampler_configs');presets.PRESETS=ns['PRESETS'];monkeypatch.setitem(sys.modules,'ideogram4.sampler_configs',presets)
 name,settings=module.sampler_settings(20)
 assert name=='V4_DEFAULT_20' and settings['mu']==0 and settings['guidance_schedule'].count(3.)==2
 name,settings=module.sampler_settings(48)
 assert name=='V4_QUALITY_48' and settings['std']==1.5 and settings['guidance_schedule'].count(3.)==3
 name,settings=module.sampler_settings(12)
 assert name=='V4_TURBO_12' and settings['mu']==.5 and settings['guidance_schedule'].count(3.)==1
 assert module.sampler_settings(8)[0]=='custom_turbo_schedule'
