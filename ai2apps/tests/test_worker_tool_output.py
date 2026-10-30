"""Cross-template Worker output normalization, independent of model names."""
import json
from types import SimpleNamespace
import pytest
from ai2apps.model_worker.tool_output import ToolOutput
from ai2apps.model_worker.protocol import ModelWorkerError
from ai2apps.model_worker.omlx_chat import OmlxChatAdapter

TOOLS = [{'type':'function','function':{'name':'inspect_item','parameters':{
 'type':'object','properties':{'label':{'type':'string'},'count':{'type':'integer'}},
 'required':['label'],'additionalProperties':False}}}]
XML='<tool_call><function=inspect_item><parameter=label>熊猫</parameter><parameter=count>2</parameter></function></tool_call>'
JSON='<tool_call>{"name":"inspect_item","arguments":{"label":"熊猫","count":2}}</tool_call>'

def parse(text, engine=None, size=1, native=None):
 p=ToolOutput(engine or SimpleNamespace(),TOOLS)
 visible=''.join(p.feed(text[i:i+size]) for i in range(0,len(text),size))
 tail,calls=p.finish(native);return visible+tail,calls

@pytest.mark.parametrize('text',[XML,JSON])
@pytest.mark.parametrize('size',[1,2,7,999])
def test_formats_and_arbitrary_chunk_boundaries(text,size):
 visible,calls=parse('Before '+text+' After',size=size)
 assert visible=='Before After'
 assert len(calls)==1
 assert calls[0]['function']['name']=='inspect_item'
 assert json.loads(calls[0]['function']['arguments'])=={'label':'熊猫','count':2}


def test_multiple_calls_native_duplicate_and_actual_tokenizer_protocol():
 assert len(parse(XML+JSON)[1])==2
 _,calls=parse(XML)
 assert len(parse(XML,native=calls)[1])==1
 tokenizer=SimpleNamespace(has_tool_calling=True,tool_call_start='@call:',tool_call_end='@end',
   tool_parser=lambda text,tools:{'name':'inspect_item','arguments':{'label':text}})
 text,calls=parse('@call:hello@end',SimpleNamespace(tokenizer=tokenizer))
 assert text=='' and json.loads(calls[0]['function']['arguments'])=={'label':'hello'}


def test_native_flat_call_and_glm_xml_and_deepseek_declared_protocol():
 native=[{'name':'inspect_item','arguments':'{"label":"native"}'}]
 assert json.loads(parse('',native=native)[1][0]['function']['arguments'])=={'label':'native'}
 glm='<tool_call>inspect_item<arg_key>label</arg_key><arg_value>GLM</arg_value></tool_call>'
 assert json.loads(parse(glm)[1][0]['function']['arguments'])=={'label':'GLM'}
 from omlx.patches.deepseek_v4 import tool_parser_v4 as ds
 tokenizer=SimpleNamespace(has_tool_calling=True,tool_call_start=ds.tool_call_start,
   tool_call_end=ds.tool_call_end,tool_parser=ds.parse_tool_call)
 text=ds.tool_call_start+'<｜DSML｜invoke name="inspect_item"><｜DSML｜parameter name="label" string="true">DS</｜DSML｜parameter></｜DSML｜invoke>'+ds.tool_call_end
 assert json.loads(parse(text,SimpleNamespace(tokenizer=tokenizer))[1][0]['function']['arguments'])=={'label':'DS'}


def test_schema_and_explicit_tool_choice_and_complex_arguments():
 p=ToolOutput(SimpleNamespace(),TOOLS,'required');p.feed('No call')
 with pytest.raises(ModelWorkerError):p.finish()
 p=ToolOutput(SimpleNamespace(),TOOLS,{'type':'function','function':{'name':'other'}});p.feed(XML)
 with pytest.raises(ModelWorkerError):p.finish()
 value='line one\\n"quoted" <tag> ```code```'
 call='<tool_call>'+json.dumps({'name':'inspect_item','arguments':{'label':value}},ensure_ascii=False)+'</tool_call>'
 assert json.loads(parse(call)[1][0]['function']['arguments'])['label']==value

@pytest.mark.parametrize('text',[XML[:-3],'<tool_call','<tool_cal','<tool_call>broken</tool_call>',XML+'<tool_call>broken</tool_call>',
 XML.replace('inspect_item','unknown'),XML.replace('>2<','>false<')])
def test_invalid_or_partial_calls_never_become_success(text):
 with pytest.raises(ModelWorkerError) as e:parse(text)
 assert e.value.code=='invalid_tool_call'

@pytest.mark.parametrize('text',['```xml\n'+XML+'\n```','Example: `'+XML+'`'])
def test_code_examples_do_not_execute(text):
 visible,calls=parse(text)
 assert visible==text and calls==[]


def test_no_tools_or_explicit_none_preserves_literal_markup():
 for tools,choice in [([],None),(TOOLS,'none')]:
  p=ToolOutput(SimpleNamespace(),tools,choice)
  assert p.feed(XML)==XML and p.finish()==('',[])

@pytest.mark.asyncio
@pytest.mark.parametrize('text',[XML,JSON])
@pytest.mark.parametrize('stream',[False,True])
async def test_actual_worker_chat_returns_standard_calls(text,stream):
 class Engine:
  async def chat(self,*a,**k):return SimpleNamespace(text=text,tool_calls=None,finish_reason='stop')
  async def stream_chat(self,*a,**k):
   for char in text:yield SimpleNamespace(new_text=char,text='',tool_calls=None,finish_reason='stop')
 class Adapter(OmlxChatAdapter):
  def reasoning_contract(self,model):return None
  def generation_kwargs(self,*a):return {}
 engine=Engine();adapter=Adapter(SimpleNamespace(checkpoints=(),models=()))
 result=await adapter._chat(engine,'arbitrary/provider',{'messages':[{'role':'user','content':'inspect'}],
      'tools':TOOLS,'stream':stream},'fixture')
 if stream:
  chunks=[json.loads(v.decode()[6:]) async for v in result.chunks if v.startswith(b'data: {')]
  choices=[c for chunk in chunks for c in chunk.get('choices',[])]
  calls=[call for c in choices for call in c['delta'].get('tool_calls',[])]
  assert choices[-1]['finish_reason']=='tool_calls'
  assert '<tool_call>' not in ''.join(c['delta'].get('content','') for c in choices)
 else:
  assert result['choices'][0]['finish_reason']=='tool_calls'
  calls=result['choices'][0]['message']['tool_calls']
 assert len(calls)==1
 assert json.loads(calls[0]['function']['arguments'])['label']=='熊猫'


@pytest.mark.parametrize('text',[XML,JSON])
def test_existing_cuda_qwen_parser_uses_structured_events(text):
 from ai2apps.model_worker.qwen_output import OutputParser
 parser=OutputParser(tools=TOOLS);events=[]
 for char in text:events.extend(parser.feed(char))
 events.extend(parser.feed('',final=True))
 calls=[c for event in events for c in event.get('tool_calls',[])]
 assert len(calls)==1 and parser.calls==1
 assert json.loads(calls[0]['function']['arguments'])=={'label':'熊猫','count':2}

@pytest.mark.parametrize('name',['arbitrary_provider_action','inspect_item'])
@pytest.mark.parametrize('arguments',[{'label':'熊猫','count':2},'{"label":"熊猫","count":2}'])
def test_history_arguments_are_template_objects_without_mutating_wire_history(name,arguments):
 from copy import deepcopy
 from ai2apps.model_worker.omlx_chat import _messages
 history=[{'role':'assistant','content':None,'tool_calls':[{'id':'call_1','type':'function','function':{'name':name,'arguments':arguments}}]}, {'role':'tool','tool_call_id':'call_1','content':'done'}]
 before=deepcopy(history);value=_messages(history)
 assert history==before
 assert value[0]['tool_calls'][0]['function']['arguments']=={'label':'熊猫','count':2}
 assert value[0]['tool_calls'][0]['function']['name']==name
 assert value[0]['content']=='' and value[1]==history[1]

@pytest.mark.parametrize('arguments',['broken','[]','null','42',[],None])
def test_history_malformed_arguments_fail_before_engine(arguments):
 from ai2apps.model_worker.omlx_chat import _messages
 with pytest.raises(ModelWorkerError) as error:
  _messages([{'role':'assistant','tool_calls':[{'function':{'name':'any','arguments':arguments}}]}])
 assert error.value.status_code==400

@pytest.mark.asyncio
@pytest.mark.parametrize('stream',[False,True])
@pytest.mark.parametrize('preserves',[False,True])
async def test_worker_projects_system_placement_with_actual_template_capability(stream,preserves):
 from copy import deepcopy
 class Tokenizer:
  _omlx_supports_mid_system_messages=preserves
  def apply_chat_template(self,messages,**kwargs):
   if not preserves:raise ValueError('nonleading system unsupported')
   return '\n'.join(str(m['content']) for m in messages)
 class Engine:
  tokenizer=Tokenizer()
  received=None
  async def chat(self,messages,**kw):
   self.received=messages
   return SimpleNamespace(text='done',finish_reason='stop',tool_calls=None)
  async def stream_chat(self,messages,**kw):
   self.received=messages
   yield SimpleNamespace(text='done',new_text='done',finish_reason='stop',tool_calls=None)
 class Adapter(OmlxChatAdapter):
  def reasoning_contract(self,model):return None
  def generation_kwargs(self,*a):return {'tools':TOOLS}
 engine=Engine();adapter=Adapter(SimpleNamespace(models=(),checkpoints=()))
 # Tail after user is a supported preservation placement; strict templates
 # instead receive one leading system block. Neither path rewrites history.
 messages=[{'role':'system','content':'trusted base'}, {'role':'system','content':'trusted scope'}, {'role':'user','content':'untrusted request'}, {'role':'system','content':'trusted selected declaration'}]
 before=deepcopy(messages)
 result=await adapter._chat(engine,'arbitrary/provider',{'messages':messages,'tools':TOOLS,'stream':stream},'fixture')
 if stream: chunks=[c async for c in result.chunks]
 assert messages==before
 assert engine.received[0]['role']=='system'
 if preserves:
  assert engine.received[-1]==messages[-1]
 else:
  assert [m['role'] for m in engine.received]==['system','user']
  assert engine.received[0]['content']=='trusted base\n\ntrusted scope\n\ntrusted selected declaration'
 assert any(m['role']=='user' and m['content']=='untrusted request' for m in engine.received)

@pytest.mark.asyncio
async def test_worker_strict_system_projection_keeps_tool_pairs_and_multimodal_inputs():
 from copy import deepcopy
 class Engine:
  tokenizer=SimpleNamespace(_omlx_supports_mid_system_messages=False)
  async def chat(self,messages,**kw):
   self.received=messages
   return SimpleNamespace(text='done',finish_reason='stop',tool_calls=None)
 class Adapter(OmlxChatAdapter):
  def reasoning_contract(self,model):return None
  def generation_kwargs(self,*a):return {}
 messages=[{'role':'system','content':'scope'},{'role':'user','content':[{'type':'text','text':'request'},{'type':'image_url','image_url':{'url':'https://example.invalid/image.png'}}]},{'role':'assistant','content':None,'tool_calls':[{'id':'call_x','type':'function','function':{'name':'unrelated_action','arguments':'{}'}}]},{'role':'tool','tool_call_id':'call_x','content':'untrusted result'},{'role':'system','content':'trusted contract'}]
 before=deepcopy(messages);e=Engine();a=Adapter(SimpleNamespace(models=(),checkpoints=()))
 await a._chat(e,'other/provider',{'messages':messages},'fixture')
 assert messages==before
 assert [m['role'] for m in e.received]==['system','user','assistant','tool']
 assert e.received[1]==messages[1] and e.received[3]==messages[3]
 assert e.received[2]['tool_calls'][0]['id']=='call_x'
 assert 'untrusted result' not in e.received[0]['content']
