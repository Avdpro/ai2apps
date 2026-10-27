"""Require source coverage and bound new-article fanout without limiting updates."""


def validate_webpages(plan, pages, previous):
    web = {i+1:p for i,p in enumerate(pages) if not p.get('platform') and p.get('content_type','') in ('','webpage')}
    counts = {i:0 for i in web}
    for event in plan.events:
        ids = set(event.evidence_ids) & web.keys()
        if not ids:
            continue
        for i in ids:
            counts[i] += 1
    validate_new_article_sources(plan.events,pages)
    excluded=set()
    for decision in plan.excluded_pages:
        i=decision.evidence_id
        if i not in web or i in excluded or counts[i]:
            raise ValueError('Invalid or conflicting webpage exclusion')
        excluded.add(i)
    if any((counts[i] != 0 if i in excluded else counts[i] < 1) for i in web):
        raise ValueError('Every ordinary webpage must be included in an article or an explicit justified exclusion')


def source_identity(source, fallback=''):
    from .models import public_url
    url=source.get('url','')
    return public_url(url) if url else fallback


def validate_new_article_sources(events, pages):
    """A source may support one new article and any number of existing updates."""
    used={}
    for position,event in enumerate(events):
        if any(i<1 or i>len(pages) for i in event.evidence_ids):raise ValueError('Unknown source evidence ID')
        if event.update_article_id:continue
        identities={source_identity(pages[i-1],str(i)) for i in event.evidence_ids}
        for identity in identities:
            if identity in used:
                raise ValueError(f'Source article is used to CREATE more than one new channel article '
                    f'(items {used[identity]} and {position}). Consolidate its new topics into ONE new article. '
                    'The same source may also UPDATE multiple supplied existing articles when supported. '
                    'Do not drop evidence, invent update IDs or exclude valid reports to bypass this limit.')
            used[identity]=position
