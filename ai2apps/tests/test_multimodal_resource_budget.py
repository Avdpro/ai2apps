import base64,io
from PIL import Image
from ai2apps.worker_resources import estimate_request_transient_bytes,_chat_input_budget,MIB,GIB

def payload(raw):
 return {'max_tokens':4096,'messages':[{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(raw).decode()}},{'type':'text','text':'Read the page'}]}]}

def test_png_transport_size_does_not_become_text_context():
 image=Image.new('RGB',(1200,2600),'white');a=io.BytesIO();b=io.BytesIO()
 image.save(a,format='PNG',compress_level=9);image.save(b,format='PNG',compress_level=0)
 small=estimate_request_transient_bytes('chat_completions',payload(a.getvalue()))
 large=estimate_request_transient_bytes('chat_completions',payload(b.getvalue()))
 # Same decoded geometry => same vision context, only transport buffer differs.
 assert large-small==4*((len(base64.b64encode(b.getvalue()))*3//4)-(len(base64.b64encode(a.getvalue()))*3//4))
 assert large<10*GIB

def test_text_still_consumes_context_and_unknown_image_is_conservative():
 assert estimate_request_transient_bytes('chat_completions',{'messages':'x'*524288})==32*GIB
 assert _chat_input_budget([{'type':'image_url','image_url':{'url':'https://example.invalid/image.png'}}])==(0,16384,0)
 assert _chat_input_budget([{'type':'image_url','image_url':{'url':'data:image/png;base64,not-valid'}}])[1]==16384

def test_multiple_images_and_responses_form_accumulate():
 image=Image.new('RGB',(100,100));out=io.BytesIO();image.save(out,format='PNG')
 content=payload(out.getvalue())['messages'][0]['content']
 assert _chat_input_budget(content*2)==tuple(n*2 for n in _chat_input_budget(content))
 assert estimate_request_transient_bytes('responses',{'input':content})>=512*MIB

def test_base64_overestimate_blocks_idle_host_but_geometry_is_admitted():
 from ai2apps.worker_resources import WorkerResourceManager,SystemMemorySnapshot
 memory=SystemMemorySnapshot(128*GIB,52*GIB,76*GIB,'ok')
 manager=WorkerResourceManager(sampler=lambda:memory)
 # Observed Host: 3 GiB resident + 32 GiB mistaken token estimate + 19.2 GiB safety.
 assert manager.try_reserve('old','arbitrary.provider',32*GIB,3*GIB) is None
 assert manager.try_reserve('fixed','arbitrary.provider',4*GIB,3*GIB) is not None
