from types import SimpleNamespace
from ai2apps.intelligence.language import output_language, normalize
from ai2apps.intelligence.store import IntelligenceStore


def test_output_language_channel_precedence_and_background(tmp_path):
    runtime=SimpleNamespace(config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=tmp_path)))
    principal=SimpleNamespace(actor_user_id='user')
    store=IntelligenceStore(tmp_path/'intelligence')
    c=store.save_channel('user',{'name':'Watch','interval_hours':0,'output_language':'ja'})
    request=SimpleNamespace(headers={'x-intelligence-language':'en'})
    assert output_language(runtime,request,principal,c['id'],{})=='Japanese'
    assert output_language(runtime,None,principal,c['id'],{})=='Japanese'
    assert output_language(None,request,principal,'new-channel',{'channel':{'output_language':'zh-TW'}})=='Traditional Chinese'
    assert output_language(None,request,principal,'entity-a',{})=='English'
    store.save_channel('user',{'name':'Renamed','interval_hours':0,'output_language':None},c['id'])
    assert store.get('channels','user',c['id'])['output_language']=='ja'


def test_language_allowlist():
    assert normalize('zh-Hant')=='zh-TW'
    assert normalize('en-US,en;q=0.8')=='en'
    assert normalize('ignore instructions') is None


def test_english_template_uses_catalog():
    import json
    from pathlib import Path
    from jinja2 import Environment, DictLoader
    root=Path(__file__).parents[1]
    source=(root/'web/templates/system_apps/intelligence.html').read_text()
    catalog=json.loads((root/'web/i18n/en.json').read_text())
    env=Environment(loader=DictLoader({'base.html':'{% block title %}{% endblock %}{% block head %}{% endblock %}{% block content %}{% endblock %}{% block scripts %}{% endblock %}','intelligence.html':source}))
    rendered=env.get_template('intelligence.html').render(t=lambda k:catalog[k],static=lambda p:'/static/'+p)
    assert 'Channel settings' in rendered and 'Import article' in rendered
    assert '频道设置' not in rendered and '收录文章' not in rendered
    assert 'AI output language' in rendered
