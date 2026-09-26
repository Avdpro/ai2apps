from __future__ import annotations

import json
import mimetypes
import secrets
import signal
import threading
import webbrowser
from collections import Counter
from collections.abc import Callable
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .case_generator import CaseGenerationError
from .catalog_service import CatalogService
from .catalog_store import CatalogConflictError
from .catalog_validation import CatalogValidationError
from .codex_driver import handoff_prompt, read_codex_output
from .state import read_json
from .human_action import current as current_human_action
from .web_assets import build_test_center_html

HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>AI2Apps Test Center</title><style>
:root{font-family:Inter,system-ui;color:#202124;background:#f6f7f9}body{margin:0}.bar{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:18px 28px;z-index:2}.title{display:flex;align-items:center;justify-content:space-between}h1{font-size:22px;margin:0}.presets{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}button{border:1px solid #ccd0d5;background:#fff;border-radius:8px;padding:8px 12px;cursor:pointer}button:disabled{cursor:not-allowed;opacity:.5}button.primary{background:#202124;color:#fff;border-color:#202124}.main{max-width:1100px;margin:24px auto;padding:0 20px}.summary,.metrics{display:flex;gap:12px;margin-bottom:18px;flex-wrap:wrap}.pill,.metric{background:#fff;border:1px solid #ddd;border-radius:999px;padding:7px 12px}.metric{border-radius:12px;min-width:120px}.metric strong{font-size:20px}.group{background:#fff;border:1px solid #ddd;border-radius:12px;margin:12px 0;overflow:hidden}.group-head{display:flex;gap:10px;align-items:center;padding:14px 16px;font-weight:650;background:#fafafa}.cases{padding:4px 16px}.case{display:grid;grid-template-columns:26px 52px 1fr auto;gap:10px;align-items:center;padding:10px 0;border-top:1px solid #eee}.badge{font-size:12px;font-weight:700}.meta{font-size:12px;color:#687078}.actions{position:sticky;bottom:0;background:rgba(246,247,249,.96);padding:16px 0;display:flex;justify-content:flex-end;gap:10px}.search{padding:9px 12px;border:1px solid #ccc;border-radius:8px;min-width:240px}.danger{color:#a12622;border-color:#e2aaa7}.hidden{display:none}.progress-shell{height:12px;background:#e4e7eb;border-radius:999px;overflow:hidden;margin:14px 0 20px}.progress-bar{height:100%;width:0;background:#2f6fed;transition:width .25s}.current{background:#eef4ff;border:1px solid #cbdcff;border-radius:12px;padding:14px 16px;margin:12px 0 20px}.status{font-size:12px;border-radius:999px;padding:4px 8px;background:#edf0f3}.status-passed{color:#137333;background:#e6f4ea}.status-failed{color:#b3261e;background:#fce8e6}.status-running{color:#174ea6;background:#e8f0fe}.status-skipped,.status-blocked{color:#6b5b00;background:#fff4ce}.report{word-break:break-all}.progress-case{display:grid;grid-template-columns:82px 52px 1fr;gap:10px;align-items:start;padding:9px 0;border-top:1px solid #eee}.issues{border:1px solid #efb8b3;background:#fff8f7;border-radius:12px;margin:0 0 20px;overflow:hidden}.issues-head{display:flex;justify-content:space-between;padding:14px 16px;font-weight:700;color:#8c1d18;background:#fce8e6}.issue{padding:12px 16px;border-top:1px solid #f3cbc7}.issue-title{font-weight:650}.issue-summary{margin-top:5px}.issue-detail{white-space:pre-wrap;max-height:160px;overflow:auto;background:#fff;border:1px solid #eed7d4;border-radius:8px;padding:9px;margin-top:8px}.continue-note{font-size:12px;font-weight:400}.case-summary{font-size:12px;color:#a12622;margin-top:3px}.codex-console{background:#111827;color:#e5e7eb;border-radius:12px;margin:0 0 20px;overflow:hidden}.codex-console-head{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:#1f2937;font-weight:700}.codex-console-meta{font-size:12px;color:#9ca3af;font-weight:400}.codex-output{padding:12px 16px;max-height:360px;overflow:auto;white-space:pre-wrap;word-break:break-word;font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}.codex-line{padding:5px 0;border-bottom:1px solid #263244}.codex-line:last-child{border-bottom:0}.codex-line-failed{color:#fca5a5}.codex-line-running{color:#93c5fd}.codex-detail{color:#cbd5e1;margin-top:2px}
</style></head><body><div class="bar"><div class="title"><h1>AI2Apps Test Center</h1><input id="search" class="search" placeholder="搜索 App、Package、Mini-App 或 Case"></div><div id="presets" class="presets"><button data-p="P0">P0 快速门禁</button><button data-p="P1">P1 核心回归</button><button data-p="P2">P2 全量产品</button><button data-p="P3">P3 发布候选</button><button id="all">全选</button><button id="none">全不选</button></div></div><main class="main"><section id="selection"><div class="summary"><span class="pill" id="priority"></span><span class="pill" id="selected"></span><span class="pill" id="scope"></span></div><div id="groups"></div><div class="actions"><button id="cancel">取消</button><button class="primary" id="start">开始测试</button></div></section><section id="progress" class="hidden"><div class="summary"><span class="pill" id="run-status">准备启动</span><span class="pill" id="run-id">等待 Run ID</span><span class="pill" id="run-priority"></span></div><div class="progress-shell"><div id="progress-bar" class="progress-bar"></div></div><div class="metrics"><div class="metric"><strong id="completed">0</strong><br>已完成</div><div class="metric"><strong id="passed">0</strong><br>通过</div><div class="metric"><strong id="failed">0</strong><br>失败</div><div class="metric"><strong id="blocked">0</strong><br>阻断</div><div class="metric"><strong id="skipped">0</strong><br>跳过</div><div class="metric"><strong id="remaining">0</strong><br>剩余</div></div><section id="issues" class="issues hidden"><div class="issues-head"><span>当前发现的问题 · <span id="issue-count">0</span></span><span class="continue-note">测试默认继续，可随时中止</span></div><div id="issue-list"></div></section><div id="account" class="current hidden"></div><div id="driver" class="current hidden"></div><section id="codex-console" class="codex-console hidden"><div class="codex-console-head"><span>Codex CLI 实时输出</span><span id="codex-output-time" class="codex-console-meta"></span></div><div id="codex-output" class="codex-output"></div></section><div id="handoff" class="current hidden"><div id="handoff-text"></div><button id="copy-handoff">复制接管指令</button></div><div id="current" class="current">正在创建测试运行…</div><div id="progress-groups"></div><p id="report" class="meta report"></p><div class="actions"><button id="stop" class="danger">中止测试</button></div></section></main><script>
const token=location.hash.slice(1);let data=null;let priority='P1';let polling=null;const selected=new Set();const rank={P0:0,P1:1,P2:2,P3:3};const $=id=>document.getElementById(id);
async function load(){data=await(await fetch('/api/plan?token='+encodeURIComponent(token))).json();priority=data.priority;selectPriority(priority)}
function eligible(c){return rank[c.priority]<=rank[priority]}
function selectPriority(p){priority=p;selected.clear();for(const g of data.groups)for(const c of g.cases)if(eligible(c))selected.add(c.id);render()}
function render(){$('priority').textContent='预设：'+priority+(selected.size===eligibleCount()?'':' · 自定义');$('selected').textContent='已选 '+selected.size+' 项';$('scope').textContent=allRequiredSelected()?'可给出完整门禁结论':'将给出范围内结论';const q=$('search').value.toLowerCase();const root=$('groups');root.innerHTML='';for(const g of data.groups){const visible=g.cases.filter(c=>eligible(c)&&(!q||(c.name+' '+c.id).toLowerCase().includes(q)));if(!visible.length)continue;const box=document.createElement('section');box.className='group';const head=document.createElement('label');head.className='group-head';const check=document.createElement('input');check.type='checkbox';const n=visible.filter(c=>selected.has(c.id)).length;check.checked=n===visible.length;check.indeterminate=n>0&&n<visible.length;check.onchange=()=>{for(const c of visible)check.checked?selected.add(c.id):selected.delete(c.id);render()};head.append(check,document.createTextNode(g.name+' ('+visible.length+')'));box.append(head);const cases=document.createElement('div');cases.className='cases';for(const c of visible){const row=document.createElement('label');row.className='case';const cb=document.createElement('input');cb.type='checkbox';cb.checked=selected.has(c.id);cb.onchange=()=>{cb.checked?selected.add(c.id):selected.delete(c.id);render()};const badge=document.createElement('span');badge.className='badge';badge.textContent=c.priority;const title=document.createElement('div');const line=document.createElement('div');line.textContent=c.name;const meta=document.createElement('div');meta.className='meta';meta.textContent=c.id;title.append(line,meta);const ex=document.createElement('span');ex.className='meta';ex.textContent=c.executor;row.append(cb,badge,title,ex);cases.append(row)}box.append(cases);root.append(box)}}
function eligibleCount(){let n=0;for(const g of data.groups)for(const c of g.cases)if(eligible(c))n++;return n}function allRequiredSelected(){for(const g of data.groups)for(const c of g.cases)if(eligible(c)&&c.required&&!selected.has(c.id))return false;return true}
document.querySelectorAll('[data-p]').forEach(b=>b.onclick=()=>selectPriority(b.dataset.p));$('all').onclick=()=>{for(const g of data.groups)for(const c of g.cases)if(eligible(c))selected.add(c.id);render()};$('none').onclick=()=>{selected.clear();render()};$('search').oninput=render;
async function begin(){$('start').disabled=true;const response=await fetch('/api/submit?token='+encodeURIComponent(token),{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({cancelled:false,priority,selected:[...selected]})});if(!response.ok){$('start').disabled=false;return}$('selection').classList.add('hidden');$('search').classList.add('hidden');$('presets').classList.add('hidden');$('progress').classList.remove('hidden');$('run-priority').textContent='优先级 '+priority;window.scrollTo(0,0);await updateProgress();polling=setInterval(updateProgress,500)}
function statusNode(status){const span=document.createElement('span');span.className='status status-'+status;span.textContent=status;return span}
function renderCases(groups){const root=$('progress-groups');root.innerHTML='';for(const group of groups){const box=document.createElement('section');box.className='group';const head=document.createElement('div');head.className='group-head';head.textContent=group.name+' · '+group.completed+'/'+group.total;box.append(head);const cases=document.createElement('div');cases.className='cases';for(const c of group.cases){const row=document.createElement('div');row.className='progress-case';const badge=document.createElement('span');badge.className='badge';badge.textContent=c.priority;const content=document.createElement('div');content.textContent=c.name;if(c.summary&&['failed','blocked'].includes(c.status)){const summary=document.createElement('div');summary.className='case-summary';summary.textContent=c.summary;content.append(summary)}row.append(statusNode(c.status),badge,content);cases.append(row)}box.append(cases);root.append(box)}}
function renderIssues(issues){$('issue-count').textContent=issues.length;$('issues').classList.toggle('hidden',!issues.length);const root=$('issue-list');root.innerHTML='';for(const issue of issues){const item=document.createElement('div');item.className='issue';const title=document.createElement('div');title.className='issue-title';title.textContent=issue.group+' · '+issue.name;const summary=document.createElement('div');summary.className='issue-summary';summary.textContent=issue.summary||issue.status;item.append(title,summary);if(issue.detail){const detail=document.createElement('div');detail.className='issue-detail';detail.textContent=issue.detail;item.append(detail)}if(issue.evidence&&issue.evidence.length){const evidence=document.createElement('div');evidence.className='meta report';evidence.textContent='证据：'+issue.evidence.join(' · ');item.append(evidence)}root.append(item)}}
function renderCodexOutput(output){const entries=output&&output.entries||[];const panel=$('codex-console');panel.classList.toggle('hidden',!entries.length);if(!entries.length)return;const root=$('codex-output');const nearBottom=root.scrollHeight-root.scrollTop-root.clientHeight<50;root.innerHTML='';for(const entry of entries){const line=document.createElement('div');line.className='codex-line codex-line-'+entry.status;const title=document.createElement('div');title.textContent=(entry.status==='running'?'▶ ':entry.status==='failed'?'✕ ':'✓ ')+entry.title;line.append(title);if(entry.detail){const detail=document.createElement('div');detail.className='codex-detail';detail.textContent=entry.detail;line.append(detail)}root.append(line)}if(nearBottom)root.scrollTop=root.scrollHeight;$('codex-output-time').textContent=output.updatedAt?'最近活动 '+new Date(output.updatedAt).toLocaleTimeString():''}
async function copyHandoff(){const value=$('handoff-text').textContent;try{await navigator.clipboard.writeText(value)}catch(error){const input=document.createElement('textarea');input.value=value;document.body.append(input);input.select();document.execCommand('copy');input.remove()}$('copy-handoff').textContent='已复制'}
async function updateProgress(){try{const s=await(await fetch('/api/status?token='+encodeURIComponent(token))).json();$('run-status').textContent=s.label;$('run-id').textContent=s.runId?'Run '+s.runId:'等待 Run ID';$('completed').textContent=s.completed;$('passed').textContent=s.counts.passed||0;$('failed').textContent=s.counts.failed||0;$('blocked').textContent=s.counts.blocked||0;$('skipped').textContent=s.counts.skipped||0;$('remaining').textContent=Math.max(0,s.total-s.completed);$('progress-bar').style.width=s.percent+'%';$('current').textContent=s.error?'运行错误：'+s.error:(s.currentCaseName?'当前 Case：'+s.currentCaseName:s.message);const account=s.testAccount||null;$('account').classList.toggle('hidden',!account);if(account)$('account').textContent='测试账号：'+(account.email||'未分配')+' · '+account.status+(account.sessionStatus?' · '+account.sessionStatus:'')+(account.heartbeatStatus?' · heartbeat '+account.heartbeatStatus:'')+(account.cleanupStatus?' · cleanup '+account.cleanupStatus:'');const driver=s.codexDriver||null;$('driver').classList.toggle('hidden',!driver);if(driver)$('driver').textContent='Codex 执行器：'+driver.status+(driver.summary?' · '+driver.summary:'')+(driver.log?' · 日志 '+driver.log:'');renderCodexOutput(s.codexOutput);$('handoff').classList.toggle('hidden',!s.handoffPrompt);if(s.handoffPrompt)$('handoff-text').textContent=s.handoffPrompt;renderIssues(s.issues||[]);renderCases(s.groups||[]);if(s.report)$('report').textContent='报告：'+s.report;if(s.terminal){clearInterval(polling);$('stop').disabled=true;$('stop').textContent=s.conclusion==='CANCELLED'?'测试已中止':'测试已结束'}}catch(error){$('current').textContent='暂时无法读取进度，正在重试…'}}
async function stop(){$('stop').disabled=true;$('stop').textContent='正在中止…';await fetch('/api/cancel?token='+encodeURIComponent(token),{method:'POST'});await updateProgress()}
$('start').onclick=begin;$('cancel').onclick=async()=>{await fetch('/api/submit?token='+encodeURIComponent(token),{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({cancelled:true})});document.body.innerHTML='<main class="main"><h1>已取消</h1></main>'};$('stop').onclick=stop;$('copy-handoff').onclick=copyHandoff;load();
</script></body></html>"""

HTML = HTML.replace(
    "</style>",
    ".nav{display:flex;gap:8px;align-items:center}.catalog-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.catalog-list,.editor{background:#fff;border:1px solid #ddd;border-radius:12px;padding:16px}.catalog-item{border-top:1px solid #eee;padding:10px 0}.catalog-actions{display:flex;gap:6px;margin-top:7px;flex-wrap:wrap}.catalog-actions button{padding:5px 8px}.editor textarea{width:100%;min-height:320px;box-sizing:border-box;font:12px/1.5 ui-monospace,monospace}.diff{white-space:pre-wrap;max-height:260px;overflow:auto;background:#111827;color:#e5e7eb;padding:12px;border-radius:8px}.error{color:#b3261e;white-space:pre-wrap}@media(max-width:800px){.catalog-grid{grid-template-columns:1fr}}</style>",
).replace(
    '<h1>AI2Apps Test Center</h1><input id="search"',
    '<h1>AI2Apps Test Center</h1><div class="nav"><button id="manage">管理测试</button><input id="search"',
).replace(
    'placeholder="搜索 App、Package、Mini-App 或 Case"></div><div id="presets"',
    'placeholder="搜索 App、Package、Mini-App 或 Case"></div></div><div id="presets"',
).replace(
    '<section id="progress" class="hidden">',
    '''<section id="management" class="hidden"><div class="summary"><button id="back-selection">返回选择</button><button id="new-group">新建 Group</button><button id="new-case">新建 Case</button><button id="refresh-catalog">刷新</button></div><div id="catalog-diagnostics" class="current"></div><div class="catalog-grid"><div class="catalog-list"><h2>Group / Case</h2><div id="catalog-items"></div></div><div class="editor"><h2 id="editor-title">Catalog 编辑器</h2><textarea id="catalog-editor" spellcheck="false"></textarea><div class="catalog-actions"><button id="validate-object">校验与 Diff 预览</button><button id="save-object" class="primary">保存</button></div><div id="catalog-errors" class="error"></div><pre id="catalog-diff" class="diff hidden"></pre></div></div></section><section id="progress" class="hidden">''',
).replace(
    "function eligible(c){return rank[c.priority]<=rank[priority]}",
    "function eligible(c){return c.priority===null||rank[c.priority]<=rank[priority]}",
).replace(
    "if(eligible(c))selected.add(c.id);render()",
    "if(c.priority!==null&&eligible(c))selected.add(c.id);render()",
).replace(
    "badge.textContent=c.priority;",
    "badge.textContent=c.priority||'按需';",
).replace(
    "$('start').onclick=begin;",
    r'''
let catalogData=null,editingKind='groups',editingRevision=null;
async function catalogApi(path,options={}){const response=await fetch(path+(path.includes('?')?'&':'?')+'token='+encodeURIComponent(token),options);const value=await response.json().catch(()=>({error:'Invalid response'}));if(!response.ok)throw new Error(value.error||JSON.stringify(value.errors||value));return value}
function showSelection(){$('management').classList.add('hidden');$('selection').classList.remove('hidden');$('search').classList.remove('hidden');$('presets').classList.remove('hidden')}
async function showManage(){$('selection').classList.add('hidden');$('search').classList.add('hidden');$('presets').classList.add('hidden');$('management').classList.remove('hidden');await refreshCatalog()}
function cleanObject(value){const copy={...value};delete copy.source_type;delete copy.source_path;delete copy.sourceType;delete copy.sourcePath;delete copy.editable;return copy}
async function editObject(kind,value){if(value.editable&&(value.source_type||value.sourceType))value=await catalogApi('/api/catalog/'+kind+'/'+encodeURIComponent(value.id));editingKind=kind;editingRevision=value.revision||null;$('editor-title').textContent=(editingRevision?'编辑 ':'新建 ')+(kind==='groups'?'Group':'Case');$('catalog-editor').value=JSON.stringify(cleanObject(value),null,2);$('catalog-errors').textContent='';$('catalog-diff').classList.add('hidden')}
function defaultGroup(){return {schemaVersion:1,id:'new-test-group',name:'New Test Group',description:'',kind:'on-demand',enabled:false,defaultSelected:false,order:500,tags:[],lifecycle:'draft'}}
function defaultCase(){const group=(catalogData.groups.find(g=>g.editable)||{}).id||'choose-group';return {schemaVersion:1,id:'new.test.case',name:'New Test Case',groupId:group,priority:null,enabled:false,required:false,executor:'codex-ui',timeoutSeconds:300,requires:[],tags:[],description:'',instructions:['Describe the visible test actions.'],expectations:['Describe the expected visible result.'],cleanup:[],lifecycle:'draft'}}
async function refreshCatalog(){catalogData=await catalogApi('/api/catalog');const d=catalogData.diagnostics;$('catalog-diagnostics').textContent='覆盖诊断：新发现 '+d.newlyDiscovered.length+' · 未覆盖 '+d.uncovered.length+' · 失效引用 '+d.staleReferences.length+' · 已归档 '+(d.disabledOrArchived.groups+d.disabledOrArchived.cases);const root=$('catalog-items');root.innerHTML='';for(const kind of ['groups','cases'])for(const item of catalogData[kind]){const row=document.createElement('div');row.className='catalog-item';const title=document.createElement('div');title.textContent=(kind==='groups'?'Group · ':'Case · ')+(item.name||item.id);const meta=document.createElement('div');meta.className='meta';meta.textContent=item.id+' · '+(item.source_type||item.sourceType||'')+' · '+(item.priority||item.kind||'按需');const actions=document.createElement('div');actions.className='catalog-actions';if(item.editable){const edit=document.createElement('button');edit.textContent='编辑';edit.onclick=()=>editObject(kind,item);actions.append(edit);const archive=document.createElement('button');archive.textContent='归档';archive.onclick=async()=>{await catalogApi('/api/catalog/'+kind+'/'+encodeURIComponent(item.id)+'/archive',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({revision:item.revision})});await refreshCatalog()};actions.append(archive);if(kind==='cases'){const trial=document.createElement('button');trial.textContent='试运行';trial.onclick=()=>trialCase(item);actions.append(trial)}}if(kind==='cases'){const copy=document.createElement('button');copy.textContent='复制为自定义';copy.onclick=()=>copyCase(item);actions.append(copy)}row.append(title,meta,actions);root.append(row)}for(const kind of ['groups','cases'])for(const item of catalogData.archived[kind]){const row=document.createElement('div');row.className='catalog-item';row.textContent='已归档 · '+item.id+' ';const restore=document.createElement('button');restore.textContent='恢复';restore.onclick=async()=>{await catalogApi('/api/catalog/'+kind+'/'+encodeURIComponent(item.id)+'/restore',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({revision:item.revision})});await refreshCatalog()};row.append(restore);root.append(row)}}
async function validateEditor(){try{const value=JSON.parse($('catalog-editor').value);const result=await catalogApi('/api/catalog/'+editingKind+'/'+encodeURIComponent(value.id)+'/validate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(value)});$('catalog-errors').textContent=result.errors.join('\n');$('catalog-diff').textContent=result.diff||'No changes';$('catalog-diff').classList.toggle('hidden',!result.ok);return result.ok}catch(error){$('catalog-errors').textContent=error.message;return false}}
async function saveEditor(){if(!await validateEditor())return;try{const value=JSON.parse($('catalog-editor').value);if(editingRevision)value.revision=editingRevision;const method=editingRevision?'PUT':'POST';const path='/api/catalog/'+editingKind+(editingRevision?'/'+encodeURIComponent(value.id):'');await catalogApi(path,{method,headers:{'content-type':'application/json'},body:JSON.stringify(value)});editingRevision=null;await refreshCatalog()}catch(error){$('catalog-errors').textContent=error.message}}
async function copyCase(item){const group=prompt('目标 Group ID');if(!group)return;const id=prompt('新 Case ID',item.id+'.copy');if(!id)return;await catalogApi('/api/catalog/cases/'+encodeURIComponent(item.id)+'/copy',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id,groupId:group})});await refreshCatalog()}
async function trialCase(item){await catalogApi('/api/catalog/cases/'+encodeURIComponent(item.id)+'/trial-run',{method:'POST',headers:{'content-type':'application/json'},body:'{}'});$('management').classList.add('hidden');$('progress').classList.remove('hidden');polling=setInterval(updateProgress,500)}
$('manage').onclick=showManage;$('back-selection').onclick=showSelection;$('refresh-catalog').onclick=refreshCatalog;$('new-group').onclick=()=>editObject('groups',defaultGroup());$('new-case').onclick=()=>editObject('cases',defaultCase());$('validate-object').onclick=validateEditor;$('save-object').onclick=saveEditor;
$('start').onclick=begin;''',
)
HTML = HTML.replace(
    '<div id="groups"></div>',
    '<div id="manifest" class="current meta"></div><div id="groups"></div>',
).replace(
    "root.append(box)}}\nfunction eligibleCount",
    "root.append(box)}$('manifest').textContent='Run Manifest：'+[...selected].slice(0,20).join(' · ')+(selected.size>20?' …':'')}\nfunction eligibleCount",
)

RunCallback = Callable[
    [dict[str, Any], threading.Event, Callable[[str, Path], None]], dict[str, Any]
]

# The maintained Test Center lives in dedicated HTML/CSS/JS resources. Keep the
# legacy inline value above as an import-time fallback for older source bundles.
with suppress(OSError):
    HTML = build_test_center_html()


def _status_payload(session: dict[str, Any], lock: threading.Lock) -> dict[str, Any]:
    with lock:
        snapshot = dict(session)
    run_dir = snapshot.get("runDirectory")
    state = None
    if run_dir:
        try:
            state = read_json(Path(run_dir) / "state.json")
        except (FileNotFoundError, json.JSONDecodeError):
            state = None
    if state is None:
        phase = snapshot.get("phase", "selecting")
        return {
            "phase": phase,
            "pipelineId": snapshot.get("pipelineId"),
            "canReturnToPipeline": bool(snapshot.get("pipelineId")) and phase in {"completed", "failed", "cancelled"},
            "label": "正在启动" if phase != "selecting" else "等待选择",
            "message": "正在创建测试运行…",
            "runId": snapshot.get("runId"),
            "completed": 0,
            "total": snapshot.get("selectedCount", 0),
            "percent": 0,
            "counts": {},
            "groups": [],
            "terminal": phase in {"cancelled", "failed"},
            "conclusion": snapshot.get("conclusion"),
            "error": snapshot.get("error"),
        }
    cases = state["plan"]["cases"]
    results = state["results"]
    counts = Counter(value.get("status", "pending") for value in results.values())
    grouped: dict[str, list[dict[str, Any]]] = {}
    issues: list[dict[str, Any]] = []
    for case in cases:
        result = results.get(case["id"], {})
        status = result.get(
            "status",
            "running" if case["id"] == state.get("currentCaseId") else "pending",
        )
        summary = str(result.get("summary", ""))
        item = {
            "id": case["id"],
            "name": case["name"],
            "priority": case["priority"],
            "status": status,
            "summary": summary,
        }
        expected_status = result.get("expectedStatus", case.get("expectedStatus"))
        if result.get("durationSeconds") is not None:
            item["durationSeconds"] = result["durationSeconds"]
        started = result.get("startedAt", state.get("caseStartedAt", {}).get(case["id"]))
        if started:
            item["startedAt"] = started
        if expected_status is not None:
            item["expectedStatus"] = expected_status
        if result.get("observedStatus") is not None:
            item["observedStatus"] = result["observedStatus"]
        if case.get("sourceCaseId") is not None:
            item["sourceCaseId"] = case["sourceCaseId"]
        display_group = ('Pipeline · ' + state['plan']['pipeline']['name']) if state['plan'].get('pipeline') else case['group']
        grouped.setdefault(display_group, []).append(item)
        if status in {"failed", "blocked"}:
            details = result.get("details", {})
            detail = ""
            if isinstance(details, dict):
                detail = str(details.get("outputTail", ""))
            failures = result.get("failures", [])
            if not detail and isinstance(failures, list):
                detail = "\n".join(str(value) for value in failures[:10])
            evidence = result.get("evidence", [])
            issues.append(
                {
                    **item,
                    "group": case["group"],
                    "detail": detail,
                    "evidence": evidence if isinstance(evidence, list) else [],
                }
            )
    groups = [
        {
            "name": name,
            "total": len(values),
            "completed": sum(
                item["status"] not in {"pending", "running"} for item in values
            ),
            "cases": values,
        }
        for name, values in grouped.items()
    ]
    completed = len(results)
    terminal = state["status"] in {"completed", "cancelled"} or snapshot.get(
        "phase"
    ) == "failed"
    labels = {
        "running": "测试进行中",
        "awaiting_agent": "Codex UI 测试进行中",
        "waiting_human": "等待用户辅助测试",
        "waiting_controller": "宿主控制器执行生命周期动作中",
        "ready_to_finalize": "正在生成报告",
        "completed": "测试完成",
        "cancelled": "测试已中止",
    }
    account = state.get("testAccountLease")
    driver = state.get("codexDriver")
    codex_output = {"entries": [], "updatedAt": None}
    if isinstance(driver, dict) and driver.get("log"):
        log_path = Path(str(driver["log"]))
        try:
            if (
                log_path.resolve().parent == (Path(run_dir) / "logs").resolve()
                and log_path.is_file()
            ):
                codex_output = read_codex_output(log_path)
        except OSError:
            pass
    message = "等待下一个测试步骤" if not terminal else "运行已经结束"
    if state.get("pipelineStop"):
        message = state["pipelineStop"]["summary"]
    if terminal and isinstance(account, dict) and account.get("status") in {
        "unavailable",
        "release_failed",
    }:
        message = "Codex 未启动：测试账号前置检查失败"
        if account.get("summary"):
            message += f" — {account['summary']}"
    elif (
        state["status"] == "awaiting_agent"
        and isinstance(driver, dict)
        and driver.get("status") == "failed"
    ):
        message = "Codex 自动执行未完成，可复制下方指令手工接管"
    return {
        "phase": state["status"],
        "humanAction": current_human_action(Path(run_dir)) if not terminal else None,
        "pipelineId": state["plan"].get("pipeline", {}).get("id"),
        "canReturnToPipeline": bool(snapshot.get("pipelineId")) and snapshot.get("phase") in {"completed", "failed", "cancelled"},
        "label": labels.get(state["status"], state["status"]),
        "message": message,
        "runId": state["runId"],
        "completed": completed,
        "total": len(cases),
        "percent": round(100 * completed / len(cases)) if cases else 100,
        "counts": dict(counts),
        "issues": issues,
        "groups": groups,
        "currentCaseId": state.get("currentCaseId"),
        "currentCaseName": state.get("currentCaseName"),
        "terminal": terminal,
        "conclusion": snapshot.get("conclusion")
        or ("CANCELLED" if state["status"] == "cancelled" else None),
        "error": snapshot.get("error"),
        "testAccount": account,
        "codexDriver": driver,
        "codexOutput": codex_output,
        "handoffPrompt": handoff_prompt(state["runId"])
        if state["status"] == "awaiting_agent"
        else None,
        "report": str(Path(run_dir) / "report.html"),
    }


def control(
    plan_payload: dict[str, Any],
    run_callback: RunCallback,
    *,
    open_browser: bool = True,
    repo_root: Path | None = None,
    keep_open: bool = False,
) -> dict[str, Any]:
    token = secrets.token_urlsafe(24)
    lock = threading.Lock()
    cancel_event = threading.Event()
    finished = threading.Event()
    terminal_seen = threading.Event()
    stopping = threading.Event()
    worker_done = threading.Event()
    worker_done.set()
    previous_interrupt = None
    if threading.current_thread() is threading.main_thread():
        def stop_controller(_signum, _frame):
            cancel_event.set()
            stopping.set()
            finished.set()
            terminal_seen.set()
        previous_interrupt = signal.signal(signal.SIGINT, stop_controller)
    session: dict[str, Any] = {"phase": "selecting"}
    catalog_service = CatalogService(repo_root) if repo_root is not None else None

    def publish_run(run_id: str, run_dir: Path) -> None:
        with lock:
            session.update(runId=run_id, runDirectory=str(run_dir), phase="running")
        print(
            json.dumps({"runId": run_id, "runDirectory": str(run_dir)}, ensure_ascii=False),
            flush=True,
        )

    def worker(selection: dict[str, Any]) -> None:
        worker_done.clear()
        trial = selection.get("trialCase")
        try:
            outcome = run_callback(selection, cancel_event, publish_run)
            if trial and outcome.get("conclusion") in {"PASS", "SCOPED_PASS"} and catalog_service:
                revision = str(trial.get("revision", ""))
                promoted = {key: value for key, value in trial.items() if key not in {"revision", "sourcePath"}}
                promoted["lifecycle"] = "trial-passed"
                catalog_service.save("cases", promoted, revision)
            with lock:
                session.update(outcome)
                session["phase"] = (
                    "cancelled"
                    if outcome.get("conclusion") == "CANCELLED"
                    else "completed"
                )
        except Exception as error:  # surfaced to the local controller and CLI
            with lock:
                session.update(phase="failed", conclusion="FAIL", error=str(error))
        finally:
            worker_done.set()
            # A trial run returns to the same catalog editing session. Keep the
            # loopback controller alive until the user starts a normal run or
            # explicitly cancels from the selection view.
            if not trial and not selection.get("pipelineId"):
                finished.set()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _authorized(self) -> bool:
            return parse_qs(urlparse(self.path).query).get("token") == [token]

        def _write_authorized(self) -> bool:
            origin = self.headers.get("Origin")
            expected = f"http://127.0.0.1:{self.server.server_port}"
            return self._authorized() and origin == expected

        def _body(self, max_bytes: int = 1_000_000) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > max_bytes:
                raise ValueError("request body is too large")
            value = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(value, dict):
                raise ValueError("request body must be a JSON object")
            return value

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            artifact_prefix = f"/artifacts/{token}/"
            if parsed.path.startswith(artifact_prefix):
                with lock:
                    directory = session.get("runDirectory")
                if not directory:
                    self.send_error(404)
                    return
                root = Path(directory).resolve()
                relative = unquote(parsed.path[len(artifact_prefix):])
                target = (root / relative).resolve()
                state = read_json(root / "state.json")
                allowed = {"report.html"}
                for result in state.get("results", {}).values():
                    allowed.update(result.get("evidence", []))
                if relative not in allowed or root not in target.parents or not target.is_file():
                    self.send_error(404)
                    return
                body = target.read_bytes()
                media = mimetypes.guess_type(target.name)[0] or "text/plain"
                self.send_response(200)
                self.send_header("Content-Type", media + ("; charset=utf-8" if media.startswith("text/") else ""))
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "sandbox allow-popups allow-popups-to-escape-sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; media-src 'self'")
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/":
                body = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/plan" and self._authorized():
                self._json(200, plan_payload)
            elif parsed.path == "/api/status" and self._authorized():
                payload = _status_payload(session, lock)
                self._json(200, payload)
                if payload["terminal"] and not session.get("trialActive"):
                    terminal_seen.set()
            elif parsed.path == "/api/catalog" and self._authorized() and catalog_service:
                self._json(200, catalog_service.snapshot())
            elif parsed.path.startswith("/api/catalog/") and self._authorized() and catalog_service:
                parts = parsed.path.strip("/").split("/")
                if len(parts) == 5 and parts[2] == "cases" and parts[4] == "content":
                    self._json(200, catalog_service.shared_case(parts[3]))
                    return
                if len(parts) == 5 and parts[2] == "pipelines" and parts[4] == "latest-run":
                    self._json(200, catalog_service.latest_pipeline_run(parts[3]))
                    return
                if len(parts) == 4 and parts[2] in {"groups", "cases", "pipelines"}:
                    self._json(200, catalog_service.get(parts[2], parts[3]))
                else:
                    self.send_error(404)
            else:
                self.send_error(404)

        def _catalog_write(self, method: str) -> bool:
            if catalog_service is None or not self.path.startswith("/api/catalog/"):
                return False
            if not self._write_authorized():
                self.send_error(404)
                return True
            try:
                parsed = urlparse(self.path)
                parts = parsed.path.strip("/").split("/")
                payload = self._body(
                    15_000_000 if parts[-1:] == ["fixtures"] else 1_000_000
                )
                if method == "POST" and parts == ["api", "catalog", "pipeline", "return"]:
                    with lock:
                        if not session.get("pipelineId") or session["phase"] not in {"completed", "failed", "cancelled"}:
                            self._json(409, {"error": "Pipeline is still finishing; retry shortly"})
                            return True
                        pipeline_id = session["pipelineId"]
                        session.clear()
                        session.update(phase="selecting", selectedCount=0, trialActive=False)
                        cancel_event.clear()
                    self._json(200, {"status": "selecting", "pipelineId": pipeline_id})
                    return True
                if method == "POST" and parts == ["api", "catalog", "trial", "return"]:
                    with lock:
                        if not session.get("trialActive") or session["phase"] not in {
                            "completed",
                            "failed",
                            "cancelled",
                        }:
                            self._json(409, {"error": "no completed trial run to return from"})
                            return True
                        for key in (
                            "runId",
                            "runDirectory",
                            "conclusion",
                            "error",
                            "currentCaseId",
                            "currentCaseName",
                            "trialCaseId",
                            "trialGroupId",
                        ):
                            session.pop(key, None)
                        session.update(
                            phase="selecting",
                            selectedCount=0,
                            trialActive=False,
                        )
                        cancel_event.clear()
                    self._json(200, {"status": "selecting"})
                    return True
                kind = parts[2] if len(parts) > 2 else ""
                if method == "PUT" and kind == "cases" and len(parts) == 5 and parts[4] == "content":
                    self._json(200, catalog_service.save_shared_case(parts[3], payload))
                    return True
                if kind not in {"groups", "cases", "pipelines"}:
                    raise ValueError("invalid catalog object kind")
                if method == "POST" and len(parts) == 3:
                    self._json(201, catalog_service.save(kind, payload))
                    return True
                if (
                    method == "POST"
                    and kind == "cases"
                    and len(parts) == 4
                    and parts[3] == "generate"
                ):
                    self._json(
                        200,
                        catalog_service.generate_case(
                            str(payload.get("description", "")),
                            str(payload.get("groupId", "")),
                        ),
                    )
                    return True
                if method == "PUT" and len(parts) == 4:
                    if payload.get("id") != parts[3]:
                        raise ValueError("object ID cannot be changed")
                    revision = str(payload.pop("revision", ""))
                    self._json(200, catalog_service.save(kind, payload, revision))
                    return True
                if method == "POST" and len(parts) == 5 and parts[4] == "validate":
                    self._json(200, catalog_service.validate(kind, payload))
                    return True
                if method == "POST" and len(parts) == 5 and parts[4] in {"archive", "restore"}:
                    action = catalog_service.archive if parts[4] == "archive" else catalog_service.restore
                    self._json(200, action(kind, parts[3], str(payload.get("revision", ""))))
                    return True
                if method == "POST" and kind == "cases" and len(parts) == 5 and parts[4] == "copy":
                    self._json(201, catalog_service.copy_case(parts[3], str(payload.get("id", "")), str(payload.get("groupId", ""))))
                    return True
                if method == "POST" and kind == "cases" and len(parts) == 5 and parts[4] == "fixtures":
                    with lock:
                        valid_trial = (
                            session.get("trialActive")
                            and session.get("trialCaseId") == parts[3]
                        )
                    if not valid_trial:
                        self._json(409, {"error": "fixtures can only be added for the active trial case"})
                        return True
                    self._json(
                        201,
                        catalog_service.store_image_fixture(
                            parts[3],
                            str(payload.get("filename", "")),
                            str(payload.get("contentBase64", "")),
                        ),
                    )
                    return True
                if method == "POST" and kind == "cases" and len(parts) == 5 and parts[4] == "trial-review":
                    with lock:
                        run_directory = session.get("runDirectory")
                        valid_trial = (
                            session.get("trialActive")
                            and session.get("trialCaseId") == parts[3]
                            and session.get("phase") in {"completed", "failed", "cancelled"}
                        )
                    if not valid_trial or not run_directory:
                        self._json(409, {"error": "the trial run is not ready for review"})
                        return True
                    self._json(
                        200,
                        catalog_service.review_trial(
                            parts[3],
                            Path(str(run_directory)),
                            payload.get("supplements", []),
                        ),
                    )
                    return True
                if method == "POST" and kind == "cases" and len(parts) == 5 and parts[4] == "trial-run":
                    raw = catalog_service.get("cases", parts[3])
                    with lock:
                        if session["phase"] != "selecting":
                            self._json(409, {"error": "a run is already active"})
                            return True
                        session.update(
                            phase="starting",
                            selectedCount=1,
                            trialActive=True,
                            trialCaseId=parts[3],
                            trialGroupId=raw.get("groupId"),
                        )
                    selection = {"priority": plan_payload.get("priority", "P1"), "selected": [], "caseIds": [], "trialCase": raw}
                    self._json(202, {"status": "starting"})
                    worker_done.clear()
                    threading.Thread(target=worker, args=(selection,), daemon=True).start()
                    return True
                if method == "POST" and kind == "pipelines" and len(parts) == 5 and parts[4] == "run":
                    pipeline = catalog_service.get("pipelines", parts[3])
                    if not pipeline.get("enabled", True):
                        self._json(409, {"error": "pipeline is disabled"})
                        return True
                    with lock:
                        if session["phase"] != "selecting":
                            self._json(409, {"error": "a run is already active"})
                            return True
                        session.update(
                            phase="starting",
                            selectedCount=len(pipeline.get("steps", [])),
                            trialActive=False,
                            pipelineId=parts[3],
                        )
                    selection = {
                        "priority": plan_payload.get("priority", "P1"),
                        "selected": [],
                        "pipelineId": parts[3],
                    }
                    self._json(202, {"status": "starting"})
                    threading.Thread(
                        target=worker, args=(selection,), daemon=True
                    ).start()
                    return True
                self.send_error(404)
            except CatalogConflictError as error:
                self._json(409, {"error": str(error)})
            except (
                CaseGenerationError,
                CatalogValidationError,
                ValueError,
                KeyError,
                FileNotFoundError,
                json.JSONDecodeError,
            ) as error:
                self._json(400, {"error": str(error), "errors": getattr(error, "errors", [])})
            return True

        def do_PUT(self) -> None:
            if not self._catalog_write("PUT"):
                self.send_error(404)

        def do_POST(self) -> None:
            if stopping.is_set():
                self._json(409, {"error": "Test controller is stopping"})
                return
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/catalog/"):
                self._catalog_write("POST")
                return
            if not self._authorized():
                self.send_error(404)
                return
            if parsed.path == "/api/cancel":
                cancel_event.set()
                with lock:
                    if session["phase"] not in {"completed", "cancelled", "failed"}:
                        session["phase"] = "cancelling"
                self._json(202, {"status": "cancelling"})
                return
            if parsed.path == '/api/human-action':
                from .human_action import submit
                with lock:
                    directory = session.get('runDirectory')
                try:
                    if not directory or cancel_event.is_set():
                        raise ValueError('No active Run')
                    self._json(200, submit(Path(directory), self._body()))
                except (ValueError, OSError) as error:
                    self._json(409, {'error': str(error)})
                return
            if parsed.path != "/api/submit":
                self.send_error(404)
                return
            payload = self._body()
            with lock:
                if session["phase"] != "selecting":
                    self._json(409, {"error": "test selection was already submitted"})
                    return
                if payload.get("cancelled"):
                    session.update(phase="cancelled", conclusion="CANCELLED")
                    self._json(200, {"status": "cancelled"})
                    finished.set()
                    terminal_seen.set()
                    return
                session.update(
                    phase="starting",
                    selectedCount=len(payload.get("selected", [])),
                    trialActive=False,
                )
            self._json(202, {"status": "starting"})
            worker_done.clear()
            threading.Thread(target=worker, args=(payload,), daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_port}/#{token}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(json.dumps({"selectorUrl": url}, ensure_ascii=False), flush=True)
    if open_browser:
        webbrowser.open(url)
    finished.wait()
    terminal_seen.wait(timeout=10)
    if keep_open:
        print("测试已结束，报告与证据链接继续可用；按 Ctrl+C 关闭测试工具。", flush=True)
        try:
            stopping.wait()
        except KeyboardInterrupt:
            pass
    if stopping.is_set():
        worker_done.wait()
    if previous_interrupt is not None:
        signal.signal(signal.SIGINT, previous_interrupt)
    server.shutdown()
    server.server_close()
    with lock:
        return dict(session)
