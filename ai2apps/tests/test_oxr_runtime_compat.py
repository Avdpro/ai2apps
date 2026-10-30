"""OXR compatibility remains model-scoped and preserves shared model behavior."""
import json

def test_oxr_discovery_requires_vision_config(tmp_path):
 from omlx.model_discovery import detect_model_type
 (tmp_path/'config.json').write_text(json.dumps({'model_type':'oxr','vit_config':{'hidden_size':1152}}))
 assert detect_model_type(tmp_path)=='vlm'

def test_registration_is_idempotent_and_preserves_other_formats():
 from mlx_vlm import prompt_utils
 before=dict(prompt_utils.MODEL_CONFIG)
 from omlx.patches.mlx_vlm_oxr_compat import apply_mlx_vlm_oxr_compat_patch
 apply_mlx_vlm_oxr_compat_patch()
 assert apply_mlx_vlm_oxr_compat_patch() is False
 assert all(prompt_utils.MODEL_CONFIG[k]==v for k,v in before.items())
 assert prompt_utils.MODEL_CONFIG['oxr']==prompt_utils.MessageFormat.LIST_WITH_IMAGE_FIRST

def test_config_uses_original_checkpoint_keys():
 from omlx.patches.mlx_vlm_oxr_compat import apply_mlx_vlm_oxr_compat_patch
 apply_mlx_vlm_oxr_compat_patch()
 from mlx_vlm.models.oxr.config import ModelConfig
 config=ModelConfig.from_dict({'llm_config':{'model_type':'qwen3','hidden_size':1024,'num_hidden_layers':1,'intermediate_size':2048,'num_attention_heads':8,'rms_norm_eps':1e-6,'vocab_size':128,'num_key_value_heads':4,'max_position_embeddings':8192,'rope_theta':1000000,'head_dim':128,'tie_word_embeddings':True},'vit_config':{'patch_size':16}})
 assert config.text_config.hidden_size==1024
 assert config.vision_config.patch_size==16
 assert config.model_type=='oxr'

def test_processor_bounds_and_alpha_compositing():
 from omlx.patches.mlx_vlm_oxr_compat import apply_mlx_vlm_oxr_compat_patch
 apply_mlx_vlm_oxr_compat_patch()
 from mlx_vlm.models.oxr.processing_oxr import smart_resize,_to_rgb,MIN_PIXELS,MAX_PIXELS
 from PIL import Image
 for h,w in [(6000,8000),(500,1200),(16,500),(1600,1200)]:
  rh,rw=smart_resize(h,w,32,MIN_PIXELS,MAX_PIXELS)
  assert rh%32==rw%32==0 and rh>0 and rw>0
 assert _to_rgb(Image.new('RGBA',(1,1),(0,0,0,0))).getpixel((0,0))==(255,255,255)
