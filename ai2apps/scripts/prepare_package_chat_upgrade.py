"""Prepare checked-in Package UI declarations/SDK, no signing or publication."""
from pathlib import Path
from html.parser import HTMLParser
import json,re,yaml
ROOT=Path(__file__).resolve().parents[2]
SDK=ROOT/'ai2apps/web/static/js/package_mini_chat.js'
VERSIONS={'ai2apps-audio-generation-suite':'0.2.3','ai2apps-media-voice-studio-suite':'0.2.3',
 'ai2apps-avatar-studio-suite':'0.1.4','ai2apps-frozen-time':'0.1.2',
 'ai2apps-search-all':'0.1.1','ai2apps-shopping-pro':'0.1.1','ai2apps-trip-planner':'0.1.1','ai2apps-web-reader':'0.1.1'}
class Fields(HTMLParser):
 def __init__(self):super().__init__();self.fields={};self.select=None
 def handle_starttag(self,tag,attrs):
  a=dict(attrs);id=a.get('id');kind=a.get('type','text')
  if tag in ('input','textarea','select') and id and kind not in ('file','password','hidden','button','submit') and not any(w in id.lower() for w in ('consent','rights','token','secret')):
   d={'type':'boolean' if kind=='checkbox' else 'number' if kind=='number' else 'string'}
   if d['type']=='string':d['maxLength']=min(16000,int(a.get('maxlength','8000')))
   for k in ('min','max'):
    if k in a:
     try:d['minimum' if k=='min' else 'maximum']=float(a[k])
     except ValueError:pass
   self.fields[id]=d
for folder in sorted((ROOT/'packages').glob('*')):
 if folder.name not in VERSIONS:continue
 path=folder/'app.yaml'
 if not path.exists():continue
 app=yaml.safe_load(path.read_text());minis=app.get('mini_apps',[])
 if not minis:continue
 new=VERSIONS[folder.name];app['version']=new
 (folder/'web/package_mini_chat.js').write_bytes(SDK.read_bytes())
 for mini in minis:
  mini['version']=new;resource=mini['entry']['resource'];html=folder/resource
  parser=Fields();parser.feed(html.read_text());fields=parser.fields
  # Media suite fields are deliberately created by its own workflow adapter.
  if folder.name=='ai2apps-media-voice-studio-suite':
   js=(folder/'web/mini-app.js').read_text()
   start=js.index("id: '"+mini['id']+"'");end=js.index('\n    }',start);js=js[start:end]
   for id,kind in re.findall(r"\{id: '([^']+)', label: '[^']*', type: '([^']+)'",js):
    if not any(w in id.lower() for w in ('consent','rights')):fields[id]={'type':'boolean' if kind=='checkbox' else 'string',**({} if kind=='checkbox' else {'maxLength':8000})}
  browser_fields={
   'ai2apps.search-all':{'query','mode','limit','profile','x-sort','xhs-sort','exclude-ads','retain-pages'},
   'ai2apps.shopping-pro':{'profile','history-pages','message','product-query','gift-recipient','gift-occasion','gift-budget','gift-profile','gift-preferences','gift-message'},
   'ai2apps.trip-planner':{'request','origin','destination','departure','return_date','hotel_checkin','hotel_checkout','nights','adults','purpose','profile','flight_cabin','hotel_bed','hotel_breakfast','airline_preference','origin_airport','destination_airport','excluded_airports','nonstop_only','hotel_near_transit','hotel_area','preferences'}}
  if mini['id'] in browser_fields:fields={k:v for k,v in fields.items() if k in browser_fields[mini['id']]}
  chat={'schema':'ai2apps.mini-app-chat/v1','enabled':True,'system_prompt':'Read and edit only declared current UI fields. Execute functions through the registered owner AaAT, never through a UI run button. Preserve task, model, material and shared output ownership.',
   'context':{'transport':'studio-bridge','maxBytes':40000},'help':{'resource':mini.get('chat',{}).get('help',{}).get('resource','help/mini-chat/help.md'),'max_bytes':32768},
   'tools':[{'name':'update_current_draft','description':'Update declared UI draft fields without submitting work.','input_schema':{'type':'object','properties':fields,'additionalProperties':False},'confirmation':'never'}]}
  mini['chat']=chat
  help=folder/chat['help']['resource'];help.parent.mkdir(parents=True,exist_ok=True)
  if not help.exists():help.write_text('# Mini-App Chat\nUse Chat to inspect or edit the current draft. Functional work uses the host-owned AaAT and original background tasks. Closing this page does not cancel accepted background work.\n')
  text=html.read_text()
  text=re.sub(r'<script>window.addEventListener\("load",\(\)=>\{window.ai2appsPackageChat=.*?</script>','',text,flags=re.S)
  text=text.replace('<script defer src="package_mini_chat.js"></script>','')
  bind=html.with_suffix('.chat.js')
  config=json.dumps({'miniAppId':mini['id'],'fields':fields},ensure_ascii=False)
  bind.write_text('window.addEventListener("load",()=>{window.ai2appsPackageChat=window.AI2AppsPackageChat.install({...'+config+',readExtra:()=>window.ai2appsCurrentUI?.()||{},afterPatch:()=>window.ai2appsSaveDraft?.()});});\n')
  text=re.sub(r'<script defer src="'+re.escape(bind.name)+r'"></script>','',text)
  text+='\n<script defer src="package_mini_chat.js"></script><script defer src="'+bind.name+'"></script>\n'
  html.write_text(text)
 path.write_text(json.dumps(app,ensure_ascii=False,indent=2)+'\n' if folder.name in ('ai2apps-search-all','ai2apps-shopping-pro','ai2apps-trip-planner','ai2apps-web-reader') else yaml.safe_dump(app,sort_keys=False,allow_unicode=True,width=110))
 manifest=folder/'ai2apps.json';m=json.loads(manifest.read_text());m['package']['version']=new
 mapping=json.loads((ROOT/'ai2apps/scripts/package_chat_catalog.json').read_text());entries=[]
 for mini in minis:
  names=mapping[mini['id']];inputs=sorted({x.get('kind','file') for x in mini.get('inputs',[])}) or ['text'];outputs=sorted({x.get('kind','file') for x in mini.get('outputs',[])}) or ['file']
  en=mini['name'];zh=mini.get('localizations',{}).get('zh-CN',{}).get('name',en)
  description=mini.get('description') or en
  entries.append({'kind':'mini-app','identity':mini['id'],'provides':names,'tasks':list(dict.fromkeys([en,zh])),
   'inputTypes':inputs,'outputTypes':outputs,'requirements':{'capabilities':[v if isinstance(v,str) else v['capability'] for v in mini.get('requirements',{}).get('capabilities',[]) if isinstance(v,str) or not v.get('optional',False)]},
   'agent':{'mode':'aaat','declarationVersion':'1.0.0','exports':[{'name':n,'interfaceVersion':'1.0.0','inputTypes':inputs,'outputTypes':outputs} for n in names]},
   'scope':'Requires a Desktop host implementing these declared AaAT exports. UI bridge edits drafts only; execution uses host-owned durable tasks and shared output.',
   'processing':'hybrid' if 'ai2apps.ai-browser' in [x['studio'] for x in mini['placements']] else 'local','pricing':'unknown',
   'localizations':{'en':{'displayName':en,'description':description},'zh':{'displayName':zh,'description':mini.get('localizations',{}).get('zh-CN',{}).get('description',description)}}})
 m['capabilityCatalog']={'schemaVersion':'ai2apps.package-capabilities.v1','entries':entries}
 manifest.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 print(folder.name,new,len(minis))
