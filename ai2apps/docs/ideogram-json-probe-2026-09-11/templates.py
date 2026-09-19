exec(open('/tmp/ideogram-json-probe/probe.py').read().split('for name,caption in cases:')[0])
cases=[]
for name,prompt in [('zh_template','胖胖熊猫吃竹子'),('en_template','A plump panda eating bamboo')]:
 cases.append((name,{'high_level_description':prompt,'style_description':{'aesthetics':'clear, detailed, coherent composition','lighting':'natural, balanced lighting','photo':'eye-level view, clear focus on the main subject','medium':'photograph'},'compositional_deconstruction':{'background':'An environment consistent with the scene: '+prompt,'elements':[{'type':'obj','desc':prompt}]}}))
exec(open('/tmp/ideogram-json-probe/probe.py').read().split('for name,caption in cases:')[1].join(['for name,caption in cases:','']))
