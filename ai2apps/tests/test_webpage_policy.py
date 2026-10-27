import pytest
from ai2apps.intelligence.models import EventPlan
from ai2apps.intelligence.webpage_policy import validate_webpages

def plan(events,**kw):return EventPlan.model_validate({'events':events,**kw})
def event(ids,update=None):return dict(title='Comparison',evidence_ids=ids,update_article_id=update)
pages=[dict(url='https://example.com/a'),dict(url='https://example.com/b')]
def test_independent_reviews():validate_webpages(plan([event([1]),event([2])]),pages,[])
def test_cannot_silently_drop():
 for events in [[],[event([1])]]:
  with pytest.raises(ValueError):validate_webpages(plan(events),pages,[])
def test_merge_related_webpages():
 validate_webpages(plan([event([1,2])]),pages,[])
def test_merge_into_existing_event_with_different_url():
 prev=[dict(id='old',sources=[dict(url='https://example.com/earlier')])]
 validate_webpages(plan([event([1,2],'old')]),pages,prev)
def test_source_cannot_create_distinct_new_articles():
 with pytest.raises(ValueError,match='CREATE more than one'):
  validate_webpages(plan([event([1]),event([1,2])]),pages,[])

def test_source_can_create_one_and_update_many_existing_articles():
 validate_webpages(plan([event([1]),event([1,2],'old1'),event([1],'old2')]),pages,[])

def test_source_can_only_update_multiple_old_articles():
 validate_webpages(plan([event([1,2],'old1'),event([1],'old2')]),pages,[])

def test_duplicate_source_url_cannot_bypass_new_article_limit():
 duplicates=[dict(url='https://example.com/a?utm_source=feed'),dict(url='https://example.com/a#detail')]
 with pytest.raises(ValueError,match='CREATE more than one'):
  validate_webpages(plan([event([1]),event([2])]),duplicates,[])

def test_several_sources_can_merge_to_one_new_article():
 validate_webpages(plan([event([1,2])]),pages,[])
def test_cannot_exclude_covered_webpage():
 p=plan([event([1,2])],excluded_pages=[dict(evidence_id=1,category='spam',reason='Page is only repeated affiliate sales links without editorial content.')])
 with pytest.raises(ValueError):validate_webpages(p,pages,[])
def test_explicit_exclusion():
 p=plan([event([2])],excluded_pages=[dict(evidence_id=1,category='spam',reason='Page is only repeated affiliate sales links without editorial content.')])
 validate_webpages(p,pages,[])
def test_social_unchanged():validate_webpages(plan([]),[dict(url='https://x.com/a',platform='x')],[])
