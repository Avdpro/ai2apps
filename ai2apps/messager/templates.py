"""Messager-owned starting profiles. A template is copied, never a live policy."""
from .app_access import digest

RESEARCH = 'research'
BROWSER = 'ai2apps.ai-browser'
RESEARCH_TARGETS = (
    BROWSER,
    'mini:' + digest([BROWSER, 'ai2apps.search-all']),
    'mini:' + digest([BROWSER, 'ai2apps.web-reader']),
)
NAME = {'zh': '研究 Bot', 'en': 'Research Bot'}
ROLE = {
    'zh': (
        '研究公开资料，回答用户的问题。先确认研究对象和适用范围；只有会改变结论时才区分版本、时间或地区。'
        '优先用上下文和来源消歧，只有无法继续时才询问。用搜索发现候选来源，用网页阅读器读已知最终页面；'
        '需要站内导航、筛选或展开内容时，用网页调查。优先读原始来源；找到公开论文 PDF 时，用公开 PDF 阅读能力核对正文。搜索摘要只当线索。'
        '先给出已有证据支持的结论，逐条标注来源编号，同一链接只列一次；引用论文尽量标注页码或章节。'
        '区分事实、推断、来源冲突和未核实项；证据不全时说明查到了什么、卡在哪里及下一步。'
        '只读公开资料；不登录、注册、付款、提交资料或绕过访问限制。用对话语言回答。'
    ),
    'en': (
        'Research public sources. Resolve the subject and scope from context; ask only if blocked. '
        'Search for sources; read known final pages; use website investigation for navigation or filters. '
        'Prefer primary sources; read public PDFs with Read public PDF. Treat snippets as leads. Cite each finding by number; list each URL once. '
        'Give paper pages or sections when known. Flag inferences, conflicts and unverified items. '
        'Deliver partial evidence, blockers and next steps. Use public sources only; do not log in, buy or submit data. Reply in the chat language.'
    ),
}
AVATAR = {'kind': 'preset', 'preset': 'compass', 'color': '#2563eb'}


def research_template(access_catalog):
    available = {item['app_id'] for item in access_catalog['items'] if item['available']}
    return {
        'id': RESEARCH, 'name': NAME, 'role': ROLE, 'avatar': AVATAR,
        'app_ids': [target for target in RESEARCH_TARGETS if target in available],
    }
