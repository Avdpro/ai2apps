"""Evidence-bound grouping of recent channel articles into concrete news topics."""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field
from . import service


class Topic(BaseModel):
    anchor: str = Field(min_length=4, max_length=100)
    title: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=900)
    article_ids: list[str] = Field(min_length=2, max_length=60)


class TopicPlan(BaseModel):
    topics: list[Topic] = Field(default_factory=list, max_length=8)


def recent(articles, now=None):
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=7)
    return sorted(
        [a for a in articles if datetime.fromisoformat(a['updated_at']) >= cutoff],
        key=lambda a: (a['updated_at'], a['id']), reverse=True)[:60]


def signature(articles):
    return hashlib.sha256(('topics-v2:'+json.dumps([
        [a['id'], a['updated_at'], a['title'], a['summary'], a['body']]
        for a in articles], ensure_ascii=False)).encode()).hexdigest()


async def summarize(runtime, request, principal, channel, articles):
    if len(articles) < 2:
        return []
    allowed = {a['id']: a for a in articles}
    def validate(value):
        plan = TopicPlan.model_validate(value)
        names, groups = set(), set()
        for topic in plan.topics:
            name = topic.title.strip().casefold()
            group = frozenset(topic.article_ids)
            if not name or name in names or len(group)!=len(topic.article_ids) or not group.issubset(allowed) or group in groups:
                raise ValueError('Topics need unique concrete names, distinct groups and unique supplied article IDs')
            normalize = lambda text: re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', text.casefold())
            anchor = normalize(topic.anchor)
            if len(anchor)<4 or anchor.isdigit():
                raise ValueError('Use a specific named model/event anchor, not a year or brand')
            for id in group:
                a = allowed[id]
                if anchor not in normalize(a['title']+' '+a['summary']+' '+a['body'][:1200]):
                    raise ValueError('Every linked article must explicitly contain the exact specific model/event anchor; omit unsupported groups')
            names.add(name);groups.add(group)
        return plan
    result = await service.model_json(runtime,request,principal,channel['id'],
        'Group related recent articles into up to 8 concrete hot topics. A topic is a specific product/model, '
        'release, competition, event or closely connected development, NOT a broad category like new releases, '
        'AI, watches, industry news or expert opinions. Merge reports about the SAME entity/event. '
        'Each topic needs at least two genuinely related supplied articles; do not force unrelated articles together. '
        'Do NOT fill a quota: two strong topics are better than eight weak ones. '
        'Supply anchor as an exact specific model name/number or event name appearing in EVERY linked article. '
        'Never use a brand/manufacturer, year, broad technology, publication name or monthly roundup as anchor. '
        'Different models from the same brand MUST stay separate. Never join unrelated models with and/or in a topic title. '
        'A multi-event roundup may support a topic only when its summary/body explicitly covers that entity. '
        'Omit unsupported singleton topics. An article may appear in multiple topics only if it discusses each. '
        'Summarize facts and developments from provided evidence only, explain the shared focus. '
        'This is channel coverage, not external popularity: never invent traffic/trending scores. '
        'Return topics=[] if no meaningful groups exist. Schema: '+json.dumps(TopicPlan.model_json_schema()),
        {'channel':{'name':channel['name'],'interests':channel['interests']},
         'articles':[{k:a.get(k) for k in ('id','title','summary','updated_at')} |
                     {'body':a['body'][:1200]} for a in articles]},validate)
    topics = []
    for t in result.topics:
        ids = sorted(t.article_ids,key=lambda id:allowed[id]['updated_at'],reverse=True)
        topics.append({'id':hashlib.sha256(t.title.strip().encode()).hexdigest()[:20],
            'title':t.title.strip(),'summary':t.summary,'article_ids':ids,
            'updated_at':max(allowed[id]['updated_at'] for id in ids)})
    return sorted(topics,key=lambda t:(len(t['article_ids']),t['updated_at']),reverse=True)
