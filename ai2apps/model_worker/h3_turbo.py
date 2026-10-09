"""Apply the pinned official LightX2V 4/8-step 768p recipes to an H3 base graph."""
from copy import deepcopy

LORA_4STEP = 'minimax_h3_fl2v_turbo_4step_v1.2_768p_comfyui_bf16.safetensors'
LORA_8STEP = 'minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors'


def _apply_lightx2v(graph, *, lora, steps):
    result=deepcopy(graph)
    if result.get('3',{}).get('class_type')!='UNETLoader':
        raise ValueError('Expected pinned H3 UNET loader')
    if result['3']['inputs'].get('unet_name')!='minimax_h3_fl2va_pruned_int8_convrot.safetensors':
        raise ValueError('This Turbo recipe requires the FL2VA base')
    expected={'8':'KSamplerSelect','9':'BasicScheduler','10':'BasicGuider'}
    for key,node_type in expected.items():
        if result.get(key,{}).get('class_type')!=node_type:
            raise ValueError('H3 graph contract changed: '+key)
    if 'turbo_lora' in result or 'turbo_shift' in result:
        raise ValueError('Turbo graph already patched')
    for key in ('9','10'):
        if result[key]['inputs'].get('model')!=['3',0]:
            raise ValueError('Expected unmodified model edge')
        result[key]['inputs']['model']=['turbo_shift',0]
    result['turbo_lora']={'class_type':'LoraLoaderModelOnly','inputs':{
        'model':['3',0],'lora_name':lora,'strength_model':1.0}}
    result['turbo_shift']={'class_type':'MiniMaxH3SigmaShift','inputs':{
        'model':['turbo_lora',0],'shift_video':6.0,'shift_audio':3.0}}
    result['8']['inputs']['sampler_name']='euler'
    result['9']['inputs'].update(steps=steps,scheduler='simple',denoise=1.0)
    return result


def apply_lightx2v_8step(graph):
    return _apply_lightx2v(graph, lora=LORA_8STEP, steps=8)


def apply_lightx2v_4step(graph):
    # Owner release announcement: huggingface.co/lightx2v/Minimax-h3-Turbo/discussions/52
    return _apply_lightx2v(graph, lora=LORA_4STEP, steps=4)
