import sys,json,time
from pathlib import Path
src=Path('/Users/avdpropang/sdk/omlx-moe-cache/packages/ai2apps-model-ideogram4-mlx')
sys.path.insert(0,str(src/'src'))
from pipeline import Ideogram4MLXPipeline,PipelinePaths
root=Path.home()/'Library/Application Support/AI2Apps/instances/app-dev/data/platform/packages/runtime/ai2apps.model.ideogram4-mlx/data/derived-models/ideogram4/q4-bf0f58f4eb023432ce3ac965'
pipe=Ideogram4MLXPipeline(PipelinePaths(root,src/'assets/qwen3-vl-8b-config'),bits=4,group_size=64,staged=True)
def wrap(s):return {'high_level_description':s,'compositional_deconstruction':{'background':'','elements':[{'type':'obj','desc':s}]}}
cases=[('zh_minimal',wrap('胖胖熊猫吃竹子')),('en_minimal',wrap('A plump panda eating bamboo')),('en_detailed',{'high_level_description':'A plump giant panda sitting in a lush bamboo forest, holding and eating fresh green bamboo.','style_description':{'aesthetics':'peaceful, natural, detailed','lighting':'soft natural daylight filtered through bamboo leaves','photo':'eye-level wildlife photograph with soft background focus','medium':'photograph'},'compositional_deconstruction':{'background':'A lush green bamboo forest with leafy stalks, mossy ground and soft dappled sunlight.','elements':[{'type':'obj','bbox':[150,180,950,820],'desc':'A plump black-and-white giant panda sitting comfortably, holding a green bamboo stalk in its front paws and chewing the leaves.'},{'type':'obj','bbox':[350,350,750,700],'desc':'Fresh green bamboo stalks and leaves held in the panda paws.'}]}})]
for name,caption in cases:
 p=json.dumps(caption,ensure_ascii=False,separators=(',',':'))
 Path('/tmp/ideogram-json-probe',name+'.json').write_text(p)
 print('START',name,flush=True)
 im,report=pipe.generate(p,height=1024,width=1024,seed=0,steps=12,mu=.5,std=1.75,guidance_schedule=[3.]+[7.]*11)
 im.save('/tmp/ideogram-json-probe/'+name+'.png')
 Path('/tmp/ideogram-json-probe',name+'-report.json').write_text(json.dumps(report,indent=2))
 print('DONE',name,report,flush=True)
