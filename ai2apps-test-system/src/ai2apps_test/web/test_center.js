const token = location.hash.slice(1);
const rank = {P0: 0, P1: 1, P2: 2, P3: 3};
const lifecycleOrder = ['draft', 'valid', 'trial-passed', 'enabled', 'archived'];
const lifecycleLabel = {'draft': '草稿', 'valid': '已校验', 'trial-passed': '试运行通过', 'enabled': '已启用', 'archived': '已归档'};
const sourceLabel = {'user-authored': '自定义', 'built-in': '内置', 'generated': '自动生成'};
const $ = id => document.getElementById(id);

let data = null;
let priority = 'P1';
let polling = null;
let currentView = 'selection';
let catalogData = null;
let activeGroup = 'all';
let activeObject = null;
let editingKind = 'groups';
let editingRevision = null;
let editorReadonly = false;
let editorArchived = false;
let copySource = null;
let generatingCase = false;
let trialContext = null;
let trialReview = null;
let reviewSupplements = [];
let reviewingTrial = false;
let activePipeline = null;
let pipelineRevision = null;
let pipelineLastRun = null;
let editingPipelineStep = null;
let editingSharedCase = null;
let pipelineSteps = [];
let selectedPipelineStep = -1;
let pipelineInsertMode = 'append';
const selected = new Set();

function apiUrl(path) {
  return path + (path.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(token);
}

async function catalogApi(path, options = {}) {
  const response = await fetch(apiUrl(path), options);
  const value = await response.json().catch(() => ({error: '服务返回了无法解析的内容'}));
  if (!response.ok) throw new Error(value.error || (value.errors || []).join('\n') || '请求失败');
  return value;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[character]));
}

function showToast(message) {
  const toast = $('toast');
  toast.textContent = message;
  toast.classList.remove('hidden');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add('hidden'), 2400);
}

function showError(message) {
  const target = $('catalog-alert');
  target.textContent = message || '';
}

async function setView(view) {
  currentView = view;
  for (const section of document.querySelectorAll('.view')) section.classList.toggle('hidden', section.id !== view);
  for (const button of document.querySelectorAll('.nav-item')) button.classList.toggle('active', button.dataset.view === view);
  document.querySelector('.top-nav').classList.toggle('hidden', view === 'progress');
  if (view === 'management') await refreshCatalog();
  if (view === 'pipelines') await refreshPipelines();
  if (view === 'diagnostics') await refreshDiagnostics();
  window.scrollTo(0, 0);
}

async function load() {
  const response = await fetch(apiUrl('/api/plan'));
  data = await response.json();
  priority = data.priority || 'P1';
  selectPriority(priority);
}

function eligible(testCase) {
  return testCase.priority === null || rank[testCase.priority] <= rank[priority];
}

function selectPriority(value) {
  priority = value;
  selected.clear();
  for (const group of data.groups) {
    for (const testCase of group.cases) {
      if (testCase.priority !== null && eligible(testCase)) selected.add(testCase.id);
    }
  }
  renderSelection();
}

function eligibleCount() {
  let count = 0;
  for (const group of data.groups) for (const testCase of group.cases) if (testCase.priority !== null && eligible(testCase)) count++;
  return count;
}

function allRequiredSelected() {
  for (const group of data.groups) {
    for (const testCase of group.cases) {
      if (testCase.priority !== null && eligible(testCase) && testCase.required && !selected.has(testCase.id)) return false;
    }
  }
  return true;
}

function selectedCases() {
  const cases = [];
  for (const group of data.groups) for (const testCase of group.cases) if (selected.has(testCase.id)) cases.push({...testCase, groupName: group.name});
  return cases;
}

function renderSelection() {
  document.querySelectorAll('[data-p]').forEach(button => button.classList.toggle('active', button.dataset.p === priority));
  $('priority').textContent = '预设 ' + priority + (selected.size === eligibleCount() ? '' : ' · 已自定义');
  $('selected').textContent = '已选 ' + selected.size + ' 项';
  $('scope').textContent = allRequiredSelected() ? '完整门禁范围' : '范围内结论';
  const query = $('search').value.trim().toLowerCase();
  const root = $('groups');
  root.innerHTML = '';
  for (const group of data.groups) {
    const visible = group.cases.filter(testCase => eligible(testCase) && (!query || (testCase.name + ' ' + testCase.id).toLowerCase().includes(query)));
    if (!visible.length) continue;
    const box = document.createElement('section');
    box.className = 'group';
    const head = document.createElement('label');
    head.className = 'group-head';
    const check = document.createElement('input');
    check.type = 'checkbox';
    const picked = visible.filter(testCase => selected.has(testCase.id)).length;
    check.checked = picked === visible.length;
    check.indeterminate = picked > 0 && picked < visible.length;
    check.onchange = () => {
      for (const testCase of visible) check.checked ? selected.add(testCase.id) : selected.delete(testCase.id);
      renderSelection();
    };
    const kind = group.kind === 'on-demand' ? ' · 按需' : '';
    head.append(check, document.createTextNode(group.name + kind + ' (' + visible.length + ')'));
    box.append(head);
    const cases = document.createElement('div');
    cases.className = 'cases';
    for (const testCase of visible) {
      const row = document.createElement('label');
      row.className = 'case';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = selected.has(testCase.id);
      checkbox.onchange = () => {
        checkbox.checked ? selected.add(testCase.id) : selected.delete(testCase.id);
        renderSelection();
      };
      const badge = document.createElement('span');
      badge.className = 'badge';
      badge.textContent = testCase.priority || '按需';
      const title = document.createElement('div');
      title.innerHTML = '<div>' + escapeHtml(testCase.name) + '</div><div class="muted mono">' + escapeHtml(testCase.id) + '</div>';
      const executor = document.createElement('span');
      executor.className = 'muted';
      executor.textContent = testCase.executor;
      row.append(checkbox, badge, title, executor);
      cases.append(row);
    }
    box.append(cases);
    root.append(box);
  }
  renderManifest();
}

function renderManifest() {
  const values = selectedCases();
  $('manifest-count').textContent = values.length;
  $('manifest-summary').textContent = values.length ? `${priority} 预设与显式选择的确定性并集` : '尚未选择测试。';
  $('manifest').innerHTML = values.slice(0, 30).map(testCase => `<div class="manifest-item"><b>${escapeHtml(testCase.name)}</b><span class="muted">${escapeHtml(testCase.priority || '按需')} · ${escapeHtml(testCase.groupName)}</span></div>`).join('') + (values.length > 30 ? `<div class="manifest-item muted">另有 ${values.length - 30} 项…</div>` : '');
}

async function begin(selection = null) {
  $('start').disabled = true;
  const payload = selection || {cancelled: false, priority, selected: [...selected]};
  const response = await fetch(apiUrl('/api/submit'), {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(payload)});
  if (!response.ok) {
    $('start').disabled = false;
    showToast('无法启动测试，请重试');
    return;
  }
  trialContext = null;
  sessionStorage.removeItem('ai2apps-test-trial-context');
  $('return-to-case').classList.add('hidden');
  $('improve-case').classList.add('hidden');
  $('stop').disabled = false;
  $('stop').textContent = '中止测试';
  await setView('progress');
  $('run-priority').textContent = '优先级 ' + (payload.priority || priority);
  await updateProgress();
  polling = setInterval(updateProgress, 500);
}

function sourceType(item) { return item.sourceType || item.source_type || 'built-in'; }
function groupId(testCase) { return testCase.groupId || testCase.group_id || ''; }
function timeout(testCase) { return testCase.timeoutSeconds || testCase.timeout_seconds || 300; }
function componentId(testCase) { return testCase.componentId || testCase.component_id || ''; }

async function refreshCatalog(keepSelection = false) {
  showError('');
  try {
    catalogData = await catalogApi('/api/catalog');
    renderLibrary();
    if (!keepSelection) closeEditor();
  } catch (error) {
    showError('无法读取测试库：' + error.message);
  }
}

function casesForGroup(id) {
  if (id === 'archived') return catalogData.archived.cases.map(item => ({...item, archived: true}));
  if (id === 'all') return catalogData.cases;
  return catalogData.cases.filter(testCase => groupId(testCase) === id);
}

async function refreshPipelines() {
  try {
    catalogData = await catalogApi('/api/catalog');
    renderPipelineList();
  } catch (error) {
    $('pipeline-alert').textContent = '无法读取 Pipeline：' + error.message;
  }
}

function renderPipelineList() {
  const values = catalogData?.pipelines || [];
  $('pipeline-count').textContent = values.length;
  $('pipeline-list').innerHTML = '';
  for (const pipeline of values) {
    const button = document.createElement('button');
    button.className = 'pipeline-list-item' + (activePipeline?.id === pipeline.id ? ' active' : '');
    button.innerHTML = `<strong>${escapeHtml(pipeline.name)}</strong><span>${escapeHtml(pipeline.id)} · ${(pipeline.steps || []).length} 步</span>`;
    button.onclick = () => editPipeline(pipeline.id);
    $('pipeline-list').append(button);
  }
}

function nextPipelineStepId() {
  const used = new Set(pipelineSteps.map(step => step.id));
  let index = 1;
  while (used.has('step-' + index)) index++;
  return 'step-' + index;
}

function newPipeline() {
  pipelineLastRun = null;
  activePipeline = {schemaVersion: 1, id: 'new-pipeline', name: 'New Pipeline', description: '', enabled: false, steps: []};
  pipelineRevision = null;
  pipelineSteps = [];
  selectedPipelineStep = -1;
  renderPipelineEditor();
}

async function editPipeline(id) {
  try {
    activePipeline = await catalogApi('/api/catalog/pipelines/' + encodeURIComponent(id));
    pipelineLastRun = (await catalogApi('/api/catalog/pipelines/' + encodeURIComponent(id) + '/latest-run')).run;
    pipelineRevision = activePipeline.revision || null;
    pipelineSteps = structuredClone(activePipeline.steps || []);
    selectedPipelineStep = -1;
    renderPipelineEditor();
    renderPipelineList();
  } catch (error) { $('pipeline-alert').textContent = error.message; }
}

function renderPipelineEditor() {
  $('empty-pipeline').classList.add('hidden');
  $('pipeline-editor-shell').classList.remove('hidden');
  $('pipeline-title').textContent = activePipeline.name || activePipeline.id;
  $('pipeline-id-label').textContent = activePipeline.id;
  $('pipeline-id').value = activePipeline.id;
  $('pipeline-id').disabled = Boolean(pipelineRevision);
  $('pipeline-name').value = activePipeline.name || '';
  $('pipeline-description').value = activePipeline.description || '';
  $('pipeline-enabled').checked = Boolean(activePipeline.enabled);
  renderPipelineSteps();
}

function pipelineCase(caseId) {
  return catalogData?.cases.find(item => item.id === caseId);
}

function renderPipelineSteps() {
  let lastRunPanel = $('pipeline-last-run');
  if (!lastRunPanel) {
    lastRunPanel = document.createElement('div');
    lastRunPanel.id = 'pipeline-last-run';
    lastRunPanel.className = 'pipeline-last-run';
    $('pipeline-steps').before(lastRunPanel);
  }
  lastRunPanel.textContent = pipelineLastRun
    ? `上次运行：${pipelineLastRun.conclusion} · ${pipelineLastRun.runId} · ${new Date(pipelineLastRun.createdAt).toLocaleString()}${pipelineLastRun.revision !== pipelineRevision ? ' · Pipeline 已修改，以下为历史结果' : ''}`
    : '尚无运行结果';
  const labels = {'include-pipeline': '引入 Pipeline', 'human-test': '用户辅助测试', 'restart-app': '重启 App', 'restart-local': '重启 Local', 'quit-all-relaunch': '全部退出再启动', 'reset-data': '重置数据'};
  $('pipeline-steps').innerHTML = pipelineSteps.length ? '' : '<div class="empty-state"><div class="empty-icon">＋</div><h3>轨迹还是空的</h3><p>添加 Case 或动作来建立第一条测试路径。</p></div>';
  pipelineSteps.forEach((step, index) => {
    const row = document.createElement('div');
    row.className = 'pipeline-step' + (selectedPipelineStep === index ? ' selected' : '');
    row.onclick = event => { if (!event.target.closest('button,select,input,label,textarea')) { selectedPipelineStep = index; renderPipelineSteps(); } };
    const source = step.type === 'case' ? pipelineCase(step.caseId) : null;
    const title = step.type === 'case' ? (source?.name || step.caseId) : step.action === 'start-helper' ? '启动 Test Helper' : labels[step.action] || step.action;
    const subtitle = step.type === 'case' ? step.caseId : 'Test 实例动作';
    const expectation = step.type === 'case' ? `<select data-expectation><option value="passed">期待通过</option><option value="failed">期待失败</option><option value="blocked">期待阻断</option><option value="stop-when-failed">stop when failed（失败即停止）</option><option value="stop-when-succeed">stop when succeed（成功即停止）</option></select>` : '<span class="muted">必须成功</span>';
    row.innerHTML = `<span class="pipeline-step-index">${index + 1}</span><span class="pipeline-step-icon">${step.type === 'case' ? 'C' : '↻'}</span><span class="pipeline-step-main"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(subtitle)}</span></span>${expectation}<span class="pipeline-step-actions"><button data-up title="上移">↑</button><button data-down title="下移">↓</button><button data-delete title="删除">×</button></span>`;
    const select = row.querySelector('[data-expectation]');
    const enabled = document.createElement('label');
    enabled.style.cssText = 'display:flex;align-items:center;gap:6px;font-size:14px';
    if (step.type === 'case') {
      const mode = document.createElement('select');
      mode.setAttribute('aria-label', `步骤执行方式 ${index + 1}：${title}`);
      mode.innerHTML = '<option value="run">运行</option><option value="skip">跳过</option><option value="manual">人工</option>';
      mode.value = step.executionMode || (step.enabled === false ? 'skip' : 'run');
      mode.onchange = () => {
        step.executionMode = mode.value;
        delete step.enabled;
        if (mode.value !== 'manual') delete step.confirmTimeoutSeconds;
        renderPipelineSteps();
      };
      enabled.append(mode);
      if (mode.value === 'manual') {
        const timeout = document.createElement('input');
        timeout.type = 'number'; timeout.min = 1; timeout.max = 86400;
        timeout.value = step.confirmTimeoutSeconds || 120;
        timeout.setAttribute('aria-label', '人工确认超时（秒）');
        timeout.oninput = () => { step.confirmTimeoutSeconds = Number(timeout.value); };
        enabled.append(document.createTextNode('确认超时（秒）'), timeout);
      }
    } else {
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = step.enabled !== false;
    checkbox.setAttribute('aria-label', `运行步骤 ${index + 1}：${title}`);
    checkbox.onchange = () => { step.enabled = checkbox.checked; renderPipelineSteps(); };
    enabled.append(checkbox, document.createTextNode(step.enabled === false ? '已跳过' : '运行'));
    }
    row.querySelector('.pipeline-step-main').append(enabled);
    if (step.type === 'action' && step.action === 'human-test') {
      const settings = document.createElement('div');
      settings.className = 'pipeline-step-result';
      settings.innerHTML = '<label>用户操作说明<textarea aria-label="用户操作说明"></textarea></label><label>等待确认超时（秒）<input type="number" min="1" max="86400" aria-label="等待确认超时（秒）"></label><p>未确认时循环提示音；超时跳过。确认后由用户提交结果。</p>';
      settings.querySelector('textarea').value = step.humanInstructions || '';
      settings.querySelector('textarea').oninput = e => { step.humanInstructions = e.target.value; };
      settings.querySelector('input').value = step.confirmTimeoutSeconds || 120;
      settings.querySelector('input').oninput = e => { step.confirmTimeoutSeconds = Number(e.target.value); };
      row.append(settings);
    }
    if (step.type === 'action' && step.action === 'include-pipeline') {
      const settings = document.createElement('label');
      settings.className = 'pipeline-step-result';
      settings.append('引入 Pipeline ');
      const select = document.createElement('select');
      select.add(new Option('请选择 Pipeline', ''));
      for (const candidate of catalogData?.pipelines || []) {
        if (candidate.id !== activePipeline?.id && candidate.enabled !== false) {
          select.add(new Option(candidate.name + ' · ' + candidate.id, candidate.id));
        }
      }
      if (step.pipelineId && !Array.from(select.options).some(option => option.value === step.pipelineId)) {
        select.add(new Option('不可用：' + step.pipelineId, step.pipelineId));
      }
      select.value = step.pipelineId || '';
      select.onchange = () => { step.pipelineId = select.value; };
      settings.append(select);
      row.append(settings);
    }
    if (step.type === 'action' && step.action === 'start-helper') {
      const settings = document.createElement('div');
      settings.className = 'pipeline-step-result';
      settings.innerHTML = `<label>测试账号登录 <select data-login><option value="none">不登录（保留现有 Session）</option><option value="auto">自动分配测试账号</option><option value="selected">指定测试账号</option></select></label>`;
      const login = settings.querySelector('select');
      login.value = step.loginMode || 'none';
      login.onchange = () => { step.loginMode = login.value; if (login.value === 'selected') step.accountEmail = 'test1@ai2apps.com'; else delete step.accountEmail; renderPipelineSteps(); };
      if (step.loginMode === 'selected') {
        const account = document.createElement('select');
        account.setAttribute('aria-label', '测试账号');
        account.innerHTML = Array.from({length: 10}, (_, i) => `<option>test${i + 1}@ai2apps.com</option>`).join('');
        account.value = step.accountEmail || '';
        account.onchange = () => { step.accountEmail = account.value; };
        settings.append(account);
      }
      row.append(settings);
    }
    if (step.type === 'case') {
      const heading = row.querySelector('.pipeline-step-main strong');
      const edit = document.createElement('button');
      edit.className = 'pipeline-case-title';
      edit.textContent = title;
      edit.title = '编辑 Case 内容';
      edit.onclick = () => openPipelineCaseEditor(step);
      heading.replaceWith(edit);
    }
    if (select) { select.value = step.expectedStatus || 'passed'; select.onchange = () => { step.expectedStatus = select.value; renderPipelineSteps(); }; }
    if (pipelineLastRun) {
      const previous = pipelineLastRun.steps[step.id];
      const result = document.createElement('div');
      result.className = 'pipeline-step-result';
      const matches = previous && (step.type === 'case' ? previous.sourceCaseId === step.caseId : previous.action === step.action && (step.action !== 'include-pipeline' || previous.pipelineId === step.pipelineId));
      if (!matches) {
        result.textContent = '上次运行：此步骤未执行';
      } else {
        const changed = previous.index !== index || previous.expectedStatus !== (step.expectedStatus || 'passed') || (source?.revision && source.revision !== previous.caseRevision) || JSON.stringify(previous.caseContent || {}) !== JSON.stringify(step.caseContent || {});
        const badge = statusNode(previous.status);
        result.append('上次运行：', badge);
        if (previous.observedStatus) result.append(' · 实际 ' + previous.observedStatus);
        if (changed || (step.type === 'case' && previous.executionMode !== (step.executionMode || (step.enabled === false ? 'skip' : 'run'))) || (step.action === 'start-helper' && (previous.loginMode !== (step.loginMode || 'none') || (previous.accountEmail || '') !== (step.accountEmail || '')))) result.append(' · 步骤或 Case 已修改，需重新验证');
        if (previous.summary) {
          const summary = document.createElement('div');
          summary.textContent = previous.summary;
          result.append(summary);
        }
      }
      row.append(result);
    }
    row.querySelector('[data-up]').onclick = () => movePipelineStep(index, -1);
    row.querySelector('[data-down]').onclick = () => movePipelineStep(index, 1);
    row.querySelector('[data-delete]').onclick = () => { pipelineSteps.splice(index, 1); selectedPipelineStep = -1; renderPipelineSteps(); };
    $('pipeline-steps').append(row);
  });
}

function movePipelineStep(index, delta) {
  const target = index + delta;
  if (target < 0 || target >= pipelineSteps.length) return;
  [pipelineSteps[index], pipelineSteps[target]] = [pipelineSteps[target], pipelineSteps[index]];
  selectedPipelineStep = target;
  renderPipelineSteps();
}

async function openPipelineCaseEditor(step) {
  let source;
  try { source = await catalogApi('/api/catalog/cases/' + encodeURIComponent(step.caseId) + '/content'); }
  catch (error) { showToast(error.message); return; }
  if (!source) { showToast('Case 定义不存在，请刷新测试库后重试'); return; }
  editingPipelineStep = step;
  editingSharedCase = source;
  const content = source;
  $('pipeline-case-identity').textContent = `ID：${step.caseId}\nGroup：${source.group || source.groupId}\n执行器：${source.executor}\n能力依赖：${(source.requires || []).join('、') || '无'}`;
  for (const field of ['name', 'description', 'instructions', 'expectations', 'cleanup']) {
    const value = content[field];
    $('pipeline-case-' + field).value = Array.isArray(value) ? value.join('\n') : (value || '');
  }
  $('pipeline-case-edit-error').textContent = '';
  $('pipeline-case-edit-dialog').classList.remove('hidden');
  $('pipeline-case-name').focus();
}

function closePipelineCaseEditor() {
  $('pipeline-case-edit-dialog').classList.add('hidden');
  editingPipelineStep = null;
}

async function applyPipelineCaseEditor() {
  if (!editingPipelineStep) return;
  const content = {};
  for (const field of ['name', 'description']) content[field] = $('pipeline-case-' + field).value.trim();
  for (const field of ['instructions', 'expectations', 'cleanup']) content[field] = $('pipeline-case-' + field).value.split('\n').map(line => line.trim()).filter(Boolean);
  try {
    await catalogApi('/api/catalog/cases/' + encodeURIComponent(editingPipelineStep.caseId) + '/content', {method: 'PUT', headers: {'content-type': 'application/json'}, body: JSON.stringify({revision: editingSharedCase.revision || '', content})});
    catalogData = await catalogApi('/api/catalog');
    closePipelineCaseEditor();
    renderPipelineSteps();
    renderCaseList();
    if (editingKind === 'cases' && activeObject?.id === editingSharedCase.id) {
      const updated = catalogData.cases.find(item => item.id === editingSharedCase.id);
      if (updated) await editObject('cases', updated);
    }
    showToast('共享 Case 已保存，所有 Pipeline 的同 ID 引用均已更新');
  } catch (error) { $('pipeline-case-edit-error').textContent = error.message; }
}

function openPipelineCasePicker(mode) {
  pipelineInsertMode = mode;
  const runnable = catalogData.cases.filter(item => item.runnable);
  const groupIds = [...new Set(runnable.map(item => groupId(item)))];
  $('pipeline-case-group').innerHTML = groupIds.map(id => {
    const group = catalogData.groups.find(item => item.id === id);
    return `<option value="${escapeHtml(id)}">${escapeHtml(group?.name || id)}</option>`;
  }).join('');
  renderPipelineCaseOptions();
  $('pipeline-cases-dialog').classList.remove('hidden');
}

function renderPipelineCaseOptions() {
  const id = $('pipeline-case-group').value;
  const values = catalogData.cases.filter(item => item.runnable && groupId(item) === id);
  $('pipeline-case-options').innerHTML = values.map(item => `<label class="pipeline-case-option"><input type="checkbox" value="${escapeHtml(item.id)}"><span><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.id)} · ${escapeHtml(item.priority || '按需')}</span></span></label>`).join('') || '<div class="review-item muted">这个 Group 没有可运行 Case。</div>';
}

function confirmPipelineCases() {
  const ids = [...$('pipeline-case-options').querySelectorAll('input:checked')].map(input => input.value);
  if (!ids.length) return;
  const used = new Set(pipelineSteps.map(step => step.id));
  let serial = 1;
  const additions = ids.map(caseId => {
    while (used.has('step-' + serial)) serial++;
    const id = 'step-' + serial++;
    used.add(id);
    return {id, type: 'case', caseId, expectedStatus: 'passed'};
  });
  let index = pipelineSteps.length;
  if (pipelineInsertMode === 'insert' && selectedPipelineStep >= 0) index = selectedPipelineStep;
  pipelineSteps.splice(index, 0, ...additions);
  $('pipeline-cases-dialog').classList.add('hidden');
  selectedPipelineStep = index;
  renderPipelineSteps();
}

function appendPipelineAction() {
  const step = {id: nextPipelineStepId(), type: 'action', action: $('pipeline-action').value};
  if (step.action === 'include-pipeline') step.pipelineId = '';
  if (step.action === 'human-test') Object.assign(step, {humanInstructions: '请在 Test App 中完成测试，并提交结果。', confirmTimeoutSeconds: 120});
  const index = selectedPipelineStep >= 0 ? selectedPipelineStep + 1 : pipelineSteps.length;
  pipelineSteps.splice(index, 0, step);
  selectedPipelineStep = index;
  renderPipelineSteps();
}

function pipelineValue() {
  return {schemaVersion: 1, id: $('pipeline-id').value.trim(), name: $('pipeline-name').value.trim(), description: $('pipeline-description').value.trim(), enabled: $('pipeline-enabled').checked, steps: pipelineSteps};
}

function savedPipelineValue() {
  if (!activePipeline) return null;
  return {schemaVersion: activePipeline.schemaVersion || 1, id: activePipeline.id, name: activePipeline.name, description: activePipeline.description || '', enabled: Boolean(activePipeline.enabled), steps: activePipeline.steps || []};
}

function showPipelineErrors(errors) {
  $('pipeline-errors').textContent = (errors || []).map(error => '• ' + error).join('\n');
  $('pipeline-errors').classList.toggle('hidden', !(errors || []).length);
}

async function validatePipelineEditor() {
  try {
    const value = pipelineValue();
    if (pipelineRevision) value.revision = pipelineRevision;
    const result = await catalogApi('/api/catalog/pipelines/' + encodeURIComponent(value.id) + '/validate', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(value)});
    showPipelineErrors(result.errors || []);
    $('pipeline-diff').textContent = result.diff || '没有文件变化';
    $('pipeline-diff-shell').classList.toggle('hidden', !result.ok);
    return result.ok;
  } catch (error) { showPipelineErrors([error.message]); return false; }
}

async function savePipelineEditor() {
  if (!await validatePipelineEditor()) return;
  const value = pipelineValue();
  if (pipelineRevision) value.revision = pipelineRevision;
  try {
    const saved = await catalogApi('/api/catalog/pipelines' + (pipelineRevision ? '/' + encodeURIComponent(value.id) : ''), {method: pipelineRevision ? 'PUT' : 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(value)});
    showToast('Pipeline 已保存');
    await refreshPipelines();
    await editPipeline(saved.id);
  } catch (error) { showPipelineErrors([error.message]); }
}

let pipelineSaveAsDraft = null;
function openPipelineSaveAs() {
  pipelineSaveAsDraft = structuredClone(pipelineValue());
  $('pipeline-save-as-id').value = pipelineSaveAsDraft.id.slice(0, 123) + '-copy';
  $('pipeline-save-as-name').value = pipelineSaveAsDraft.name + ' 副本';
  $('pipeline-save-as-error').textContent = '';
  $('pipeline-save-as-dialog').classList.remove('hidden');
  $('pipeline-save-as-id').focus();
}

async function confirmPipelineSaveAs() {
  const value = {...pipelineSaveAsDraft, id: $('pipeline-save-as-id').value.trim(), name: $('pipeline-save-as-name').value.trim()};
  const button = $('confirm-pipeline-save-as');
  button.disabled = true;
  try {
    if (!/^[a-z0-9][a-z0-9.-]{0,127}$/.test(value.id)) throw new Error('ID 只能包含小写字母、数字、点和连字符，最长 128 字符');
    if (value.id === pipelineSaveAsDraft.id) throw new Error('请使用不同于原 Pipeline 的新 ID');
    if (!value.name) throw new Error('请填写显示名称');
    // POST without revision is create-only: an existing ID must never be overwritten.
    const saved = await catalogApi('/api/catalog/pipelines', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify(value)});
    $('pipeline-save-as-dialog').classList.add('hidden');
    showToast('已另存为新 Pipeline');
    await refreshPipelines();
    await editPipeline(saved.id);
  } catch (error) { $('pipeline-save-as-error').textContent = error.message; }
  finally { button.disabled = false; }
}

async function runPipeline() {
  if (!pipelineRevision) { showPipelineErrors(['请先保存 Pipeline']); return; }
  if (JSON.stringify(pipelineValue()) !== JSON.stringify(savedPipelineValue())) {
    showPipelineErrors(['Pipeline 有尚未保存的修改，请先保存再运行']);
    return;
  }
  try {
    await catalogApi('/api/catalog/pipelines/' + encodeURIComponent(activePipeline.id) + '/run', {method: 'POST', headers: {'content-type': 'application/json'}, body: '{}'});
    trialContext = null;
    $('return-to-pipeline').classList.add('hidden');
    $('return-to-case').classList.add('hidden');
    $('improve-case').classList.add('hidden');
    $('stop').disabled = false;
    $('stop').textContent = '中止测试';
    await setView('progress');
    $('run-priority').textContent = 'Pipeline · ' + activePipeline.name;
    await updateProgress();
    polling = setInterval(updateProgress, 500);
  } catch (error) { showPipelineErrors([error.message]); }
}

function renderLibrary() {
  const activeGroups = catalogData.groups;
  const archivedGroups = catalogData.archived.groups;
  $('group-total').textContent = activeGroups.length;
  $('all-case-count').textContent = catalogData.cases.length;
  $('archived-count').textContent = archivedGroups.length + catalogData.archived.cases.length;
  renderGroupSection('regular-groups', activeGroups.filter(group => group.kind === 'regular'));
  renderGroupSection('ondemand-groups', activeGroups.filter(group => group.kind === 'on-demand'));
  document.querySelectorAll('.group-filter[data-group]').forEach(button => button.classList.toggle('active', button.dataset.group === activeGroup));
  renderCaseList();
}

function renderGroupSection(targetId, groups) {
  const target = $(targetId);
  target.innerHTML = '';
  for (const group of groups) {
    const button = document.createElement('button');
    button.className = 'group-filter' + (activeGroup === group.id ? ' active' : '');
    button.dataset.group = group.id;
    const count = catalogData.cases.filter(testCase => groupId(testCase) === group.id).length;
    button.innerHTML = `<span class="filter-icon">${group.kind === 'on-demand' ? '◇' : '□'}</span><span title="${escapeHtml(group.name)}">${escapeHtml(group.name)}</span><b>${count}</b>`;
    button.onclick = () => selectGroup(group.id, group);
    target.append(button);
  }
}

function selectGroup(id, group = null) {
  activeGroup = id;
  document.querySelectorAll('.group-filter').forEach(button => button.classList.toggle('active', button.dataset.group === id));
  renderCaseList();
  if (group) editObject('groups', group);
  else closeEditor();
}

function renderCaseList() {
  if (!catalogData) return;
  const query = $('catalog-search').value.trim().toLowerCase();
  const source = $('source-filter').value;
  const executor = $('executor-filter').value;
  const values = casesForGroup(activeGroup).filter(testCase => {
    const matchesText = !query || (String(testCase.name || '') + ' ' + testCase.id).toLowerCase().includes(query);
    return matchesText && (source === 'all' || sourceType(testCase) === source) && (executor === 'all' || testCase.executor === executor);
  });
  const selectedGroup = catalogData.groups.find(group => group.id === activeGroup);
  $('case-list-title').textContent = activeGroup === 'all' ? '全部 Case' : activeGroup === 'archived' ? '已归档资产' : selectedGroup?.name || activeGroup;
  $('case-list-subtitle').textContent = activeGroup === 'archived' ? `另有 ${catalogData.archived.groups.length} 个已归档 Group` : '选择一个 Case 查看详细定义';
  $('visible-case-count').textContent = `显示 ${values.length} 项`;
  const root = $('catalog-items');
  root.innerHTML = '';
  if (!values.length) {
    root.innerHTML = '<div class="empty-state"><div class="empty-icon">⌕</div><h3>没有匹配项</h3><p>调整搜索词或筛选条件后再试。</p></div>';
    return;
  }
  for (const testCase of values) {
    const button = document.createElement('button');
    const archived = Boolean(testCase.archived);
    button.className = 'catalog-item' + (activeObject?.id === testCase.id ? ' active' : '');
    const lifecycle = archived ? 'archived' : (testCase.lifecycle || (testCase.enabled ? 'enabled' : 'draft'));
    button.innerHTML = `<span class="catalog-item-title"><b><i class="source-dot ${escapeHtml(sourceType(testCase))}"></i>${escapeHtml(testCase.name || testCase.id)}</b><span>${escapeHtml(testCase.id)}</span></span><span class="badge">${escapeHtml(testCase.priority || '按需')}</span><span>${escapeHtml(testCase.executor || '—')}</span><span><i class="state-pill ${escapeHtml(lifecycle)}">${escapeHtml(lifecycleLabel[lifecycle] || lifecycle)}</i></span>`;
    button.onclick = () => editObject('cases', testCase, archived);
    root.append(button);
  }
  if (activeGroup === 'archived') {
    for (const group of catalogData.archived.groups) {
      const button = document.createElement('button');
      button.className = 'catalog-item';
      button.innerHTML = `<span class="catalog-item-title"><b><i class="source-dot user-authored"></i>${escapeHtml(group.name || group.id)}</b><span>${escapeHtml(group.id)} · Group</span></span><span>—</span><span>—</span><span><i class="state-pill archived">已归档</i></span>`;
      button.onclick = () => editObject('groups', group, true);
      root.prepend(button);
    }
  }
}

function cleanObject(value) {
  const runtimeFields = new Set(['source_type', 'source_path', 'sourceType', 'sourcePath', 'editable', 'group_id', 'component_id', 'timeout_seconds', 'default_selected', 'group', 'revision', 'command']);
  return Object.fromEntries(Object.entries(value).filter(([key]) => !runtimeFields.has(key)));
}

function defaultGroup() {
  return {schemaVersion: 1, id: 'new-test-group', name: 'New Test Group', description: '', kind: 'on-demand', enabled: false, defaultSelected: false, order: 500, tags: [], lifecycle: 'draft'};
}

function defaultCase() {
  const group = catalogData.groups.find(item => item.editable)?.id || '';
  const groupObject = catalogData.groups.find(item => item.id === group);
  return {schemaVersion: 1, id: 'new.test.case', name: 'New Test Case', groupId: group, priority: groupObject?.kind === 'regular' ? 'P2' : null, enabled: false, required: false, executor: 'codex-ui', timeoutSeconds: 300, requires: [], tags: [], componentId: null, description: '', instructions: ['描述可见的测试操作。'], expectations: ['描述应观察到的结果。'], cleanup: [], fixtures: [], lifecycle: 'draft'};
}

async function editObject(kind, value, archived = false) {
  try {
    if (!archived && value.editable && sourceType(value) === 'user-authored') value = await catalogApi('/api/catalog/' + kind + '/' + encodeURIComponent(value.id));
    activeObject = value;
    editingKind = kind;
    editingRevision = value.revision || null;
    editorArchived = archived;
    editorReadonly = archived || !value.editable && sourceType(value) !== 'user-authored' && Boolean(value.sourceType || value.source_type);
    $('empty-inspector').classList.add('hidden');
    $('editor-shell').classList.remove('hidden');
    $('editor-kind').textContent = kind === 'groups' ? 'GROUP' : 'CASE';
    $('editor-title').textContent = value.name || value.id;
    $('editor-id').textContent = value.id;
    $('readonly-notice').classList.toggle('hidden', !editorReadonly || archived);
    $('advanced-editor').classList.toggle('hidden', editorReadonly);
    renderLifecycle(archived ? 'archived' : value.lifecycle || 'draft');
    renderForm(cleanObject(value));
    syncRawFromForm();
    $('catalog-errors').classList.add('hidden');
    $('catalog-diff-shell').classList.add('hidden');
    $('archive-object').classList.toggle('hidden', editorReadonly || !editingRevision || archived);
    $('restore-object').classList.toggle('hidden', !archived);
    $('copy-object').classList.toggle('hidden', kind !== 'cases');
    $('edit-shared-content').classList.toggle('hidden', kind !== 'cases' || archived || !editorReadonly);
    $('trial-object').classList.toggle('hidden', kind !== 'cases' || editorReadonly || archived || !editingRevision);
    $('validate-object').classList.toggle('hidden', editorReadonly || archived);
    $('save-object').classList.toggle('hidden', editorReadonly || archived);
    renderCaseList();
  } catch (error) {
    showError(error.message);
  }
}

function renderLifecycle(lifecycle) {
  const currentIndex = lifecycleOrder.indexOf(lifecycle);
  $('lifecycle-stepper').innerHTML = lifecycleOrder.map((value, index) => `<span class="life-step ${index < currentIndex ? 'done' : index === currentIndex ? 'current' : ''}">${escapeHtml(lifecycleLabel[value])}</span>`).join('');
}

function field(name, label, value, options = {}) {
  const classes = 'field' + (options.full ? ' full' : '');
  const disabled = editorReadonly || options.disabled ? ' disabled' : '';
  const help = options.help ? `<span class="field-help">${escapeHtml(options.help)}</span>` : '';
  if (options.type === 'checkbox') return `<label class="field check-field"><input data-field="${name}" type="checkbox" ${value ? 'checked' : ''}${disabled}>${escapeHtml(label)}</label>`;
  if (options.choices) {
    const choices = options.choices.map(choice => `<option value="${escapeHtml(choice.value)}" ${String(value ?? '') === String(choice.value) ? 'selected' : ''}>${escapeHtml(choice.label)}</option>`).join('');
    return `<label class="${classes}">${escapeHtml(label)}<select data-field="${name}"${disabled}>${choices}</select>${help}</label>`;
  }
  const type = options.type || 'text';
  return `<label class="${classes}">${escapeHtml(label)}<input data-field="${name}" type="${type}" value="${escapeHtml(value ?? '')}"${disabled}>${help}</label>`;
}

function area(name, label, value, options = {}) {
  const text = Array.isArray(value) ? value.join('\n') : value || '';
  return `<label class="field full">${escapeHtml(label)}<textarea data-field="${name}" data-list="${options.list ? 'true' : 'false'}" ${editorReadonly ? 'disabled' : ''}>${escapeHtml(text)}</textarea>${options.help ? `<span class="field-help">${escapeHtml(options.help)}</span>` : ''}</label>`;
}

function renderForm(value) {
  const lifecycleChoices = lifecycleOrder.filter(item => item !== 'archived').map(item => ({value: item, label: lifecycleLabel[item]}));
  let html = '<section class="form-section"><p class="form-section-title">基本信息</p><div class="form-grid">';
  html += field('id', '稳定 ID', value.id, {full: true, disabled: Boolean(editingRevision), help: '创建后不可修改，只允许小写字母、数字、点和连字符。'});
  html += field('name', '显示名称', value.name, {full: true});
  html += area('description', '说明', value.description, {});
  if (editingKind === 'groups') {
    html += field('kind', '组类型', value.kind, {choices: [{value: 'regular', label: '常规测试'}, {value: 'on-demand', label: '按需测试'}]});
    html += field('order', '显示顺序', value.order ?? 500, {type: 'number'});
    html += field('lifecycle', '生命周期', value.lifecycle || 'draft', {choices: lifecycleChoices});
    html += field('enabled', '启用 Group', value.enabled, {type: 'checkbox'});
    html += field('defaultSelected', '默认选中', value.defaultSelected, {type: 'checkbox', help: '按需 Group 不允许默认选中。'});
    html += area('tags', '标签（每行一个）', value.tags, {list: true});
  } else {
    const groups = catalogData.groups.filter(group => group.editable).map(group => ({value: group.id, label: group.name + (group.kind === 'on-demand' ? ' · 按需' : '')}));
    if (value.groupId && !groups.some(group => group.value === value.groupId)) groups.unshift({value: value.groupId, label: value.groupId + ' · 只读来源'});
    html += field('groupId', '所属 Group', value.groupId, {choices: groups});
    html += field('priority', '优先级', value.priority ?? '', {choices: [{value: '', label: '按需 / 无优先级'}, ...Object.keys(rank).map(item => ({value: item, label: item}))]});
    const executorChoices = [{value: 'codex-ui', label: 'Codex UI'}, {value: 'builtin', label: 'Builtin'}];
    if (value.executor === 'command') executorChoices.push({value: 'command', label: 'Command · 只读官方执行器'});
    html += field('executor', '执行器', value.executor, {choices: executorChoices});
    html += field('timeoutSeconds', '超时（秒）', value.timeoutSeconds ?? 300, {type: 'number'});
    html += field('lifecycle', '生命周期', value.lifecycle || 'draft', {choices: lifecycleChoices});
    html += field('componentId', '组件 ID（可选）', value.componentId || '');
    html += field('enabled', '启用 Case', value.enabled, {type: 'checkbox'});
    html += field('required', '影响运行结论', value.required, {type: 'checkbox'});
    html += area('requires', '能力依赖（每行一个）', value.requires, {list: true});
    html += area('tags', '标签（每行一个）', value.tags, {list: true});
    html += '</div></section><section class="form-section"><p class="form-section-title">执行合同</p><div class="form-grid">';
    html += area('instructions', '操作步骤（每行一步）', value.instructions, {list: true, help: '描述 Codex 应执行的可见操作，不要填写命令或秘密。'});
    html += area('expectations', '预期结果（每行一项）', value.expectations, {list: true});
    html += area('cleanup', '清理动作（每行一项）', value.cleanup, {list: true});
    html += area('fixtures', '受管理测试素材（每行一个）', value.fixtures, {list: true, help: '由试运行复盘上传并生成；路径必须位于 tests/ats/fixtures/<case-id>/。'});
  }
  html += '</div></section>';
  $('catalog-form').innerHTML = html;
  $('catalog-form').querySelectorAll('[data-field]').forEach(control => {
    control.addEventListener('input', () => { syncRawFromForm(); $('catalog-diff-shell').classList.add('hidden'); });
    control.addEventListener('change', () => { adaptCasePriority(control); syncRawFromForm(); });
  });
}

function adaptCasePriority(control) {
  if (editingKind !== 'cases' || control.dataset.field !== 'groupId') return;
  const group = catalogData.groups.find(item => item.id === control.value);
  const priorityControl = $('catalog-form').querySelector('[data-field="priority"]');
  if (group?.kind === 'on-demand') priorityControl.value = '';
  else if (!priorityControl.value) priorityControl.value = 'P2';
}

function valueFromForm() {
  const value = {schemaVersion: 1};
  for (const control of $('catalog-form').querySelectorAll('[data-field]')) {
    let fieldValue = control.type === 'checkbox' ? control.checked : control.value;
    if (control.dataset.list === 'true') fieldValue = control.value.split('\n').map(item => item.trim()).filter(Boolean);
    if (control.type === 'number') fieldValue = Number(control.value);
    if (control.dataset.field === 'priority' && fieldValue === '') fieldValue = null;
    if (control.dataset.field === 'componentId' && fieldValue === '') fieldValue = null;
    value[control.dataset.field] = fieldValue;
  }
  return value;
}

function syncRawFromForm() {
  if (!$('catalog-form').children.length || editorReadonly) return;
  $('catalog-editor').value = JSON.stringify(valueFromForm(), null, 2);
  const lifecycle = $('catalog-form').querySelector('[data-field="lifecycle"]')?.value || 'draft';
  renderLifecycle(lifecycle);
}

function showFormErrors(errors) {
  const target = $('catalog-errors');
  target.textContent = errors.filter(Boolean).map(error => '• ' + error).join('\n');
  target.classList.toggle('hidden', !errors.length);
}

async function validateEditor() {
  try {
    const value = valueFromForm();
    if (editingRevision) value.revision = editingRevision;
    const result = await catalogApi('/api/catalog/' + editingKind + '/' + encodeURIComponent(value.id) + '/validate', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(value)});
    showFormErrors(result.errors || []);
    $('catalog-diff').textContent = result.diff || '没有文件变化';
    $('catalog-diff-shell').classList.toggle('hidden', !result.ok);
    if (result.ok) showToast('校验通过，可以保存');
    return result.ok;
  } catch (error) {
    showFormErrors([error.message]);
    return false;
  }
}

async function saveEditor() {
  if (!await validateEditor()) return;
  try {
    const value = valueFromForm();
    if (editingRevision) value.revision = editingRevision;
    const method = editingRevision ? 'PUT' : 'POST';
    const path = '/api/catalog/' + editingKind + (editingRevision ? '/' + encodeURIComponent(value.id) : '');
    const saved = await catalogApi(path, {method, headers: {'content-type': 'application/json'}, body: JSON.stringify(value)});
    showToast('已保存到 Catalog');
    await refreshCatalog(true);
    await editObject(editingKind, saved);
  } catch (error) {
    showFormErrors([error.message]);
  }
}

async function archiveObject() {
  if (!activeObject || !confirm(`归档 ${activeObject.id}？内容可以恢复。`)) return;
  try {
    await catalogApi(`/api/catalog/${editingKind}/${encodeURIComponent(activeObject.id)}/archive`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({revision: editingRevision})});
    showToast(editingKind === 'groups' ? 'Group 及其自定义 Case 已归档' : 'Case 已归档');
    await refreshCatalog();
  } catch (error) { showFormErrors([error.message]); }
}

async function restoreObject() {
  try {
    await catalogApi(`/api/catalog/${editingKind}/${encodeURIComponent(activeObject.id)}/restore`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({revision: activeObject.revision})});
    showToast('已恢复到测试库');
    activeGroup = 'all';
    await refreshCatalog();
  } catch (error) { showFormErrors([error.message]); }
}

function openCopyDialog() {
  if (!activeObject || editingKind !== 'cases') return;
  copySource = activeObject;
  $('copy-id').value = activeObject.id + '.copy';
  const groups = catalogData.groups.filter(group => group.editable && !group.archived);
  $('copy-group').innerHTML = groups.map(group => `<option value="${escapeHtml(group.id)}">${escapeHtml(group.name)}</option>`).join('');
  $('copy-error').classList.add('hidden');
  $('copy-dialog').classList.remove('hidden');
}

function closeCopyDialog() { $('copy-dialog').classList.add('hidden'); }

async function confirmCopy() {
  try {
    const created = await catalogApi('/api/catalog/cases/' + encodeURIComponent(copySource.id) + '/copy', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({id: $('copy-id').value.trim(), groupId: $('copy-group').value})});
    closeCopyDialog();
    showToast('自定义副本已创建');
    activeGroup = created.groupId;
    await refreshCatalog(true);
    await editObject('cases', created);
  } catch (error) {
    $('copy-error').textContent = error.message;
    $('copy-error').classList.remove('hidden');
  }
}

function openGenerateDialog() {
  const groups = catalogData.groups.filter(group => group.editable);
  $('generate-group').innerHTML = groups.length
    ? groups.map(group => `<option value="${escapeHtml(group.id)}">${escapeHtml(group.name)}${group.kind === 'on-demand' ? ' · 按需' : ''}</option>`).join('')
    : '<option value="">请先创建自定义 Group</option>';
  const preferred = groups.find(group => group.id === activeGroup);
  if (preferred) $('generate-group').value = preferred.id;
  $('generate-description').value = '';
  $('generate-error').textContent = groups.length ? '' : '当前没有可写的自定义 Group。你可以先填写描述，但生成前需要新建 Group。';
  $('generate-error').classList.toggle('hidden', Boolean(groups.length));
  $('generate-status').classList.add('hidden');
  generatingCase = false;
  $('confirm-generate').disabled = !groups.length;
  $('cancel-generate').disabled = false;
  $('close-generate').disabled = false;
  $('generate-dialog').classList.remove('hidden');
  $('generate-description').focus();
}

function closeGenerateDialog() {
  if (generatingCase) return;
  $('generate-dialog').classList.add('hidden');
}

async function generateCase() {
  const description = $('generate-description').value.trim();
  if (!$('generate-group').value) {
    $('generate-error').textContent = '请先创建并选择一个自定义 Group。';
    $('generate-error').classList.remove('hidden');
    return;
  }
  if (!description) {
    $('generate-error').textContent = '请先描述要测试什么。';
    $('generate-error').classList.remove('hidden');
    return;
  }
  $('generate-error').classList.add('hidden');
  $('generate-status').classList.remove('hidden');
  generatingCase = true;
  $('confirm-generate').disabled = true;
  $('cancel-generate').disabled = true;
  $('close-generate').disabled = true;
  try {
    const draft = await catalogApi('/api/catalog/cases/generate', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({description, groupId: $('generate-group').value})
    });
    $('generate-dialog').classList.add('hidden');
    activeGroup = draft.groupId;
    showToast('Codex 已生成草稿，请检查后保存');
    await editObject('cases', draft);
  } catch (error) {
    $('generate-error').textContent = error.message;
    $('generate-error').classList.remove('hidden');
  } finally {
    generatingCase = false;
    $('generate-status').classList.add('hidden');
    $('confirm-generate').disabled = false;
    $('cancel-generate').disabled = false;
    $('close-generate').disabled = false;
  }
}

async function trialCase() {
  try {
    const context = {caseId: activeObject.id, groupId: groupId(activeObject)};
    await catalogApi('/api/catalog/cases/' + encodeURIComponent(activeObject.id) + '/trial-run', {method: 'POST', headers: {'content-type': 'application/json'}, body: '{}'});
    trialContext = context;
    sessionStorage.setItem('ai2apps-test-trial-context', JSON.stringify(context));
    $('return-to-case').classList.add('hidden');
    $('improve-case').classList.add('hidden');
    $('stop').disabled = false;
    $('stop').textContent = '中止测试';
    await setView('progress');
    $('run-priority').textContent = '隔离试运行';
    await updateProgress();
    polling = setInterval(updateProgress, 500);
  } catch (error) { showFormErrors([error.message]); }
}

async function returnToTrialCase(proposal = null) {
  if (!trialContext) return;
  const context = trialContext;
  try {
    await catalogApi('/api/catalog/trial/return', {method: 'POST', headers: {'content-type': 'application/json'}, body: '{}'});
    await setView('management');
    activeGroup = context.groupId || 'all';
    renderLibrary();
    const testCase = proposal || catalogData?.cases.find(item => item.id === context.caseId);
    if (!testCase) {
      showError('找不到刚才试运行的 Case：' + context.caseId);
      return;
    }
    await editObject('cases', testCase);
    trialContext = null;
    sessionStorage.removeItem('ai2apps-test-trial-context');
    showToast('已返回试运行 Case，可根据结果继续修改');
  } catch (error) {
    showToast('暂时无法返回 Case：' + error.message);
  }
}

function closeTrialReview() {
  if (reviewingTrial) return;
  $('review-dialog').classList.add('hidden');
}

async function requestTrialReview() {
  if (!trialContext || reviewingTrial) return;
  reviewingTrial = true;
  $('review-dialog').classList.remove('hidden');
  $('review-loading').classList.remove('hidden');
  $('review-content').classList.add('hidden');
  $('review-error').classList.add('hidden');
  $('reanalyze-review').classList.add('hidden');
  $('apply-review').classList.add('hidden');
  $('close-review').disabled = true;
  $('cancel-review').disabled = true;
  try {
    trialReview = await catalogApi('/api/catalog/cases/' + encodeURIComponent(trialContext.caseId) + '/trial-review', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({supplements: reviewSupplements})
    });
    renderTrialReview(trialReview);
  } catch (error) {
    $('review-error').textContent = error.message;
    $('review-error').classList.remove('hidden');
  } finally {
    reviewingTrial = false;
    $('review-loading').classList.add('hidden');
    $('close-review').disabled = false;
    $('cancel-review').disabled = false;
  }
}

function renderTrialReview(review) {
  $('review-summary').textContent = review.summary || 'Codex 已完成复盘。';
  $('review-assessment').textContent = review.resultAssessment || '';
  const changes = review.automaticChanges || [];
  $('review-changes').innerHTML = changes.length
    ? changes.map(item => `<div class="review-item"><strong>${escapeHtml(item.field)}</strong>${escapeHtml(item.reason)}</div>`).join('')
    : '<div class="review-item muted">没有建议自动修改的字段。</div>';
  const requests = review.userRequests || [];
  $('review-user-section').classList.toggle('hidden', !requests.length);
  $('review-user-requests').innerHTML = requests.map(item => {
    const criteria = (item.acceptanceCriteria || []).map(value => `<li>${escapeHtml(value)}</li>`).join('');
    let input = `<label>补充说明<textarea data-request-note placeholder="请填写 Codex 后续判断所需的事实或说明"></textarea></label>`;
    if (item.kind === 'image') input = `<label>选择图片（PNG、JPEG、WebP 或 GIF，最大 10 MB）<input data-request-file type="file" accept=".png,.jpg,.jpeg,.webp,.gif,image/png,image/jpeg,image/webp,image/gif"></label>${input}`;
    if (item.kind === 'confirmation') input = `<label class="check-field"><input data-request-confirm type="checkbox">我已确认此条件</label>${input}`;
    return `<div class="review-item review-request" data-request-id="${escapeHtml(item.id)}" data-request-kind="${escapeHtml(item.kind)}" data-request-required="${item.required ? 'true' : 'false'}"><strong>${escapeHtml(item.title)} ${item.required ? '<span class="request-required">必需</span>' : ''}</strong><div>${escapeHtml(item.description)}</div><div class="muted">为什么需要：${escapeHtml(item.why)}</div>${criteria ? `<ul>${criteria}</ul>` : ''}${input}</div>`;
  }).join('');
  const issues = review.nonCaseIssues || [];
  $('review-noncase-section').classList.toggle('hidden', !issues.length);
  $('review-noncase').innerHTML = issues.map(item => `<div class="review-item"><strong>${escapeHtml(item.category)} · ${escapeHtml(item.summary)}</strong>${escapeHtml(item.recommendation)}</div>`).join('');
  $('review-diff').textContent = review.diff || '当前没有 Case 字段变化。';
  $('review-content').classList.remove('hidden');
  $('reanalyze-review').classList.toggle('hidden', !requests.length);
  $('apply-review').classList.toggle('hidden', !review.readyToApply || !review.hasChanges);
}

function fileBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('无法读取所选图片'));
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '');
    reader.readAsDataURL(file);
  });
}

async function reanalyzeTrialReview() {
  if (reviewingTrial) return;
  const values = new Map(reviewSupplements.map(item => [item.requestId, item]));
  try {
    for (const card of $('review-user-requests').querySelectorAll('.review-request')) {
      const requestId = card.dataset.requestId;
      const kind = card.dataset.requestKind;
      const required = card.dataset.requestRequired === 'true';
      const note = card.querySelector('[data-request-note]')?.value.trim() || '';
      let fixturePath = values.get(requestId)?.fixturePath || '';
      if (kind === 'image') {
        const file = card.querySelector('[data-request-file]')?.files[0];
        if (file) {
          if (file.size > 10 * 1024 * 1024) throw new Error('图片不能超过 10 MB：' + file.name);
          const stored = await catalogApi('/api/catalog/cases/' + encodeURIComponent(trialContext.caseId) + '/fixtures', {
            method: 'POST',
            headers: {'content-type': 'application/json'},
            body: JSON.stringify({filename: file.name, contentBase64: await fileBase64(file)})
          });
          fixturePath = stored.path;
        }
      }
      const confirmed = card.querySelector('[data-request-confirm]')?.checked || false;
      if (required && kind === 'image' && !fixturePath) throw new Error('请为“' + requestId + '”选择图片');
      if (required && kind === 'text' && !note) throw new Error('请填写“' + requestId + '”的补充说明');
      if (required && kind === 'confirmation' && !confirmed) throw new Error('请确认“' + requestId + '”');
      if (note || fixturePath || confirmed) values.set(requestId, {requestId, note: note || (confirmed ? '用户已确认' : ''), fixturePath});
    }
    reviewSupplements = [...values.values()];
    await requestTrialReview();
  } catch (error) {
    $('review-error').textContent = error.message;
    $('review-error').classList.remove('hidden');
  }
}

async function applyTrialReview() {
  if (!trialReview?.readyToApply || !trialReview.proposal) return;
  closeTrialReview();
  await returnToTrialCase(trialReview.proposal);
  showToast('修订已应用到编辑器，请检查 Diff 后保存');
}

function closeEditor() {
  activeObject = null;
  editingRevision = null;
  $('editor-shell').classList.add('hidden');
  $('empty-inspector').classList.remove('hidden');
  renderCaseList();
}

async function refreshDiagnostics() {
  try {
    if (!catalogData) catalogData = await catalogApi('/api/catalog');
    const diagnostics = catalogData.diagnostics;
    const disabled = diagnostics.disabledOrArchived.groups + diagnostics.disabledOrArchived.cases;
    const cards = [
      ['newlyDiscovered', '新发现组件', diagnostics.newlyDiscovered.length, 'attention'],
      ['uncovered', '未覆盖组件', diagnostics.uncovered.length, diagnostics.uncovered.length ? 'problem' : 'healthy'],
      ['staleReferences', '失效引用', diagnostics.staleReferences.length, diagnostics.staleReferences.length ? 'problem' : 'healthy'],
      ['changedContracts', '合同变化', diagnostics.changedContracts.length, diagnostics.changedContracts.length ? 'attention' : 'healthy'],
      ['disabledOrArchived', '停用 / 归档', disabled, '']
    ];
    $('diagnostic-cards').innerHTML = cards.map(card => `<article class="diagnostic-card ${card[3]}"><strong>${card[2]}</strong><span>${card[1]}</span></article>`).join('');
    const explanations = {
      newlyDiscovered: ['新发现组件', '当前 Inventory 中存在，但尚未进入已审阅基线。'],
      uncovered: ['未覆盖组件', '没有任何 Test Case 引用这些组件。'],
      staleReferences: ['失效引用', 'Case 指向的组件已不在当前 Inventory。'],
      changedContracts: ['合同变化', '组件类型、发布状态或元数据与审阅基线不同。']
    };
    $('diagnostic-sections').innerHTML = Object.entries(explanations).map(([key, copy]) => {
      const values = diagnostics[key] || [];
      return `<article class="diagnostic-section"><h3>${copy[0]} <span class="count-badge">${values.length}</span></h3><p>${copy[1]}</p>${values.length ? values.map(value => `<div class="diagnostic-row">${escapeHtml(value)}</div>`).join('') : '<div class="empty-good">✓ 当前没有发现问题</div>'}</article>`;
    }).join('');
  } catch (error) { showToast('诊断读取失败：' + error.message); }
}

function statusNode(status) {
  const span = document.createElement('span');
  span.className = 'status status-' + status;
  span.textContent = status;
  return span;
}

function renderCases(groups) {
  const root = $('progress-groups');
  root.innerHTML = '';
  for (const group of groups) {
    const box = document.createElement('section');
    box.className = 'group';
    const head = document.createElement('div');
    head.className = 'group-head';
    head.textContent = group.name + ' · ' + group.completed + '/' + group.total;
    box.append(head);
    const cases = document.createElement('div');
    cases.className = 'cases';
    for (const testCase of group.cases) {
      const row = document.createElement('div');
      row.className = 'progress-case';
      const badge = document.createElement('span');
      badge.className = 'badge';
      badge.textContent = testCase.priority || '按需';
      const content = document.createElement('div');
      content.textContent = testCase.name;
      const timing = document.createElement('div');
      timing.className = 'case-expectation';
      const elapsed = testCase.durationSeconds ?? (testCase.startedAt && testCase.status === 'running' ? Math.max(0, (Date.now() - Date.parse(testCase.startedAt)) / 1000) : null);
      timing.textContent = elapsed === null ? '耗时：—' : `耗时：${elapsed.toFixed(1)} 秒`;
      content.append(timing);
      if (testCase.expectedStatus) {
        const expectation = document.createElement('div');
        expectation.className = 'case-expectation';
        const observed = testCase.observedStatus ? ' · 实际 ' + testCase.observedStatus : '';
        expectation.textContent = '期待 ' + testCase.expectedStatus + observed;
        content.append(expectation);
      }
      if (testCase.summary && ['failed', 'blocked'].includes(testCase.status)) {
        const summary = document.createElement('div');
        summary.className = 'case-summary';
        summary.textContent = testCase.summary;
        content.append(summary);
      }
      row.append(statusNode(testCase.status), badge, content);
      cases.append(row);
    }
    box.append(cases);
    root.append(box);
  }
}

function artifactLink(path, label = path) {
  const url = '/artifacts/' + encodeURIComponent(token) + '/' + path.split('/').map(encodeURIComponent).join('/');
  return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
}

async function returnToPipeline() {
  try {
    const result = await catalogApi('/api/catalog/pipeline/return', {method: 'POST', headers: {'content-type': 'application/json'}, body: '{}'});
    clearInterval(polling);
    await setView('pipelines');
    await editPipeline(result.pipelineId);
  } catch (error) { showToast(error.message); }
}

function renderIssues(issues) {
  $('issue-count').textContent = issues.length;
  $('issues').classList.toggle('hidden', !issues.length);
  $('issue-list').innerHTML = '';
  for (const issue of issues) {
    const item = document.createElement('div');
    item.className = 'issue';
    item.innerHTML = `<div class="issue-title">${escapeHtml(issue.group)} · ${escapeHtml(issue.name)}</div><div class="issue-summary">${escapeHtml(issue.summary || issue.status)}</div>`;
    if (issue.detail) item.innerHTML += `<div class="issue-detail">${escapeHtml(issue.detail)}</div>`;
    if (issue.evidence?.length) item.innerHTML += `<div class="muted report">证据：${issue.evidence.map(path => artifactLink(path)).join(' · ')}</div>`;
    $('issue-list').append(item);
  }
}

function renderCodexOutput(output) {
  const entries = output?.entries || [];
  const panel = $('codex-console');
  panel.classList.toggle('hidden', !entries.length);
  if (!entries.length) return;
  const root = $('codex-output');
  const nearBottom = root.scrollHeight - root.scrollTop - root.clientHeight < 50;
  root.innerHTML = entries.map(entry => `<div class="codex-line codex-line-${escapeHtml(entry.status)}"><div>${entry.status === 'running' ? '▶ ' : entry.status === 'failed' ? '✕ ' : '✓ '}${escapeHtml(entry.title)}</div>${entry.detail ? `<div class="codex-detail">${escapeHtml(entry.detail)}</div>` : ''}</div>`).join('');
  if (nearBottom) root.scrollTop = root.scrollHeight;
  $('codex-output-time').textContent = output.updatedAt ? '最近活动 ' + new Date(output.updatedAt).toLocaleTimeString() : '';
}

let humanKey = '';
function renderHumanAction(value) {
  let card = $('human-action-card');
  if (!card) {
    card = document.createElement('section');
    card.id = 'human-action-card';
    card.className = 'card';
    card.tabIndex = -1;
    card.style.cssText = 'padding:24px;border:2px solid #6366f1;margin:16px 0';
    $('current').closest('.page-heading').after(card);
  }
  const visible = value && ['waiting', 'active'].includes(value.phase);
  card.classList.toggle('hidden', !visible);
  if (!visible) { humanKey = ''; return; }
  const key = value.id + value.phase;
  if (humanKey !== key) {
    humanKey = key;
    card.innerHTML = `<h3>用户辅助测试 · ${escapeHtml(value.caseId)}</h3><p style="white-space:pre-wrap">${escapeHtml(value.instructions)}</p><p data-countdown></p><div data-controls></div><p data-error role="alert"></p>`;
    const controls = card.querySelector('[data-controls]');
    if (value.phase === 'waiting') {
      controls.innerHTML = '<button class="button primary" data-action="start">Confirm Start</button> <button class="button secondary" data-action="mute">静音提醒</button>';
    } else {
      controls.innerHTML = '<label>原因（Block / Failed 必填，请勿输入密码等秘密）<textarea data-reason maxlength="4000"></textarea></label><button class="button secondary" data-action="skipped">Skip</button> <button class="button primary" data-action="passed">Pass</button> <button class="button secondary" data-action="blocked">Block</button> <button class="button danger" data-action="failed">Failed</button>';
    }
    controls.querySelectorAll('[data-action]').forEach(button => {
      button.onclick = async () => {
        const reason = controls.querySelector('[data-reason]')?.value || '';
        if (['blocked', 'failed'].includes(button.dataset.action) && !reason.trim()) {
          card.querySelector('[data-error]').textContent = '请填写原因'; return;
        }
        button.disabled = true;
        try {
          const response = await fetch(apiUrl('/api/human-action'), {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id:value.id, action:button.dataset.action, reason})});
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || '提交失败');
          await updateProgress();
        } catch (e) { card.querySelector('[data-error]').textContent = e.message; }
        finally { button.disabled = false; }
      };
    });
    card.scrollIntoView({behavior:'smooth', block:'center'});
    (controls.querySelector('button') || card).focus({preventScroll:true});
  }
  card.querySelector('[data-countdown]').textContent = value.phase === 'waiting' ? `等待确认：${Math.max(0, Math.ceil(value.deadline - Date.now()/1000))} 秒${value.muted ? ' · 已静音' : ' · 每 3 秒提示音'}` : '测试已开始，请操作 Test App 后提交结果。';
  if (value.phase === 'waiting') {
    const expired = Date.now()/1000 >= value.deadline;
    card.querySelector('[data-action="start"]').disabled = expired;
    if (expired) card.querySelector('[data-countdown]').textContent = '确认已超时，正在跳过此步骤…';
  }
}

async function updateProgress() {
  try {
    const status = await (await fetch(apiUrl('/api/status'))).json();
    $('run-status').textContent = status.label;
    $('run-id').textContent = status.runId ? 'Run ' + status.runId : '等待 Run ID';
    $('completed').textContent = status.completed;
    $('passed').textContent = status.counts.passed || 0;
    $('failed').textContent = status.counts.failed || 0;
    $('blocked').textContent = status.counts.blocked || 0;
    $('skipped').textContent = status.counts.skipped || 0;
    $('remaining').textContent = Math.max(0, status.total - status.completed);
    $('progress-bar').style.width = status.percent + '%';
    $('current').textContent = status.error ? '运行错误：' + status.error : status.currentCaseName ? '当前 Case：' + status.currentCaseName : status.message;
    const account = status.testAccount || null;
    $('account').classList.toggle('hidden', !account);
    if (account) $('account').textContent = '测试账号：' + (account.email || '未分配') + ' · ' + account.status + (account.sessionStatus ? ' · ' + account.sessionStatus : '') + (account.heartbeatStatus ? ' · heartbeat ' + account.heartbeatStatus : '') + (account.cleanupStatus ? ' · cleanup ' + account.cleanupStatus : '');
    const driver = status.codexDriver || null;
    $('driver').classList.toggle('hidden', !driver);
    if (driver) $('driver').textContent = 'Codex 执行器：' + driver.status + (driver.summary ? ' · ' + driver.summary : '') + (driver.log ? ' · 日志 ' + driver.log : '');
    renderCodexOutput(status.codexOutput);
    $('handoff').classList.toggle('hidden', !status.handoffPrompt);
    if (status.handoffPrompt) $('handoff-text').textContent = status.handoffPrompt;
    renderIssues(status.issues || []);
    renderCases(status.groups || []);
    renderHumanAction(status.humanAction);
    if (status.report) $('report').innerHTML = '报告：' + artifactLink('report.html', '打开测试报告 ↗');
    $('return-to-case').classList.toggle('hidden', !status.terminal || !trialContext);
    $('return-to-pipeline').classList.toggle('hidden', !status.pipelineId);
    $('return-to-pipeline').disabled = !status.canReturnToPipeline;
    $('improve-case').classList.toggle('hidden', !status.terminal || !trialContext || status.conclusion === 'CANCELLED');
    if (status.terminal) {
      if (!status.pipelineId || status.canReturnToPipeline) clearInterval(polling);
      $('stop').disabled = true;
      $('stop').textContent = status.conclusion === 'CANCELLED' ? '测试已中止' : '测试已结束';
    }
  } catch (error) { $('current').textContent = '暂时无法读取进度，正在重试…'; }
}

async function stop() {
  $('stop').disabled = true;
  $('stop').textContent = '正在中止…';
  await fetch(apiUrl('/api/cancel'), {method: 'POST'});
  await updateProgress();
}

async function copyHandoff() {
  const value = $('handoff-text').textContent;
  try { await navigator.clipboard.writeText(value); }
  catch (error) {
    const input = document.createElement('textarea');
    input.value = value;
    document.body.append(input);
    input.select();
    document.execCommand('copy');
    input.remove();
  }
  $('copy-handoff').textContent = '已复制';
}

const returnPipelineButton = document.createElement('button');
returnPipelineButton.id = 'return-to-pipeline';
returnPipelineButton.className = 'button secondary hidden';
returnPipelineButton.textContent = '← 返回编辑 Pipeline';
returnPipelineButton.onclick = returnToPipeline;
$('stop').before(returnPipelineButton);
document.querySelectorAll('.nav-item').forEach(button => button.onclick = () => setView(button.dataset.view));
document.querySelectorAll('[data-p]').forEach(button => button.onclick = () => selectPriority(button.dataset.p));
document.querySelectorAll('.group-filter[data-group]').forEach(button => button.onclick = () => selectGroup(button.dataset.group));
$('manage').onclick = () => setView('management');
$('all').onclick = () => { for (const group of data.groups) for (const testCase of group.cases) if (eligible(testCase)) selected.add(testCase.id); renderSelection(); };
$('none').onclick = () => { selected.clear(); renderSelection(); };
$('search').oninput = renderSelection;
$('start').onclick = () => begin();
$('cancel').onclick = async () => { await fetch(apiUrl('/api/submit'), {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({cancelled: true})}); document.body.innerHTML = '<main><div class="empty-state"><div class="empty-icon">✓</div><h2>已取消</h2></div></main>'; };
$('refresh-catalog').onclick = () => refreshCatalog(true);
$('new-group').onclick = async () => { activeGroup = 'all'; await editObject('groups', defaultGroup()); };
$('new-case').onclick = openGenerateDialog;
$('catalog-search').oninput = renderCaseList;
$('source-filter').onchange = renderCaseList;
$('executor-filter').onchange = renderCaseList;
$('close-editor').onclick = closeEditor;
$('validate-object').onclick = validateEditor;
$('save-object').onclick = saveEditor;
$('archive-object').onclick = archiveObject;
$('restore-object').onclick = restoreObject;
$('copy-object').onclick = openCopyDialog;
$('edit-shared-content').onclick = () => openPipelineCaseEditor({caseId: activeObject.id});
$('trial-object').onclick = trialCase;
$('close-diff').onclick = () => $('catalog-diff-shell').classList.add('hidden');
$('close-copy').onclick = closeCopyDialog;
$('cancel-copy').onclick = closeCopyDialog;
$('confirm-copy').onclick = confirmCopy;
$('copy-dialog').onclick = event => { if (event.target === $('copy-dialog')) closeCopyDialog(); };
$('close-generate').onclick = closeGenerateDialog;
$('cancel-generate').onclick = closeGenerateDialog;
$('confirm-generate').onclick = generateCase;
$('generate-dialog').onclick = event => { if (event.target === $('generate-dialog')) closeGenerateDialog(); };
$('generate-description').onkeydown = event => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') generateCase();
};
$('refresh-diagnostics').onclick = async () => { catalogData = null; await refreshDiagnostics(); };
$('stop').onclick = stop;
$('return-to-case').onclick = returnToTrialCase;
$('improve-case').onclick = () => { trialReview = null; reviewSupplements = []; requestTrialReview(); };
$('close-review').onclick = closeTrialReview;
$('cancel-review').onclick = closeTrialReview;
$('reanalyze-review').onclick = reanalyzeTrialReview;
$('apply-review').onclick = applyTrialReview;
$('review-dialog').onclick = event => { if (event.target === $('review-dialog')) closeTrialReview(); };
$('refresh-pipelines').onclick = refreshPipelines;
$('close-pipeline-case-edit').onclick = closePipelineCaseEditor;
$('cancel-pipeline-case-edit').onclick = closePipelineCaseEditor;
$('apply-pipeline-case-edit').onclick = applyPipelineCaseEditor;
$('new-pipeline').onclick = newPipeline;
$('append-cases').onclick = () => openPipelineCasePicker('append');
$('insert-cases').onclick = () => openPipelineCasePicker('insert');
$('pipeline-case-group').onchange = renderPipelineCaseOptions;
$('close-pipeline-cases').onclick = () => $('pipeline-cases-dialog').classList.add('hidden');
$('cancel-pipeline-cases').onclick = () => $('pipeline-cases-dialog').classList.add('hidden');
$('confirm-pipeline-cases').onclick = confirmPipelineCases;
$('append-action').onclick = appendPipelineAction;
$('pipeline-action').add(new Option('用户辅助测试', 'human-test'));
$('pipeline-action').add(new Option('引入 Pipeline', 'include-pipeline'));
$('validate-pipeline').onclick = validatePipelineEditor;
$('save-pipeline').onclick = savePipelineEditor;
$('save-as-pipeline').onclick = openPipelineSaveAs;
$('confirm-pipeline-save-as').onclick = confirmPipelineSaveAs;
$('cancel-pipeline-save-as').onclick = () => { $('pipeline-save-as-dialog').classList.add('hidden'); $('save-as-pipeline').focus(); };
$('run-pipeline').onclick = runPipeline;
$('close-pipeline-diff').onclick = () => $('pipeline-diff-shell').classList.add('hidden');
$('copy-handoff').onclick = copyHandoff;
try { trialContext = JSON.parse(sessionStorage.getItem('ai2apps-test-trial-context')); }
catch (_error) { sessionStorage.removeItem('ai2apps-test-trial-context'); }
load();
