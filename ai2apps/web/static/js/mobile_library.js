(() => {
    'use strict';
    const $=id=>document.getElementById(id), type=$('library').dataset.library, knowledge=type==='knowledge', base='/v1/mobile/'+type;
    let current=null, sequence=0;
    const notice=t=>{$('notice').textContent=t;};
    async function api(path,method='GET',body){
        const form=body instanceof FormData;
        const r=await fetch(base+path,{method,credentials:'same-origin',cache:'no-store',headers:body&&!form?{'Content-Type':'application/json'}:{},body:body?(form?body:JSON.stringify(body)):undefined});
        const data=await r.json().catch(()=>({}));
        if(!r.ok){
            const detail=data.detail;
            const message=typeof detail==='string'?detail:
                typeof detail?.message==='string'?detail.message:
                Array.isArray(detail)?detail.map(x=>typeof x.msg==='string'?x.msg:'').filter(Boolean).join('；'):'';
            throw new Error(message||(typeof data.error?.message==='string'?data.error.message:'请求失败（'+r.status+'）'));
        }return data;
    }
    const mediaUrl=id=>base+'/assets/'+encodeURIComponent(id)+'/content';
    async function collections(){
        const old=$('collection').value, data=await api(knowledge?'/buckets':'/collections');
        $('collection').replaceChildren(new Option('全部',''),...data.items.map(x=>new Option(x.name,x.id)));
        if(data.items.some(x=>x.id===old))$('collection').value=old;
        if(knowledge){for(const [id,label,value] of [['ask-bucket','全部知识',''],['add-bucket','自动','auto']]){const select=$(id),prior=select.value;select.replaceChildren(new Option(label,value),...data.items.map(x=>new Option(x.name,x.id)));if([...select.options].some(o=>o.value===prior))select.value=prior;}}
    }
    async function load(){
        const seq=++sequence;notice('正在加载…');
        const params=new URLSearchParams({q:$('query').value,limit:knowledge?'100':'500'});
        if($('collection').value)params.set(knowledge?'bucket_id':'collection_id',$('collection').value);
        if(!knowledge&&$('kind').value)params.set('kind',$('kind').value);
        try{
            const data=await api((knowledge?'/items':'/assets')+'?'+params);
            if(seq!==sequence)return;
            $('items').replaceChildren();
            for(const item of data.items){
                const card=document.createElement('button');card.className='card';
                if(!knowledge){
                    if(item.kind==='image'){const img=document.createElement('img');img.className='thumb';img.loading='lazy';img.alt='';img.src=mediaUrl(item.id);card.append(img);}
                    else{const tile=document.createElement('div');tile.className='video-tile';tile.textContent='▷';card.append(tile);}
                }
                const title=document.createElement('strong');title.textContent=item.title||item.name;
                const subtitle=document.createElement('small');subtitle.textContent=knowledge?item.text.slice(0,160):(item.kind==='video'?'视频':'图片');
                card.append(title,subtitle);card.onclick=()=>open(item);if(!knowledge)bindGalleryHold(card,item);$('items').append(card);
            }
            $('count').textContent='显示 '+data.items.length+' 项'+(data.items.length===(knowledge?100:500)?' · 可使用搜索或分类缩小范围':'');
            if(!data.items.length){const p=document.createElement('p');p.className='empty';p.textContent='暂无符合条件的内容';$('items').append(p);}
            notice(data.fallback_recent_limit ? '短词匹配：已检索最近 500 条可见知识。' : '');
        }catch(e){if(seq===sequence)notice(e.message);}
    }
    let cancelActiveHold=()=>{}, assetMenu=null;
    function bindGalleryHold(card,item){
        let timer=null,point=null,suppress=false;
        const cancel=()=>{clearTimeout(timer);timer=null;point=null;};
        const menu=()=>{
            cancel();if(!card.isConnected)return;suppress=true;
            assetMenu?.remove();const dialog=document.createElement('dialog');assetMenu=dialog;dialog.className='library-asset-menu';dialog.setAttribute('aria-label',item.name);
            const title=document.createElement('h2');title.textContent=item.name;dialog.append(title);
            const close=()=>{dialog.close();dialog.remove();assetMenu=null;card.focus();};
            const preview=document.createElement('button');preview.textContent=item.kind==='video'?'播放':'查看大图';preview.onclick=()=>{close();open(item);};dialog.append(preview);
            const save=document.createElement('a');save.textContent='保存原文件';save.href=mediaUrl(item.id)+'?download=true';save.download='';save.onclick=close;dialog.append(save);
            const dismiss=document.createElement('button');dismiss.textContent='取消';dismiss.onclick=close;dialog.append(dismiss);
            dialog.addEventListener('cancel',event=>{event.preventDefault();close();});dialog.onclick=event=>{if(event.target===dialog)close();};document.body.append(dialog);dialog.showModal();
        };
        card.addEventListener('pointerdown',event=>{cancelActiveHold();suppress=false;if(!['touch','pen'].includes(event.pointerType)||event.isPrimary===false)return;point={id:event.pointerId,x:event.clientX,y:event.clientY};cancelActiveHold=cancel;timer=setTimeout(menu,550);});
        card.addEventListener('pointermove',event=>{if(point&&(event.pointerId!==point.id||Math.hypot(event.clientX-point.x,event.clientY-point.y)>10))cancel();});
        for(const name of ['pointerup','pointercancel','pointerleave'])card.addEventListener(name,cancel);
        card.addEventListener('click',event=>{if(suppress){suppress=false;event.preventDefault();event.stopImmediatePropagation();}},true);
        card.addEventListener('contextmenu',event=>{event.preventDefault();menu();});
    }
    if(!knowledge){window.addEventListener('scroll',()=>cancelActiveHold(),true);window.addEventListener('blur',()=>cancelActiveHold());}
    async function open(item){
        const seq=++sequence;current=item;notice('');$('browse').hidden=true;$('detail').hidden=false;
        $('item-title').textContent=item.title||item.name;$('item-info').textContent='';
        if(knowledge){
            $('reading').textContent='正在读取…';$('collect').disabled=true;
            try{const detail=await api('/items/'+encodeURIComponent(item.id));if(seq!==sequence)return;
                $('reading').textContent=detail.text;const attached=await api('/items/'+encodeURIComponent(item.id)+'/attachments');if(seq!==sequence)return;for(const file of attached.items||[]){const link=document.createElement('a');link.className='button';link.textContent='附件 '+(file.ordinal+1)+' · '+file.name;link.href=base+'/items/'+encodeURIComponent(item.id)+'/attachments/'+encodeURIComponent(file.item_id);link.download='';$('reading').append(document.createElement('br'),link);}$('item-info').textContent=detail.visibility==='private'?'私有知识':'设备共享知识';$('collect').disabled=false;
            }catch(e){if(seq===sequence){$('reading').textContent='';notice(e.message);}}
        }else{
            $('preview').replaceChildren();const media=document.createElement(item.kind==='video'?'video':'img');media.src=mediaUrl(item.id);
            if(item.kind==='video'){media.controls=true;media.playsInline=true;media.preload='metadata';}else media.alt=item.name;
            media.onerror=()=>notice('预览不可用，请检查会话或保存原文件。');$('preview').append(media);$('download').href=mediaUrl(item.id)+'?download=true';
        }
    }
    $('back').onclick=()=>{sequence++;if(!knowledge)$('preview').replaceChildren();$('detail').hidden=true;$('browse').hidden=false;current=null;notice('');};
    if(knowledge)$('collect').onclick=async()=>{
        if(!current)return;const id=current.id;$('collect').disabled=true;
        try{await api('/items/'+encodeURIComponent(id)+'/collect','POST');await collections();notice('已保存到“手机收藏”');}catch(e){notice(e.message);}finally{$('collect').disabled=false;}
    };
    if(!knowledge){
        $('fullscreen').onclick=()=>{
            const original=$('preview').firstElementChild;if(!original)return;
            if(original.tagName==='VIDEO')original.pause();
            $('full-media').replaceChildren(original.cloneNode(true));$('media-dialog').showModal();
        };
        $('close-fullscreen').onclick=()=>{$('media-dialog').close();};
        $('media-dialog').addEventListener('close',()=>{$('full-media').replaceChildren();});
    }
    if(knowledge){
        let mode='file',files=[],saving=false,asking=false,poll=null,disposed=false;
        function setMode(value){mode=value;for(const b of document.querySelectorAll('[data-add-mode]'))b.setAttribute('aria-pressed',String(b.dataset.addMode===mode));$('add-files').hidden=mode!=='file';$('add-web').hidden=mode!=='webpage';$('add-note').hidden=mode!=='note';$('web-url').disabled=mode!=='webpage';}
        for(const button of document.querySelectorAll('[data-add-mode]'))button.onclick=()=>setMode(button.dataset.addMode);
        function renderFiles(){ $('selected-files').replaceChildren();for(const [index,file] of files.entries()){const row=document.createElement('li'),name=document.createElement('span'),remove=document.createElement('button');name.textContent=file.name;remove.textContent='移除';remove.type='button';remove.onclick=()=>{files.splice(index,1);renderFiles();};row.append(name,remove);$('selected-files').append(row);}}
        function addFiles(list){for(const file of list)if(!files.some(f=>f.name===file.name&&f.size===file.size&&f.lastModified===file.lastModified))files.push(file);renderFiles();}
        for(const id of ['photo-input','file-input'])$(id).onchange=e=>{addFiles(e.target.files);e.target.value='';};
        $('knowledge-add').ondragover=e=>e.preventDefault();$('knowledge-add').ondrop=e=>{e.preventDefault();setMode('file');addFiles(e.dataTransfer.files);};
        $('add-knowledge').onclick=()=>{setMode('file');$('add-error').textContent='';$('knowledge-add').showModal();};
        $('close-add').onclick=()=>{if(!saving)$('knowledge-add').close();};
        $('knowledge-add').addEventListener('cancel',e=>{if(saving)e.preventDefault();});
        $('knowledge-add-form').onsubmit=async e=>{e.preventDefault();if(saving)return;saving=true;$('save-knowledge').disabled=true;$('add-error').textContent='';const bucket=$('add-bucket').value;
            try{if(mode==='file'){if(!files.length)throw new Error('请先选择图片或文件');const form=new FormData();files.forEach(f=>form.append('files',f,f.name));form.append('bucketId',bucket);form.append('mergeRecord',String($('merge-files').checked));form.append('detectOverlap',String($('detect-overlap').checked));if($('merge-files').checked&&$('group-title').value.trim())form.append('recordTitle',$('group-title').value.trim());form.append('sourceAppId','ai2apps.knowledge');const imported=await api('/files','POST',form);if(imported.job?.status==='failed')throw new Error('文件导入失败，请检查格式或文件大小');files=[];renderFiles();}
                else if(mode==='webpage'){if(!$('web-url').value.trim())throw new Error('请输入网页链接');await api('/web','POST',{url:$('web-url').value.trim(),bucket_id:bucket});$('web-url').value='';}
                else{await api('/notes','POST',{title:$('note-title').value.trim(),text:$('note-text').value.trim(),bucket_id:bucket});$('note-title').value='';$('note-text').value='';}
                $('knowledge-add').close();await collections();await load();notice('已保存，文件内容会在后台处理。');await processing();
            }catch(error){$('add-error').textContent=error.message;}finally{saving=false;$('save-knowledge').disabled=false;}};
        function showAsk(ask){$('mobile-ask').hidden=!ask;$('browse').hidden=ask;$('detail').hidden=true;$('show-ask').setAttribute('aria-pressed',String(ask));$('show-library').setAttribute('aria-pressed',String(!ask));}
        $('show-ask').onclick=()=>showAsk(true);$('show-library').onclick=()=>showAsk(false);
        $('ask-form').onsubmit=async e=>{e.preventDefault();if(asking)return;const question=$('ask-question').value.trim();if(!question)return;asking=true;$('ask-send').disabled=true;
            const user=document.createElement('p');user.className='question';user.textContent=question;$('ask-messages').append(user);
            try{const data=await api('/ask','POST',{question,bucket_id:$('ask-bucket').value||null});const answer=document.createElement('article');answer.textContent=data.answer;const sources=document.createElement('div');for(const citation of data.citations||[]){const b=document.createElement('button');b.type='button';b.textContent='['+citation.marker+'] '+citation.title;b.onclick=()=>{showAsk(false);open({id:citation.item_id,title:citation.title});};sources.append(b);}answer.append(sources);$('ask-messages').append(answer);$('ask-question').value='';notice('');}catch(error){notice(error.message);}finally{asking=false;$('ask-send').disabled=false;}};
        async function processing(){clearTimeout(poll);if(disposed)return;if(document.hidden){poll=setTimeout(processing,5000);return;}
            try{const [ocr,routing,imports]=await Promise.all([api('/image-ocr'),api('/bucket-routing'),api('/imports?limit=8')]);const jobs=[...(ocr.items||[]).map(j=>({...j,type:'image-ocr',token:j.consent_token})),...(routing.items||[]).map(j=>({...j,type:'bucket-routing'}))].filter(j=>['queued','running','pending','awaiting_consent','failed','blocked'].includes(j.status));$('mobile-processing').hidden=!jobs.length&&!(imports.items||[]).some(j=>['queued','running'].includes(j.status));$('processing-jobs').replaceChildren();for(const job of (imports.items||[]).filter(j=>['queued','running'].includes(j.status))){const progress=document.createElement('p');progress.textContent='文件导入：'+(job.completed_files||0)+' / '+job.total_files;$('processing-jobs').append(progress);}
                for(const job of jobs){const row=document.createElement('article'),title=document.createElement('p');title.textContent=job.title+' · '+({'queued':'排队中','running':'处理中','pending':'等待内容或模型','awaiting_consent':'等待授权','failed':'处理失败','blocked':'缺少可用模型'}[job.status]||job.status);row.append(title);if(job.status==='awaiting_consent'){const text=document.createElement('p');text.textContent=job.type==='bucket-routing'?'允许 '+job.model_id+' 读取提取文本和私有知识桶名称以归类？':'允许 '+(job.model_label||job.model_id)+' 解读这张图片？';row.append(text);for(const [label,allow] of [['允许本次',true],['暂不使用',false]]){const b=document.createElement('button');b.textContent=label;b.onclick=async()=>{b.disabled=true;try{await api('/'+job.type+'/'+encodeURIComponent(job.item_id)+'/decision','POST',{token:job.token,revision:job.revision||job.item_revision,allow});await processing();}catch(error){notice(error.message);b.disabled=false;}};row.append(b);}}$('processing-jobs').append(row);}
            }catch(_){/* Library reading remains available while status is unavailable. */}if(!disposed)poll=setTimeout(processing,5000);}
        window.addEventListener('pagehide',()=>{disposed=true;clearTimeout(poll);});window.addEventListener('pageshow',()=>{if(disposed){disposed=false;void processing();}});void processing();
    }
    $('search-form').onsubmit=e=>{e.preventDefault();load();};$('collection').onchange=load;if(!knowledge)$('kind').onchange=load;
    $('refresh').onclick=async()=>{try{await collections();if(current)await open(current);else await load();}catch(e){notice(e.message);}};
    collections().then(load).catch(e=>notice(e.message));
})();
