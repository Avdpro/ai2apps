(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const zh = /^zh/i.test(new URLSearchParams(location.search).get('locale') || navigator.language);
  const tr = (en, cn) => zh ? cn : en;
  const kinds = {
    text: tr('Text','文字'), voice: tr('Voice message','语音消息'), call: tr('Voice call','语音通话'), image: tr('Image','图片'), video: tr('Video','视频'),
    link: tr('Web link','网页链接'), location: tr('Location','位置'), contact: tr('Contact','名片'),
    transfer: tr('Transfer','转账'), envelope: tr('Red envelope','红包'),
  };
  const sizes = {'9:16':[720,1280], '3:4':[720,960], '16:9':[1280,720]};
  const people = [], messages = [];
  const profileLimit = 20;
  const draftSchema = 'ai2apps.mini-app-draft/v1';
  const miniApp = 'ai2apps.imagine.fantasy-feed';
  let profiles = [], libraryReady = false;
  const newProfile = () => ({id:'',name:'',avatar:null,aliases:'',isSelf:false});
  let profileDraft = newProfile();
  let sequence = 0, timer, playing = false, busy = false, pending = 0;
  const canvas = $('preview');
  const paint = window.FantasyFeedRenderer(canvas, tr);
  if (zh) {
    document.documentElement.lang = 'zh-CN';
    document.querySelectorAll('[data-zh]').forEach(el => { el.textContent = el.dataset.zh; });
    document.querySelectorAll('[data-label-zh]').forEach(el => el.setAttribute('aria-label', el.dataset.labelZh));
  }
  function el(tag, attributes = {}, children = []) {
    const node = Object.assign(document.createElement(tag), attributes);
    node.append(...children);
    return node;
  }
  function button(label, run, disabled = false) {
    return el('button', {type:'button', textContent:label, onclick:run, disabled});
  }
  function field(label, input) {
    return el('label', {}, [el('span',{textContent:label}), input]);
  }
  function inputField(label, record, key, attributes = {}) {
    const input = el('input', {...attributes, value:record[key] ?? ''});
    input.addEventListener('input', () => { record[key] = input.value; });
    return field(label, input);
  }
  function selectField(label, record, key, options, update) {
    const select = el('select');
    for (const [value, text] of options) select.add(el('option',{value,textContent:text}));
    select.value = record[key];
    select.addEventListener('change', () => {
      record[key] = select.value;
      if (update) update();
      else preview(messages.length);
    });
    return field(label,select);
  }
  function refreshLabels() {
    for (const select of $('messages').querySelectorAll('select[data-sender]')) {
      for (const option of select.options) {
        const person = people.find(item => item.id === option.value);
        if (person) option.textContent = person.name.trim() || tr('Unnamed','未命名');
      }
    }
  }
  function addPerson(name,avatar=null) {
    if (people.length >= 16) return;
    people.push({id:String(++sequence),name,avatar});
    updateRows();
  }
  function addMessage(sender = people[0].id, text = '', offset = messages.length ? '25' : '0') {
    if (messages.length >= 30) return;
    messages.push({sender,offset,kind:'text',text});
    updateRows();
  }
  function releaseMedia(asset) {
    if (asset?.url) URL.revokeObjectURL(asset.url);
  }
  function loadVideo(file) {
    const url = URL.createObjectURL(file);
    return new Promise((resolve, reject) => {
      const video = el('video',{muted:true,playsInline:true,preload:'auto'});
      const timeout = setTimeout(() => finish(false), 12000);
      function finish(ok) {
        clearTimeout(timeout);
        video.onloadeddata = video.onerror = null;
        if (!ok) {
          video.removeAttribute('src');
          video.load();
          URL.revokeObjectURL(url);
          reject(Error(tr('This video could not be decoded. Try H.264 MP4 or WebM.', '无法解码此视频，请试用 H.264 MP4 或 WebM。')));
          return;
        }
        const poster = el('canvas');
        const scale = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
        poster.width = Math.max(1, Math.round(video.videoWidth * scale));
        poster.height = Math.max(1, Math.round(video.videoHeight * scale));
        poster.getContext('2d').drawImage(video,0,0,poster.width,poster.height);
        const duration = video.duration;
        video.removeAttribute('src');
        video.load();
        resolve({image:poster,duration,url,name:file.name});
      }
      video.onloadeddata = () => finish(video.videoWidth > 0 && Number.isFinite(video.duration));
      video.onerror = () => finish(false);
      video.src = url;
    });
  }
  async function loadImage(file, size) {
    const bitmap = await createImageBitmap(file);
    try {
      const thumbnail = el('canvas');
      const scale = Math.min(1, size / Math.max(bitmap.width, bitmap.height));
      thumbnail.width = Math.max(1, Math.round(bitmap.width * scale));
      thumbnail.height = Math.max(1, Math.round(bitmap.height * scale));
      thumbnail.getContext('2d').drawImage(bitmap,0,0,thumbnail.width,thumbnail.height);
      return {image:thumbnail,url:thumbnail.toDataURL(),name:file.name};
    } finally { bitmap.close(); }
  }
  function mediaField(label, record, key, video = false, refresh = updateRows) {
    const asset = record[key];
    const picker = el('input',{type:'file',accept:video?'video/*':'image/*'});
    picker.addEventListener('change', async () => {
      const file = picker.files[0];
      if (!file) return;
      stop();
      pending++;
      controls();
      try {
        if (file.size > (video ? 80 : 15) * 1024 * 1024)
          throw Error(tr('The selected file is too large.', '所选文件过大。'));
        const loaded = video ? await loadVideo(file) : await loadImage(file,key === 'avatar' ? 160 : 640);
        releaseMedia(record[key]);
        record[key] = loaded;
        refresh();
      } catch (error) {
        (record === profileDraft ? $('profile-status') : $('status')).textContent = error.message;
        picker.value = '';
      } finally { pending--; controls(); }
    });
    const content = [field(label,picker)];
    if (asset) {
      const clear = button(tr('Remove file','移除文件'), () => {
        releaseMedia(asset);
        delete record[key];
        refresh();
      });
      const thumbnail = !video && key === 'avatar' ? [el('img',{className:'thumbnail',src:asset.url,alt:label})] : [];
      content.push(el('div',{className:'row-actions'},[...thumbnail,el('small',{textContent:asset.name || ''}),clear]));
      if (video) content.push(el('video',{src:asset.url,controls:true,playsInline:true,preload:'metadata'}));
    }
    return content;
  }
  function details(message) {
    const line = (en,cn,key,limit = 80) => inputField(tr(en,cn),message,key,{maxLength:limit});
    switch (message.kind) {
      case 'call':
        return [inputField(tr('Call duration (mm:ss)','通话时长（分:秒）'),message,'callDuration',
          {placeholder:'02:04',maxLength:6,required:true})];
      case 'voice': {
        const transcript = el('textarea',{rows:2,maxLength:300,value:message.transcript || ''});
        transcript.oninput = () => { message.transcript = transcript.value; };
        return [inputField(tr('Voice duration (seconds)','语音时长（秒）'),message,'voiceSeconds',
          {type:'number',min:'1',max:'60',step:'1',required:true}),
        field(tr('Transcript (optional)','转写文字（可选）'),transcript),
        el('small',{textContent:tr('Displays a simulated voice bubble. The exported video is silent.',
          '生成模拟语音气泡，导出视频为无声画面。')})];
      }
      case 'text': {
        const text = el('textarea',{rows:2,maxLength:300,value:message.text || ''});
        text.oninput = () => { message.text = text.value; };
        return [field(tr('Message text','消息正文'),text)];
      }
      case 'image':
      case 'video':
        return [...mediaField(kinds[message.kind],message,message.kind,message.kind === 'video'),
          line('Caption','配文','caption',90)];
      case 'link':
        return [line('Page URL (https://…)','网页地址（https://…）','url',300),
          line('Page title','网页标题','title'), line('Summary','摘要','summary',110),
          line('Source name (optional)','来源名称（可选）','source',40),
          ...mediaField(tr('Preview image (optional)','预览图（可选）'),message,'cover')];
      case 'location':
        return [line('Place name','地点名称','place'),line('Street address','详细地址','address'),
          ...mediaField(tr('Map screenshot (optional)','地图截图（可选）'),message,'map')];
      case 'contact':
        return [line('Contact name','联系人名称','contact'),line('Contact ID or phone','账号或号码','handle'),
          ...mediaField(tr('Contact photo (optional)','名片头像（可选）'),message,'avatar')];
      case 'transfer':
      case 'envelope': {
        const states = message.kind === 'envelope'
          ? [['sent',tr('Unopened','待领取')],['received',tr('Opened','已领取')],['expired',tr('Expired','已过期')]]
          : [['sent',tr('Pending','待收款')],['received',tr('Received','已收款')],['expired',tr('Returned','已退回')]];
        const amount = inputField(tr('Amount','金额'),message,'amount',{type:'number',min:'0.01',max:'999999',step:'0.01'});
        const money = selectField(tr('Currency','货币'),message,'currency',[['CNY','CNY ¥'],['USD','USD $'],['HKD','HKD $'],['EUR','EUR €'],['BRL','BRL R$'],['INR','INR ₹']]);
        return [el('div',{className:'grid'},[amount,money]),line('Note','备注','note'),
          selectField(tr('Status','状态'),message,'state',states)];
      }
      default: return [];
    }
  }
  async function loadProfiles(draft) {
    const rows = draft?.participantProfiles ?? [];
    if (!Array.isArray(rows) || rows.length > profileLimit)
      throw Error(tr('Could not read participant profiles.', '无法读取参与者档案。'));
    const ids = new Set();
    return Promise.all(rows.map(async row => {
      if (!row || typeof row.id !== 'string' || !/^[0-9a-f]{32}$/.test(row.id) || ids.has(row.id) ||
          typeof row.name !== 'string' || !row.name.trim() || row.name.length > 30)
        throw Error(tr('Invalid participant profile.', '参与者档案格式无效。'));
      ids.add(row.id);
      let avatar = null;
      if (row.avatar != null) {
        if (typeof row.avatar !== 'string' || row.avatar.length > 150000 ||
            !/^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(row.avatar))
          throw Error(tr('Invalid profile avatar.', '档案头像格式无效。'));
        const image = el('img',{src:row.avatar});
        await image.decode();
        if (image.width > 160 || image.height > 160)
          throw Error(tr('Invalid profile avatar size.', '档案头像尺寸无效。'));
        avatar = {image,url:row.avatar};
      }
      const aliases = row.aliases ?? [];
      if (!Array.isArray(aliases) || aliases.length > 8 || aliases.some(alias=>
          typeof alias !== 'string' || !alias.trim() || alias.length > 30))
        throw Error(tr('Invalid profile aliases.','档案别名无效。'));
      return {id:row.id,name:row.name,avatar,aliases,isSelf:row.isSelf === true};
    }));
  }
  function profileOptions() {
    return profiles.map(({id,name})=>[id,name]);
  }
  function renderProfiles() {
    const panel = $('profile-library');
    if (!libraryReady) {
      panel.replaceChildren();
      return;
    }
    const selection = selectField(tr('Saved profile','已保存档案'),{id:profileDraft.id},'id',
      [['',tr('New profile','新建档案')],...profileOptions()],() => {
        const saved = profiles.find(row=>row.id === selection.querySelector('select').value);
        profileDraft = saved ? {...saved,aliases:saved.aliases.join('、')} : newProfile();
        $('profile-status').textContent = '';
        renderProfiles();
      });
    const add = button(tr('Add to conversation','加入当前会话'),() => {
      const profile = profiles.find(row=>row.id === profileDraft.id);
      if (profile) addPerson(profile.name,profile.avatar);
    },!profileDraft.id || people.length >= 16);
    const self = el('input',{type:'checkbox',checked:profileDraft.isSelf});
    self.addEventListener('change',()=>{ profileDraft.isSelf = self.checked; });
    panel.replaceChildren(selection,
      inputField(tr('Profile nickname','档案昵称'),profileDraft,'name',{type:'text',maxLength:30}),
      inputField(tr('Aliases for Bot matching (comma-separated)','Bot 匹配别名（逗号分隔）'),profileDraft,'aliases',{type:'text',maxLength:248}),
      field(tr('This profile is me','这个档案是我'),self),
      ...mediaField(tr('Profile avatar','档案头像'),profileDraft,'avatar',false,renderProfiles),
      el('div',{className:'row-actions'},[button(tr('Save profile','保存档案'),saveProfile),add]));
  }
  async function readProfileDraft() {
    const value = await hostRequest('draft.get',{},10000);
    const draft = value == null ? {schema:draftSchema,miniApp} : JSON.parse(value);
    if (draft?.schema !== draftSchema || draft.miniApp !== miniApp)
      throw Error(tr('Could not read participant profiles.', '无法读取参与者档案。'));
    return draft;
  }
  async function saveProfile() {
    const name = profileDraft.name.trim();
    if (!name) {
      $('profile-status').textContent = tr('Enter a nickname first.', '请先填写档案昵称。');
      return;
    }
    stop();
    pending++;
    controls();
    try {
      const draft = await readProfileDraft();
      const saved = await loadProfiles(draft);
      const index = saved.findIndex(row=>row.id === profileDraft.id);
      if (index < 0 && saved.length >= profileLimit)
        throw Error(tr('Up to 20 profiles can be saved.', '最多保存 20 个档案。'));
      const avatar = profileDraft.avatar || null;
      if (avatar?.url.length > 150000)
        throw Error(tr('Profile avatar is too large.', '档案头像过大。'));
      const id = profileDraft.id || Array.from(crypto.getRandomValues(new Uint8Array(16)),
        byte=>byte.toString(16).padStart(2,'0')).join('');
      const aliases = [...new Set(profileDraft.aliases.split(/[,，、]/).map(value=>value.trim()).filter(Boolean))];
      if (aliases.length > 8 || aliases.some(value=>value.length > 30))
        throw Error(tr('Use up to 8 aliases of 30 characters each.','最多设置 8 个别名，每个不超过 30 字。'));
      const profile = {id,name,avatar,aliases,isSelf:profileDraft.isSelf};
      if (profile.isSelf) for (const row of saved) row.isSelf = false;
      if (index < 0) saved.push(profile);
      else saved[index] = profile;
      const participantProfiles = saved.map(row=>({id:row.id,name:row.name,avatar:row.avatar?.url ?? null,
        aliases:row.aliases,isSelf:row.isSelf}));
      await hostRequest('draft.set',{value:JSON.stringify({...draft,participantProfiles})},10000);
      profiles = saved;
      profileDraft = {...profile,aliases:aliases.join('、')};
      updateRows();
      $('profile-status').textContent = tr('Profile saved.', '档案已保存。');
    } catch (error) { $('profile-status').textContent = error.message; }
    finally { pending--; controls(); }
  }
  function updateRows() {
    $('participants').replaceChildren(...people.map((person,index) => {
      const inUse = messages.some(item => item.sender === person.id);
      const remove = button(tr('Remove','删除'),() => {
        releaseMedia(person.avatar);
        people.splice(index,1);
        updateRows();
      },index === 0 || inUse);
      if (inUse) remove.title = tr('Reassign their messages before removing them.', '请先调整该参与者所发消息的发送者。');
      const name = inputField(tr('Display name','显示名称'),person,'name',{maxLength:30});
      name.addEventListener('input',refreshLabels);
      const useProfile = profiles.length ? [selectField(tr('Use saved profile','选用已保存档案'),{id:''},'id',
        [['',tr('Choose a profile','选择档案')],...profileOptions()],() => {
          const saved = profiles.find(row=>row.id === useProfile[0].querySelector('select').value);
          if (!saved) return;
          person.name = saved.name;
          person.avatar = saved.avatar;
          updateRows();
        })] : [];
      return el('div',{className:'card'},[
        el('div',{className:'card-heading'},[el('strong',{textContent:index === 0 ? tr('Me (outgoing)','自己（右侧）') : tr('Participant ','参与者 ') + index}),remove]),
        ...useProfile,name,...mediaField(tr('Avatar','头像'),person,'avatar'),
      ]);
    }));
    $('messages').replaceChildren(...messages.map((message,index) => {
      const senders = people.map(item => [item.id,item.name.trim() || tr('Unnamed','未命名')]);
      const sender = selectField(tr('Sender','发送者'),message,'sender',senders,updateRows);
      sender.querySelector('select').dataset.sender = '';
      const offset = inputField(tr('Time since previous (seconds)','距上一条（秒）'),message,'offset',
        {type:'number',min:'0',max:'2592000',step:'1',required:true});
      if (index === 0) offset.firstChild.textContent = tr('Time from start (seconds)','距会话开始（秒）');
      const kind = selectField(tr('Message type','消息类型'),message,'kind',Object.entries(kinds),() => {
        if (['transfer','envelope'].includes(message.kind)) {
          message.state ||= 'sent';
          message.currency ||= ({imessage:'USD',whatsapp:'BRL'}[$('theme').value] || 'CNY');
        }
        updateRows();
      });
      const move = delta => {
        [messages[index],messages[index+delta]] = [messages[index+delta],messages[index]];
        updateRows();
      };
      return el('li',{className:'card'},[
        el('div',{className:'card-heading'},[el('strong',{textContent:tr('Message ','消息 ') + (index+1)}),
          el('div',{className:'row-actions'},[
            button(tr('Up','上移'),() => move(-1),index === 0),
            button(tr('Down','下移'),() => move(1),index === messages.length-1),
            button(tr('Delete','删除'),() => {
              for (const key of ['image','video','cover','map','avatar']) releaseMedia(message[key]);
              messages.splice(index,1);
              updateRows();
            }),
          ])]),
        el('div',{className:'grid'},[sender,offset,kind]),
        el('small',{className:'message-time',textContent:''}),...details(message),
      ]);
    }));
    renderProfiles();
    $('add-person').disabled = people.length >= 16;
    $('add-message').disabled = messages.length >= 30;
    preview(messages.length);
  }
  function read(strict = false) {
    const parts = $('start').value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/);
    const delay = Number($('delay').value);
    if (!parts || ![0.5,1,1.5,2,2.5,3].includes(delay))
      throw Error(tr('Set a start time and an animation interval of 0.5–3 seconds.', '请设置会话开始时间和 0.5～3 秒的动画间隔。'));
    let time = Date.parse($('start').value+'Z');
    if (!Number.isFinite(time) || +parts[1] < 1900 || +parts[1] > 9998)
      throw Error(tr('Enter a year between 1900 and 9998.', '请输入 1900～9998 年内的日期。'));
    const start = time;
    const sceneMessages = messages.map((message,index) => {
      const offset = Number(message.offset);
      let problem = '';
      if (message.offset === '' || !Number.isInteger(offset) || offset < 0 || offset > 2592000)
        problem = tr('Enter an offset from 0 to 2,592,000 seconds.','请输入 0～2592000 秒的整数时间差。');
      else time += offset*1000;
      const item = {...message,time,person:people.find(person => person.id === message.sender),own:message.sender === people[0].id};
      if (message.kind === 'link' && message.url) {
        try {
          const url = new URL(message.url);
          if (!['https:','http:'].includes(url.protocol) || url.username || url.password) throw Error();
          item.domain = url.hostname;
        } catch (_) {}
      }
      const required = {
        call:/^\d{1,3}:[0-5]\d$/.test(message.callDuration || ''),
        voice:Number.isInteger(Number(message.voiceSeconds)) &&
          Number(message.voiceSeconds) >= 1 && Number(message.voiceSeconds) <= 60,
        text:!!message.text?.trim(), image:!!message.image, video:!!message.video,
        link:!!item.domain, location:!!message.place?.trim(), contact:!!message.contact?.trim(),
        transfer:Number(message.amount) >= 0.01 && Number(message.amount) <= 999999,
        envelope:!message.amount || (Number(message.amount) >= 0.01 && Number(message.amount) <= 999999),
      };
      if (message.kind === 'call' && required.call) item.callDuration = message.callDuration.padStart(5,'0');
      if (strict && (problem || !required[message.kind]))
        throw Error(tr('Message ','消息 ') + (index+1) + ' · ' + (problem ||
          tr('Complete the fields for ','请补全') + kinds[message.kind]));
      return item;
    });
    if (strict && !sceneMessages.length) throw Error(tr('Add at least one message.', '请至少添加一条消息。'));
    const captureDate = $('capture-date').value;
    const captureTime = captureDate ? Date.parse(captureDate+'T00:00:00Z') : (sceneMessages.at(-1)?.time ?? start);
    const battery = $('battery').valueAsNumber;
    if (strict && (!Number.isInteger(battery) || battery < 0 || battery > 100))
      throw Error(tr('Enter a battery level from 0 to 100%.','请输入 0～100 的整数电量。'));
    const now = new Date();
    const localClock = [now.getHours(),now.getMinutes()].map(value=>String(value).padStart(2,'0')).join(':');
    return {captureTime,footerText:$('footer-text').value.trim(),statusOS:$('status-os').value,battery:Number.isFinite(battery)?battery:60,composerMode:$('composer-mode').value,title:$('title').value.trim() || tr('Conversation','对话'), theme:$('theme').value,
      size:sizes[$('ratio').value], group:people.length > 2, people, messages:sceneMessages, start, delay, clock:$('clock').value || localClock};
  }
  function controls() {
    const blocked = busy || pending > 0;
    if (blocked) {
      for (const node of $('editor').querySelectorAll('input, select, textarea, button')) {
        if (!node.disabled) { node.disabled = true; node.dataset.blocked = ''; }
      }
    } else {
      for (const node of $('editor').querySelectorAll('[data-blocked]')) {
        node.disabled = false;
        delete node.dataset.blocked;
      }
    }
    $('scrub').disabled = blocked;
    $('play').textContent = playing ? tr('Stop preview','停止预览') : tr('Play preview','播放预览');
  }
  function stop() { clearTimeout(timer); playing = false; controls(); }
  function draw(scene,count) {
    paint(scene,count);
    $('messages').querySelectorAll('.message-time').forEach((node,index) => {
      node.textContent = new Date(scene.messages[index].time).toISOString().slice(0,19).replace('T',' ');
    });
    $('scrub').max = scene.messages.length;
    $('scrub').value = count;
    $('position').textContent = count + ' / ' + scene.messages.length;
  }
  function preview(count) {
    stop();
    try { draw(read(),count); $('status').textContent = ''; }
    catch (error) { $('status').textContent = error.message; }
  }
  $('editor').addEventListener('submit', event => event.preventDefault());
  $('editor').addEventListener('input',event => {
    if (['file','select-one'].includes(event.target.type)) return;
    preview(messages.length);
  });
  $('theme').addEventListener('change', () => {
    $('composer-mode-field').hidden = $('theme').value !== 'wechat';
    preview(messages.length);
  });
  for (const id of ['ratio','composer-mode','status-os']) $(id).addEventListener('change', () => preview(messages.length));
  $('scrub').addEventListener('input',() => preview(Number($('scrub').value)));
  $('add-person').onclick = () => addPerson(tr('Participant ','参与者 ') + people.length);
  $('add-message').onclick = () => addMessage();
  $('play').onclick = () => {
    if (playing) return stop();
    try {
      const scene = read(true);
      let count = 0;
      playing = true;
      controls();
      function step() {
        draw(scene,++count);
        if (count < scene.messages.length) timer = setTimeout(step,scene.delay*1000);
        else stop();
      }
      step();
    } catch (error) { $('status').textContent = error.message; }
  };
  const portableFields = {
    theme:'theme', ratio:'ratio', status_os:'status-os', composer_mode:'composer-mode',
    battery:'battery', interval:'delay',
  };
  let portableRevision = 0;
  const stateRevision = () => ({
    revision:portableRevision,
    values:Object.fromEntries(Object.entries(portableFields).map(([key,id]) =>
      [key,['battery','interval'].includes(key) ? $(id).valueAsNumber : $(id).value])),
    busy:busy || pending > 0,
  });
  for (const id of Object.values(portableFields)) {
    $(id).addEventListener('input',()=>portableRevision++);
    $(id).addEventListener('change',()=>portableRevision++);
  }
  window.addEventListener('message',event=>{
    const message = event.data;
    const port = event.ports[0];
    if (event.source !== parent || event.origin !== location.origin || !port ||
        message?.type !== 'ai2apps:fantasy-feed-state/v1') return;
    try {
      if (message.action === 'apply') {
        if (busy || pending || message.revision !== portableRevision)
          throw Error('Fantasy Feed settings changed or the editor is busy.');
        const values = message.values;
        const choices = {theme:['wechat','whatsapp','telegram','imessage'],
          ratio:Object.keys(sizes),status_os:['ios','samsung'],composer_mode:['text','voice'],
          interval:[0.5,1,1.5,2,2.5,3]};
        if (!values || Object.keys(values).length !== 6 ||
            Object.entries(choices).some(([key,options])=>!options.includes(values[key])) ||
            !Number.isInteger(values.battery) || values.battery < 0 || values.battery > 100)
          throw Error('Invalid Fantasy Feed settings.');
        for (const [key,id] of Object.entries(portableFields)) $(id).value = values[key];
        portableRevision++;
        $('composer-mode-field').hidden = $('theme').value !== 'wechat';
        preview(Number($('scrub').value));
      } else if (message.action !== 'capture') throw Error('Unknown settings action.');
      port.postMessage({state:stateRevision()});
    } catch(error) { port.postMessage({error:error.message}); }
    finally { port.close(); }
  });
  const connected = new Promise((resolve,reject) => {
    function accept(event) {
      if (event.source !== parent || event.data?.type !== 'ai2apps:studio-connected' || event.data.version !== 1 || !event.ports[0]) return;
      clearTimeout(timeout); window.removeEventListener('message',accept); resolve(event.ports[0]);
    }
    const timeout = setTimeout(() => { window.removeEventListener('message',accept); reject(Error(tr('Open this Mini-App in Imagine Studio to export.','请在 Imagine Studio 中打开此 Mini-App 后导出。'))); },8000);
    window.addEventListener('message',accept);
    window.addEventListener('load',() => setTimeout(() => parent.postMessage({type:'ai2apps:studio-connect',version:1},'*'),0),{once:true});
  });
  connected.catch(() => {});
  let requestId = 0;
  let requestQueue = Promise.resolve();
  function hostRequest(operation,fields,timeoutMs) {
    const task = requestQueue.then(async () => {
      const port = await connected;
      return new Promise((resolve,reject) => {
        const id = ++requestId;
        function receive(event) {
          if (event.data?.id !== id) return;
          clearTimeout(timeout); port.removeEventListener('message',receive);
          if (event.data.error) reject(Error(event.data.error));
          else resolve(event.data.value);
        }
        const timeout = setTimeout(() => {
          port.removeEventListener('message',receive);
          reject(Error(operation === 'invoke' ?
            tr('Export timed out. Check Studio Output before retrying.','导出等待超时，请先查看 Studio 输出。') :
            tr('Profile request timed out. Reopen the editor to check saved profiles.','档案请求超时，请重新打开编辑器查看已保存档案。')));
        },timeoutMs);
        port.addEventListener('message',receive); port.start();
        port.postMessage({id,operation,...fields});
      });
    });
    requestQueue = task.catch(() => {});
    return task;
  }
  function invoke(file) {
    return hostRequest('invoke',{capability:'media.visual_sequence.export',fields:[['file',file]]},120000);
  }
  async function publish(format) {
    const selected = Number($('scrub').value);
    stop();
    busy = true;
    controls();
    try {
      const scene = read(true);
      const last = format === 'png' ? Math.max(1, selected) : scene.messages.length;
      const first = format === 'png' ? last : 1;
      $('status').textContent = tr('Creating output…','正在生成…');
      const frames = [];
      for (let count = first; count <= last; count++) {
        draw(scene,count);
        const mediaType = format === 'png' ? 'image/png' : 'image/jpeg';
        frames.push(canvas.toDataURL(mediaType,0.85).split(',')[1]);
        await new Promise(resolve => setTimeout(resolve,0));
      }
      const payload = new Blob([JSON.stringify({
        format, frames, seconds:scene.delay, encoding:format === 'mp4' ? 'jpeg' : 'png',
      })],{type:'application/json'});
      if (payload.size > 8 * 1024 * 1024)
        throw Error(tr('This export exceeds 8 MiB. Try fewer media messages or a smaller aspect ratio.', '导出超过 8 MiB，请减少媒体消息，或改用较小画幅。'));
      const result = await invoke(payload);
      if (result.status !== 200) {
        const failure = await result.body.text();
        let detail;
        try { detail = JSON.parse(failure).detail; } catch (_) {}
        throw Error(detail?.message || (typeof detail === 'string' && detail) || tr('Export failed.','导出失败。'));
      }
      $('status').textContent = tr('Ready in Studio Output.','已生成，可在创意画坊输出区预览和下载。');
    } catch (error) { $('status').textContent = error.message; }
    finally { busy = false; controls(); }
  }
  $('png').onclick = () => publish('png');
  $('mp4').onclick = () => publish('mp4');
  $('title').value = tr('Family group','周末家庭群');
  setInterval(() => {
    if (busy || playing || pending || $('clock').value || document.hidden) return;
    try { paint(read(),Number($('scrub').value)); } catch (_) {}
  },15000);
  $('footer-text').value = tr('SIMULATED CHAT','虚构对话');
  $('start').value = '2026-11-09T07:48';
  addPerson(tr('Me','我'));
  addPerson(tr('Mom','妈妈'));
  addPerson(tr('Dad','爸爸'));
  addPerson(tr('Sis','姐姐'));
  addMessage(people[1].id,tr('Who wants to go for a walk this afternoon?','下午有人想去散步吗？'));
  addMessage(people[3].id,tr('Count me in 🙋','算我一个 🙋'),'45');
  addMessage(people[2].id,tr('I’ll bring something to eat.','我带点吃的。'),'660');
  addMessage(people[0].id,tr('See you at the park entrance!','公园门口见！'),'15');
  $('profile-status').textContent = tr('Loading saved profiles…','正在读取已保存档案…');
  readProfileDraft().then(loadProfiles).then(saved => {
    profiles = saved;
    libraryReady = true;
    updateRows();
    $('profile-status').textContent = '';
  }).catch(() => {
    $('profile-status').textContent = tr('Saved profiles are available when opened in Imagine Studio.',
      '请在创意画坊中打开或重新打开，以读取已保存档案。');
  });
})();
