"""Reserve new bilingual conversation families; no generation or model selection."""
import hashlib,importlib.util,json
from pathlib import Path
from tokenizers import Tokenizer
root=Path('artifacts/dsv41-l2-new-conversation-holdout-20260916');root.mkdir(exist_ok=False)
checkpoint=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD')
spec=importlib.util.spec_from_file_location('encoding',checkpoint/'encoding/encoding.py');encoding=importlib.util.module_from_spec(spec);spec.loader.exec_module(encoding);tokenizer=Tokenizer.from_file(str(checkpoint/'tokenizer.json'))
scenarios=[
 ('encoder','A rotary encoder on a pottery wheel reports occasional reverse motion only when the kiln ventilation motor starts.','陶轮旋转编码器仅在窑炉排风电机启动时偶发反向读数。'),
 ('archive','A coastal museum is moving wax-cylinder recordings into a new cabinet while humidity logs disagree between two sensors.','海边博物馆要把蜡筒录音移入新柜体，但两只湿度计记录相互矛盾。'),
 ('ferry','A small island ferry must carry cargo and school commuters with two tide-dependent docking windows and a backup pier.','海岛渡轮要运货并接送学生，每天有两个受潮汐限制的靠泊窗口，还有一个备用码头。'),
 ('compiler','A toy language allows nested pattern matching, lazy guards and destructuring; the interpreter and bytecode VM disagree on side-effect order.','玩具语言允许嵌套模式匹配、惰性守卫和解构，但解释器与字节码虚拟机的副作用顺序不一致。'),
 ('astronomy','An amateur telescope array shares a clock but sees star centroid drift after camera rotation, despite unchanged focus.','业余望远镜阵列共享时钟，但相机旋转后恒星质心出现漂移，焦点并未改变。'),
 ('ceramics','A community ceramics studio must attribute glaze pinholes to drying, mixing or kiln schedule with only six test tiles.','社区陶艺室只有六块试片，需要区分釉面针孔源于干燥、调配还是烧成曲线。'),
 ('music','A string quartet arrangement must preserve a five-note motif while moving from 7/8 to 4/4 without extending the total duration.','弦乐四重奏改编需保留五音动机，并从7/8转到4/4拍而不延长总时长。'),
 ('water','A rainwater tank network has uncertain inlet measurements, one leaking valve and a pump that cannot run during evening quiet hours.','雨水蓄水罐网络的进水测量不确定，一只阀门泄漏，泵在晚间安静时段不能运行。'),
 ('puzzle','A cooperative board game uses hidden inventories and simultaneous orders; design a reveal phase that prevents information advantage.','合作桌游采用隐藏库存和同时下单，需要设计揭示阶段以避免信息优势。'),
 ('robot','A line-following warehouse cart loses localization on a polished floor only after crossing a metal expansion joint.','循线仓库小车只有越过金属伸缩缝后，才会在抛光地面上丢失定位。'),
 ('lexicon','A small endangered-language dictionary needs to distinguish speaker corrections, dialect variants and uncertain transcriptions without deleting history.','小型濒危语言词典要区分说话人纠正、方言变体和不确定转写，同时保留历史。'),
 ('combinatorics','Design a tournament schedule for nine teams where each pair meets once, two courts are available and no team plays three consecutive rounds.','为九支队伍设计单循环赛程，只有两块场地，而且任何队伍都不能连续打三轮。')]
rows=[]
for topic,en,zh in scenarios:
 for lang,scenario in [('en',en),('zh',zh)]:
  if lang=='en':
   messages=[{'role':'user','content':scenario+' Start by stating the unknowns and a small diagnostic plan.'},{'role':'assistant','content':'First separate measurement uncertainty from changes in the underlying process. Record the initial conditions, keep a control, vary one factor at a time, and preserve observations that contradict the working explanation. The current information is insufficient to choose one cause.'},{'role':'user','content':'Update the plan: the first two trials contradict one another, we can afford only three further trials, and one measurement channel may be biased. Give an explicit decision tree, a compact example table, and explain which conclusion would remain unjustified.'}]
  else:
   messages=[{'role':'user','content':scenario+'请先列出未知条件，并给出一个小规模诊断计划。'},{'role':'assistant','content':'先区分测量误差与过程本身的变化。记录初始条件，保留对照，每次只改变一个因素，并保存与当前解释矛盾的观察。现有信息不足以唯一确定原因。'},{'role':'user','content':'现在更新条件：前两次试验结果互相矛盾，预算只够再做三次，其中一个测量通道可能有偏差。请给出明确的决策树、简短示例表格，并说明哪些结论仍然不能成立。'}]
  prompt,media=encoding.encode_messages(messages,thinking_mode='chat',return_multi_modal_data=True)
  name=f'new-{topic}-{lang}';path=root/(name+'.json');path.write_text(json.dumps(dict(prompt=prompt,input_ids=tokenizer.encode(prompt).ids,messages=messages),ensure_ascii=False,indent=2))
  rows.append(dict(id=name,family_id='new-conversation:'+topic,split='test',language=lang,scope=topic,kind='authored_multiturn',fixture=str(path),fixture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),decode_steps=256))
(root/'reservation.json').write_text(json.dumps(dict(status='reserved_not_collected_not_evaluated',samples=rows,rows_max=6144,limitations=['Authored synthetic multi-turn histories, not private real user logs','Shared follow-up form across families'],use='Evaluate only after freezing a validation-selected candidate; never train on these families'),ensure_ascii=False,indent=2))
print('Reserved',len(rows),'conversations in',root)
