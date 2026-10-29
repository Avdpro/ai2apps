"""Product-owned browser Mini-Apps, shipped with the Desktop, not registry Packages."""
from copy import deepcopy
import json
from pathlib import Path

HOST = 'ai2apps.ai-browser'
ROOT = Path(__file__).resolve().parents[1] / 'web/static/builtin_mini_apps'


def definitions():
    result = []
    resources = []
    for name in ('search-all', 'web-reader'):
        folder = ROOT / name
        mini = json.loads((folder / 'app.yaml').read_text())['mini_apps'][0]
        mini['entry']['resource'] = f'builtin_mini_apps/{name}/web/index.html'
        if name == 'search-all':
            export = mini['aaat']['exports'][0]
            export['inputSchema']['properties']['mode']['default'] = 'fast'
            export['agentContext']['instructions'].insert(0,
                'Default ordinary web searches to Search All fast mode. This built-in Mini-App is always available; do not substitute server HTTP search silently. Use a dedicated Mini-App for its supported task before general browser exploration.')
        else:
            mini['aaat']['exports'][0]['agentContext']['instructions'].append(
                'Read rendered public webpage text. This is not screenshot vision: when the request requires visual appearance or images beyond this reader, discover browser.complete_goal with visual=true after checking dedicated Mini-Apps. Do not claim a text read is a visual observation.')
        help_file=(mini.get('chat') or {}).get('help',{}).get('resource')
        if help_file:
            mini['chat']['help']['resource']=f'builtin_mini_apps/{name}/{help_file}'
        result.append(mini)
        files=[p for p in (folder / 'web').rglob('*') if p.is_file()]
        if help_file:files.append(folder/help_file)
        for path in files:
            resources.append(str(path.relative_to(ROOT.parent)))
    return deepcopy(result), sorted(resources)


def install(runtime, register):
    """Reuse owner adapters and forms; no independent Package or execution loop."""
    from ai2apps.browser.package_sdk import confirmed_search, search_form
    from ai2apps.research.mini_apps import WebMiniAppAdapters
    from ai2apps.browser.package_sdk import citation_policy
    minis, _ = definitions()
    for mini in minis:
        spec = mini['aaat']['exports'][0]
        search = spec['name'] == 'web.search'
        key = mini['id'] + ('.search' if search else '.fetch')
        async def execute(args, context, search=search):
            if search:
                from ai2apps.research.search_workflow import invoke
                return await invoke(runtime,args,context)
            return await WebMiniAppAdapters(runtime).fetch(args,context)
        async def policy(args, context, mini=mini, spec=spec):
            return await confirmed_search(runtime, args, context, mini, spec)
        register(spec['name'], HOST,
            '一搜到底 / Search All' if search else '网页阅读器 / Web Reader',
            'Built-in browser search; default fast mode.' if search else 'Read rendered public webpage content through the existing browser Profile.',
            spec['inputSchema'], execute, mini=mini['id'], existing=True,
            provider_id_override=key, provider_version=mini['version'],
            field_labels={f['key']:f['label'] if isinstance(f['label'],dict) else {'zh':{'preparation_id':'搜索准备标识','cloud_consent':'允许付费搜索','cloud_price_version':'价格版本','cloud_max_points':'最高点数','confirmation_id':'搜索确认标识','locale':'输出语言'}.get(f['key'],f['label']),'en':f['label'].replace('_',' ').capitalize()} for f in spec['fields']},
            selection_required=spec['selectionRequired'], agent_context=spec['agentContext'],
            invocation_policy=policy if search else None, priority=100,
            form_name=spec['displayName'], form_summary=spec['summary'])
        if search:
            search_form(runtime, key, mini, spec)
    citation_policy(runtime)
