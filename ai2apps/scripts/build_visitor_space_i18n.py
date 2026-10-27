"""Embed visitor UI locales in the existing public JS route (no new Cloud route).

Author translations in web/i18n/<language>.json; the source-text key manifest
only addresses authored UI strings, never user content. Run after locale edits.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEGIN = '// BEGIN GENERATED VISITOR I18N\n'
END = '// END GENERATED VISITOR I18N\n'


def build():
    keys = json.loads((ROOT / 'web/i18n/visitor-space-keys.json').read_text())
    catalogs = {}
    for language in ('zh', 'zh-TW', 'en', 'ja', 'ko', 'fr', 'es', 'pt-BR', 'ru'):
        source = json.loads((ROOT / f'web/i18n/{language}.json').read_text())
        catalogs[language] = {text: source[key] for text, key in keys.items()}
    payload = json.dumps(catalogs, ensure_ascii=False, separators=(',', ':'))
    helper = r'''(() => {
    'use strict';
    const catalogs=CATALOGS;
    function resolve(languages){
        for(const language of languages){
            const tag=String(language||'').replace(/_/g,'-').toLowerCase();
            if(/^zh(?:-|$)/.test(tag))return /(?:^|-)(?:tw|hk|mo|hant)(?:-|$)/.test(tag)?'zh-TW':'zh';
            if(/^pt(?:-|$)/.test(tag))return 'pt-BR';
            const base=tag.split('-')[0];if(catalogs[base])return base;
        }
        return 'en';
    }
    const publicPage=!!document.querySelector('[data-visitor-public]');
    const preferences=publicPage?(typeof navigator!=='undefined'?(navigator.languages?.length?navigator.languages:[navigator.language]):[]):[document.documentElement?.lang];
    const language=resolve(preferences);
    function t(text,params={}){
        const value=catalogs[language][text]??catalogs.en[text]??text;
        return typeof value==='string'?value.replace(/\{(\w+)\}/g,(match,key)=>Object.hasOwn(params,key)?String(params[key]):match):value;
    }
    window.VisitorSpaceI18n=Object.freeze({t,language,resolve});
    if(publicPage&&document.documentElement)document.documentElement.lang=language;
    if(!publicPage&&document.querySelector('#visitor-editor'))document.title=t('访客空间')+' - AI2Apps';
    {
        // Explicitly marked static UI only. Never scan the published content tree.
        document.querySelectorAll?.('[data-vs-label]').forEach(el=>el.textContent=t(el.getAttribute('data-vs-label')));
        document.querySelectorAll?.('[data-vs-aria]').forEach(el=>el.setAttribute('aria-label',t(el.getAttribute('data-vs-aria'))));
        document.querySelectorAll?.('[data-vs-alt]').forEach(el=>el.setAttribute('alt',t(el.getAttribute('data-vs-alt'))));
    }
})();
'''.replace('CATALOGS', payload)
    path = ROOT / 'web/static/js/space.js'
    script = path.read_text()
    if script.startswith(BEGIN):
        script = script.split(END, 1)[1]
    path.write_text(BEGIN + helper + END + script)


if __name__ == '__main__':
    build()
