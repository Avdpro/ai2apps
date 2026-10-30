import pytest
from ai2apps.knowledge.overlap import trim_overlap
ROWS=['第一项：项目进展与负责人信息 alpha', '第二项：下周计划与交付日期 beta', '第三项：当前风险和处理方案 gamma']
def test_continuous_text_boundary():
 overlap='\n'.join(ROWS)
 result,e=trim_overlap('前面的独有内容\n'+overlap,overlap+'\n后面的独有内容')
 assert result=='后面的独有内容' and e['removed_lines']==3
 assert e['matched_text'].strip()==overlap
@pytest.mark.parametrize('before,after',[
 ('标题\n项目 金额\nA 12','项目 金额\nA 12\nB 15'),
 ('\n'.join(ROWS),'\n'.join(ROWS)),
 ('前文\n'+ '\n'.join(ROWS), '\n'.join(ROWS[:2]+['第三项：当前风险和处理方案 DELTA'])+'\n后文'),
 ('发票 A\n抬头 公司\n税号 123\n金额 456','发票 B\n抬头 公司\n税号 123\n金额 456'),
 ('前文\n项目甲数量 100 价格 200\n项目乙数量 300 价格 400\n项目丙数量 500 价格 600','项目甲数量 100 价格 200\n项目乙数量 301 价格 400\n项目丙数量 500 价格 600\n后文'),
])
def test_ambiguous_or_different_content_preserved(before,after):
 assert trim_overlap(before,after)==(after,None)
def test_whitespace_and_unicode_normalization():
 source='\n'.join(ROWS)
 current='\n'.join(row.replace('：',':').replace(' ', '  ') for row in ROWS)+'\n更多内容'
 assert trim_overlap('开头\n'+source,current)[0]=='更多内容'
