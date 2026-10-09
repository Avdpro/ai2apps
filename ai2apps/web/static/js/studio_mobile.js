/* Mobile navigation and media actions shared by Studio hosts. */
(() => {
    'use strict';
    const labels = {
        zh: {back:'返回',output:'输出',play:'播放',view:'查看大图',gallery:'加入 Gallery',download:'下载',file:'选择文件',photos:'从照片中选择',pickGallery:'从 Gallery 中选择',cancel:'取消',loading:'正在读取…',empty:'没有符合此素材槽类型的素材',error:'操作失败，请重试',search:'搜索素材',choose:'选择素材'},
        en: {back:'Back',output:'Output',play:'Play',view:'View image',gallery:'Add to Gallery',download:'Download',file:'Choose file',photos:'Choose from Photos',pickGallery:'Choose from Gallery',cancel:'Cancel',loading:'Loading…',empty:'No compatible assets',error:'Could not complete action. Try again.',search:'Search assets',choose:'Choose asset'}
    };
    function accepts(accept, type, name='') {
        return !accept || accept.split(',').some(raw => { const rule=raw.trim().toLowerCase(); return rule.startsWith('.') ? name.toLowerCase().endsWith(rule) : rule.endsWith('/*') ? type.startsWith(rule.slice(0,-1)) : type===rule; });
    }
    function mountOutputCollapse(output, media) {
        const preview=output.querySelector('.is-image-preview');
        if(!preview)return;
        function update(){
            if(!media.matches){preview.classList.remove('sm-collapsing-preview');return;}
            // Read the original size only when visible. Keep the flow footprint
            // stable so shrinking cannot change scrollTop and cause oscillation.
            if(!preview.offsetHeight)return;
            if(!preview.classList.contains('sm-collapsing-preview')){
                preview.style.setProperty('--sm-preview-expanded',preview.offsetHeight+'px');
                preview.style.setProperty('--sm-preview-margin',window.getComputedStyle(preview).marginBottom);
                preview.classList.add('sm-collapsing-preview');
            }
            const expanded=parseFloat(preview.style.getPropertyValue('--sm-preview-expanded'));
            const compact=Math.min(112,expanded);
            const shrink=Math.min(expanded-compact,Math.max(0,output.scrollTop));
            preview.style.setProperty('--sm-preview-shrink',shrink+'px');
        }
        output.addEventListener('scroll',update,{passive:true});
        const observer=new ResizeObserver(()=>{
            preview.classList.remove('sm-collapsing-preview');update();
        });
        // The panel size is independent of preview height; don't observe the image.
        observer.observe(output);
        media.addEventListener('change',update);
    }
    function mount(root, app) {
        if(root.dataset.mobileStudioMounted) return;
        root.dataset.mobileStudioMounted='true';
        const t=labels[document.documentElement.lang.startsWith('zh')?'zh':'en'];
        const media=window.matchMedia('(max-width: 760px)');
        const isImagine=root.dataset.appId==='ai2apps.imagine-studio';
        const sidebar=root.querySelector('.vs-studio-sidebar,.ra-studio-sidebar');
        const workspace=root.querySelector('.is-mini-app-workspace,.vs-mini-app-workspace,.ra-pipeline-workspace');
        const output=root.querySelector('.vs-render-workspace,.ra-render-workspace');
        if(!sidebar||!workspace||!output) return;
        if(isImagine)mountOutputCollapse(output,media);
        sidebar.dataset.smPanel='library'; workspace.dataset.smPanel='create';output.dataset.smPanel='output';
        let page='library',returnPage='library',bypass=false;
        const header=root.querySelector('.studio-header');
        const back=document.createElement('button'),out=document.createElement('button');
        for(const button of [back,out]){button.type='button';button.className='studio-header-button sm-nav';}
        back.textContent='‹ '+t.back;out.textContent=t.output;out.classList.add('sm-output');
        header.prepend(back);header.append(out);
        function go(next){page=next;root.dataset.smPage=next;back.hidden=next==='library';out.hidden=next==='output';if(isImagine)app.mobileSurface=next; if(next==='library')app.leftView='mini-apps';}
        back.onclick=()=>go(page==='output'?returnPage:'library');
        function showOutput(){if(page!=='output')returnPage=page;go('output');}
        out.onclick=showOutput;
        if(isImagine){
            const originalOutput=app.openMobileOutput;
            app.openMobileOutput=function(){
                if(media.matches)showOutput();
                else originalOutput?.call(this);
            };
        }
        // Observe host-owned output feeds, never private Mini-App/Line caches.
        // The first successful refresh establishes history without navigation.
        const feeds = root.dataset.appId==='ai2apps.readaloud'
            ? [['refreshOutputs','studioOutputs','selectedOutput']]
            : isImagine ? [['refreshRuns','runs','selectedRunId']]
            : [['refresh','tasks','selectedTaskId'],['refresh','audioRuns','selectedAudioRunId'],
               ['refresh','composerRuns','selectedComposerRunId'],['refresh','upscalingRuns','selectedUpscalingRunId'],
               ['refresh','packageRuns','selectedPackageRunId']];
        const complete=item=>['succeeded','completed'].includes(item?.status) ||
            (root.dataset.appId==='ai2apps.readaloud' && !item?.status && !!item?.downloadUrl);
        const methods=new Map();
        for(const [method,field,selection] of feeds){
            if(typeof app[method]!=='function')continue;
            if(!methods.has(method))methods.set(method,[]);
            methods.get(method).push({field,selection,seen:null});
        }
        for(const [method,states] of methods){
            const original=app[method];
            app[method]=async function(...args){
                const result=await original.apply(this,args);
                let latest=null;
                for(const state of states){
                    const rows=this[state.field]||[];
                    const previous=state.seen;
                    state.seen=new Map(rows.map(item=>[item.id,complete(item)]));
                    if(previous){
                        const fresh=rows.find(item=>complete(item)&&previous.get(item.id)!==true);
                        if(fresh&&!latest)latest={item:fresh,selection:state.selection};
                    }
                }
                if(latest&&media.matches&&root.isConnected){
                    this[latest.selection]=latest.selection==='selectedOutput'?latest.item:latest.item.id;
                    if(isImagine)this.selectRun(latest.item);
                    showOutput();
                }
                return result;
            };
        }
        if(root.dataset.appId==='ai2apps.video-studio'&&typeof app.joinFinished==='function'){
            const join=app.joinFinished;
            app.joinFinished=async function(...args){
                const before=this.joinedVideoUrl;const result=await join.apply(this,args);
                if(media.matches&&root.isConnected&&this.joinedVideoUrl&&this.joinedVideoUrl!==before)showOutput();
                return result;
            };
        }
        window.addEventListener('ai2apps:studio-output',event=>{
            const detail=event.detail;
            if(!media.matches||!root.isConnected||detail?.studioId!==root.dataset.appId)return;
            const result=detail.result;
            if(!result?.downloadUrl&&!result?.tracks?.some(track=>track.downloadUrl))return;
            if(result.status&& !['completed','succeeded'].includes(result.status))return;
            // Hosts select and refresh the published artifact in their own handlers.
            if(app.$nextTick)app.$nextTick(showOutput);else showOutput();
        });
        const select=app.selectMiniApp;
        app.selectMiniApp=async function(id){
            if(media.matches && this.currentMiniApp?.id===id){go('create');return;}
            await select.call(this,id);
            if(media.matches && this.currentMiniApp?.id===id)go('create');
        };
        function resize(){root.classList.toggle('sm-mobile',media.matches);if(media.matches)go(page);}
        media.addEventListener('change',resize);resize();
        // The Gallery iframe remains mounted throughout a drag. Hiding or replacing
        // the drag source can cancel native dragging and touch pointer capture.
        let galleryDrag=null,dragTimeout=null;
        function finishGalleryDrag(accepted=false){
            if(!galleryDrag)return;
            const saved=galleryDrag;galleryDrag=null;clearTimeout(dragTimeout);
            saved.ghost?.remove();saved.target?.classList.remove('sm-drop-target');
            root.classList.remove('sm-gallery-drag');
            if(accepted)go('create');else{go(saved.page);app.leftView=saved.leftView;}
        }
        function dragSlot(x,y){
            let target=document.elementFromPoint(x,y);
            if(!target||!workspace.contains(target))return null;
            if(target.tagName==='IFRAME'){
                try{const rect=target.getBoundingClientRect();target=target.contentDocument?.elementFromPoint(x-rect.left,y-rect.top);}catch(_){return null;}
            }
            const label=target?.closest('label');
            const input=target?.matches('input[type=file]')?target:label?.querySelector('input[type=file]');
            if(!input||input.disabled||input.webkitdirectory)return null;
            const asset=galleryDrag.asset;
            const type=asset.mediaType||({image:'image/*',video:'video/*',audio:'audio/*'}[asset.kind]||'');
            if(asset.mediaType&&!accepts(input.accept,type,asset.name))return null;
            return {input,label:label||input};
        }
        function updateGalleryDrag(data){
            const state=galleryDrag;if(!state)return;
            clearTimeout(dragTimeout);dragTimeout=setTimeout(()=>finishGalleryDrag(false),30000);
            const x=state.rect.left+data.x,y=state.rect.top+data.y;
            state.target?.classList.remove('sm-drop-target');
            const slot=dragSlot(x,y);state.slot=slot;state.target=slot?.label;
            state.target?.classList.add('sm-drop-target');
            if(state.ghost){state.ghost.style.left=x+'px';state.ghost.style.top=y+'px';state.ghost.textContent=(slot?'＋ ':'')+state.asset.name;}
        }
        window.addEventListener('message',async event=>{
            const frame=root.querySelector('iframe[x-ref="galleryMini"]');
            const data=event.data;
            if(!media.matches||!root.isConnected||!frame||event.origin!==window.location.origin||event.source!==frame.contentWindow||data?.type!=='ai2apps.gallery.studio-drag')return;
            if(!['start','move','end','cancel'].includes(data.phase)||!data.asset||typeof data.asset.id!=='string'||data.asset.id.length>200||!data.asset.id||typeof data.asset.name!=='string'||data.asset.name.length>1000||!Number.isFinite(data.x)||!Number.isFinite(data.y))return;
            if(data.phase==='start'){
                finishGalleryDrag(false);
                const rect=frame.getBoundingClientRect();
                galleryDrag={asset:{...data.asset},frame,rect,page,leftView:app.leftView,touch:data.touch===true,miniAppId:app.currentMiniApp?.id,dropped:false};
                root.classList.add('sm-gallery-drag');page='create';root.dataset.smPage='create';back.hidden=false;out.hidden=false;
                if(galleryDrag.touch){const ghost=document.createElement('div');ghost.className='sm-drag-ghost';ghost.setAttribute('role','status');document.body.append(ghost);galleryDrag.ghost=ghost;}
                updateGalleryDrag(data);return;
            }
            const state=galleryDrag;if(!state||state.frame!==frame||state.asset.id!==data.asset.id||state.touch!==(data.touch===true))return;
            if(data.phase==='cancel'){finishGalleryDrag(false);return;}
            if(data.phase==='move'){updateGalleryDrag(data);return;}
            if(!state.touch){finishGalleryDrag(state.dropped);return;}
            updateGalleryDrag(data);const input=state.slot?.input;
            if(!input){finishGalleryDrag(false);return;}
            try{
                const response=await fetch('/v1/platform/gallery/assets/'+encodeURIComponent(state.asset.id)+'/content',{credentials:'same-origin'});
                if(!response.ok)throw new Error(t.error);
                const blob=await response.blob();
                if(galleryDrag!==state)return;
                if(app.currentMiniApp?.id!==state.miniAppId||!input.isConnected||input.disabled){finishGalleryDrag(false);return;}
                if(!accepts(input.accept,blob.type,state.asset.name))throw new Error(t.empty);
                const transfer=new DataTransfer();transfer.items.add(new File([blob],state.asset.name,{type:blob.type}));
                input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));finishGalleryDrag(true);
            }catch(error){if(galleryDrag===state){finishGalleryDrag(false);app.fail?.(error);}}
        });
        root.addEventListener('drop',event=>{if(galleryDrag&&!galleryDrag.touch)galleryDrag.dropped=workspace.contains(event.target);},true);
        window.addEventListener('blur',()=>finishGalleryDrag(false));

        let dialog=null,returnFocus=null,controller=null;
        function close(){controller?.abort();controller=null;if(dialog){dialog.close();dialog.remove();dialog=null;}returnFocus?.focus?.();}
        function sheet(title){close();returnFocus=document.activeElement;dialog=document.createElement('dialog');dialog.className='sm-sheet';dialog.setAttribute('aria-label',title);const heading=document.createElement('h2');heading.textContent=title;dialog.append(heading);dialog.addEventListener('cancel',e=>{e.preventDefault();close();});dialog.addEventListener('click',e=>{if(e.target===dialog)close();});root.append(dialog);dialog.showModal();return dialog;}
        function action(parent,title,callback,disabled=false){const button=document.createElement('button');button.type='button';button.textContent=title;button.disabled=disabled;button.onclick=async()=>{button.disabled=true;try{await callback();}catch(error){if(error.name==='AbortError')return;const note=document.createElement('p');note.role='alert';note.textContent=error.message||t.error;(dialog||parent).append(note);}finally{button.disabled=disabled;}};parent.append(button);return button;}
        function invoke(element){bypass=true;try{element.click();}finally{bypass=false;}}
        async function gallery(input){
            const box=sheet(t.pickGallery);const search=document.createElement('input');search.type='search';search.placeholder=t.search;search.setAttribute('aria-label',t.search);box.append(search);const list=document.createElement('div');list.className='sm-assets';box.append(list);action(box,t.cancel,close);
            let seq=0;
            async function load(){const ticket=++seq;controller?.abort();controller=new AbortController();list.textContent=t.loading;
                try{const params=new URLSearchParams({collectionId:'recent',search:search.value});const response=await fetch('/v1/platform/gallery/assets?'+params,{credentials:'same-origin',signal:controller.signal});if(!response.ok)throw new Error(t.error);const data=await response.json();if(ticket!==seq||!box.isConnected)return;list.replaceChildren();const items=(data.items||[]).filter(a=>accepts(input.accept,a.media_type||a.mimeType||a.mediaType||'',a.name||''));
                    if(!items.length)list.textContent=t.empty;
                    for(const item of items)action(list,item.name||t.choose,async()=>{if(input.disabled||!input.isConnected)return;const r=await fetch('/v1/platform/gallery/assets/'+encodeURIComponent(item.id)+'/content',{credentials:'same-origin'});if(!r.ok)throw new Error(t.error);const blob=await r.blob();if(!accepts(input.accept,blob.type,item.name||''))throw new Error(t.empty);if(!input.isConnected||input.disabled||!box.isConnected)return;const transfer=new DataTransfer();transfer.items.add(new File([blob],item.name||'asset',{type:blob.type}));input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));close();});
                }catch(error){if(error.name!=='AbortError'&&ticket===seq&&box.isConnected)list.textContent=t.error;}
            }
            search.onchange=load;await load();
        }
        function pick(input,photos){
            const picker=document.createElement('input');picker.type='file';picker.multiple=input.multiple;picker.accept=photos?(input.accept.split(',').filter(v=>/image|video/.test(v)).join(',')||'image/*,video/*'):input.accept;
            picker.onchange=()=>{if(picker.files.length&&input.isConnected&&!input.disabled){input.files=picker.files;input.dispatchEvent(new Event('change',{bubbles:true}));}picker.remove();};picker.oncancel=()=>picker.remove();picker.hidden=true;root.append(picker);close();invoke(picker);
        }
        const handleClick=event=>{
            if(!media.matches||bypass||event.target.closest('.sm-sheet,.sm-nav'))return;
            if(event.target.closest('button,a'))return;
            const label=event.target.closest('label');const input=event.target.matches('input[type=file]')?event.target:label?.querySelector('input[type=file]');
            if(input&&!input.disabled&&!input.webkitdirectory&&/image|audio|video/.test(input.accept)){
                event.preventDefault();event.stopImmediatePropagation();const box=sheet(t.choose);action(box,t.file,()=>pick(input,false));action(box,t.photos,()=>pick(input,true),!/image|video/.test(input.accept));action(box,t.pickGallery,()=>gallery(input));action(box,t.cancel,close);return;
            }
            const preview=event.target.closest('.vs-preview,.vs-audio-preview,.ra-audio-preview,.ra-output-file');
            if(!preview||!output.contains(preview)||event.target.closest('button,a,input,select'))return;
            const player=preview.querySelector('video[src],audio[src]');const image=preview.querySelector('img[src]');
            if(!(player?.getAttribute('src')||image?.getAttribute('src')||(root.dataset.appId==='ai2apps.readaloud'&&app.outputDownloadUrl)))return;
            if(player?.dataset.smControls==='true'&&event.target===player)return;
            event.preventDefault();event.stopImmediatePropagation();const box=sheet(t.output);const outputUrl=app.outputDownloadUrl;
            action(box,image?t.view:t.play,()=>{close();if(image)invoke(image);else{player.controls=true;player.dataset.smControls='true';preview.dataset.smPlaying='true';return player.play();}},!player&&!image);
            const add=preview.querySelector('[data-sm-add-gallery]');
            action(box,t.gallery,async()=>{if(add){invoke(add);close();}else if(root.dataset.appId==='ai2apps.readaloud'){
                const path=new URL(outputUrl,location.origin);const match=path.pathname.match(/^\/v1\/platform\/sessions\/([^/]+)\/artifacts\/([^/]+)\/download$/);if(path.origin!==location.origin||!match)throw new Error(t.error);
                await app.addArtifactToGallery({metadata:{artifactSessionId:decodeURIComponent(match[1]),sourceArtifactId:decodeURIComponent(match[2])}});close();
            }},add?add.disabled:root.dataset.appId!=='ai2apps.readaloud');
            const download=preview.querySelector('a[download]')||output.querySelector('.ra-export-controls a[download],.ra-output-file a[download]');
            action(box,t.download,()=>{if(download)invoke(download);close();},!download?.getAttribute('href'));
            action(box,t.cancel,close);
        };
        root.addEventListener('click',handleClick,true);
        // Package frames retain their own change handlers. Only same-origin,
        // DOM-accessible frames participate; never relax an iframe sandbox.
        for(const frame of root.querySelectorAll('.is-package-mini-app-frame,.vs-package-mini-app-frame,.ra-package-mini-app-frame')) {
            const attach=()=>{try{const doc=frame.contentDocument;if(doc&&!doc.documentElement.dataset.smPicker){doc.documentElement.dataset.smPicker='true';doc.addEventListener('click',handleClick,true);}}catch(_){} };
            frame.addEventListener('load',attach);attach();
        }
    }
    window.AI2AppsMobileStudio={mount,accepts,mountOutputCollapse};
})();
