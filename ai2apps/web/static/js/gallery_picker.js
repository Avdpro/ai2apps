(() => {
    'use strict';
    const MIME = 'application/x-ai2apps-gallery-assets';
    function droppedAssetIds(transfer) {
        const raw = transfer?.getData(MIME);
        if (raw) {
            const values = JSON.parse(raw);
            if (!Array.isArray(values) || values.some(value => typeof value !== 'string' || !value)) throw new Error('Invalid Gallery references');
            return [...new Set(values)];
        }
        const single = transfer?.getData('application/x-ai2apps-gallery-asset');
        return single ? [single] : [];
    }
    function acceptsDrop(transfer) {
        return [...(transfer?.types || [])].some(type => ['Files', MIME, 'application/x-ai2apps-gallery-asset'].includes(type));
    }
    const labels = {
        zh: {title:'从图库选择文件',search:'搜索文件',all:'最近文件',cancel:'取消',confirm:'添加所选文件',empty:'没有匹配的文件',loading:'正在加载…',limit:'最多选择 {count} 个文件',selected:'已选择 {count} 个文件'},
        en: {title:'Choose files from Gallery',search:'Search files',all:'Recent files',cancel:'Cancel',confirm:'Add selected files',empty:'No matching files',loading:'Loading…',limit:'Choose up to {count} files',selected:'{count} files selected'},
    };
    async function open(options = {}) {
        const max = options.multiple === false ? 1 : (options.maxSelection ?? 8);
        const locale = document.documentElement.lang.startsWith('zh') ? 'zh' : 'en';
        const tr = (key, count) => labels[locale][key].replace('{count}', String(count));
        const selected = new Map();
        const previousFocus = document.activeElement;
        const dialog = document.createElement('dialog'); dialog.className = 'ai2apps-gallery-picker';
        const heading = document.createElement('h2'); heading.textContent = tr('title'); heading.id = 'gallery-picker-title-' + crypto.randomUUID(); dialog.setAttribute('aria-labelledby', heading.id);
        const tools = document.createElement('div'); tools.className = 'gallery-picker-tools';
        const collection = document.createElement('select'); collection.setAttribute('aria-label',tr('all')); collection.add(new Option(tr('all'),''));
        const search = document.createElement('input'); search.type = 'search'; search.placeholder = tr('search'); search.setAttribute('aria-label',tr('search'));
        tools.append(collection,search);
        const status = document.createElement('p'); status.setAttribute('role','status'); status.setAttribute('aria-live','polite');
        const grid = document.createElement('div'); grid.className = 'gallery-picker-grid';
        const footer = document.createElement('footer');
        const count = document.createElement('span');
        const cancel = document.createElement('button'); cancel.type = 'button'; cancel.textContent = tr('cancel');
        const confirm = document.createElement('button'); confirm.type = 'button'; confirm.textContent = tr('confirm'); confirm.className = 'primary';
        footer.append(count,cancel,confirm); dialog.append(heading,tools,status,grid,footer); document.body.append(dialog);
        const tooltip = document.createElement('div'); tooltip.className = 'gallery-picker-tooltip'; tooltip.id = 'gallery-picker-tip-' + crypto.randomUUID(); tooltip.setAttribute('role','tooltip'); tooltip.hidden = true; dialog.append(tooltip);
        const hideTooltip = () => {tooltip.hidden = true;};
        const showTooltip = (button, name) => {
            tooltip.textContent = name; tooltip.hidden = false;
            const anchor = button.getBoundingClientRect(), tip = tooltip.getBoundingClientRect();
            const width = document.documentElement.clientWidth, height = document.documentElement.clientHeight;
            tooltip.style.left = Math.max(8,Math.min(anchor.left,width-tip.width-8)) + 'px';
            tooltip.style.top = Math.max(8,Math.min(anchor.bottom+6,height-tip.height-8)) + 'px';
        };
        grid.addEventListener('scroll',hideTooltip);
        let resolve, finished = false, requestRevision = 0, searchTimer;
        const result = new Promise(done => {resolve = done;});
        const finish = values => { if (finished) return; finished = true; clearTimeout(searchTimer); dialog.close(); dialog.remove(); previousFocus?.focus(); resolve(values); };
        const updateCount = () => {count.textContent = tr('selected',selected.size); confirm.disabled = !selected.size;};
        cancel.onclick = () => finish([]); confirm.onclick = () => finish([...selected.values()]);
        dialog.addEventListener('cancel',event => {event.preventDefault(); finish([]);});
        dialog.addEventListener('click',event => {if (event.target === dialog) {const r=dialog.getBoundingClientRect(); if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom) finish([]);}});
        async function request(path) {
            const response = await fetch('/v1/platform/gallery'+path, {credentials:'same-origin'});
            const data = await response.json();
            if (!response.ok) throw new Error(data.error?.message || response.statusText);
            return data;
        }
        async function load() {
            const revision = ++requestRevision;
            status.textContent = tr('loading');
            const query = new URLSearchParams({limit:'500',search:search.value}); if(collection.value) query.set('collectionId',collection.value);
            try {
                const data = await request('/assets?'+query);
                if(finished || revision !== requestRevision) return;
                hideTooltip();
                grid.replaceChildren(); status.textContent = data.items?.length ? '' : tr('empty');
                for (const asset of data.items || []) {
                    const button = document.createElement('button'); button.type='button'; button.className='gallery-picker-asset'; button.setAttribute('aria-pressed',String(selected.has(asset.id)));
                    const contentUrl = '/v1/platform/gallery/assets/'+encodeURIComponent(asset.id)+'/content';
                    if (asset.kind === 'image' || asset.kind === 'video') {
                        const media = document.createElement(asset.kind === 'image' ? 'img' : 'video');
                        media.src = contentUrl;
                        if (asset.kind === 'image') {media.alt = ''; media.loading = 'lazy';}
                        else {media.muted = true; media.preload = 'metadata'; media.playsInline = true; media.setAttribute('aria-hidden','true');}
                        button.append(media);
                        if (asset.kind === 'video') {const badge=document.createElement('span'); badge.className='gallery-picker-video-badge'; badge.textContent='▶'; badge.setAttribute('aria-hidden','true'); button.append(badge);}
                    } else {
                        const icon = document.createElement('span'); icon.className = 'gallery-picker-file-icon'; icon.setAttribute('aria-hidden','true');
                        const paths = asset.kind === 'audio'
                            ? '<path d="M2 10v4m4-7v10m4-14v18m4-15v12m4-10v8m4-6v4"/>'
                            : '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h6"/>';
                        icon.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'+paths+'</svg>';
                        button.append(icon);
                    }
                    const name=document.createElement('span'); name.className='gallery-picker-name'; name.textContent=asset.name; button.append(name);
                    button.setAttribute('aria-describedby',tooltip.id);
                    button.addEventListener('mouseenter',() => showTooltip(button,asset.name));
                    button.addEventListener('mouseleave',hideTooltip);
                    button.addEventListener('focus',() => showTooltip(button,asset.name));
                    button.addEventListener('blur',hideTooltip);
                    button.onclick = () => {
                        if(selected.has(asset.id)) selected.delete(asset.id);
                        else if(selected.size>=max) {status.textContent=tr('limit',max); return;}
                        else selected.set(asset.id,asset);
                        button.setAttribute('aria-pressed',String(selected.has(asset.id))); status.textContent=''; updateCount();
                    };
                    grid.append(button);
                }
            } catch(error) {if(!finished && revision===requestRevision) status.textContent=error.message;}
        }
        collection.onchange=load; search.oninput=()=> {clearTimeout(searchTimer); searchTimer=setTimeout(load,200);};
        updateCount(); dialog.showModal(); search.focus();
        void request('/collections').then(data => {if(finished) return; for(const item of data.items || []) {if(item.system_key!=='trash') collection.add(new Option(item.name,item.id));}}).catch(error => {if(!finished) status.textContent=error.message;});
        void load();
        return result;
    }
    window.AI2AppsGalleryPicker = {open, droppedAssetIds, acceptsDrop};
})();
