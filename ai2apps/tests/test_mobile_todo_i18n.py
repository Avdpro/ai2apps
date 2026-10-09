from pathlib import Path
import re
from jinja2 import Environment, FileSystemLoader
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('lang,expected', [('zh','新建项目'),('en','New project'),('en-US','New project')])
def test_mobile_todo_localized_template(lang,expected):
    env=Environment(loader=FileSystemLoader(ROOT/'web/templates'),autoescape=True)
    html=env.get_template('mobile_todo.html').render(current_lang=lang,mobile_static=lambda x:'/static/'+x)
    assert expected in html
    if lang.startswith('en'):
        assert not re.search(r'[\u4e00-\u9fff]',html)
        assert 'Adjust progress in steps of 5%' in html
        assert 'Search projects' in html
    else:
        assert '调整进度，每步 5%' in html
