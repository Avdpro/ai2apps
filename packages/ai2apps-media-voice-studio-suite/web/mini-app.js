(async function () {
  'use strict';

  // The opaque Package frame never fetches authenticated resources or reads
  // browser storage. Only the immediate Studio Host can supply this port.
  let sequence = 0;
  let queue = Promise.resolve();
  const pending = new Map();
  const connected = new Promise((resolve, reject) => {
    const timer = setTimeout(() => { window.removeEventListener('message', accept); reject(new Error('Studio Host 通道不可用，请更新 App 后重新打开。')); }, 15000);
    function accept(event) {
      if (event.source !== window.parent || event.data?.type !== 'ai2apps:studio-connected' || event.data?.version !== 1 || !event.ports?.[0]) return;
      clearTimeout(timer);
      window.removeEventListener('message', accept);
      const port = event.ports[0];
      port.onmessage = event => {
        const request = pending.get(event.data?.id);
        if (!request) return;
        pending.delete(event.data.id); clearTimeout(request.timer);
        if (event.data.error) request.reject(new Error(event.data.error));
        else request.resolve(event.data.value);
      };
      resolve(port);
    }
    window.addEventListener('message', accept);
    const connect = () => setTimeout(() => window.parent.postMessage({type: 'ai2apps:studio-connect', version: 1}, '*'), 0);
    if (document.readyState === 'complete') connect();
    else window.addEventListener('load', connect, {once: true});
  });
  // Avoid unhandled rejection while the synchronous form is being constructed.
  connected.catch(() => {});
  function hostRequest(operation, fields = {}) {
    const task = queue.then(async () => {
      const port = await connected;
      return new Promise((resolve, reject) => {
        const id = ++sequence;
        const timer = setTimeout(() => { pending.delete(id); reject(new Error('操作等待超时，请检查任务状态，不要重复提交。')); }, operation === 'invoke' ? 1800000 : 30000);
        pending.set(id, {resolve, reject, timer});
        port.postMessage({id, operation, ...fields});
      });
    });
    queue = task.catch(() => {});
    return task;
  }
  async function invokeHost(capabilityUrl, options) {
    const capability = decodeURIComponent(capabilityUrl.split('/capabilities/')[1]?.split('/')[0] || '');
    const result = await hostRequest('invoke', {capability, fields: [...options.body.entries()]});
    return new Response(result.body, {status: result.status, headers: result.headers});
  }
  const draftStorage = {
    getItem: () => hostRequest('draft.get'),
    setItem: (_key, value) => hostRequest('draft.set', {value}),
    removeItem: () => hostRequest('draft.remove'),
  };

  const workflows = {
    transcription: {
      id: 'ai2apps.media-voice.transcription',
      eyebrow: 'Audio intelligence',
      title: '生成录音文本记录',
      description: '识别逐字时间戳和说话人，完成后可把匿名角色改成真实姓名，并导出结构化记录或字幕。',
      accept: 'audio/*,video/mp4,video/quicktime',
      fileLabel: '录音或视频',
      capabilities: ['audio.detailed_transcription', 'audio.speaker_diarization'],
      primaryCapability: 'audio.detailed_transcription',
      phases: ['解析媒体', '语音识别', '角色分离', '人工命名', '导出'],
      executable: true,
      runLabel: '开始本地转写',
      roles: true,
      fields: [
        {id: 'profile', label: '模型配置', type: 'select', options: [['compact', 'Compact · 速度优先'], ['quality', 'Quality · 质量优先']]},
        {id: 'language', label: '音频语言', type: 'select', options: [['auto', '自动检测'], ['zh', '中文'], ['en', 'English'], ['ja', '日本語'], ['yue', '粤语']]},
        {id: 'output', label: '主要输出', type: 'select', options: [['transcript-json', '逐字记录 + JSON'], ['markdown', '可读 Markdown'], ['srt', 'SRT 字幕']]},
        {id: 'wordTimestamps', label: '保留逐字时间戳', type: 'checkbox', value: true}
      ]
    },
    separation: {
      id: 'ai2apps.media-voice.source-separation',
      eyebrow: 'Audio processing',
      title: '分离人声和背景音',
      description: '从音频中拆出独立人声与背景轨，并保持原始时间线，方便后续换声、混音或字幕制作。',
      accept: 'audio/*,video/mp4,video/quicktime',
      fileLabel: '音频或含音轨的视频',
      capabilities: ['audio.source_separation'],
      primaryCapability: 'audio.source_separation',
      phases: ['解析媒体', '分离音轨', '响度检查', '导出'],
      executable: true,
      runLabel: '开始本地分离',
      fields: [
        {id: 'profile', label: '输出拓扑', type: 'select', options: [['vocals_instrumental', '人声 / 伴奏'], ['dialogue_background', '对白 / 背景'], ['music_4stem', '鼓 / 贝斯 / 其他 / 人声']]}
      ]
    },
    'audio-voice-replacement': {
      id: 'ai2apps.media-voice.audio-speaker-replacement',
      eyebrow: 'Voice conversion',
      title: '替换录音中的某个角色声音',
      description: '识别目标说话人的片段，只转换该角色的音色，并将其他人声与背景轨按原时间线混回。',
      accept: 'audio/*',
      fileLabel: '包含多个角色的录音',
      capabilities: ['audio.speaker_voice_replacement', 'audio.detailed_transcription', 'audio.speaker_diarization', 'audio.source_separation', 'audio.voice_conversion'],
      primaryCapability: 'audio.speaker_voice_replacement',
      phases: ['识别角色', '分离目标片段', '音色转换', '混合与校验', '导出'],
      executable: true,
      runLabel: '先识别录音角色',
      roles: true,
      voiceReference: true,
      referenceRequired: true,
      fields: [
        {id: 'targetSpeaker', label: '要替换的角色', type: 'role-select'},
        {id: 'voiceName', label: '目标声音名称', type: 'text', placeholder: '例如：旁白角色 A', required: true},
        {id: 'conversionProfile', label: '换声质量', type: 'select', options: [['timbre_fast', '音色 · 快速'], ['timbre_quality', '音色 · 高质量'], ['voice_quality', '声音 · 高质量']]},
        {id: 'consent', label: '我确认拥有使用目标声音和处理源录音的权利', type: 'checkbox', value: false, required: true, full: true}
      ]
    },
    'video-subtitles': {
      id: 'ai2apps.media-voice.video-subtitles',
      eyebrow: 'Video localization',
      title: '生成、翻译与添加视频字幕',
      description: '从视频对白生成带时间轴的字幕，可翻译为另一种语言，导出字幕文件或直接烧录到视频。',
      accept: 'video/*',
      fileLabel: '需要制作字幕的视频',
      capabilities: ['media.video_subtitles', 'audio.detailed_transcription', 'text.translation', 'media.subtitle.export', 'media.video.subtitle_burn_in'],
      primaryCapability: 'media.video_subtitles',
      phases: ['提取音轨', '生成字幕', '翻译与校对', '排版', '导出'],
      executable: true,
      runLabel: '开始生成字幕',
      fields: [
        {id: 'sourceLanguage', label: '原始语言', type: 'select', options: [['auto', '自动检测'], ['zh', '中文'], ['en', 'English'], ['ja', '日本語'], ['ko', '한국어']]},
        {id: 'targetLanguage', label: '翻译', type: 'select', options: [['none', '不翻译'], ['zh', '翻译为中文'], ['en', 'Translate to English'], ['ja', '日本語に翻訳'], ['ko', '한국어로 번역']]},
        {id: 'subtitleFormat', label: '字幕文件', type: 'select', options: [['srt', 'SRT'], ['vtt', 'WebVTT'], ['ass', 'ASS']]},
        {id: 'burnIn', label: '同时生成烧录字幕的视频', type: 'checkbox', value: false},
        {id: 'bilingual', label: '翻译时保留双语字幕', type: 'checkbox', value: true},
        {id: 'speakerLabels', label: '字幕中显示角色名', type: 'checkbox', value: false}
      ]
    },
    'video-voice-replacement': {
      id: 'ai2apps.media-voice.video-speaker-replacement',
      eyebrow: 'Video voice conversion',
      title: '替换视频中的某个角色声音',
      description: '从视频中定位一个说话人，转换对应对白音色，再与其他角色、环境声和画面同步合成。',
      accept: 'video/*',
      fileLabel: '包含目标角色的视频',
      capabilities: ['media.video_speaker_voice_replacement', 'audio.speaker_voice_replacement', 'media.audio.extract', 'audio.detailed_transcription', 'audio.speaker_diarization', 'audio.source_separation', 'audio.voice_conversion', 'media.video.audio_mux'],
      primaryCapability: 'media.video_speaker_voice_replacement',
      phases: ['提取音轨', '识别角色', '音色转换', '同步混音', '封装视频'],
      executable: true,
      runLabel: '先识别视频角色',
      roles: true,
      voiceReference: true,
      referenceRequired: true,
      fields: [
        {id: 'targetSpeaker', label: '要替换的角色', type: 'role-select'},
        {id: 'voiceName', label: '目标声音名称', type: 'text', placeholder: '例如：角色新配音', required: true},
        {id: 'conversionProfile', label: '换声质量', type: 'select', options: [['timbre_fast', '音色 · 快速'], ['timbre_quality', '音色 · 高质量'], ['voice_quality', '声音 · 高质量']]},
        {id: 'consent', label: '我确认拥有使用目标声音和处理源视频的权利', type: 'checkbox', value: false, required: true, full: true}
      ]
    }
  };

  const mode = document.body.dataset.workflow;
  const config = workflows[mode];
  const root = document.getElementById('app');
  if (!config || !root) return;

  const state = {files: {}, fileObjects: {}, roles: [{id: 'speaker-1', name: '角色 1'}, {id: 'speaker-2', name: '角色 2'}], draft: null, analysis: null, result: null, resultUrl: null};
  const storageKey = `ai2apps.media-voice-suite.${mode}.draft.v1`;
  let refreshRoles = null;

  function node(tag, className, text) {
    const value = document.createElement(tag);
    if (className) value.className = className;
    if (text != null) value.textContent = text;
    return value;
  }

  function fileSize(bytes) {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function renderFilePicker(id, label, accept, required) {
    const wrap = node('div', 'field full');
    const zone = node('label', 'drop-zone');
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = accept;
    input.dataset.fileId = id;
    input.required = required;
    const copy = node('div');
    copy.append(node('strong', '', label), node('span', '', '点击选择，或把文件拖到这里'));
    zone.append(input, copy);
    const detail = node('div', 'file-pill');
    detail.hidden = true;
    wrap.append(zone, detail);

    function select(file) {
      if (!file) return;
      state.files[id] = {name: file.name, size: file.size, type: file.type || 'application/octet-stream'};
      state.fileObjects[id] = file;
      detail.textContent = `${file.name} · ${fileSize(file.size)}`;
      detail.hidden = false;
      setStatus('文件已就绪，可继续配置。', 'ready');
    }
    input.addEventListener('change', () => select(input.files[0]));
    ['dragenter', 'dragover'].forEach(name => zone.addEventListener(name, event => { event.preventDefault(); zone.classList.add('dragging'); }));
    ['dragleave', 'drop'].forEach(name => zone.addEventListener(name, event => { event.preventDefault(); zone.classList.remove('dragging'); }));
    zone.addEventListener('drop', event => {
      const file = event.dataTransfer.files[0];
      if (file) select(file);
    });
    return wrap;
  }

  function renderField(field) {
    const wrap = node('div', `field${field.full ? ' full' : ''}`);
    if (field.type === 'checkbox') {
      const label = node('label', 'check');
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.id = field.id;
      input.checked = Boolean(field.value);
      input.required = Boolean(field.required);
      label.append(input, document.createTextNode(field.label));
      wrap.append(label);
      return wrap;
    }
    const label = node('label', '', field.label);
    label.htmlFor = field.id;
    let input;
    if (field.type === 'select' || field.type === 'role-select') {
      input = document.createElement('select');
      if (field.type === 'role-select') input.dataset.roleSelect = 'true';
      (field.options || []).forEach(([value, text]) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = text;
        input.append(option);
      });
    } else {
      input = document.createElement(field.type === 'textarea' ? 'textarea' : 'input');
      if (input.tagName === 'INPUT') input.type = field.type || 'text';
      if (field.placeholder) input.placeholder = field.placeholder;
    }
    input.id = field.id;
    input.required = Boolean(field.required);
    wrap.append(label, input);
    return wrap;
  }

  function syncRoleSelects() {
    document.querySelectorAll('[data-role-select]').forEach(select => {
      const previous = select.value;
      select.replaceChildren();
      state.roles.forEach(role => {
        const option = document.createElement('option');
        option.value = role.id;
        option.textContent = role.name || role.id;
        select.append(option);
      });
      if (state.roles.some(role => role.id === previous)) select.value = previous;
    });
  }

  function renderRoles(container) {
    const list = node('div', 'roles');
    list.id = 'role-list';
    function refresh() {
      list.replaceChildren();
      state.roles.forEach((role, index) => {
        const row = node('div', 'role-row');
        const key = node('span', 'role-key', `SPEAKER_${String(index + 1).padStart(2, '0')}`);
        const input = document.createElement('input');
        input.type = 'text';
        input.value = role.name;
        input.setAttribute('aria-label', `角色 ${index + 1} 名称`);
        input.addEventListener('input', () => { role.name = input.value; syncRoleSelects(); renderTranscript(); });
        const remove = node('button', 'icon-button', '−');
        remove.type = 'button';
        remove.title = '删除角色';
        remove.setAttribute('aria-label', `删除角色 ${index + 1}`);
        remove.disabled = state.roles.length === 1;
        remove.addEventListener('click', () => { state.roles.splice(index, 1); refresh(); syncRoleSelects(); });
        row.append(key, input, remove);
        list.append(row);
      });
    }
    refreshRoles = refresh;
    const add = node('button', 'secondary', '添加角色');
    add.type = 'button';
    add.addEventListener('click', () => {
      const number = state.roles.length + 1;
      state.roles.push({id: `speaker-${number}-${Date.now()}`, name: `角色 ${number}`});
      refresh();
      syncRoleSelects();
    });
    container.append(list, add);
    refresh();
  }

  root.className = 'shell';
  const hero = node('header', 'hero');
  hero.append(node('p', 'eyebrow', config.eyebrow), node('h1', '', config.title), node('p', 'lede', config.description));
  const capabilityDisclosure = node('details', 'capability-disclosure');
  capabilityDisclosure.append(node('summary', '', `所需能力 · ${config.capabilities.length}`));
  const caps = node('div', 'capabilities');
  config.capabilities.forEach(capability => caps.append(node('span', 'capability', capability)));
  capabilityDisclosure.append(caps);
  hero.append(capabilityDisclosure);
  root.append(hero);

  const notice = node('div', 'notice', config.executable
    ? '此工作流已接入 mount-bound Host Capability Broker。文件只提交给本机已安装的可信模型 Package。'
    : 'MVP 已完成 Package、Mini-App UI、工作流配置与草稿导出。此工作流的模型执行仍在接入 Host Capability Broker。');
  root.append(notice);

  const sourcePanel = node('section', 'panel');
  const sourceHeading = node('div', 'panel-heading');
  const sourceTitle = node('div');
  sourceTitle.append(node('span', 'step', 'Step 01'), node('h2', '', '选择素材'));
  sourceHeading.append(sourceTitle);
  const sourceGrid = node('div', 'grid');
  sourceGrid.append(renderFilePicker('source', config.fileLabel, config.accept, true));
  if (config.voiceReference) sourceGrid.append(renderFilePicker('voiceReference', config.referenceRequired ? '目标声音参考（必选）' : '目标声音参考（可选）', 'audio/*', Boolean(config.referenceRequired)));
  sourcePanel.append(sourceHeading, sourceGrid);
  root.append(sourcePanel);

  const settingsPanel = node('section', 'panel');
  const settingsHeading = node('div', 'panel-heading');
  const settingsTitle = node('div');
  settingsTitle.append(node('span', 'step', 'Step 02'), node('h2', '', '配置工作流'), node('p', 'hint', '',));
  settingsHeading.append(settingsTitle);
  const settingsGrid = node('div', 'grid');
  config.fields.forEach(field => settingsGrid.append(renderField(field)));
  settingsPanel.append(settingsHeading, settingsGrid);
  root.append(settingsPanel);

  if (config.roles) {
    const rolePanel = node('section', 'panel');
    const roleHeading = node('div', 'panel-heading');
    const roleTitle = node('div');
    roleTitle.append(node('span', 'step', 'Step 03'), node('h2', '', '角色名称'), node('p', 'hint', '模型先产生匿名角色；用户确认后再绑定名字。MVP 可预先配置，执行结果回来后仍可修改。'));
    roleHeading.append(roleTitle);
    rolePanel.append(roleHeading);
    renderRoles(rolePanel);
    root.append(rolePanel);
    syncRoleSelects();
  }

  const pipelinePanel = node('section', 'panel');
  const pipelineHeading = node('div', 'panel-heading');
  const pipelineTitle = node('div');
  pipelineTitle.append(node('span', 'step', config.roles ? 'Step 04' : 'Step 03'), node('h2', '', '处理链路'));
  pipelineHeading.append(pipelineTitle);
  const pipeline = node('div', 'pipeline');
  pipeline.style.setProperty('--phase-count', String(config.phases.length));
  config.phases.forEach((phase, index) => {
    const item = node('div', 'phase');
    item.append(node('div', 'phase-index', String(index + 1).padStart(2, '0')), node('div', 'phase-name', phase));
    pipeline.append(item);
  });
  pipelinePanel.append(pipelineHeading, pipeline);
  const actions = node('div', 'actions');
  const status = node('div', 'status', '尚未保存任务草稿。');
  status.id = 'status';
  const reset = node('button', 'secondary', '重置');
  reset.type = 'button';
  const exportButton = node('button', 'secondary', '导出 JSON');
  exportButton.type = 'button';
  exportButton.disabled = true;
  const save = node('button', config.executable ? 'secondary' : 'primary', '保存任务草稿');
  save.type = 'button';
  actions.append(status, reset, exportButton, save);
  let runButton = null;
  if (config.executable) {
    runButton = node('button', 'primary', config.runLabel || '开始本地处理');
    runButton.type = 'button';
    actions.append(runButton);
  }
  pipelinePanel.append(actions);
  root.append(pipelinePanel);

  const resultPanel = node('section', 'panel result-panel');
  resultPanel.hidden = true;
  resultPanel.id = 'result-panel';
  root.append(resultPanel);

  function setStatus(message, kind) {
    status.textContent = message;
    status.className = `status${kind ? ` ${kind}` : ''}`;
  }

  function collect() {
    const options = {};
    config.fields.forEach(field => {
      const input = document.getElementById(field.id);
      options[field.id] = field.type === 'checkbox' ? input.checked : input.value.trim();
    });
    return {
      schema: 'ai2apps.mini-app-draft/v1',
      miniApp: config.id,
      createdAt: new Date().toISOString(),
      files: state.files,
      options,
      roles: config.roles ? state.roles.map(role => ({...role})) : [],
      requiredCapabilities: [...config.capabilities],
      executionStatus: 'draft'
    };
  }

  function clock(seconds) {
    const value = Math.max(0, Number(seconds) || 0);
    const minutes = Math.floor(value / 60);
    return `${String(minutes).padStart(2, '0')}:${(value % 60).toFixed(1).padStart(4, '0')}`;
  }

  function speakerName(speaker) {
    const transcript = state.analysis || state.result;
    const index = transcript?.speakerIds?.indexOf(speaker) ?? -1;
    return index >= 0 ? (state.roles[index]?.name || speaker) : (speaker || '未分配');
  }

  function renderTranscript() {
    const transcriptResult = state.analysis || state.result;
    if (!transcriptResult?.segments) return;
    resultPanel.hidden = false;
    resultPanel.replaceChildren();
    const heading = node('div', 'panel-heading');
    const title = node('div');
    title.append(node('span', 'step', 'Result'), node('h2', '', '角色识别结果'), node('p', 'hint', `${transcriptResult.language || '未知语言'} · ${clock(transcriptResult.duration)} · ${transcriptResult.segments.length} 个片段`));
    heading.append(title);
    const transcript = node('div', 'transcript');
    transcriptResult.segments.forEach(segment => {
      const row = node('article', 'transcript-row');
      const meta = node('div', 'transcript-meta');
      meta.append(node('strong', '', speakerName(segment.speaker)), node('span', '', `${clock(segment.start)} – ${clock(segment.end)}`));
      row.append(meta, node('p', '', segment.text || ''));
      transcript.append(row);
    });
    resultPanel.append(heading, transcript);
  }

  function mountedCapabilityUrl(capability) {
    const query = new URLSearchParams(window.location.search);
    const mountId = query.get('mount_id');
    const studioId = query.get('studio_id');
    if (!mountId || !studioId) return '';
    return `/v1/platform/studios/${encodeURIComponent(studioId)}/mini-app-mounts/${encodeURIComponent(mountId)}/capabilities/${encodeURIComponent(capability)}/invoke`;
  }

  async function responseError(response, fallback) {
    const payload = await response.json().catch(() => null);
    return payload?.detail?.message || payload?.error?.message || `${fallback} (${response.status})`;
  }

  async function runTranscription() {
    const error = validate();
    if (error) { setStatus(error, 'error'); return; }
    const source = state.fileObjects.source;
    if (!source) { setStatus('执行前请重新选择本地素材文件。', 'error'); return; }
    const capabilityUrl = mountedCapabilityUrl(config.primaryCapability);
    if (!capabilityUrl) { setStatus('可信 Mini-App mount 上下文不可用。', 'error'); return; }
    runButton.disabled = true;
    setStatus('正在本机执行详细转写与角色分离…');
    const form = new FormData();
    form.append('file', source, source.name);
    form.append('profile', document.getElementById('profile').value);
    const language = document.getElementById('language').value;
    form.append('language', language === 'auto' ? '' : language);
    form.append('word_timestamps', String(document.getElementById('wordTimestamps').checked));
    form.append('diarization', 'true');
    try {
      const response = await invokeHost(capabilityUrl, {
        method: 'POST', credentials: 'same-origin', body: form
      });
      if (!response.ok) throw new Error(await responseError(response, '转写失败'));
      const payload = await response.json();
      const segments = Array.isArray(payload?.segments) ? payload.segments : [];
      const speakerIds = [...new Set(segments.map(item => item?.speaker).filter(Boolean))];
      state.result = {...payload, segments, speakerIds};
      if (speakerIds.length) {
        const previous = state.roles;
        state.roles = speakerIds.map((id, index) => ({id, name: previous[index]?.name || `角色 ${index + 1}`}));
        refreshRoles?.();
        syncRoleSelects();
      }
      state.draft = {...collect(), executionStatus: 'completed', resultSummary: {language: payload.language || null, duration: payload.duration || 0, segmentCount: segments.length}};
      await draftStorage.setItem(storageKey, JSON.stringify(state.draft));
      exportButton.disabled = false;
      renderTranscript();
      setStatus('本地转写完成。请检查角色名称和文本后再导出。', 'ready');
    } catch (runError) {
      setStatus(runError?.message || String(runError), 'error');
    } finally {
      runButton.disabled = false;
    }
  }

  async function runSeparation() {
    const error = validate();
    if (error) { setStatus(error, 'error'); return; }
    const source = state.fileObjects.source;
    if (!source) { setStatus('执行前请重新选择本地素材文件。', 'error'); return; }
    const capabilityUrl = mountedCapabilityUrl(config.primaryCapability);
    if (!capabilityUrl) { setStatus('可信 Mini-App mount 上下文不可用。', 'error'); return; }
    runButton.disabled = true;
    setStatus('正在本机分离音轨；较长素材需要一些时间…');
    const profile = document.getElementById('profile').value;
    const form = new FormData();
    form.append('file', source, source.name);
    form.append('profile', profile);
    try {
      const response = await invokeHost(capabilityUrl, {
        method: 'POST', credentials: 'same-origin', body: form
      });
      if (!response.ok) throw new Error(await responseError(response, '音轨分离失败'));
      const archive = await response.blob();
      if (state.resultUrl) URL.revokeObjectURL(state.resultUrl);
      state.resultUrl = URL.createObjectURL(archive);
      const disposition = response.headers.get('content-disposition') || '';
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const filename = match?.[1] || `separated-${profile}.zip`;
      state.result = {schema: 'ai2apps.source-separation-result/v1', profile, filename, size: archive.size};
      state.draft = {...collect(), executionStatus: 'completed', resultSummary: state.result};
      await draftStorage.setItem(storageKey, JSON.stringify(state.draft));
      exportButton.disabled = false;
      resultPanel.hidden = false;
      resultPanel.replaceChildren();
      const heading = node('div', 'panel-heading');
      const title = node('div');
      title.append(node('span', 'step', 'Result'), node('h2', '', '音轨分离完成'), node('p', 'hint', `${profile} · ${fileSize(archive.size)} · ZIP 内含 WAV 音轨和 separation.json`));
      heading.append(title);
      const download = node('a', 'primary', '下载分离音轨 ZIP');
      download.href = state.resultUrl;
      download.download = filename;
      resultPanel.append(heading, download);
      setStatus('本地音轨分离完成。结果只保留在当前页面，请及时下载。', 'ready');
    } catch (runError) {
      setStatus(runError?.message || String(runError), 'error');
    } finally {
      runButton.disabled = false;
    }
  }

  async function runVideoSubtitles() {
    const error = validate();
    if (error) { setStatus(error, 'error'); return; }
    const source = state.fileObjects.source;
    if (!source) { setStatus('执行前请重新选择本地视频文件。', 'error'); return; }
    const capabilityUrl = mountedCapabilityUrl(config.primaryCapability);
    if (!capabilityUrl) { setStatus('可信 Mini-App mount 上下文不可用。', 'error'); return; }
    runButton.disabled = true;
    setStatus('正在本机提取对白、生成字幕并准备导出…');
    const sourceLanguage = document.getElementById('sourceLanguage').value;
    const targetLanguage = document.getElementById('targetLanguage').value;
    const subtitleFormat = document.getElementById('subtitleFormat').value;
    const burnIn = document.getElementById('burnIn').checked;
    const form = new FormData();
    form.append('file', source, source.name);
    form.append('source_language', sourceLanguage === 'auto' ? '' : sourceLanguage);
    form.append('target_language', targetLanguage === 'none' ? '' : targetLanguage);
    form.append('subtitle_format', subtitleFormat);
    form.append('bilingual', String(document.getElementById('bilingual').checked));
    form.append('burn_in', String(burnIn));
    form.append('speaker_labels', String(document.getElementById('speakerLabels').checked));
    try {
      const response = await invokeHost(capabilityUrl, {
        method: 'POST', credentials: 'same-origin', body: form
      });
      if (!response.ok) throw new Error(await responseError(response, '字幕生成失败'));
      const archive = await response.blob();
      if (state.resultUrl) URL.revokeObjectURL(state.resultUrl);
      state.resultUrl = URL.createObjectURL(archive);
      const filename = 'video-subtitles.zip';
      state.result = {
        schema: 'ai2apps.video-subtitles-result/v1',
        sourceLanguage,
        targetLanguage: targetLanguage === 'none' ? null : targetLanguage,
        subtitleFormat,
        burnIn,
        filename,
        size: archive.size
      };
      state.draft = {...collect(), executionStatus: 'completed', resultSummary: state.result};
      await draftStorage.setItem(storageKey, JSON.stringify(state.draft));
      exportButton.disabled = false;
      resultPanel.hidden = false;
      resultPanel.replaceChildren();
      const heading = node('div', 'panel-heading');
      const title = node('div');
      const contents = burnIn ? `.${subtitleFormat}、转写 JSON 和烧录视频` : `.${subtitleFormat} 和转写 JSON`;
      title.append(node('span', 'step', 'Result'), node('h2', '', '视频字幕已生成'), node('p', 'hint', `${fileSize(archive.size)} · ZIP 内含 ${contents}`));
      heading.append(title);
      const download = node('a', 'primary', '下载字幕结果 ZIP');
      download.href = state.resultUrl;
      download.download = filename;
      resultPanel.append(heading, download);
      setStatus('字幕工作流完成。结果只保留在当前页面，请及时下载。', 'ready');
    } catch (runError) {
      setStatus(runError?.message || String(runError), 'error');
    } finally {
      runButton.disabled = false;
    }
  }

  async function runAudioSpeakerReplacement() {
    const replacementStage = Boolean(state.analysis);
    const error = validate({replacementStage});
    if (error) { setStatus(error, 'error'); return; }
    const source = state.fileObjects.source;
    const isVideo = mode === 'video-voice-replacement';
    if (!source) { setStatus(isVideo ? '执行前请重新选择本地视频。' : '执行前请重新选择本地录音。', 'error'); return; }
    const capabilityUrl = mountedCapabilityUrl(config.primaryCapability);
    if (!capabilityUrl) { setStatus('可信 Mini-App mount 上下文不可用。', 'error'); return; }
    const action = replacementStage ? 'replace' : 'analyze';
    const reference = state.fileObjects.voiceReference;
    if (action === 'replace' && !reference) { setStatus('请选择目标声音参考。', 'error'); return; }
    runButton.disabled = true;
    setStatus(action === 'analyze' ? '正在识别说话人和时间轴…' : `正在分离对白、转换目标角色并重新${isVideo ? '封装视频' : '混音'}…`);
    const form = new FormData();
    form.append('file', source, source.name);
    form.append('action', action);
    if (action === 'replace') {
      form.append('reference', reference, reference.name);
      form.append('target_speaker', document.getElementById('targetSpeaker').value);
      form.append('conversion_profile', document.getElementById('conversionProfile').value);
      form.append('consent', String(document.getElementById('consent').checked));
    }
    try {
      const response = await invokeHost(capabilityUrl, {
        method: 'POST', credentials: 'same-origin', body: form
      });
      if (!response.ok) throw new Error(await responseError(response, action === 'analyze' ? '角色识别失败' : '角色换声失败'));
      if (action === 'analyze') {
        const payload = await response.json();
        const segments = Array.isArray(payload?.segments) ? payload.segments : [];
        const speakerIds = [...new Set(segments.map(item => item?.speaker).filter(Boolean))];
        state.analysis = {...payload, segments, speakerIds};
        const previous = state.roles;
        state.roles = speakerIds.map((id, index) => ({id, name: previous[index]?.name || `角色 ${index + 1}`}));
        refreshRoles?.();
        syncRoleSelects();
        renderTranscript();
        runButton.textContent = '开始替换所选角色';
        setStatus('角色识别完成。请命名角色、选择目标角色和参考声音，然后再次执行。', 'ready');
        return;
      }
      const audio = await response.blob();
      if (state.resultUrl) URL.revokeObjectURL(state.resultUrl);
      state.resultUrl = URL.createObjectURL(audio);
      const filename = isVideo ? 'speaker-replaced.mp4' : 'speaker-replaced.wav';
      state.result = {
        schema: isVideo ? 'ai2apps.video-speaker-voice-replacement-result/v1' : 'ai2apps.speaker-voice-replacement-result/v1',
        targetSpeaker: document.getElementById('targetSpeaker').value,
        voiceName: document.getElementById('voiceName').value,
        conversionProfile: document.getElementById('conversionProfile').value,
        filename,
        size: audio.size
      };
      state.draft = {...collect(), executionStatus: 'completed', resultSummary: state.result};
      await draftStorage.setItem(storageKey, JSON.stringify(state.draft));
      exportButton.disabled = false;
      resultPanel.hidden = false;
      resultPanel.replaceChildren();
      const heading = node('div', 'panel-heading');
      const title = node('div');
      title.append(node('span', 'step', 'Result'), node('h2', '', '角色换声完成'), node('p', 'hint', `${fileSize(audio.size)} · ${isVideo ? 'MP4' : 'WAV'}`));
      heading.append(title);
      const download = node('a', 'primary', isVideo ? '下载替换后的视频' : '下载替换后的音频');
      download.href = state.resultUrl;
      download.download = state.result.filename;
      resultPanel.append(heading, download);
      setStatus(`目标角色换声与${isVideo ? '视频封装' : '混音'}完成。结果只保留在当前页面，请及时下载。`, 'ready');
    } catch (runError) {
      setStatus(runError?.message || String(runError), 'error');
    } finally {
      runButton.disabled = false;
    }
  }

  function validate({replacementStage = true} = {}) {
    if (!state.files.source) return '请先选择源素材。';
    const stagedReplacement = mode === 'audio-voice-replacement' || mode === 'video-voice-replacement';
    if (config.referenceRequired && (!stagedReplacement || replacementStage) && !state.files.voiceReference) return '请选择目标声音参考。';
    for (const field of config.fields) {
      if (stagedReplacement && !replacementStage && ['targetSpeaker', 'voiceName', 'conversionProfile', 'consent'].includes(field.id)) continue;
      const input = document.getElementById(field.id);
      if (field.required && (field.type === 'checkbox' ? !input.checked : !input.value.trim())) return `请完成“${field.label}”。`;
    }
    return '';
  }

  save.addEventListener('click', async () => {
    const error = validate();
    if (error) { setStatus(error, 'error'); return; }
    state.draft = collect();
    try { await draftStorage.setItem(storageKey, JSON.stringify(state.draft)); }
    catch (error) { setStatus(error.message, 'error'); return; }
    exportButton.disabled = false;
    setStatus('任务草稿已保存；可以开始本地执行。', 'ready');
    window.parent.postMessage({type: 'ai2apps:mini-app-draft-saved', miniAppId: state.draft.miniApp}, '*');
  });

  exportButton.addEventListener('click', () => {
    if (!state.draft) return;
    if (mode === 'transcription' && state.result?.segments) {
      const output = document.getElementById('output').value;
      const roleNames = Object.fromEntries(state.roles.map(role => [role.id, role.name]));
      let content;
      let filename;
      let type;
      if (output === 'markdown') {
        const lines = state.result.segments.map(segment => `**${roleNames[segment.speaker] || segment.speaker || '未分配'}** · ${clock(segment.start)}–${clock(segment.end)}\n\n${segment.text || ''}`);
        content = `# 录音文本记录\n\n${lines.join('\n\n')}\n`;
        filename = 'transcript.md';
        type = 'text/markdown;charset=utf-8';
      } else if (output === 'srt') {
        const stamp = seconds => {
          const milliseconds = Math.max(0, Math.round((Number(seconds) || 0) * 1000));
          const hours = Math.floor(milliseconds / 3600000);
          const minutes = Math.floor((milliseconds % 3600000) / 60000);
          const secs = Math.floor((milliseconds % 60000) / 1000);
          const millis = milliseconds % 1000;
          return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(millis).padStart(3, '0')}`;
        };
        content = state.result.segments.map((segment, index) => `${index + 1}\n${stamp(segment.start)} --> ${stamp(segment.end)}\n[${roleNames[segment.speaker] || segment.speaker || '未分配'}] ${segment.text || ''}\n`).join('\n');
        filename = 'transcript.srt';
        type = 'application/x-subrip;charset=utf-8';
      } else {
        content = JSON.stringify({...state.result, roleNames}, null, 2);
        filename = 'transcript.json';
        type = 'application/json';
      }
      const blob = new Blob([content], {type});
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 0);
      return;
    }
    const exported = state.result ? {...state.draft, result: state.result} : state.draft;
    if (state.result && config.roles) exported.roleNames = Object.fromEntries(state.roles.map(role => [role.id, role.name]));
    const blob = new Blob([JSON.stringify(exported, null, 2)], {type: 'application/json'});
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${mode}-draft.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 0);
  });

  const runners = {transcription: runTranscription, separation: runSeparation, 'video-subtitles': runVideoSubtitles, 'audio-voice-replacement': runAudioSpeakerReplacement, 'video-voice-replacement': runAudioSpeakerReplacement};
  runButton?.addEventListener('click', runners[mode]);

  reset.addEventListener('click', async () => {
    try {
      await draftStorage.removeItem(storageKey);
      state.files = {}; state.fileObjects = {}; state.draft = null; state.analysis = null; state.result = null;
      if (state.resultUrl) URL.revokeObjectURL(state.resultUrl);
      state.resultUrl = null;
      state.roles = [{id: 'speaker-1', name: '角色 1'}, {id: 'speaker-2', name: '角色 2'}];
      refreshRoles?.(); syncRoleSelects();
      document.querySelectorAll('input[type="file"]').forEach(input => { input.value = ''; });
      document.querySelectorAll('.file-pill').forEach(pill => { pill.hidden = true; pill.textContent = ''; });
      for (const field of config.fields) {
        const input = document.getElementById(field.id);
        if (field.type === 'checkbox') input.checked = Boolean(field.value);
        else if (input.tagName === 'SELECT') input.selectedIndex = 0;
        else input.value = '';
      }
      resultPanel.hidden = true; resultPanel.replaceChildren(); exportButton.disabled = true;
      if (runButton) runButton.textContent = config.runLabel;
      setStatus('草稿和输入已重置。', 'ready');
    }
    catch (error) { setStatus(error.message, 'error'); }
  });

  try {
    const saved = JSON.parse(await draftStorage.getItem(storageKey) || 'null');
    if (saved && saved.schema === 'ai2apps.mini-app-draft/v1') {
      state.draft = saved;
      state.files = saved.files || {};
      if (config.roles && Array.isArray(saved.roles) && saved.roles.length) {
        state.roles = saved.roles;
        refreshRoles?.();
        syncRoleSelects();
      }
      Object.entries(saved.options || {}).forEach(([id, value]) => {
        const input = document.getElementById(id);
        if (!input) return;
        if (input.type === 'checkbox') input.checked = Boolean(value);
        else input.value = value;
      });
      exportButton.disabled = false;
      setStatus('已恢复上次草稿。执行前需要重新选择本地素材文件。', 'ready');
    }
  } catch (error) {
    setStatus(error.message || '无法恢复草稿。', 'error');
  }

  async function probeCapabilities() {
    if (!config.executable) return;
    const query = new URLSearchParams(window.location.search);
    const mountId = query.get('mount_id');
    const studioId = query.get('studio_id');
    if (!mountId || !studioId) return;
    try {
      const payload = await hostRequest('probe');
      const capability = payload.items?.find(item => item.capability === config.primaryCapability);
      notice.classList.toggle('ready', capability?.ready === true);
      if (mode === 'separation') {
        notice.textContent = capability?.ready
          ? '音轨分离能力已就绪。素材只提交给本机已安装并验证的 MLX Demucs Package。'
          : '音轨分离模型尚未配置。请先在 Models/ACPF 安装 MLX Demucs。';
      } else if (mode === 'video-subtitles') {
        notice.textContent = capability?.ready
          ? '视频字幕 Host 流程已就绪；转写、翻译和烧录能力会在执行时分别校验。'
          : '视频字幕 Host 流程不可用；请更新当前 AI2Apps App。';
      } else if (mode === 'audio-voice-replacement') {
        notice.textContent = capability?.ready
          ? '指定角色换声链路已就绪；先识别角色，再用授权参考声音替换所选角色。'
          : '指定角色换声所需模型尚未齐备。请安装 Detailed Transcription、MLX Demucs 和 MLX Seed-VC v2。';
      } else if (mode === 'video-voice-replacement') {
        notice.textContent = capability?.ready
          ? '视频指定角色换声链路已就绪；先识别角色，再转换目标对白并保留原画面封装。'
          : '视频角色换声所需模型尚未齐备。请安装 Detailed Transcription、MLX Demucs 和 MLX Seed-VC v2。';
      } else {
        notice.textContent = capability?.ready
          ? '详细转写能力已就绪。文件只提交给本机已安装并验证的 MLX WhisperX Package。'
          : '详细转写模型尚未配置。请先在 Models/ACPF 安装 Detailed Transcription Compact 或 Quality。';
      }
    } catch (_) {
      notice.textContent = '无法检查本地模型能力；重新打开 Mini-App 后可重试。';
    }
  }

  let resizeFrame = 0;
  function reportHostHeight() {
    if (window.parent === window || resizeFrame) return;
    resizeFrame = window.requestAnimationFrame(() => {
      resizeFrame = 0;
      const height = Math.ceil(root.getBoundingClientRect().height);
      window.parent.postMessage({type: 'ai2apps:mini-app-resize', version: 1, height}, '*');
    });
  }
  if ('ResizeObserver' in window) new ResizeObserver(reportHostHeight).observe(root);
  window.addEventListener('load', reportHostHeight, {once: true});
  reportHostHeight();
  probeCapabilities();
})();
