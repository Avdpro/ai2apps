"""Product-owned browser Mini-Apps, shipped with the Desktop, not registry Packages."""
from copy import deepcopy
import json
from pathlib import Path

HOST = 'ai2apps.ai-browser'
ROOT = Path(__file__).resolve().parents[1] / 'web/static/builtin_mini_apps'


def definitions():
    result = []
    resources = []
    for name in ('search-all', 'web-reader', 'share-works'):
        folder = ROOT / name
        mini = json.loads((folder / 'app.yaml').read_text())['mini_apps'][0]
        mini['entry']['resource'] = f'builtin_mini_apps/{name}/web/index.html'
        if name == 'search-all':
            export = mini['aaat']['exports'][0]
            export['inputSchema']['properties']['mode']['default'] = 'fast'
            export['agentContext']['instructions'].insert(0,
                'Use Search All fast mode to discover sources or a starting URL. If search returns partial coverage with candidate URLs but no readable bodies, use a relevant observed URL as a starting point for browser.complete_goal when the task requires site investigation. Search titles and snippets alone are not factual evidence. Do not substitute server HTTP search silently.')
        elif name == 'web-reader':
            export = mini['aaat']['exports'][0]
            export['summary'] = {
                'zh': '读取一张已知最终网页的正文。站内搜索、筛选、展开控件或打开详情页请用网页调查。',
                'en': 'Read text from one known final page. Use browser.complete_goal for site navigation, filtering, expanding controls, or opening detail pages.',
            }
            export['agentContext']['instructions'].insert(0,
                'Select Web Reader only when the supplied URL is the final page and the requested evidence is already in its rendered content. If the page opened but requires navigation, expanding controls, or collecting evidence across pages, invoke browser.complete_goal with the observed URL and remaining goal. This is a separate authorized invocation; do not use it to bypass blocked access or uncertain input. For visual appearance, use a suitable dedicated Mini-App or browser.complete_goal with visual=true.')
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
        if mini['id']=='ai2apps.share-works':
            from ai2apps.share_works.aaat import install as install_share
            install_share(runtime,register,mini)
            continue
        if not mini.get('aaat', {}).get('exports'): continue
        spec = mini['aaat']['exports'][0]
        search = spec['name'] == 'web.search'
        key = mini['id'] + ('.search' if search else '.fetch')
        async def execute(args, context, search=search):
            if search:
                from ai2apps.research.search_workflow import invoke
                return await invoke(runtime,args,context)
            return await WebMiniAppAdapters(runtime).fetch(args,context)
        async def policy(args, context, mini=mini, spec=spec):
            if not args.get('confirmation_id'):
                from ai2apps.research.mini_apps import principal_for
                from ai2apps.research.search_preparation import automatic_values
                return automatic_values(runtime, principal_for(runtime, context), args, context) is not None
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
    from ai2apps.research.pdf_reader import install as install_pdf_reader
    install_pdf_reader(runtime, register)
    citation_policy(runtime)
