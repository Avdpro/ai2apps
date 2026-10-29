(function () {
    'use strict';

    function appInstanceId() {
        return window.AI2AppsCapabilities?.appInstanceId?.()
            || document.querySelector('[data-app-instance-id]')?.dataset?.appInstanceId
            || new URLSearchParams(window.location.hash.slice(1)).get('ai2apps-instance')
            || (window.AI2APPS_MOBILE_SURFACE&&window.location.pathname.startsWith('/mobile/app-resource/')?window.location.pathname.split('/')[4]:'')
            || '';
    }

    // Device data stays on the client running this host (including Mobile).
    // A live mount and an explicit host-owned prompt are required each time.
    async function requestDeviceLocation({signal, active=()=>true}={}) {
        if(!navigator.geolocation || !window.isSecureContext) throw new Error('Location unavailable; enter a city manually / 无法定位，请手动输入城市');
        const zh=/^zh/i.test(document.documentElement.lang||'');
        const allowed=await new Promise(resolve=>{
            const dialog=document.createElement('dialog');
            dialog.style.cssText='max-width:420px;width:calc(100vw - 40px);box-sizing:border-box;padding:24px;border:1px solid #ddd;border-radius:18px';
            const title=document.createElement('h2');title.textContent=zh?'使用此设备的位置？':'Use this device’s location?';
            const text=document.createElement('p');text.textContent=zh?'将本设备的大致经纬度提供给当前 Mini-App；只有继续整理需求时才会发送给所选模型。也可以取消并手动输入城市。':'Share approximate coordinates with this Mini-App. They are sent to your selected model only if you continue preparing your request. You can cancel and enter a city manually.';
            text.style.lineHeight='1.6';
            const cancel=document.createElement('button'),accept=document.createElement('button');
            cancel.textContent=zh?'取消':'Cancel';accept.textContent=zh?'使用当前位置':'Use current location';
            for(const button of [cancel,accept])button.style.cssText='font:inherit;padding:12px 16px;margin:8px 8px 0 0;border:1px solid #ddd;border-radius:10px';
            let finished=false;
            const done=value=>{if(finished)return;finished=true;clearTimeout(timer);signal?.removeEventListener('abort',aborted);dialog.remove();resolve(value);};
            const aborted=()=>done(false),timer=setTimeout(()=>done(false),60000);
            cancel.onclick=()=>done(false);accept.onclick=()=>done(true);
            dialog.addEventListener('cancel',event=>{event.preventDefault();done(false);});
            signal?.addEventListener('abort',aborted,{once:true});
            dialog.append(title,text,cancel,accept);document.body.append(dialog);dialog.showModal();
            if(signal?.aborted||!active())done(false);
        });
        if(!allowed||!active()||signal?.aborted)throw new Error('Location cancelled / 已取消定位');
        return new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(position=>{
            if(!active()||signal?.aborted){reject(new Error('Mini-App closed'));return;}
            const {latitude,longitude,accuracy}=position.coords;
            if(!Number.isFinite(latitude)||!Number.isFinite(longitude)||Math.abs(latitude)>90||Math.abs(longitude)>180){reject(new Error('Invalid location'));return;}
            resolve({latitude:Number(latitude.toFixed(2)),longitude:Number(longitude.toFixed(2)),accuracy_m:Math.max(1500,Number(accuracy)||1500)});
        },()=>reject(new Error('Location denied or unavailable; enter a city manually / 定位失败，请手动输入城市')),
        {enableHighAccuracy:false,timeout:15000,maximumAge:60000}));
    }

    function mobileResultURL(task, raw) {
        const url = new URL(raw);
        if(url.protocol!=='https:' || url.username || url.password) throw new Error('Invalid result URL');
        const items=[...(task.result?.items||[]),...(task.result?.articles||[]),...(task.result?.links||[])];
        if(!items.some(item=>item.url===url.href)) throw new Error('Result URL was not observed by this Task');
        return url;
    }

    function mobileCartURLs(task) {
        if(task.status!=='completed'||!['prepare_cart','gift_prepare_cart'].includes(task.capability)||task.result?.recognized!==true) throw new Error('Cart preparation is not complete');
        const stores=task.result.stores?.length?task.result.stores:[{page_url:task.result.page_url,channel:'amazon'}];
        return stores.map(store=>{
            const url=new URL(store.page_url);
            const path=decodeURIComponent(url.pathname);
            if(url.origin!=='https://www.amazon.com'||url.username||url.password||url.hash||!/(?:^|\/)cart(?:\/|$)/i.test(path)||/checkout|buy|purchase/i.test(path))throw new Error('Invalid prepared Amazon cart');
            return {url,channel:store.channel};
        });
    }

    function showMobileResult(url, options={}) {
        const locale=(document.documentElement.lang||'en').split('-')[0];
        const labels={
            zh:['打开搜索结果','在小红书 App 打开','网页打开（新标签页）','关闭','请确认系统的 App 打开提示；未安装 App 时可选择网页入口。'],
            en:['Open search result','Open in Xiaohongshu App','Open webpage in new tab','Close','Confirm the system App prompt. If the App is unavailable, use the webpage link.'],
            ja:['検索結果を開く','小紅書 Appで開く','新しいタブで開く','閉じる','システムの確認画面で App を開いてください。利用できない場合はウェブをご利用ください。'],
            ko:['검색 결과 열기','샤오홍슈 앱에서 열기','새 탭에서 웹페이지 열기','닫기','시스템 앱 열기 요청을 확인하세요. 앱이 없으면 웹페이지를 이용하세요.'],
            fr:['Ouvrir le résultat','Ouvrir dans Xiaohongshu','Ouvrir dans un nouvel onglet','Fermer',"Confirmez l’ouverture de l’application. Sinon, utilisez le lien web."],
            es:['Abrir resultado','Abrir en Xiaohongshu','Abrir en una pestaña nueva','Cerrar','Confirma la apertura de la app. Si no está disponible, usa el enlace web.'],
            pt:['Abrir resultado','Abrir no Xiaohongshu','Abrir em nova aba','Fechar','Confirme a abertura do app. Se indisponível, use o link da página.'],
            ru:['Открыть результат','Открыть в Xiaohongshu','Открыть в новой вкладке','Закрыть','Подтвердите открытие приложения. Если оно недоступно, используйте веб-ссылку.']
        };
        let [heading,appText,webText,closeText,hintText]=labels[locale]||labels.en;
        const cartLabels={zh:['查看亚马逊购物车','在手机打开购物车','请使用与准备购物车时相同的亚马逊账号。是否打开 App 由手机系统决定；也可以在网页中查看。'],en:['View Amazon cart','Open cart on this phone','Use the same Amazon account used to prepare the cart. Your phone may open the App or the website.'],ja:['Amazonカートを確認','この端末でカートを開く','準備時と同じAmazonアカウントを使用してください。端末によりアプリまたはウェブで開きます。'],ko:['Amazon 장바구니 보기','이 휴대폰에서 장바구니 열기','준비할 때와 동일한 Amazon 계정을 사용하세요. 앱 또는 웹사이트가 열릴 수 있습니다.'],fr:['Voir le panier Amazon','Ouvrir le panier sur ce téléphone','Utilisez le même compte Amazon. Le téléphone peut ouvrir l’application ou le site.'],es:['Ver carrito de Amazon','Abrir carrito en este teléfono','Usa la misma cuenta de Amazon. El teléfono puede abrir la app o el sitio.'],pt:['Ver carrinho Amazon','Abrir carrinho neste telefone','Use a mesma conta Amazon. O telefone pode abrir o app ou o site.'],ru:['Корзина Amazon','Открыть корзину на телефоне','Используйте тот же аккаунт Amazon. Телефон может открыть приложение или сайт.']};
        if(options.cart)[heading,webText,hintText]=cartLabels[locale]||cartLabels.en;
        const targets=mobileResultTargets(url);
        const dialog=document.createElement('dialog');
        dialog.style.cssText='box-sizing:border-box;width:calc(100vw - 40px);max-width:460px;max-height:calc(100dvh - 48px);overflow:auto;border:1px solid #ddd;border-radius:20px;padding:24px;color:#292524;background:#fff';
        const title=document.createElement('h2');title.textContent=heading;title.style.cssText='font-size:20px;line-height:1.35;margin:0 0 10px';
        const site=document.createElement('p');site.textContent=url.hostname;site.style.cssText='font-size:14px;color:#78716c;margin:0 0 20px;overflow-wrap:anywhere';
        const actions=document.createElement('div');actions.style.cssText='display:grid;gap:12px';
        const makeLink=(text,href,primary)=>{
            const link=document.createElement('a');link.href=href;link.target='_blank';link.rel='noopener noreferrer';link.textContent=text;
            link.style.cssText='box-sizing:border-box;display:block;width:100%;padding:14px 16px;min-height:48px;border:1px solid #d6d3d1;border-radius:12px;text-align:center;text-decoration:none;font-size:16px;line-height:1.4;'+(primary?'background:#171717;color:#fff':'background:#fff;color:#292524');
            // Native user-activated links preserve Safari's App confirmation
            // and open a new tab without an about:blank navigation race.
            return link;
        };
        dialog.append(title,site);
        if(options.cart){
            const hint=document.createElement('p');hint.textContent=hintText;hint.style.cssText='font-size:14px;line-height:1.5;margin:0 0 18px';dialog.append(hint);
        }
        if(targets.app){
            actions.append(makeLink(appText,targets.app,true));
            const hint=document.createElement('p');hint.textContent=hintText;hint.style.cssText='font-size:13px;line-height:1.5;color:#78716c;margin:0 0 18px';dialog.append(hint);
        }
        if(options.cart){
            for(const store of options.stores){const name=({fresh:'Amazon Fresh',whole_foods:'Whole Foods',amazon:'Amazon',unknown:'Amazon'})[store.channel]||'Amazon';actions.append(makeLink(name+' · '+webText,store.url.href,true));}
        } else actions.append(makeLink(webText,targets.web,!targets.app));
        const button=document.createElement('button');button.textContent=closeText;button.onclick=()=>dialog.close();button.style.cssText='font:inherit;min-height:44px;border:0;background:transparent;color:#78716c;padding:12px;margin-top:6px';actions.append(button);
        dialog.addEventListener('close',()=>dialog.remove(),{once:true});
        dialog.append(actions);document.body.append(dialog);dialog.showModal();
        return dialog;
    }

    function mobileResultTargets(url) {
        const web=new URL(url.href);
        const note=/^\/(?:explore|search_result)\/([a-f0-9]{24})\/?$/i.exec(web.pathname);
        if(/^(www\.)?(xiaohongshu|rednote)\.com$/.test(web.hostname)&&note){
            web.pathname='/explore/'+note[1];
            const app=new URL('xhsdiscover://item/'+note[1]);
            for(const key of ['xsec_token','xsec_source'])if(web.searchParams.has(key))app.searchParams.set(key,web.searchParams.get(key));
            return {web:web.href,app:app.href};
        }
        return {web:web.href,app:null};
    }

    function normalizedLocale(value) {
        const raw = String(value || 'en').trim().replaceAll('_', '-');
        if (!/^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$/.test(raw)) return 'en';
        return raw.split('-').map((part, index) => {
            if (index === 0) return part.toLowerCase();
            if (part.length === 2 && /^[A-Za-z]+$/.test(part)) return part.toUpperCase();
            if (part.length === 4 && /^[A-Za-z]+$/.test(part)) return part[0].toUpperCase() + part.slice(1).toLowerCase();
            return part.toLowerCase();
        }).join('-');
    }

    function localizedDeclaration(item, locale = document.documentElement.lang) {
        if (!item || typeof item !== 'object') return item;
        const normalized = normalizedLocale(locale);
        const localizations = item.localizations && typeof item.localizations === 'object'
            ? item.localizations : {};
        const byLocale = Object.fromEntries(Object.entries(localizations).map(([key, value]) => [
            String(key).replaceAll('_', '-').toLowerCase(), value,
        ]));
        const language = normalized.split('-', 1)[0].toLowerCase();
        const chineseFallback = /^zh-(HK|MO|Hant)$/i.test(normalized) ? byLocale['zh-tw'] : null;
        const languageDefault = language === 'zh' ? byLocale['zh-cn'] : null;
        const localized = byLocale[normalized.toLowerCase()] || chineseFallback
            || byLocale[language] || languageDefault || {};
        return {
            ...item,
            name: localized.name || item.name,
            summary: localized.summary || item.summary,
            description: localized.description || item.description,
        };
    }

    function taskModelError(value, locale = document.documentElement.lang) {
        const detail = value?.detail || value?.error || value;
        const raw = typeof detail === 'string' ? detail : String(detail?.message || '');
        const code = ['translation_not_ready', 'translation_failed'].includes(detail?.code) ? detail.code : (/translation_not_ready/.test(raw) ? 'translation_not_ready' : /translation_failed/.test(raw) ? 'translation_failed' : '');
        if (!['translation_not_ready', 'translation_failed'].includes(code)) return null;
        const zh = /^zh/i.test(locale || '');
        const simple = (detail?.details?.purpose || raw).includes('work_simple');
        const task = zh ? (simple ? '简单任务' : '标准任务') : (simple ? 'Simple Task' : 'Standard Task');
        if (code === 'translation_not_ready') return zh
            ? `尚未配置“${task}”模型。请打开“模型 → 默认模型”，为“${task}”选择已启用的 BYOK 或本地聊天模型，点击“保存默认设置”，再重试。脱机模式不能使用 Cloud 默认模型。`
            : `No ${task} model is configured. Open Models → Default models, select an enabled BYOK or local chat model for ${task}, save the defaults, then retry. Cloud defaults are unavailable in offline mode.`;
        const status = Number(detail?.details?.upstream_status || raw.match(/HTTP (\d{3})/)?.[1]);
        const advice = status === 401 || status === 403
            ? (zh ? '调用被拒绝。请检查 BYOK 密钥及模型访问权限；如果聊天可用而此处仍失败，请反馈此错误以检查系统调用权限。' : 'Access was denied. Check the BYOK key and model permissions. If Chat works but this workflow fails, report this error for a system permission check.')
            : status === 429
                ? (zh ? '请求受限。请检查供应商额度或用量限制，稍后重试。' : 'The request was limited. Check provider quota or rate limits, then retry later.')
                : (zh ? '请检查该模型能否正常聊天；确认供应商连接或本地模型运行状态，或在默认模型设置中换用其他模型后重试。' : 'Check whether the model works in Chat, verify the provider connection or local model status, or choose another default model and retry.');
        return `${zh ? `“${task}”模型调用失败` : `${task} model request failed`}${status ? ` (HTTP ${status})` : ''}。${advice}`;
    }

    async function payload(response) {
        const value = await response.json().catch(() => null);
        if (!response.ok) {
            // Include only the path, never query parameters or credentials.
            let route = '';
            try { if (response.url) route = ' [' + new URL(response.url, location.origin).pathname + ']'; } catch (_) {}
            throw new Error(`HTTP ${response.status}${route}: ` + (value?.error?.message || value?.detail?.message || value?.detail || 'Request failed'));
        }
        return value;
    }

    async function readAvatarInput(request, signal) {
        const ref = request.reference;
        const kind = request.kind;
        if (!['image', 'audio'].includes(kind) || !ref) throw new Error('Invalid avatar input');
        const identifier = value => typeof value === 'string' && /^[a-zA-Z0-9_-]{1,200}$/.test(value);
        const get = url => fetch(url, {credentials: 'same-origin', cache: 'no-store', signal});
        let url, name;
        if (ref.source === 'gallery' && identifier(ref.assetId)) {
            const asset = await payload(await get(`/v1/platform/gallery/assets/${encodeURIComponent(ref.assetId)}`));
            if (asset.kind !== kind) throw new Error('素材类型与槽位不匹配');
            url = `/v1/platform/gallery/assets/${encodeURIComponent(ref.assetId)}/content`;
            name = asset.name;
        } else if (ref.source === 'image-output' && kind === 'image' && identifier(ref.artifactId) && identifier(ref.appInstanceId)) {
            const runs = await payload(await fetch('/v1/platform/imagine-studio/runs?limit=100', {
                credentials: 'same-origin', cache: 'no-store', signal, headers: {'X-AI2Apps-App-Instance': ref.appInstanceId},
            }));
            const artifact = runs.items?.flatMap(run => run.artifacts || []).find(item => item.id === ref.artifactId);
            const parsed = new URL(artifact?.previewUrl || '/', location.origin);
            if (parsed.origin !== location.origin || !/^\/v1\/platform\/imagine-studio\/results\/isr_[0-9a-f]{32}\/content$/.test(parsed.pathname) || parsed.searchParams.get('appInstanceId') !== ref.appInstanceId) throw new Error('图片输出不可用');
            url = parsed.href; name = artifact.name;
        } else if (ref.source === 'audio-output' && kind === 'audio' && identifier(ref.sessionId) && identifier(ref.artifactId)) {
            const outputs = await payload(await get('/v1/platform/readaloud/outputs'));
            const expected = `/v1/platform/sessions/${encodeURIComponent(ref.sessionId)}/artifacts/${encodeURIComponent(ref.artifactId)}/download`;
            const item = outputs.items?.find(item => item.downloadUrl === expected && item.mediaType?.startsWith('audio/'));
            if (!item) throw new Error('声音输出不可用');
            url = expected; name = (item.title || 'speech') + '.wav';
        } else throw new Error('素材来源或类型不支持');
        const response = await get(url);
        if (!response.ok) throw new Error('无法读取素材');
        const type = (response.headers.get('content-type') || '').split(';')[0];
        const limit = (kind === 'image' ? 20 : 100) * 1024 * 1024;
        if (kind === 'image' ? !['image/png','image/jpeg','image/webp'].includes(type) : !type.startsWith('audio/')) throw new Error('素材类型与槽位不匹配');
        if (Number(response.headers.get('content-length')) > limit) throw new Error('素材超过槽位大小限制');
        const reader = response.body.getReader(), chunks = [];
        let size = 0;
        try {
            while (true) {
                const {done, value} = await reader.read();
                if (done) break;
                size += value.byteLength;
                if (size > limit) throw new Error('素材超过槽位大小限制');
                chunks.push(value);
            }
        } finally { await reader.cancel(); }
        if (!size) throw new Error('素材为空');
        return {body: new Blob(chunks, {type}), name: String(name || (kind === 'image' ? 'portrait.png' : 'speech.wav')).replace(/[\\/]/g, '-')};
    }

    function primaryCapability(miniApp) {
        const values = miniApp?.requirements?.capabilities;
        if (!Array.isArray(values) || values.length === 0) return '';
        const first = values[0];
        return typeof first === 'string' ? first : (typeof first?.capability === 'string' ? first.capability : '');
    }
    function setupStorageKey(studioId) { return `ai2apps.studio-mini-app.setup.${studioId}`; }
    function pendingSetup(studioId) {
        try { return JSON.parse(localStorage.getItem(setupStorageKey(studioId)) || 'null'); }
        catch (_) { localStorage.removeItem(setupStorageKey(studioId)); return null; }
    }
    function clearPendingSetup(studioId) { localStorage.removeItem(setupStorageKey(studioId)); }

    const PACKAGE_FRAME_SELECTORS = [
        '.ra-package-mini-app-frame',
        '.vs-package-mini-app-frame',
        '.is-package-mini-app-frame',
        '.aib-package-mini-app-frame',
    ].join(',');
    function packageFrameForSource(source) {
        return [...document.querySelectorAll(PACKAGE_FRAME_SELECTORS)]
            .find(frame => frame.contentWindow === source);
    }
    function handlePackageMiniAppResize(event) {
        const message = event?.data;
        if (message?.type !== 'ai2apps:mini-app-resize' || message?.version !== 1) return;
        const frame = packageFrameForSource(event.source);
        if (!frame) return;
        const requested = Number(message.height);
        if (!Number.isFinite(requested)) return;
        const height = Math.min(20000, Math.max(620, Math.ceil(requested)));
        if (frame.dataset.contentHeight === String(height)) return;
        frame.dataset.contentHeight = String(height);
        frame.style.height = `${height}px`;
    }
    window.addEventListener('message', handlePackageMiniAppResize);

    const mountedFrames = new Map();
    const channels = new WeakMap();
    const mediaCapabilities = new Set(['video.avatar_generation', 'audio.detailed_transcription', 'audio.source_separation',
        'media.video_subtitles', 'media.video_audio_translation',
        'audio.speaker_voice_replacement', 'media.video_speaker_voice_replacement']);
    const audioGenerationCapabilities = new Set(['audio.music_generation', 'audio.sound_effects_generation', 'audio.song_generation']);
    const setupCapabilities = new Set([...mediaCapabilities, ...audioGenerationCapabilities, 'audio.voice_clone', 'image.frozen_time.da', 'image.frozen_time.vggt']);
    const progressCapabilities = new Set([
        'video.avatar_generation',
        'media.video_subtitles',
        'media.video_audio_translation',
    ]);
    const formFields = new Set(['avatar_model_id', 'avatar_resolution', 'file', 'reference', 'profile', 'language', 'word_timestamps', 'diarization', 'output_format',
        'source_language', 'target_language', 'subtitle_format', 'subtitle_action', 'subtitle_segments', 'bilingual', 'burn_in', 'speaker_labels',
        'subtitle_font_size', 'subtitle_background', 'voice_profile_id', 'voice_clone_model_id', 'asr_verification',
        'action', 'target_speaker', 'consent', 'conversion_profile', 'voice_name']);
    window.addEventListener('message', event => {
        if (event.data?.type !== 'ai2apps:studio-connect' || event.data?.version !== 1) return;
        const frame = packageFrameForSource(event.source);
        const binding = frame && mountedFrames.get(frame.src);
        if (!binding || (event.origin !== 'null' && event.origin !== location.origin)) return;
        channels.get(frame)?.();
        const channel = new MessageChannel();
        const source = event.source;
        const src = frame.src;
        let closed = false;
        let busy = false;
        let avatarJobsState = "";
        const downloads = new Set();
        const mobileDialogs = new Set();
        const progressSources = new Set();
        let audioRecorder = null;
        let audioGenerationJob = null, audioGenerationCancelRequested = false;
        let audioGenerationAbort = null, llmAbort = null;
        let webPollTimer = null;
        const abort = new AbortController();
        const active = () => !closed && frame.isConnected && frame.src === src && frame.contentWindow === source;
        const close = () => {
            closed = true; abort.abort(); audioGenerationAbort?.abort(); llmAbort?.abort();
            clearTimeout(webPollTimer);
            mobileDialogs.forEach(dialog=>dialog.remove());mobileDialogs.clear();
            audioRecorder?.dispose();
            progressSources.forEach(source => source.close()); progressSources.clear();
            channel.port1.close(); observer.disconnect(); localeObserver.disconnect();
            frame.removeEventListener('load', revoke);
        };
        const revoke = () => { mountedFrames.delete(src); close(); };
        const observer = new MutationObserver(() => { if (!active()) revoke(); });
        const localeObserver = new MutationObserver(() => {
            if (active()) channel.port1.postMessage({type: 'ai2apps:studio-locale', locale: document.documentElement.lang || 'en'});
        });
        localeObserver.observe(document.documentElement, {attributes: true, attributeFilter: ['lang']});
        observer.observe(frame, {attributes: true, attributeFilter: ['src']});
        observer.observe(document.documentElement, {childList: true, subtree: true});
        frame.addEventListener('load', revoke);
        channels.set(frame, close);
        const base = `/v1/platform/studios/${encodeURIComponent(binding.studioId)}/mini-app-mounts/${encodeURIComponent(binding.mountId)}`;
        const webTasks = new Set();
        let webEvents = null;
        const webTaskRefresh = new Map();
        const webTaskVersions = new Map();
        const watchWebTask = taskId => {
            if (!active()) return Promise.resolve();
            const current = webTaskRefresh.get(taskId);
            if (current) { current.again = true; return current.promise; }
            const refresh = {again: false};
            refresh.promise = (async () => {
                do {
                    refresh.again = false;
                    const task = await payload(await fetch(`${base}/web-agent/tasks/${encodeURIComponent(taskId)}`, {
                        credentials:'same-origin',cache:'no-store',signal:abort.signal,
                    }));
                    const version = JSON.stringify([task.status,task.message,task.result,task.failure,
                        task.progress,task.status_label,task.requires_user,task.paused,task.assistance_kind,task.browser_context?.cleanup]);
                    if(active() && webTaskVersions.get(taskId)!==version) {
                        webTaskVersions.set(taskId,version);
                        channel.port1.postMessage({type:'ai2apps:web-agent-task',task});
                    }
                    if(['completed','failed','cancelled'].includes(task.status)) webTasks.delete(taskId);
                } while(active() && refresh.again);
            })().finally(()=>webTaskRefresh.delete(taskId));
            webTaskRefresh.set(taskId,refresh);
            return refresh.promise;
        };
        const startWebPolling = () => {
            if(webPollTimer || !active()) return;
            webPollTimer = setTimeout(async () => {
                webPollTimer = null;
                await Promise.allSettled([...webTasks].map(id=>watchWebTask(id)));
                if(active() && webTasks.size) startWebPolling();
            }, 3000);
        };
        const startWebEvents = () => {
            // Mobile proxies and suspended phone tabs can lose SSE updates.
            // Refresh tracked tasks through the authenticated bridge as well.
            startWebPolling();
            if(webEvents) return;
            webEvents = new EventSource('/v1/platform/browser-workspace/events',{withCredentials:true});
            progressSources.add(webEvents);
            webEvents.addEventListener('browser.workspace.snapshot',()=>{
                for(const id of webTasks) void watchWebTask(id).catch(()=>{});
            });
            webEvents.addEventListener('browser.workspace.changed',event=>{
                try { const id=JSON.parse(event.data)?.payload?.task?.id;
                    if(webTasks.has(id)) void watchWebTask(id).catch(()=>{});
                } catch (_) {}
            });
            webEvents.onopen=()=>{for(const id of webTasks)void watchWebTask(id).catch(()=>{});};
        };
        const storageKey = `ai2apps.studio-draft.v1:${binding.owner}:${binding.provider}:${binding.resource}`;
        channel.port1.onmessage = async message => {
            const request = message.data;
            let progressSource = null;
            if (!active()) { close(); return; }
            if (!Number.isSafeInteger(request?.id) || request.id < 1) return;
            const reply = value => { if (active()) channel.port1.postMessage({id: request.id, ...value}); };
            if (request.operation === 'llm.cancel') { llmAbort?.abort(); reply({value:{cancelled:!!llmAbort}}); return; }
            if (request.operation === 'audio-generation.cancel') {
                // A private channel may cancel only its own in-flight generation.
                audioGenerationCancelRequested = true;
                if (audioGenerationJob) {
                    try { await payload(await fetch(`/v1/platform/studio-jobs/${encodeURIComponent(audioGenerationJob)}/cancel`,
                        {method:'POST', credentials:'same-origin'})); }
                    catch (error) { reply({error:error.message}); return; }
                }
                audioGenerationAbort?.abort(); reply({value: {cancelled: !!audioGenerationAbort}}); return;
            }
            if (busy) { reply({error: 'A Mini-App operation is already running'}); return; }
            busy = true;
            if (request.operation === 'audio-generation.generate') { audioGenerationAbort = new AbortController(); audioGenerationJob = null; audioGenerationCancelRequested = false; }
            if (request.operation === 'llm.complete') llmAbort = new AbortController();
            try {
                // Revalidate actor, live mount and signed declaration for every operation,
                // including draft access; the iframe never receives session credentials.
                const probe = await payload(await fetch(`${base}/capabilities`, {
                    credentials: 'same-origin', cache: 'no-store', signal: abort.signal,
                }));
                if (!active()) return;
                if (request.operation === 'device.location') {
                    if(!probe.items?.some(item=>item.capability==='device.location'&&item.ready)) throw new Error('device.location is not declared');
                    reply({value:await requestDeviceLocation({signal:abort.signal,active})});
                }
                else if (request.operation === 'llm.complete') {
                    if (!probe.items?.some(item => item.capability === 'llm.text')) throw new Error('llm.text is required');
                    reply({value: await payload(await fetch(`${base}/llm`, {
                        method:'POST', credentials:'same-origin', signal:llmAbort.signal,
                        headers:{'Content-Type':'application/json'}, body:JSON.stringify(request.payload || {})
                    }))});
                }
                else if (request.operation === 'notifications.send') {
                    const response=await fetch(`/v1/platform/studios/${encodeURIComponent(binding.studioId)}/mini-app-mounts/${encodeURIComponent(binding.mountId)}/notifications`,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(request.notification)});
                    reply({value:await payload(response)});
                }
                else if (request.operation === 'asset.pick') {
                    if (!['image/png,image/jpeg,image/webp','image/*','audio/*','video/*'].includes(request.accept)) throw new Error('Invalid asset types');
                    reply({value: await window.AI2AppsMobileStudio.pickAsset(frame, {accept:request.accept,signal:abort.signal})});
                }
                else if (request.operation === 'probe') reply({value: probe});
                else if (request.operation === 'web-agent.startup') {
                    if(binding.studioId !== 'ai2apps.ai-browser') throw new Error('Not a Web-Agent Mini-App');
                    // Independent, read-only startup data share one mount probe.
                    // Custom sources also enforce their actor/mount scope at the API.
                    const read = path => fetch(path, {
                        credentials:'same-origin',cache:'no-store',signal:abort.signal,
                    }).then(payload);
                    const [profiles, sources, saved] = await Promise.all([
                        read('/v1/platform/client/browser-profiles'),
                        request.includeDraft ? Promise.resolve(null) : read(`${base}/web-agent/custom-sources`),
                        request.includeDraft ? read(`${base}/draft`) : Promise.resolve(null),
                    ]);
                    reply({value:{profiles:profiles.map(({key,name,is_default})=>({key,name,is_default})),
                        ...(sources?{sources:sources.sources}:{}),...(request.includeDraft?{draft:saved.value}:{})}});
                }
                else if (request.operation === 'web-agent.profiles') {
                    if(binding.studioId !== 'ai2apps.ai-browser') throw new Error('Not a Web-Agent Mini-App');
                    const profiles = await payload(await fetch('/v1/platform/client/browser-profiles', {
                        credentials:'same-origin',cache:'no-store',signal:abort.signal,
                    }));
                    reply({value:profiles.map(({key,name,is_default})=>({key,name,is_default}))});
                }
                else if(request.operation==='web-agent.search-config') {
                    if(binding.studioId !== 'ai2apps.ai-browser')throw new Error('Not a Web-Agent Mini-App');
                    reply({value:await payload(await fetch(`${base}/web-agent/search-config`,{method:request.config?'PUT':'GET',credentials:'same-origin',signal:abort.signal,headers:{'Content-Type':'application/json'},...(request.config?{body:JSON.stringify(request.config)}:{})}))});
                }
                else if(request.operation==='web-agent.cloud-search-request') {
                    if(binding.studioId!=='ai2apps.ai-browser'||binding.miniAppId!=='ai2apps.search-all')throw new Error('Search All required');
                    const method={read:'GET',cancel:'POST',delete:'DELETE'}[request.action||'read'];
                    if(!method||typeof request.taskId!=='string')throw new Error('Invalid search request action');
                    reply({value:await payload(await fetch(`${base}/web-agent/cloud-search-requests/${encodeURIComponent(request.taskId)}`,{
                        method,credentials:'same-origin',cache:'no-store',signal:abort.signal}))});
                }
                else if(request.operation==='web-agent.search-preparation'||request.operation==='web-agent.search-workflow') {
                    if(binding.studioId!=='ai2apps.ai-browser'||binding.miniAppId!=='ai2apps.search-all')throw new Error('Search All required');
                    const kind=request.operation==='web-agent.search-preparation'?'search-preparations':'search-workflows';
                    const suffix=request.preparationId?'/'+encodeURIComponent(request.preparationId):'';
                    reply({value:await payload(await fetch(`${base}/web-agent/${kind}${suffix}`,{
                        method:request.body?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:abort.signal,
                        headers:{'Content-Type':'application/json'},...(request.body?{body:JSON.stringify(request.body)}:{})}))});
                }
                else if(['web-agent.search-summary','web-agent.search-chat'].includes(request.operation)) {
                    if(binding.studioId!=='ai2apps.ai-browser'||binding.miniAppId!=='ai2apps.search-all')throw new Error('Search All required');
                    const chat=request.operation==='web-agent.search-chat';
                    const result=await payload(await fetch(`${base}/web-agent/search-workflows/${encodeURIComponent(request.preparationId)}/${chat?'chat':'summary'}`,{
                        method:request.start||chat?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:abort.signal,
                        headers:{'Content-Type':'application/json'},...(chat?{body:JSON.stringify({request_id:request.requestId})}:{})}));
                    reply({value:result});
                    if(chat){
                        // Reload the destination Shell so its existing Chat startup
                        // reads the newly selected, owner-scoped conversation.
                        const mobile=!!window.AI2APPS_MOBILE_SURFACE||!!frame.closest('.sm-mobile,.aib-mobile');
                        window.top.location.assign(mobile?(window.top.location.pathname.startsWith('/mobile/home')?'/mobile/home':'/mobile')+'#app=ai2apps.general-chat':'/apps/ai2apps.general-chat');
                    }
                }
                else if(request.operation==='web-agent.custom-sources') {
                    if(binding.studioId !== 'ai2apps.ai-browser')throw new Error('Not a Web-Agent Mini-App');
                    const suffix=request.sourceId?'/'+encodeURIComponent(request.sourceId):'';
                    reply({value:await payload(await fetch(`${base}/web-agent/custom-sources${suffix}`,{
                        method:request.sourceId?'DELETE':request.taskId?'POST':'GET',credentials:'same-origin',
                        cache:'no-store',signal:abort.signal,headers:{'Content-Type':'application/json'},
                        ...(request.taskId?{body:JSON.stringify({task_id:request.taskId})}:{})}))});
                }
                else if(request.operation==='web-agent.delete-shopping-history') {
                    if(binding.studioId !== 'ai2apps.ai-browser')throw new Error('Not a Web-Agent Mini-App');
                    reply({value:await payload(await fetch(`${base}/web-agent/delete-shopping-history`,{method:'POST',credentials:'same-origin',signal:abort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmation:request.confirmation})}))});
                }
                else if(request.operation==='web-agent.product-images') {
                    if(binding.studioId !== 'ai2apps.ai-browser')throw new Error('Not a Web-Agent Mini-App');
                    reply({value:await payload(await fetch(`${base}/web-agent/product-images`,{method:'POST',credentials:'same-origin',signal:abort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({task_ids:request.taskIds})}))});
                }
                else if(request.operation==='web-agent.retained-tasks') {
                    if(binding.studioId !== 'ai2apps.ai-browser')throw new Error('Not a Web-Agent Mini-App');
                    reply({value:await payload(await fetch(`${base}/web-agent/retained-tasks`,{credentials:'same-origin',cache:'no-store',signal:abort.signal}))});
                }
                else if (['web-agent.submit','web-agent.task','web-agent.watch','web-agent.pages','web-agent.open-result'].includes(request.operation)) {
                    if(binding.studioId !== 'ai2apps.ai-browser') throw new Error('Not a Web-Agent Mini-App');
                    if(request.operation==='web-agent.open-result') {
                        if(window.AI2APPS_MOBILE_SURFACE || frame.closest('.sm-mobile,.aib-mobile')) {
                            const task=await payload(await fetch(`${base}/web-agent/tasks/${encodeURIComponent(request.taskId)}`,{credentials:'same-origin',cache:'no-store',signal:abort.signal}));
                            const url=mobileResultURL(task,request.url);
                            const dialog=showMobileResult(url);mobileDialogs.add(dialog);
                            dialog.addEventListener('close',()=>mobileDialogs.delete(dialog),{once:true});
                            reply({value:{opened_on:'mobile',url:url.href}});
                            return;
                        }
                        reply({value:await payload(await fetch(`${base}/web-agent/tasks/${encodeURIComponent(request.taskId)}/open-result`,{method:'POST',credentials:'same-origin',signal:abort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({url:request.url})}))});
                    } else if(request.operation==='web-agent.pages') {
                        if(!['list','focus','close'].includes(request.action))throw new Error('Invalid page action');
                        if(request.action==='focus'&&(window.AI2APPS_MOBILE_SURFACE||frame.closest('.sm-mobile,.aib-mobile'))&&binding.miniAppId==='ai2apps.shopping-pro') {
                            const task=await payload(await fetch(`${base}/web-agent/tasks/${encodeURIComponent(request.taskId)}`,{credentials:'same-origin',cache:'no-store',signal:abort.signal}));
                            if(['prepare_cart','gift_prepare_cart'].includes(task.capability)){
                                const stores=mobileCartURLs(task);
                                const dialog=showMobileResult(stores[0].url,{cart:true,stores});mobileDialogs.add(dialog);
                                dialog.addEventListener('close',()=>mobileDialogs.delete(dialog),{once:true});
                                reply({value:{opened_on:'mobile',urls:stores.map(store=>store.url.href)}});return;
                            }
                        }

                        reply({value:await payload(await fetch(`${base}/web-agent/tasks/${encodeURIComponent(request.taskId)}/pages/${request.action}`,{method:'POST',credentials:'same-origin',signal:abort.signal}))});
                    } else if(request.operation==='web-agent.submit') {
                        const task = await payload(await fetch(`${base}/web-agent/tasks`, {
                            method:'POST',credentials:'same-origin',signal:abort.signal,
                            headers:{'Content-Type':'application/json'},
                            body:JSON.stringify({capability:request.capability,parameters:request.parameters||{},
                                profile:request.profile||'default',request_id:request.requestId,retain_pages:request.retainPages===true,
                                ...(request.batchId?{batch_id:request.batchId,batch_size:request.batchSize}: {})}),
                        }));
                        webTasks.add(task.id);startWebEvents();reply({value:task});
                        window.dispatchEvent(new CustomEvent('ai2apps:web-agent-submitted',{detail:{task}}));
                        void watchWebTask(task.id).catch(()=>{});
                    } else {
                        const task=await payload(await fetch(`${base}/web-agent/tasks/${encodeURIComponent(request.taskId)}`, {
                            credentials:'same-origin',cache:'no-store',signal:abort.signal,
                        }));
                        if(request.operation==='web-agent.watch'){webTasks.add(task.id);startWebEvents();}
                        reply({value:task});
                    }
                }
                else if (request.operation === 'audio-generation.models' || request.operation === 'audio-generation.generate') {
                    if (binding.studioId !== 'ai2apps.readaloud' || !audioGenerationCapabilities.has(request.capability)
                        || !probe.items?.some(item => item.capability === request.capability)) throw new Error('Capability is not allowed');
                    if (request.operation === 'audio-generation.models') {
                        reply({value: await payload(await fetch(`${base}/audio-generation-models?capability=${encodeURIComponent(request.capability)}`,
                            {credentials: 'same-origin', signal: abort.signal, cache: 'no-store'}))});
                    } else {
                        if (!request.payload || JSON.stringify(request.payload).length > (request.capability === 'audio.song_generation' ? 524288 : 20000)) throw new Error('Invalid generation request');
                        if (audioGenerationAbort.signal.aborted) throw new Error('Generation cancelled');
                        let invocationId = '';
                        window.dispatchEvent(new CustomEvent('ai2apps:studio-output-state', {detail: {studioId: binding.studioId, running: true}}));
                        try {
                            if (request.capability === 'audio.song_generation') {
                                const invocation = await payload(await fetch(`${base}/invocations`, {method:'POST', credentials:'same-origin',
                                    signal:audioGenerationAbort.signal, headers:{'Content-Type':'application/json'},
                                    body:JSON.stringify({capability:request.capability})}));
                                if (!/^[0-9a-f]{32}$/.test(invocation.id || '')) throw new Error('Invalid progress invocation');
                                invocationId = invocation.id;
                                const eventsUrl = new URL(invocation.eventsUrl, location.origin);
                                if (eventsUrl.origin !== location.origin || eventsUrl.pathname !== `${base}/invocations/${invocationId}/events`) throw new Error('Invalid progress URL');
                                progressSource = new EventSource(eventsUrl.href, {withCredentials:true});
                                progressSources.add(progressSource);
                                progressSource.addEventListener('progress', event => {
                                    try { const progress=JSON.parse(event.data);
                                        if(active() && progress.invocationId===invocationId) channel.port1.postMessage({type:'ai2apps:studio-progress',progress});
                                    } catch (_) {}
                                });
                            }
                            let result = await payload(await fetch(`${base}/audio-generation`, {method:'POST', credentials:'same-origin',
                                headers:{'Content-Type':'application/json','Prefer':'respond-async','Idempotency-Key':`audio-${Date.now()}-${Math.random().toString(36).slice(2)}`,...(invocationId?{'X-AI2Apps-Invocation-ID':invocationId}:{})},
                                body:JSON.stringify({...request.payload, capability:request.capability})}));
                            if (result.id && result.status) {
                                audioGenerationJob = result.id;
                                if (audioGenerationCancelRequested) {
                                    await payload(await fetch(`/v1/platform/studio-jobs/${encodeURIComponent(result.id)}/cancel`,
                                        {method:'POST', credentials:'same-origin'}));
                                }
                                if (progressSource) { progressSource.close(); progressSources.delete(progressSource); }
                                const phases = {plan:0,abc:0,semantic:1,synthesis:2,synthesize:2,decode:3,vae:3,saving:4,complete:4};
                                // Unmount aborts observation only. The accepted job belongs to Local.
                                while (!['succeeded','failed','cancelled','interrupted','publish_failed'].includes(result.status)) {
                                    if (audioGenerationAbort.signal.aborted) throw new Error('Observation stopped');
                                    await new Promise(resolve => setTimeout(resolve, 1000));
                                    result = await payload(await fetch(`/v1/platform/studio-jobs/${encodeURIComponent(audioGenerationJob)}`,
                                        {credentials:'same-origin', cache:'no-store', signal:audioGenerationAbort.signal}));
                                    const phase = result.result?.progress;
                                    if (active() && invocationId && phases[phase] !== undefined) channel.port1.postMessage({type:'ai2apps:studio-progress',
                                        progress:{invocationId,phaseIndex:phases[phase],status:'running',percent:0,detail:phase}});
                                }
                                if (result.status !== 'succeeded') throw new Error(result.error?.message || result.status);
                                result = result.result;
                            }
                            const url = new URL(result.downloadUrl, location.origin);
                            if (url.origin !== location.origin || !/^\/v1\/platform\/sessions\/[^/]+\/artifacts\/[^/]+\/download$/.test(url.pathname)) throw new Error('Invalid output URL');
                            window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail:{studioId:binding.studioId,miniAppId:binding.miniAppId,result}}));
                            reply({value:{completed:true, durationSeconds:result.durationSeconds, reachedLimit:result.reachedLimit === true, preparedPrompt:result.preparedPrompt}});
                        } finally {
                            if (progressSource) { progressSource.close(); progressSources.delete(progressSource); }
                            audioGenerationAbort = null;
                            audioGenerationJob = null;
                            window.dispatchEvent(new CustomEvent('ai2apps:studio-output-state', {detail:{studioId:binding.studioId,running:false}}));
                        }
                    }
                }
                else if (['avatar.record.start', 'avatar.record.stop', 'avatar.record.cancel'].includes(request.operation)) {
                    if (binding.studioId !== 'ai2apps.video-studio' || !probe.items?.some(item => item.capability === 'video.avatar_generation')) throw new Error('Capability is not allowed');
                    if (request.operation === 'avatar.record.start') {
                        if (audioRecorder?.pending || audioRecorder?.recorder?.state === 'recording') throw new Error('recording_busy');
                        audioRecorder?.dispose();
                        audioRecorder = new window.AI2AppsStudioAudioRecorder();
                        reply({value: await audioRecorder.start(request.maxSeconds)});
                    } else if (request.operation === 'avatar.record.stop') {
                        if (!audioRecorder) throw new Error('recording_empty');
                        reply({value: await audioRecorder.stop()});
                    } else { audioRecorder?.dispose(); audioRecorder = null; reply({value:{cancelled:true}}); }
                }
                else if (request.operation.startsWith('frozen.')) {
                    if (binding.studioId !== 'ai2apps.imagine-studio' || binding.miniAppId !== 'ai2apps.imagine.frozen-time'
                        || !probe.items?.some(item => item.capability === 'image.frozen_time.vggt')) throw new Error('Capability is not allowed');
                    const headers = {'X-AI2Apps-App-Instance': appInstanceId()};
                    const root = '/v1/platform/imagine-studio';
                    if (request.operation === 'frozen.models') reply({value: await payload(await fetch(`${root}/frozen-time/models`, {credentials:'same-origin', headers, signal:abort.signal}))});
                    else if (request.operation === 'frozen.latest') {
                        const history=await payload(await fetch(`${root}/runs`,{credentials:'same-origin',headers,signal:abort.signal}));
                        reply({value:history.items?.find(item=>item.miniAppId===binding.miniAppId&&item.status==='succeeded')||null});
                    }
                    else if (request.operation === 'frozen.input.read') reply({value: await readAvatarInput({...request, kind:request.kind==='audio'?'audio':'image'}, abort.signal)});
                    else if (request.operation === 'frozen.preview') {
                        if (!(request.image instanceof Blob) || !request.image.size || request.image.size>20*1024*1024) throw new Error('Image exceeds 20 MiB');
                        const body = new FormData();body.append('image',request.image,request.image.name||'image.png');
                        for (const key of ['depth','output','long_edge','trajectory']) body.append(key,String(request.options?.[key]??''));
                        body.append('reference_speedup',String(request.options?.reference_speedup??true));
                        reply({value:await payload(await fetch(`${root}/frozen-time/mounts/${encodeURIComponent(binding.mountId)}/previews`,{method:'POST',credentials:'same-origin',headers,body,signal:abort.signal}))});
                    } else if (['frozen.preview.status','frozen.preview.video','frozen.preview.cancel'].includes(request.operation)) {
                        if (!/^[a-f0-9]{32}$/.test(request.previewId||'')) throw new Error('Invalid preview');
                        const response = await fetch(`${root}/frozen-time/previews/${request.previewId}${request.operation==='frozen.preview.video'?'/video':''}`,{method:request.operation==='frozen.preview.cancel'?'DELETE':'GET',credentials:'same-origin',headers,signal:abort.signal});
                        if(request.operation==='frozen.preview.video') {if(!response.ok)throw new Error('Preview unavailable');reply({value:await response.blob()});}
                        else reply({value:await payload(response)});
                    }
                    else if (request.operation === 'frozen.save-live-photo') {
                        if (!/^strun_[a-zA-Z0-9_-]+$/.test(request.runId||''))throw new Error('Invalid Run');
                        reply({value:await payload(await fetch(`${root}/frozen-time/mounts/${encodeURIComponent(binding.mountId)}/runs/${encodeURIComponent(request.runId)}/save-live-photo`,{method:'POST',credentials:'same-origin',headers,signal:abort.signal}))});
                    }
                    else if (request.operation === 'frozen.convert') {
                        if (!/^strun_[a-zA-Z0-9_-]+$/.test(request.runId||''))throw new Error('Invalid Run');
                        const body=new FormData();body.append('output',request.output||'');
                        if (request.audio != null) {
                            if (request.output!=='mp4'||!(request.audio instanceof Blob)||!request.audio.size||request.audio.size>100*1024*1024||!request.audio.type.startsWith('audio/'))throw new Error('Invalid MP4 soundtrack');
                            body.append('audio',request.audio,request.audio.name||'soundtrack');
                        }
                        const result=await payload(await fetch(`${root}/frozen-time/mounts/${encodeURIComponent(binding.mountId)}/runs/${encodeURIComponent(request.runId)}/convert`,{method:'POST',credentials:'same-origin',headers,body}));
                        window.dispatchEvent(new CustomEvent('ai2apps:studio-output',{detail:{studioId:binding.studioId,miniAppId:binding.miniAppId,runId:result.id}}));
                        reply({value:result});
                    }
                    else if (request.operation === 'frozen.run') {
                        if (!/^[a-f0-9]{32}$/.test(request.previewId||'')) throw new Error('Preview the camera movement first');
                        if (request.audio != null && (request.options?.output!=='mp4'||!(request.audio instanceof Blob)||!request.audio.size||request.audio.size>100*1024*1024||!request.audio.type.startsWith('audio/')))throw new Error('Invalid MP4 soundtrack');
                        const run = await payload(await fetch(`${root}/frozen-time/mounts/${encodeURIComponent(binding.mountId)}/runs`, {method:'POST', credentials:'same-origin', headers, signal:abort.signal}));
                        const body = new FormData(); body.append('preview_id',request.previewId);
                        for (const key of ['depth','output','long_edge','seed','trajectory']) body.append(key, String(request.options?.[key] ?? ''));
                        body.append('reference_speedup',String(request.options?.reference_speedup??true));
                        if (request.audio != null) {
                            if (request.options?.output!=='mp4'||!(request.audio instanceof Blob)||!request.audio.size||request.audio.size>100*1024*1024||!request.audio.type.startsWith('audio/'))throw new Error('Invalid MP4 soundtrack');
                            body.append('audio',request.audio,request.audio.name||'soundtrack');
                        }
                        const result = await payload(await fetch(`${root}/runs/${encodeURIComponent(run.id)}/frozen-time`, {method:'POST', credentials:'same-origin', headers, body}));
                        window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail:{studioId:binding.studioId, miniAppId:binding.miniAppId, runId:result.id}}));
                        reply({value:result});
                    } else if (request.operation === 'frozen.status' || request.operation === 'frozen.cancel') {
                        if (!/^strun_[a-zA-Z0-9_-]+$/.test(request.runId || '')) throw new Error('Invalid Run');
                        if (request.operation === 'frozen.cancel') await payload(await fetch(`${root}/runs/${encodeURIComponent(request.runId)}`, {credentials:'same-origin',headers,signal:abort.signal}));
                        const result = await payload(await fetch(`${root}/runs/${encodeURIComponent(request.runId)}`, {method:request.operation === 'frozen.cancel'?'PATCH':'GET', credentials:'same-origin',
                            headers:{...headers,...(request.operation==='frozen.cancel'?{'Content-Type':'application/json'}:{})},
                            ...(request.operation==='frozen.cancel'?{body:JSON.stringify({status:'cancelled',detail:'Cancelled'})}:{}), signal:abort.signal}));
                        if (['succeeded','failed','cancelled'].includes(result.status)) window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail:{studioId:binding.studioId,miniAppId:binding.miniAppId,runId:result.id}}));
                        reply({value:result});
                    } else throw new Error('Unknown Frozen Time operation');
                }
                else if (request.operation === 'avatar.input.read') {
                    if (binding.studioId !== 'ai2apps.video-studio' || !probe.items?.some(item => item.capability === 'video.avatar_generation')) throw new Error('Capability is not allowed');
                    reply({value: await readAvatarInput(request, abort.signal)});
                }
                else if (['avatar.models', 'avatar.jobs', 'avatar.cancel', 'avatar.retry'].includes(request.operation)) {
                    if (!probe.items?.some(item => item.capability === 'video.avatar_generation')) throw new Error('Capability is not allowed');
                    let suffix = request.operation === 'avatar.models' ? 'models' : 'jobs';
                    const cancelling = ['avatar.cancel', 'avatar.retry'].includes(request.operation);
                    if (cancelling) {
                        if (typeof request.jobId !== 'string' || !/^[a-zA-Z0-9_-]{1,100}$/.test(request.jobId)) throw new Error('Invalid avatar job');
                        suffix = `jobs/${encodeURIComponent(request.jobId)}/${request.operation === "avatar.retry" ? "retry" : "cancel"}`;
                    }
                    const result = await payload(await fetch(`${base}/avatar/${suffix}`, {
                        method: cancelling ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', signal: abort.signal,
                    }));
                    if (request.operation !== 'avatar.models') {
                        const nextState = JSON.stringify(result);
                        if (nextState !== avatarJobsState) window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail: {studioId: binding.studioId, miniAppId: binding.miniAppId}}));
                        avatarJobsState = nextState;
                    }
                    reply({value: result});
                }
                else if (request.operation === 'output.read') {
                    if (binding.studioId !== 'ai2apps.readaloud') throw new Error('Output source is not allowed');
                    const reference = request.reference;
                    const history = await payload(await fetch('/v1/platform/readaloud/outputs', {credentials: 'same-origin', signal: abort.signal}));
                    const expected = `/v1/platform/sessions/${encodeURIComponent(reference?.sessionId || '')}/artifacts/${encodeURIComponent(reference?.artifactId || '')}/download`;
                    const item = history.items?.find(item => item.downloadUrl === expected && item.mediaType?.startsWith('audio/'));
                    if (!item) throw new Error('Unknown Studio audio output');
                    const response = await fetch(item.downloadUrl, {credentials: 'same-origin', signal: abort.signal});
                    if (!response.ok) throw new Error('Could not read Studio output');
                    reply({value: {body: await response.blob(), name: item.title + '.wav'}});
                }
                else if (request.operation === 'export.text') {
                    if (typeof request.content !== 'string' || new TextEncoder().encode(request.content).length > 4 * 1024 * 1024) throw new Error('Export exceeds 4 MiB');
                    const result = await payload(await fetch(`${base}/exports`, {
                        method: 'POST', credentials: 'same-origin', signal: abort.signal,
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({filename: request.filename, content: request.content}),
                    }));
                    const url = new URL(result.downloadUrl, location.origin);
                    if (url.origin !== location.origin || !/^\/v1\/platform\/sessions\/[^/]+\/artifacts\/[^/]+\/download$/.test(url.pathname)) throw new Error('Invalid export URL');
                    downloads.add(result.downloadUrl);
                    window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail: {studioId: binding.studioId, miniAppId: binding.miniAppId, result}}));
                    const link = document.createElement('a');
                    link.href = result.downloadUrl; link.download = result.filename;
                    document.body.append(link); link.click(); link.remove();
                    reply({value: {started: true}});
                }
                else if (request.operation === 'download') {
                    if (!downloads.has(request.url)) throw new Error('Unknown Mini-App output');
                    const link = document.createElement('a');
                    link.href = request.url; link.download = ''; document.body.append(link);
                    link.click(); link.remove();
                    reply({value: {started: true}});
                }
                else if (request.operation === 'setup') {
                    if (!setupCapabilities.has(request.capability) || !probe.items?.some(item => item.capability === request.capability)) throw new Error('Capability is not allowed');
                    const result = await window.AI2AppsStudioMiniApps.setup(binding.studioId, {
                        id: binding.miniAppId,
                        requirements: {capabilities: [request.capability]},
                    }, {installMore: request.installMore === true});
                    reply({value: {outcome: result?.outcome || 'cancelled'}});
                }
                else if (request.operation === 'characters.list') {
                    if (!probe.items?.some(item => item.capability === 'audio.speech_generation')) throw new Error('Character access is not allowed');
                    reply({value: await payload(await fetch(`${base}/characters`, {
                        credentials: 'same-origin', cache: 'no-store', signal: abort.signal,
                    }))});
                }
                else if (request.operation === 'voice-clone-models.list') {
                    if (!probe.items?.some(item => item.capability === 'audio.voice_clone')) throw new Error('Voice-clone model access is not allowed');
                    reply({value: await payload(await fetch(`${base}/voice-clone-models`, {
                        credentials: 'same-origin', cache: 'no-store', signal: abort.signal,
                    }))});
                }
                else if (['subtitle.profiles.get', 'subtitle.profiles.set'].includes(request.operation)) {
                    if (!probe.items?.some(item => item.capability === 'media.video_subtitles')) throw new Error('Subtitle access is not allowed');
                    const profileKey = storageKey + ':correction-profiles';
                    if (request.operation === 'subtitle.profiles.get') reply({value: JSON.parse(localStorage.getItem(profileKey) || '[]')});
                    else if (request.operation === 'subtitle.profiles.set') {
                        const profiles = request.profiles;
                        if (!Array.isArray(profiles) || profiles.length > 100 || profiles.some(p => !p || typeof p.id !== 'string' || p.id.length > 100 || typeof p.name !== 'string' || !p.name.trim() || p.name.length > 100 || typeof p.rules !== 'string' || p.rules.length > 8000)) throw new Error('Invalid correction profiles');
                        localStorage.setItem(profileKey, JSON.stringify(profiles.map(({id,name,rules}) => ({id,name,rules}))));
                        reply({value: null});
                    }
                }
                else if (request.operation === 'draft.get') {
                    const saved = await payload(await fetch(`${base}/draft`, {credentials:'same-origin', cache:'no-store', signal:abort.signal}));
                    let value = saved.value;
                    // Migrate this exact App/Mini-App's old browser draft only if
                    // no durable draft exists. Keep the old copy as a backup.
                    const legacy = binding.studioId === 'ai2apps.ai-browser' ? null : localStorage.getItem(storageKey);
                    if (value == null && legacy) {
                        const draft = JSON.parse(legacy);
                        if (draft?.schema === 'ai2apps.mini-app-draft/v1' && draft.miniApp === binding.miniAppId) {
                            await payload(await fetch(`${base}/draft`, {method:'PUT', credentials:'same-origin', signal:abort.signal,
                                headers:{'Content-Type':'application/json'}, body:JSON.stringify({value:legacy})}));
                            value = legacy;
                        }
                    }
                    reply({value});
                }
                else if (request.operation === 'draft.remove') {
                    await payload(await fetch(`${base}/draft`, {method:'DELETE', credentials:'same-origin', signal:abort.signal}));
                    localStorage.removeItem(storageKey); reply({value: null});
                }
                else if (request.operation === 'draft.set') {
                    if (typeof request.value !== 'string' || new TextEncoder().encode(request.value).length > 4 * 1024 * 1024) throw new Error('Draft exceeds 4 MiB');
                    const draft = JSON.parse(request.value);
                    if (draft?.schema !== 'ai2apps.mini-app-draft/v1' || draft.miniApp !== binding.miniAppId) throw new Error('Invalid Mini-App draft');
                    await payload(await fetch(`${base}/draft`, {method:'PUT', credentials:'same-origin', signal:abort.signal,
                        headers:{'Content-Type':'application/json'}, body:JSON.stringify({value:request.value})}));
                    reply({value: null});
                } else if (request.operation === 'invoke') {
                    if (!mediaCapabilities.has(request.capability) || !probe.items?.some(item => item.capability === request.capability)) throw new Error('Capability is not allowed');
                    if (!Array.isArray(request.fields) || request.fields.length > 24) throw new Error('Invalid media fields');
                    const body = new FormData();
                    const names = new Set();
                    for (const entry of request.fields) {
                        if (!Array.isArray(entry) || entry.length !== 2) throw new Error('Invalid field');
                        const [name, value] = entry;
                        if (!formFields.has(name) || names.has(name)) throw new Error('Invalid or duplicate field');
                        names.add(name);
                        if (name === 'file' || name === 'reference') {
                            if (!(value instanceof Blob)) throw new Error('Expected media file');
                            const limit = name === 'file' ? 1024 * 1024 * 1024 : 100 * 1024 * 1024;
                            if (value.size === 0) throw new Error('Media input is empty');
                            if (value.size > limit) throw new Error(name === 'file'
                                ? 'Media input exceeds the 1 GiB limit'
                                : 'Reference audio exceeds the 100 MiB limit');
                            body.append(name, value, value.name || 'media.bin');
                        } else {
                            const limit = name === 'subtitle_segments' ? 2 * 1024 * 1024 : 4096;
                            if (typeof value !== 'string' || new TextEncoder().encode(value).length > limit) throw new Error('Invalid option');
                            body.append(name, value);
                        }
                    }
                    if (!names.has('file')) throw new Error('Media file is required');
                    let invocationId = '';
                    if (progressCapabilities.has(request.capability) && request.capability !== 'video.avatar_generation') {
                        const invocation = await payload(await fetch(`${base}/invocations`, {
                            method: 'POST', credentials: 'same-origin', signal: abort.signal,
                            headers: {'Content-Type': 'application/json', Accept: 'application/json'},
                            body: JSON.stringify({capability: request.capability}),
                        }));
                        if (!/^[0-9a-f]{32}$/.test(invocation?.id || '')) throw new Error('Invalid progress invocation');
                        const eventsUrl = new URL(invocation.eventsUrl, location.origin);
                        if (eventsUrl.origin !== location.origin
                            || !eventsUrl.pathname.startsWith(`${base}/invocations/${invocation.id}/events`)) throw new Error('Invalid progress URL');
                        invocationId = invocation.id;
                        progressSource = new EventSource(eventsUrl.href, {withCredentials: true});
                        progressSources.add(progressSource);
                        progressSource.addEventListener('progress', event => {
                            try {
                                const progress = JSON.parse(event.data);
                                if (!active() || progress?.invocationId !== invocationId) return;
                                channel.port1.postMessage({type: 'ai2apps:studio-progress', progress});
                                const terminal = progress.status === 'failed'
                                    || (progress.status === 'completed' && Number(progress.percent) >= 100);
                                if (terminal) {
                                    progressSource.close(); progressSources.delete(progressSource);
                                }
                            } catch (_) {}
                        });
                    }
                    window.dispatchEvent(new CustomEvent('ai2apps:studio-output-state', {detail: {studioId: binding.studioId, running: true}}));
                    const durableVideo = (binding.studioId === 'ai2apps.video-studio' &&
                        ['audio.source_separation','audio.detailed_transcription','media.video_subtitles','media.video_audio_translation','media.video_speaker_voice_replacement'].includes(request.capability)) ||
                        (binding.studioId === 'ai2apps.readaloud' && ['audio.source_separation','audio.detailed_transcription','audio.speaker_voice_replacement'].includes(request.capability) &&
                        (request.capability !== 'audio.speaker_voice_replacement' || request.fields.some(([key,value])=>key==='action' && value==='replace')));
                    let response = await fetch(`${base}/capabilities/${encodeURIComponent(request.capability)}/invoke`, {
                        method: 'POST', credentials: 'same-origin', body,
                        ...(durableVideo ? {} : {signal: abort.signal}),
                        headers: {Accept: 'application/json', ...(durableVideo ? {Prefer:'respond-async','Idempotency-Key':`video-${Date.now()}-${Math.random().toString(36).slice(2)}`} : {}), ...(invocationId ? {'X-AI2Apps-Invocation-ID': invocationId} : {})},
                    });
                    let durableRunId = '';
                    let durableOutputUrl = '';
                    let durableResult = null;
                    if (durableVideo && response.status === 202) {
                        let job = await payload(response);
                        durableRunId = job.run_id;
                        window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail:{studioId:binding.studioId,miniAppId:binding.miniAppId,runId:durableRunId}}));
                        if (progressSource) { progressSource.close(); progressSources.delete(progressSource); }
                        // Unmount stops only observation; accepted work remains owned by Local.
                        while (!['succeeded','failed','cancelled','interrupted','publish_failed'].includes(job.status)) {
                            if (abort.signal.aborted) throw new Error('Observation stopped');
                            if (active() && job.result?.progress) channel.port1.postMessage({type:'ai2apps:studio-progress',progress:{...job.result.progress,invocationId}});
                            await new Promise(resolve => setTimeout(resolve,1000));
                            job = await payload(await fetch(`/v1/platform/studio-jobs/${encodeURIComponent(job.id)}`,{credentials:'same-origin',signal:abort.signal}));
                        }
                        if (job.status !== 'succeeded') throw new Error(job.error?.message || 'Video task stopped');
                        durableResult = job.result;
                        durableOutputUrl = job.result.downloadUrl;
                        const output = new URL(job.result.responseUrl || durableOutputUrl, location.origin);
                        if(output.origin !== location.origin || !/^\/v1\/platform\/sessions\/[^/]+\/artifacts\/[^/]+\/download$/.test(output.pathname)) throw new Error('Invalid output URL');
                        response = await fetch(output.href,{credentials:'same-origin',signal:abort.signal});
                    }
                    const separationResult = durableResult && binding.studioId === 'ai2apps.readaloud' && request.capability === 'audio.source_separation';
                    let responseBody = separationResult ? new Blob([JSON.stringify(durableResult)], {type:'application/json'}) : await response.blob();
                    if (!response.ok) {
                        const failure = await responseBody.text();
                        let value;
                        try { value = JSON.parse(failure); } catch (_) { value = failure; }
                        const message = taskModelError(value);
                        if (message) responseBody = new Blob([JSON.stringify({detail: {message}})], {type: 'application/json'});
                    }
                    if (response.status === 202 && request.capability === 'video.avatar_generation') {
                        window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail: {studioId: binding.studioId, miniAppId: binding.miniAppId}}));
                    }
                    if (response.ok && request.capability === 'audio.source_separation' && response.headers.get('content-type')?.includes('application/json')) {
                        const result = JSON.parse(await responseBody.text());
                        const url = new URL(result.downloadUrl, location.origin);
                        if (url.origin !== location.origin || !/^\/v1\/platform\/sessions\/[^/]+\/artifacts\/[^/]+\/download$/.test(url.pathname)) throw new Error('Invalid output URL');
                        downloads.add(result.downloadUrl);
                        window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail: {studioId: binding.studioId, miniAppId: binding.miniAppId, result}}));
                    }
                    const outputUrl = durableOutputUrl || response.headers.get('X-AI2Apps-Download-URL');
                    const outputRunId = durableRunId || response.headers.get('X-AI2Apps-Studio-Run-ID') || '';
                    if (response.ok && outputUrl) {
                        const url = new URL(outputUrl, location.origin);
                        if (url.origin !== location.origin || !/^\/v1\/platform\/sessions\/[^/]+\/artifacts\/[^/]+\/download$/.test(url.pathname)) throw new Error('Invalid output URL');
                        downloads.add(outputUrl);
                        window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail: {studioId: binding.studioId, miniAppId: binding.miniAppId, result: {downloadUrl: outputUrl, runId: outputRunId}, preserveSelection: !!durableRunId}}));
                    }
                    reply({value: {status: response.status, body: responseBody,
                        headers: {'x-ai2apps-download-url': outputUrl || '', 'content-type': separationResult ? 'application/json' : response.headers.get('content-type') || '',
                            'content-disposition': response.headers.get('content-disposition') || ''}}});
                } else throw new Error('Unknown Mini-App operation');
            } catch (error) { reply({error: error?.message || 'Mini-App operation failed'}); }
            finally {
                busy = false;
                if (request.operation === 'audio-generation.generate') audioGenerationAbort = null;
                if (request.operation === 'llm.complete') llmAbort = null;
                if (request.operation === 'invoke') {
                    window.dispatchEvent(new CustomEvent('ai2apps:studio-output-state', {detail: {studioId: binding.studioId, running: false}}));
                    if (progressSource && progressSources.has(progressSource)) {
                        const cleanupTimer = setTimeout(() => { progressSource.close(); progressSources.delete(progressSource); }, 30000);
                        cleanupTimer?.unref?.();
                    }
                }
            }
        };
        source.postMessage({type: 'ai2apps:studio-connected', version: 1, mobile:!!window.AI2APPS_MOBILE_SURFACE||!!frame.closest('.sm-mobile,.aib-mobile'), locale: document.documentElement.lang || 'en'}, '*', [channel.port2]);
    });

    window.AI2AppsStudioMiniApps = Object.freeze({
        async list(studioId) {
            const catalog = await payload(await fetch(`/v1/platform/studios/${encodeURIComponent(studioId)}/mini-apps`, {
                credentials: 'same-origin', headers: { Accept: 'application/json' }, cache: 'no-store',
            }));
            return {
                ...catalog,
                items: (catalog?.items || []).map(item => ['package','builtin'].includes(item?.source)
                    ? localizedDeclaration(item, document.documentElement.lang)
                    : item),
            };
        },
        async mount(studioId, miniAppId, { placement = 'inline', context = {} } = {}) {
            const instanceId = appInstanceId();
            if (!instanceId) throw new Error('Studio App instance is unavailable');
            const locale = normalizedLocale(context.locale || document.documentElement.lang || navigator.language);
            const mountContext = {...context, locale};
            const mount = await payload(await fetch(`/v1/platform/studios/${encodeURIComponent(studioId)}/mini-app-mounts`, {
                method: 'POST', credentials: 'same-origin',
                headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-AI2Apps-App-Instance': instanceId },
                body: JSON.stringify({ miniAppId, placement, context: mountContext }),
            }));
            const url = new URL(mount.content_url, location.origin);
            if (url.origin !== location.origin) throw new Error('Invalid Mini-App content origin');
            url.searchParams.set('locale', locale);
            mount.content_url = `${url.pathname}${url.search}${url.hash}`;
            if (mountedFrames.size >= 128) mountedFrames.delete(mountedFrames.keys().next().value);
            mountedFrames.set(url.href, {studioId, mountId: mount.id, miniAppId,
                owner: instanceId, provider: mount.app_instance_id, resource: mount.resource, locale});
            return mount;
        },
        localize(item, locale) { return localizedDeclaration(item, locale); },
        async probe(studioId, mountId) {
            return payload(await fetch(`/v1/platform/studios/${encodeURIComponent(studioId)}/mini-app-mounts/${encodeURIComponent(mountId)}/capabilities`, {
                credentials: 'same-origin', headers: { Accept: 'application/json' }, cache: 'no-store',
            }));
        },
        async probeAll(studioId) {
            const instanceId = appInstanceId();
            if (!instanceId) throw new Error('Studio App instance is unavailable');
            return payload(await fetch(`/v1/platform/studios/${encodeURIComponent(studioId)}/mini-app-capabilities`, {
                credentials: 'same-origin',
                headers: { Accept: 'application/json', 'X-AI2Apps-App-Instance': instanceId },
                cache: 'no-store',
            }));
        },
        async readiness(studioId) {
            const catalog = await this.probeAll(studioId);
            return Object.fromEntries((catalog?.items || []).map(probe => {
                const capabilities = Array.isArray(probe?.items) ? probe.items : [];
                const required = capabilities.filter(value => value?.required !== false);
                if (probe.miniAppId === 'ai2apps.imagine.frozen-time') {
                    return [probe.miniAppId, capabilities.some(value => value?.implemented === true && value?.ready === true)];
                }
                return [probe.miniAppId, required.length > 0 && required.every(value => value?.implemented === true && value?.ready === true)];
            }));
        },
        async setup(studioId, miniApp, {installMore = false} = {}) {
            const capability = primaryCapability(miniApp);
            if (!capability) throw new Error('Mini-App does not declare a setup capability');
            if (!window.AI2AppsCapabilities?.ensure) throw new Error('ACPF is unavailable');
            const resumeToken = globalThis.crypto?.randomUUID?.() || `studio-mini-app-${Date.now()}`;
            localStorage.setItem(setupStorageKey(studioId), JSON.stringify({ miniAppId: miniApp.id, capability, resumeToken }));
            try {
                const result = await window.AI2AppsCapabilities.ensure({
                    appId: studioId,
                    capability,
                    actionId: 'setup-mini-app',
                    requirements: {},
                    intent: {
                        returnTo: `/apps/${studioId}`,
                        resumeToken,
                        completionPolicy: 'configure_only',
                    },
                }, {installMore});
                if (result?.outcome === 'configured' && result.session?.id) {
                    await window.AI2AppsCapabilities.acknowledge(result.session.id, { appId: studioId });
                }
                return result;
            } finally {
                clearPendingSetup(studioId);
            }
        },
        pendingSetup,
        async resumeSetup(studioId, miniApps = []) {
            if (!window.AI2AppsCapabilities?.resume) return null;
            const pending = pendingSetup(studioId);
            try {
                const result = await window.AI2AppsCapabilities.resume(studioId, { actionId: 'setup-mini-app' });
                if (result?.outcome === 'configured' && result.session?.id) {
                    await window.AI2AppsCapabilities.acknowledge(result.session.id, { appId: studioId });
                }
                const capability = result?.session?.capability || pending?.capability || '';
                const inferred = miniApps.find(item => primaryCapability(item) === capability);
                return result ? { ...result, miniAppId: pending?.miniAppId || inferred?.id || '' } : null;
            } finally {
                if (pending) clearPendingSetup(studioId);
            }
        },
    });
})();
