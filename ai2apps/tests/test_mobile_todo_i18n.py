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

@pytest.mark.parametrize('owner_home,signed', [(False, False), (False, True), (True, False), (True, True)])
@pytest.mark.parametrize('template', ['mobile.html', 'mobile_todo.html', 'mobile_agent_pair.html', 'mobile_chat.html'])
def test_mobile_templates_use_real_gateway_asset_allowlist(template, owner_home, signed):
    import ast
    from types import SimpleNamespace
    routes = ROOT.parent / 'omlx/admin/routes.py'
    tree = ast.parse(routes.read_text())
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == 'MOBILE_STATIC_FILES' for target in node.targets))
    versioner = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_mobile_static_version')
    namespace = {'static_dir': ROOT/'web/static'}
    exec(compile(ast.Module(body=[assignment, versioner], type_ignores=[]), str(routes), 'exec'), namespace)
    requested = []
    def static(path):
        requested.append(path)
        assert (ROOT/'web/static'/path).is_file(), f'Missing Mobile asset: {path}'
        return namespace['_mobile_static_version'](path)
    env = Environment(loader=FileSystemLoader(ROOT/'web/templates'), autoescape=True)
    html = env.get_template(template).render(current_lang='zh', mobile_static=static, mobile_agent_signed=signed, owner_home=owner_home, mobile_agent_home=owner_home,
        request=SimpleNamespace(url=SimpleNamespace(path='/mobile/member/complete'), state=SimpleNamespace()))
    assert 'mobile_navigation_trace.js' not in html
    if template in ('mobile.html', 'mobile_chat.html'):
        assert 'js/chat_artifacts.js' in requested
        assert 'js/mobile_images.js' not in requested
        assert 'AI2AppsMobileImages' in (ROOT/'web/static/js/chat_artifacts.js').read_text()
