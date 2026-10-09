(() => {
    'use strict';
    const $=id=>document.getElementById(id), type=$('library').dataset.library, knowledge=type==='knowledge', base='/v1/mobile/'+type;
    let current=null, sequence=0;
    const notice=t=>{$('notice').textContent=t;};
    async function api(path,method='GET'){
        const r=await fetch(base+path,{method,credentials:'same-origin',cache:'no-store'});
        const data=await r.json().catch(()=>({}));
        if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:data.error?.message||'请求失败（'+r.status+'）');return data;
    }
    const mediaUrl=id=>base+'/assets/'+encodeURIComponent(id)+'/content';
    async function collections(){
        const old=$('collection').value, data=await api(knowledge?'/buckets':'/collections');
        $('collection').replaceChildren(new Option('全部',''),...data.items.map(x=>new Option(x.name,x.id)));
        if(data.items.some(x=>x.id===old))$('collection').value=old;
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
                $('reading').textContent=detail.text;$('item-info').textContent=detail.visibility==='private'?'私有知识':'设备共享知识';$('collect').disabled=false;
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
    $('search-form').onsubmit=e=>{e.preventDefault();load();};$('collection').onchange=load;if(!knowledge)$('kind').onchange=load;
    $('refresh').onclick=async()=>{try{await collections();if(current)await open(current);else await load();}catch(e){notice(e.message);}};
    collections().then(load).catch(e=>notice(e.message));
})();
