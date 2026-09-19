exec(open('/tmp/ideogram-json-probe/probe.py').read().split('for name,caption in cases:')[0])
cases=[('zh_detailed',{'high_level_description':'一只胖胖的大熊猫坐在茂密的竹林里，抱着新鲜的绿竹，正在吃竹叶。','style_description':{'aesthetics':'宁静、自然、细节丰富','lighting':'柔和的自然光穿过竹叶','photo':'平视角度的野生动物摄影，背景柔和虚化','medium':'photograph'},'compositional_deconstruction':{'background':'茂密的绿色竹林，竹竿上长满叶片，地面覆盖青苔，洒落柔和的斑驳阳光。','elements':[{'type':'obj','bbox':[150,180,950,820],'desc':'一只胖胖的黑白大熊猫舒服地坐着，用前爪抱住一根绿色竹竿，嘴里嚼着竹叶。'},{'type':'obj','bbox':[350,350,750,700],'desc':'大熊猫爪中抱着的新鲜绿色竹竿和竹叶。'}]}}),('zh_template20',json.loads(Path('/tmp/ideogram-json-probe/zh_template.json').read_text()))]
for name,caption in cases:
 p=json.dumps(caption,ensure_ascii=False,separators=(',',':'))
 Path('/tmp/ideogram-json-probe',name+'.json').write_text(p)
 print('START',name,flush=True)
 params=dict(steps=20,mu=0.,std=1.75,guidance_schedule=[3.]*2+[7.]*18) if name.endswith('20') else dict(steps=12,mu=.5,std=1.75,guidance_schedule=[3.]+[7.]*11)
 im,report=pipe.generate(p,height=1024,width=1024,seed=0,**params)
 im.save('/tmp/ideogram-json-probe/'+name+'.png')
 Path('/tmp/ideogram-json-probe',name+'-report.json').write_text(json.dumps(report,indent=2))
 print('DONE',name,report,flush=True)
