import json
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_builtin_profile_copy_has_english_and_chinese_translations():
    locales = {
        lang: json.loads((ROOT / f'ai2apps/web/i18n/{lang}.json').read_text())
        for lang in ('en', 'zh')
    }

    def check(value):
        if isinstance(value, dict):
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
        elif isinstance(value, str) and re.search(r'[\u4e00-\u9fff]', value):
            for locale in locales.values():
                assert 'acpf.' + value in locale, value

    for profile in (ROOT / 'ai2apps/provisioning/profiles').glob('*.yaml'):
        check(yaml.safe_load(profile.read_text()))


def test_acpf_formats_counts_and_restored_plan_reasons_in_host_language():
    script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync('ai2apps/web/static/js/capability_provisioning.js', 'utf8')
    .replace('window.AI2AppsCapabilities = {', 'window.translateForTest = tr; window.AI2AppsCapabilities = {');
for (const language of ['en', 'zh']) {
    const context = {window: {_t: JSON.parse(fs.readFileSync(`ai2apps/web/i18n/${language}.json`))}};
    vm.runInNewContext(source, context);
    const tr = context.window.translateForTest;
    assert.equal(tr('安装所选 {0} 个模型', 3), language === 'en' ? 'Install 3 selected models' : '安装所选 3 个模型');
    assert.equal(tr('统一内存约 128 GiB'), language === 'en' ? 'Approximately 128 GiB unified memory' : '统一内存约 128 GiB');
    assert.equal(tr('配置本地绘图模型'), language === 'en' ? 'Set up local image models' : '配置本地绘图模型');
    assert.equal(tr('ai2apps/runtime-omlx'), 'ai2apps/runtime-omlx');
}
'''
    subprocess.run(['node', '-e', script], cwd=ROOT, check=True)


def test_restart_action_names_ai2apps_instead_of_internal_local_service():
    en = json.loads((ROOT / 'ai2apps/web/i18n/en.json').read_text())
    zh = json.loads((ROOT / 'ai2apps/web/i18n/zh.json').read_text())

    assert en['discover.install.restart_local'] == 'Restart AI2Apps'
    assert zh['discover.install.restart_local'] == '重启 AI2Apps'
    assert en['acpf.重启本地服务'] == 'Restart AI2Apps'
    assert zh['acpf.重启本地服务'] == '重启 AI2Apps'
