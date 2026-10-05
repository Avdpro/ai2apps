(() => {
  'use strict';
  const {t, setLocale, presetLabel} = window.AvatarI18n;
  const INSTALL_MODEL = '__install_model__';
  let previousModel = '';
  const inputs = {portrait:null, speech:null}, previewUrls = {};
  let importing = false, recording = false, recordTimer = null, recordStarted = 0, recordedSeconds = null;
  let audioDuration = null, durationContext = null;
  const capability = 'video.avatar_generation';
  const $ = id => document.getElementById(id);
  const terminal = new Set(['succeeded','failed','cancelled','expired']);
  let port, nextId = 0, submitting = false, models = [], currentJob = null, polling = false;
  const pending = new Map();
  let statusKey = 'connecting';
  function setStatus(key) { statusKey = key; $('status').textContent = t(key); }
  const selected = () => models.find(model => model.id === $('model').value);
  const activeJob = () => currentJob && !terminal.has(currentJob.status);
  function state() {
    $('record-start').disabled = !port || submitting || importing || !!activeJob() || !!recording;
    $('record-start').hidden = !!recording;
    $('record-stop').hidden = $('record-cancel').hidden = !recording;
    $('record-stop').disabled = $('record-cancel').disabled = recording !== 'active';
    $('generate').disabled = !selected()?.ready || submitting || importing || !!recording || activeJob() || !inputs.portrait || !inputs.speech;
    $('cancel').disabled = !activeJob() || submitting || importing || !!recording;
    $('retry').disabled = !currentJob || !['failed','cancelled','expired'].includes(currentJob.status) || submitting || importing || !!recording;
    for (const id of ['model','preset','resolution','portrait','speech']) $(id).disabled = submitting || importing || !!recording || !!activeJob() || (id === 'model' ? !port : ['preset','resolution'].includes(id) && !models.length);
    for (const id of ['portrait','speech']) {
      const disabled = submitting || importing || !!recording || !!activeJob();
      $(id+'-pick').disabled = disabled; $(id+'-clear').disabled = disabled;
      if (disabled) $(id+'-slot').setAttribute('aria-disabled', 'true');
      else $(id+'-slot').removeAttribute('aria-disabled');
    }
  }
  function call(operation, fields = {}) {
    return new Promise((resolve, reject) => {
      if (!port) return reject(new Error(t('disconnected')));
      const id = ++nextId;
      pending.set(id, {resolve, reject});
      port.postMessage({id, operation, ...fields});
    });
  }
  function options(element, items, value) {
    element.replaceChildren(...items.map(item => {
      const option = document.createElement('option'); option.value = item.id; option.textContent = item.label;
      return option;
    }));
    if (items.some(item => item.id === value)) element.value = value;
  }
  function modelChanged() {
    const model = selected();
    options($('preset'), (model?.presets || []).map(p => ({...p,label:presetLabel(p.label)})), model?.defaults.preset);
    options($('resolution'), (model?.resolutions || []).map(id => ({id,label:id === 'source' ? t('source') : id.replace('x',' × ')})), model?.defaults.resolution);
    $('model-limits').textContent = model ? t('limits', {min:Math.max(0.001,model.minimumSeconds),max:model.maximumSeconds || 600}) + (model.ready ? '' : t('notReady')) : t('installPrompt');
    state();
  }
  async function refreshModels() {
    const previous = $('model').value;
    models = (await call('avatar.models')).items || [];
    options($('model'), [...models.map(model => ({id:model.id,label:model.label + (model.ready ? '' : t('needsSetup'))})), {id:INSTALL_MODEL,label:t('install')}], previous || models.find(model => model.ready)?.id);
    if (!models.length) {
      const placeholder = document.createElement('option'); placeholder.value = ''; placeholder.textContent = t('selectModel');
      $('model').prepend(placeholder); $('model').value = '';
    }
    previousModel = $('model').value;
    modelChanged();
  }
  function showJob(job) {
    currentJob = job;
    if (job) {
      if (activeJob() && models.some(model => model.id === job.modelId)) {
        $('model').value = job.modelId; modelChanged();
        $('preset').value = job.preset || selected().defaults.preset;
        $('resolution').value = job.resolution || selected().defaults.resolution;
      }
      $('progress').value = job.progress || 0;
      const states = {queued:t('queued'),running:t('running'),succeeded:t('succeeded'),cancelled:t('cancelled'),expired:t('expired'),failed:t('failed')};
      $('status').textContent = job.error?.message || states[job.status] || job.detail || job.status;
    }
    state();
  }
  async function poll() {
    if (!port || polling || submitting || importing || !!recording) return;
    polling = true;
    try {
      const jobs = (await call('avatar.jobs')).items || [];
      const job = jobs.find(job => !terminal.has(job.status)) || jobs.find(job => job.id === currentJob?.id) || jobs[0];
      if (job && JSON.stringify(job) !== JSON.stringify(currentJob)) showJob(job);
    } catch (error) { statusKey = null; $('status').textContent = error.message; }
    finally { polling = false; }
  }
  function accept(event) {
    if (event.source !== window.parent || event.data?.type !== 'ai2apps:studio-connected' || event.data.version !== 1 || !event.ports?.[0]) return;
    setLocale(event.data.locale || new URLSearchParams(window.location.search).get('locale') || navigator.language);
    window.removeEventListener('message', accept);
    port = event.ports[0];
    port.onmessage = event => {
      if (event.data?.type === 'ai2apps:studio-locale') { setLocale(event.data.locale); return; }
      const task = pending.get(event.data?.id); if (!task) return;
      pending.delete(event.data.id);
      if (event.data.error) task.reject(new Error(event.data.error)); else task.resolve(event.data.value);
    };
    (async () => {
      await refreshModels();
      setStatus(models.some(model=>model.ready) ? 'start' : 'configureAvatar');
      await poll(); setInterval(poll, 2000);
    })().catch(error => { statusKey = null; $('status').textContent = error.message; state(); });
  }
  window.addEventListener('message', accept);
  window.addEventListener('load', () => window.parent.postMessage({type:'ai2apps:studio-connect',version:1}, '*'), {once:true});
  $('model').onchange = async () => {
    if ($('model').value === INSTALL_MODEL) { $('model').value = previousModel; await setupModels(); }
    else { previousModel = $('model').value; modelChanged(); }
  };
  const waitForPoll = async () => { while (polling) await new Promise(resolve => setTimeout(resolve, 25)); };
  async function setupModels() {
    submitting = true; state(); await waitForPoll();
    try { await call('setup', {capability, installMore: true}); await refreshModels(); }
    catch (error) { statusKey = null; $('status').textContent = error.message; }
    finally { submitting = false; state(); }
  };
  $('cancel').onclick = async () => {
    if (!activeJob()) return;
    submitting = true; state(); await waitForPoll();
    try { showJob(await call('avatar.cancel', {jobId:currentJob.id})); }
    catch (error) { statusKey = null; $('status').textContent = error.message; }
    finally { submitting = false; state(); }
  };
  $('retry').onclick = async () => {
    if (!currentJob || activeJob()) return;
    submitting = true; state(); await waitForPoll();
    try { showJob(await call('avatar.retry', {jobId:currentJob.id})); }
    catch (error) { statusKey = null; $('status').textContent = error.message; }
    finally { submitting = false; state(); }
  };
  $('avatar-form').onsubmit = async event => {
    event.preventDefault();
    const image = inputs.portrait, speech = inputs.speech;
    if (!image || !speech || submitting || recording || activeJob()) return;
    if (Number.isFinite(audioDuration) && audioDuration > (selected()?.maximumSeconds || 600)) { statusKey = null; $('status').textContent = t('durationError', {max:selected()?.maximumSeconds || 600}); return; }
    if (image.size > 20 * 1024 * 1024) { setStatus('imageLarge'); return; }
    submitting = true; state(); $('progress').value = 0; setStatus('submitting');
    await waitForPoll();
    try {
      const result = await call('invoke', {capability, fields: [['file', speech], ['reference', image], ['profile', $('preset').value], ['avatar_model_id', $('model').value], ['avatar_resolution', $('resolution').value]]});
      const data = JSON.parse(await result.body.text());
      if (result.status >= 400) throw new Error(submissionError(data));
      showJob(data);
    } catch (error) { statusKey = null; $('status').textContent = error.message; }
    finally { submitting = false; state(); }
  };

  function selectInput(id, file) {
    const image = id === 'portrait';
    const ext = String(file.name || '').split('.').pop().toLowerCase();
    const type = file.type || ({png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',webp:'image/webp',wav:'audio/wav',mp3:'audio/mpeg',m4a:'audio/mp4',flac:'audio/flac',ogg:'audio/ogg',aac:'audio/aac',aiff:'audio/aiff'}[ext] || '');
    if (image ? !['image/png','image/jpeg','image/webp'].includes(type) : !type.startsWith('audio/')) throw new Error(image ? t('imageType') : t('audioType'));
    if (!file.size || file.size > (image ? 20 : 100) * 1024 * 1024) throw new Error(image ? t('imageSize') : t('audioSize'));
    const selectedFile = new File([file], file.name || (image ? 'portrait.png' : 'speech.wav'), {type});
    clearInput(id);
    inputs[id] = selectedFile;
    if (image) {
      previewUrls[id] = URL.createObjectURL(selectedFile);
      $(id+'-preview').src = previewUrls[id]; $(id+'-preview').hidden = false;
    }
    if (!image) setupAudioPreview(selectedFile);
    $(id+'-name').textContent = `${selectedFile.name} · ${(selectedFile.size/1024/1024).toFixed(1)} MB`;
    $(id+'-clear').hidden = false; $(id+'-slot').classList.add('has-file');
    $(id+'-pick').querySelector('strong').textContent = t('replace');
    state();
  }
  function clearInput(id) {
    if (id === 'speech') {
      const audio = $('speech-preview'); audio.pause(); audio.onloadedmetadata = audio.ondurationchange = audio.onerror = null; audio.removeAttribute('src'); audio.load();
      $('speech-details').hidden = true; $('speech-sources').hidden = false; audioDuration = null;
      durationContext?.close().catch(() => {}); durationContext = null;
    }
    if (id === 'portrait') { $(id+'-preview').removeAttribute('src'); $(id+'-preview').hidden = true; }
    if (previewUrls[id]) URL.revokeObjectURL(previewUrls[id]);
    delete previewUrls[id]; inputs[id] = null; $(id).value = '';
    $(id+'-clear').hidden = true; $(id+'-slot').classList.remove('has-file');
    $(id+'-name').textContent = id === 'portrait' ? t('portraitSources') : t('speechSources');
    $(id+'-pick').querySelector('strong').textContent = id === 'portrait' ? t('dropPortrait') : t('dropSpeech');
    state();
  }
  for (const id of ['portrait','speech']) {
    const slot = $(id+'-slot');
    $(id+'-pick').onclick = () => $(id).click();
    $(id+'-clear').onclick = () => clearInput(id);
    $(id).onchange = () => { try { if ($(id).files[0]) selectInput(id, $(id).files[0]); } catch (error) { statusKey = null; $('status').textContent = error.message; } };
    for (const name of ['dragenter','dragover']) slot.addEventListener(name, event => {
      event.preventDefault(); event.stopPropagation();
      if (!submitting && !importing && !activeJob()) { slot.classList.add('dragging'); event.dataTransfer.dropEffect = 'copy'; }
    });
    slot.addEventListener('dragleave', event => { if (!slot.contains(event.relatedTarget)) slot.classList.remove('dragging'); });
    slot.addEventListener('drop', async event => {
      event.preventDefault(); event.stopPropagation(); slot.classList.remove('dragging');
      if (submitting || importing || !!recording || activeJob()) return;
      // Capture drag data synchronously; browsers clear it after the event returns.
      const transfer = event.dataTransfer;
      const file = transfer.files?.[0];
      const galleryId = transfer.getData('application/x-ai2apps-gallery-asset');
      const imageRef = transfer.getData('application/x-ai2apps-image-result');
      const audioRef = transfer.getData('application/x-ai2apps-audio-artifact');
      importing = true; state();
      try {
        if (file) selectInput(id, file);
        else {
          const reference = galleryId ? {source:'gallery',assetId:galleryId} : imageRef ? {source:'image-output',...JSON.parse(imageRef)} : audioRef ? {source:'audio-output',...JSON.parse(audioRef)} : null;
          if (!reference) throw new Error(t('dropSupported'));
          await waitForPoll();
          const result = await call('avatar.input.read', {kind:id === 'portrait' ? 'image' : 'audio',reference});
          selectInput(id, new File([result.body], result.name, {type:result.body.type}));
        }
        setStatus('ready');
      } catch (error) { statusKey = null; $('status').textContent = error.message; }
      finally { importing = false; state(); }
    });
  }


  function clock(seconds) { const n = Math.max(0, Math.floor(seconds)); return `${Math.floor(n / 60)}:${String(n % 60).padStart(2, '0')}`; }
  function renderDuration() { $('speech-duration').textContent = Number.isFinite(audioDuration) ? t('audioDuration', {time:clock(audioDuration), seconds:audioDuration.toFixed(1)}) : t('durationLoading'); }
  function setupAudioPreview(file) {
    const audio = $('speech-preview');
    const url = URL.createObjectURL(file); previewUrls.speech = url;
    $('speech-details').hidden = false; $('speech-sources').hidden = true;
    audioDuration = recordedSeconds; recordedSeconds = null; renderDuration();
    const update = () => { if (inputs.speech === file && Number.isFinite(audio.duration) && audio.duration > 0) { audioDuration = audio.duration; renderDuration(); } };
    audio.onloadedmetadata = update; audio.ondurationchange = update;
    audio.onerror = () => { if (inputs.speech === file) $('speech-duration').textContent = t('previewUnavailable'); };
    audio.src = url; audio.load();
    // Some WebM recordings have an infinite container duration. Decode only
    // when metadata cannot supply a finite value; never play automatically.
    audio.onloadedmetadata = async () => {
      update();
      if (Number.isFinite(audioDuration)) return;
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) { $('speech-duration').textContent = t('durationUnknown'); return; }
      const context = new AudioContext(); durationContext = context;
      try { const buffer = await context.decodeAudioData(await file.arrayBuffer()); if (inputs.speech === file) { audioDuration = buffer.duration; renderDuration(); } }
      catch (_) { if (inputs.speech === file) $('speech-duration').textContent = t('durationUnknown'); }
      finally { await context.close().catch(() => {}); if (durationContext === context) durationContext = null; }
    };
  }
  function recordingError(error) {
    const key = {recording_permission_denied:'micDenied',recording_no_device:'micMissing',recording_unavailable:'recordUnavailable',recording_empty:'recordEmpty'}[error.message] || 'recordFailed';
    setStatus(key);
  }
  async function stopRecording(discard = false) {
    if (recording !== 'active') return;
    recording = 'stopping'; clearInterval(recordTimer); state();
    try {
      const result = await call(discard ? 'avatar.record.cancel' : 'avatar.record.stop');
      if (!discard) { recordedSeconds = (Date.now() - recordStarted) / 1000; selectInput('speech', new File([result.body], result.name, {type:result.body.type})); setStatus('ready'); }
      else setStatus('recordDiscarded');
    } catch (error) { recordingError(error); }
    finally { recording = false; $('record-time').textContent = ''; state(); }
  }
  $('record-start').onclick = async () => {
    if (recording || submitting || importing || activeJob()) return;
    recording = 'starting'; state(); await waitForPoll(); $('speech-preview').pause();
    setStatus('micRequest');
    try {
      const result = await call('avatar.record.start', {maxSeconds:Math.max(0.2,(selected()?.maximumSeconds || 60) - 0.25)});
      recording = 'active'; recordStarted = Date.now(); setStatus('recording');
      const tick = () => { const elapsed = (Date.now()-recordStarted)/1000; $('record-time').textContent = `${clock(elapsed)} / ${clock(result.maxSeconds)}`; if (elapsed >= result.maxSeconds) stopRecording(); };
      tick(); recordTimer = setInterval(tick, 200); state();
    } catch (error) { recording = false; recordingError(error); state(); }
  };
  $('record-stop').onclick = () => stopRecording();
  $('record-cancel').onclick = () => stopRecording(true);

  function submissionError(data) {
    const error = data.error || data.detail || data;
    const message = typeof error === 'string' ? error : error?.message;
    if (message === 'decoded audio exceeds the duration limit') return t('durationError', {max:selected()?.maximumSeconds || 600});
    return message || t('submitFailed');
  }
  window.addEventListener('avatar-locale-changed', () => {
    const model = $('model').value, preset = $('preset').value, resolution = $('resolution').value;
    if (models.length) options($('model'), [...models.map(m => ({id:m.id,label:m.label + (m.ready ? '' : t('needsSetup'))})), {id:INSTALL_MODEL,label:t('install')}], model);
    modelChanged(); $('preset').value = preset; $('resolution').value = resolution;
    for (const id of ['portrait','speech']) {
      $(id+'-pick').querySelector('strong').textContent = inputs[id] ? t('replace') : t(id === 'portrait' ? 'dropPortrait' : 'dropSpeech');
      if (inputs[id]) $(id+'-name').textContent = `${inputs[id].name} · ${(inputs[id].size/1024/1024).toFixed(1)} MB`;
      else $(id+'-name').textContent = t(id === 'portrait' ? 'portraitSources' : 'speechSources');
    }
    if (inputs.speech) renderDuration();
    if (currentJob) showJob(currentJob);
    else if (statusKey) $('status').textContent = t(statusKey);
  });
  window.addEventListener('pagehide', () => { clearInterval(recordTimer); if (recording && port) port.postMessage({id:++nextId,operation:'avatar.record.cancel'}); $('speech-preview').pause(); durationContext?.close().catch(() => {}); Object.values(previewUrls).forEach(url => URL.revokeObjectURL(url)); });
  new ResizeObserver(() => window.parent.postMessage({type:'ai2apps:mini-app-resize',version:1,height:document.documentElement.scrollHeight}, '*')).observe(document.body);
})();
