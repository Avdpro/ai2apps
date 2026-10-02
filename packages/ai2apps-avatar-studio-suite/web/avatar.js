(() => {
  'use strict';
  const INSTALL_MODEL = '__install_model__';
  let previousModel = '';
  const inputs = {portrait:null, speech:null}, previewUrls = {};
  let importing = false;
  const capability = 'video.avatar_generation';
  const $ = id => document.getElementById(id);
  const terminal = new Set(['succeeded','failed','cancelled','expired']);
  let port, nextId = 0, submitting = false, models = [], currentJob = null, polling = false;
  const pending = new Map();
  const selected = () => models.find(model => model.id === $('model').value);
  const activeJob = () => currentJob && !terminal.has(currentJob.status);
  function state() {
    $('generate').disabled = !selected()?.ready || submitting || importing || activeJob() || !inputs.portrait || !inputs.speech;
    $('cancel').disabled = !activeJob() || submitting || importing;
    $('retry').disabled = !currentJob || !['failed','cancelled','expired'].includes(currentJob.status) || submitting || importing;
    for (const id of ['model','preset','resolution','portrait','speech']) $(id).disabled = submitting || importing || !!activeJob() || (id === 'model' ? !port : ['preset','resolution'].includes(id) && !models.length);
    for (const id of ['portrait','speech']) {
      const disabled = submitting || importing || !!activeJob();
      $(id+'-pick').disabled = disabled; $(id+'-clear').disabled = disabled;
      if (disabled) $(id+'-slot').setAttribute('aria-disabled', 'true');
      else $(id+'-slot').removeAttribute('aria-disabled');
    }
  }
  function call(operation, fields = {}) {
    return new Promise((resolve, reject) => {
      if (!port) return reject(new Error('工作室尚未连接'));
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
    options($('preset'), model?.presets || [], model?.defaults.preset);
    options($('resolution'), (model?.resolutions || []).map(id => ({id,label:id === 'source' ? '保留原图尺寸' : id.replace('x',' × ')})), model?.defaults.resolution);
    $('model-limits').textContent = model ? `音频最短 ${Math.max(0.001,model.minimumSeconds)} 秒，最长 ${model.maximumSeconds || 600} 秒。${model.ready ? '' : '请先完成该模型的配置。'}` : '请通过配置模型安装一个数字人模型。';
    state();
  }
  async function refreshModels() {
    const previous = $('model').value;
    models = (await call('avatar.models')).items || [];
    options($('model'), [...models.map(model => ({id:model.id,label:model.label + (model.ready ? '' : '（需配置）')})), {id:INSTALL_MODEL,label:'＋ 安装模型…'}], previous || models.find(model => model.ready)?.id);
    if (!models.length) {
      const placeholder = document.createElement('option'); placeholder.value = ''; placeholder.textContent = '请选择或安装模型';
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
      const states = {queued:'已排队，可切换 Mini-App 等待',running:'正在生成，可切换 Mini-App 等待',succeeded:'视频已保存到工作室的预览与输出。',cancelled:'生成已停止。',expired:'任务已过期。',failed:'生成失败'};
      $('status').textContent = job.error?.message || states[job.status] || job.detail || job.status;
    }
    state();
  }
  async function poll() {
    if (!port || polling || submitting || importing) return;
    polling = true;
    try {
      const jobs = (await call('avatar.jobs')).items || [];
      const job = jobs.find(job => !terminal.has(job.status)) || jobs.find(job => job.id === currentJob?.id) || jobs[0];
      if (job && JSON.stringify(job) !== JSON.stringify(currentJob)) showJob(job);
    } catch (error) { $('status').textContent = error.message; }
    finally { polling = false; }
  }
  function accept(event) {
    if (event.source !== window.parent || event.data?.type !== 'ai2apps:studio-connected' || event.data.version !== 1 || !event.ports?.[0]) return;
    window.removeEventListener('message', accept);
    port = event.ports[0];
    port.onmessage = event => {
      const task = pending.get(event.data?.id); if (!task) return;
      pending.delete(event.data.id);
      if (event.data.error) task.reject(new Error(event.data.error)); else task.resolve(event.data.value);
    };
    (async () => {
      await refreshModels();
      $('status').textContent = models.some(model=>model.ready) ? '选择人像和音频开始生成。' : '请先配置数字人模型。';
      await poll(); setInterval(poll, 2000);
    })().catch(error => { $('status').textContent = error.message; state(); });
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
    catch (error) { $('status').textContent = error.message; }
    finally { submitting = false; state(); }
  };
  $('cancel').onclick = async () => {
    if (!activeJob()) return;
    submitting = true; state(); await waitForPoll();
    try { showJob(await call('avatar.cancel', {jobId:currentJob.id})); }
    catch (error) { $('status').textContent = error.message; }
    finally { submitting = false; state(); }
  };
  $('retry').onclick = async () => {
    if (!currentJob || activeJob()) return;
    submitting = true; state(); await waitForPoll();
    try { showJob(await call('avatar.retry', {jobId:currentJob.id})); }
    catch (error) { $('status').textContent = error.message; }
    finally { submitting = false; state(); }
  };
  $('avatar-form').onsubmit = async event => {
    event.preventDefault();
    const image = inputs.portrait, speech = inputs.speech;
    if (!image || !speech || submitting || activeJob()) return;
    if (image.size > 20 * 1024 * 1024) { $('status').textContent = '图片不得超过 20 MiB'; return; }
    submitting = true; state(); $('progress').value = 0; $('status').textContent = '正在提交素材…';
    await waitForPoll();
    try {
      const result = await call('invoke', {capability, fields: [['file', speech], ['reference', image], ['profile', $('preset').value], ['avatar_model_id', $('model').value], ['avatar_resolution', $('resolution').value]]});
      const data = JSON.parse(await result.body.text());
      if (result.status >= 400) throw new Error(data.detail?.message || data.detail || '提交失败');
      showJob(data);
    } catch (error) { $('status').textContent = error.message; }
    finally { submitting = false; state(); }
  };

  function selectInput(id, file) {
    const image = id === 'portrait';
    const ext = String(file.name || '').split('.').pop().toLowerCase();
    const type = file.type || ({png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',webp:'image/webp',wav:'audio/wav',mp3:'audio/mpeg',m4a:'audio/mp4',flac:'audio/flac',ogg:'audio/ogg',aac:'audio/aac',aiff:'audio/aiff'}[ext] || '');
    if (image ? !['image/png','image/jpeg','image/webp'].includes(type) : !type.startsWith('audio/')) throw new Error(image ? '请选择 PNG、JPEG 或 WebP 图片' : '请选择声音文件');
    if (!file.size || file.size > (image ? 20 : 100) * 1024 * 1024) throw new Error(image ? '图片须小于 20 MiB 且不能为空' : '声音须小于 100 MiB 且不能为空');
    const selectedFile = new File([file], file.name || (image ? 'portrait.png' : 'speech.wav'), {type});
    clearInput(id);
    inputs[id] = selectedFile;
    if (image) {
      previewUrls[id] = URL.createObjectURL(selectedFile);
      $(id+'-preview').src = previewUrls[id]; $(id+'-preview').hidden = false;
    }
    $(id+'-name').textContent = `${selectedFile.name} · ${(selectedFile.size/1024/1024).toFixed(1)} MB`;
    $(id+'-clear').hidden = false; $(id+'-slot').classList.add('has-file');
    $(id+'-pick').querySelector('strong').textContent = '点击更换文件';
    state();
  }
  function clearInput(id) {
    if (id === 'portrait') { $(id+'-preview').removeAttribute('src'); $(id+'-preview').hidden = true; }
    if (previewUrls[id]) URL.revokeObjectURL(previewUrls[id]);
    delete previewUrls[id]; inputs[id] = null; $(id).value = '';
    $(id+'-clear').hidden = true; $(id+'-slot').classList.remove('has-file');
    $(id+'-name').textContent = id === 'portrait' ? 'Finder · Gallery · 图片 Output' : 'Finder · Gallery · 声音 Output';
    $(id+'-pick').querySelector('strong').textContent = id === 'portrait' ? '拖入人像图片' : '拖入驱动音频';
    state();
  }
  for (const id of ['portrait','speech']) {
    const slot = $(id+'-slot');
    $(id+'-pick').onclick = () => $(id).click();
    $(id+'-clear').onclick = () => clearInput(id);
    $(id).onchange = () => { try { if ($(id).files[0]) selectInput(id, $(id).files[0]); } catch (error) { $('status').textContent = error.message; } };
    for (const name of ['dragenter','dragover']) slot.addEventListener(name, event => {
      event.preventDefault(); event.stopPropagation();
      if (!submitting && !importing && !activeJob()) { slot.classList.add('dragging'); event.dataTransfer.dropEffect = 'copy'; }
    });
    slot.addEventListener('dragleave', event => { if (!slot.contains(event.relatedTarget)) slot.classList.remove('dragging'); });
    slot.addEventListener('drop', async event => {
      event.preventDefault(); event.stopPropagation(); slot.classList.remove('dragging');
      if (submitting || importing || activeJob()) return;
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
          if (!reference) throw new Error('请拖入 Finder 文件、Gallery 素材或图片/声音 Output');
          await waitForPoll();
          const result = await call('avatar.input.read', {kind:id === 'portrait' ? 'image' : 'audio',reference});
          selectInput(id, new File([result.body], result.name, {type:result.body.type}));
        }
        $('status').textContent = '素材已就绪。';
      } catch (error) { $('status').textContent = error.message; }
      finally { importing = false; state(); }
    });
  }
  window.addEventListener('pagehide', () => Object.values(previewUrls).forEach(url => URL.revokeObjectURL(url)));
  new ResizeObserver(() => window.parent.postMessage({type:'ai2apps:mini-app-resize',version:1,height:document.documentElement.scrollHeight}, '*')).observe(document.body);
})();
