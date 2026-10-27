(() => {
    'use strict';
    const zh = document.documentElement.lang.startsWith('zh');
    const words = zh ? {
        title:'设置账户头像', note:'头像将用于你的账户和公开空间。原图不会上传或修改。', local:'选择本地图片', gallery:'从 Gallery 选择', rotate:'旋转', reset:'重置', zoom:'缩放', cancel:'取消', save:'上传并保存', remove:'移除头像', saving:'正在保存…', choose:'请选择 PNG、JPEG 或静态 WebP 图片。', invalid:'图片格式不支持、已损坏或过大（最多 20 MiB / 4000 万像素）。', conflict:'头像已在其它地方更新，已读取最新头像。裁剪内容已保留；再次点击保存才会替换。', unknown:'尚无法确认保存结果，已尝试读取最新头像。请检查后再操作。', old:'服务器尚不支持头像上传，请更新后重试。', failed:'头像保存失败，请重试。', preview:'头像圆形裁剪预览', retry:'请求过于频繁，请稍后再试。', success:'头像已保存', removed:'头像已移除'
    } : {
        title:'Account avatar', note:'Used on your account and public space. The original image stays private and unchanged.', local:'Choose local image', gallery:'Choose from Gallery', rotate:'Rotate', reset:'Reset', zoom:'Zoom', cancel:'Cancel', save:'Upload and save', remove:'Remove avatar', saving:'Saving…', choose:'Choose a PNG, JPEG or static WebP image.', invalid:'Unsupported, damaged or oversized image (20 MiB / 40 megapixels maximum).', conflict:'Your avatar changed elsewhere. The latest avatar is loaded and your crop is preserved. Save again only to replace it.', unknown:'The save result is uncertain. We tried to reload your current avatar; review before trying again.', old:'The server does not support avatar uploads yet.', failed:'Could not save the avatar. Try again.', preview:'Circular avatar crop preview', retry:'Too many requests. Please try again later.', success:'Avatar saved', removed:'Avatar removed'
    };
    const validRevision = p => Number.isSafeInteger(p?.avatarRevision) && p.avatarRevision >= 0;
    function bound(state) {
        const width = state.turn % 2 ? state.height : state.width;
        const height = state.turn % 2 ? state.width : state.height;
        state.scale = Math.max(300 / width, 300 / height) * state.zoom;
        state.x = Math.max(-(width * state.scale - 300) / 2, Math.min((width * state.scale - 300) / 2, state.x));
        state.y = Math.max(-(height * state.scale - 300) / 2, Math.min((height * state.scale - 300) / 2, state.y));
        return state;
    }
    function animated(bytes, type) {
        const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
        const tag=offset=>String.fromCharCode(...bytes.slice(offset,offset+4));
        if(type==='image/png'){
            for(let i=8;i+12<=bytes.length;){const size=view.getUint32(i);if(tag(i+4)==='acTL')return true;if(size>bytes.length-i-12)break;i+=size+12;}
        }else if(type==='image/webp'){
            for(let i=12;i+8<=bytes.length;){const size=view.getUint32(i,true);if(tag(i)==='ANIM'||tag(i)==='ANMF')return true;if(size>bytes.length-i-8)break;i+=8+size+(size%2);}
        }
        return false;
    }
    let opened = false;
    async function open({readProfile, updateAvatar}) {
        if (opened) return;
        opened = true;
        const previous = document.activeElement;
        const dialog = document.createElement('dialog'); dialog.className = 'account-avatar-dialog';
        const el = (tag, text) => {const n=document.createElement(tag); if(text)n.textContent=text; return n;};
        const title=el('h2',words.title);title.id='account-avatar-title';dialog.setAttribute('aria-labelledby',title.id);
        const note=el('p',words.note), current=el('div');current.className='account-avatar-current';
        const status=el('p',words.choose);status.setAttribute('role','status');
        const actions=el('div');actions.className='account-avatar-actions';
        const button=(text,fn,parent=actions)=>{const b=el('button',text);b.type='button';b.onclick=fn;parent.append(b);return b;};
        const input=el('input');input.type='file';input.accept='image/png,image/jpeg,image/webp';input.hidden=true;
        const canvas=el('canvas');canvas.width=canvas.height=300;canvas.className='account-avatar-crop';canvas.setAttribute('aria-label',words.preview);canvas.hidden=true;
        const controls=el('div');controls.className='account-avatar-actions';controls.hidden=true;
        const slider=el('input');slider.type='range';slider.min='1';slider.max='4';slider.step='0.01';slider.value='1';slider.setAttribute('aria-label',words.zoom);
        const foot=el('div');foot.className='account-avatar-actions';
        let busy=false, profile=null, image=null, url=null, revision=0, closed=false, retryUntil=0;
        let state={width:300,height:300,turn:0,zoom:1,x:0,y:0,scale:1};
        const points=new Map(); let gesture=null;
        function showCurrent(p){current.replaceChildren();const fallback=el('span',(p?.displayName||'A').trim().slice(0,1).toUpperCase());current.append(fallback);if(p?.avatarUrl){try{const u=new URL(p.avatarUrl);if(u.origin!=='https://coder.ai2apps.com'||!/^\/v1\/public\/avatars\/[\da-f-]+\.png$/.test(u.pathname)||u.search||u.hash)return;const img=el('img');img.alt='';img.src=u.href;img.onerror=()=>img.remove();current.append(img);}catch(_){}}}
        async function reload(){profile=await readProfile();if(closed)return;updateAvatar(profile);showCurrent(profile);}
        function sync(){dialog.querySelectorAll('button,input').forEach(n=>n.disabled=busy);save.disabled=busy||!image||!validRevision(profile);remove.disabled=busy||!profile?.avatarUrl||!validRevision(profile);}
        function draw(ctx=canvas.getContext('2d')){bound(state);ctx.clearRect(0,0,300,300);if(!image)return;ctx.save();ctx.translate(150+state.x,150+state.y);ctx.scale(state.scale,state.scale);ctx.rotate(state.turn*Math.PI/2);ctx.drawImage(image,-state.width/2,-state.height/2);ctx.restore();}
        function finish(){if(busy)return;closed=true;revision++;if(url)URL.revokeObjectURL(url);dialog.close();dialog.remove();opened=false;previous?.focus();}
        async function select(blob){const selection=++revision;status.textContent='';try{
            if(!blob||blob.size>20*1024*1024||!['image/png','image/jpeg','image/webp'].includes(blob.type))throw Error(words.invalid);
            const bytes=new Uint8Array(await blob.arrayBuffer());
            // Reject animated containers before converting their first frame into PNG.
            if(animated(bytes,blob.type))throw Error(words.invalid);
            const nextUrl=URL.createObjectURL(blob), next=new Image();
            try{next.src=nextUrl;await next.decode();if(next.naturalWidth*next.naturalHeight>40000000||!next.naturalWidth)throw Error(words.invalid);
                if(closed||selection!==revision){URL.revokeObjectURL(nextUrl);return;}
                if(url)URL.revokeObjectURL(url);url=nextUrl;image=next;
            }catch(e){URL.revokeObjectURL(nextUrl);throw e;}
            state={width:image.naturalWidth,height:image.naturalHeight,turn:0,zoom:1,x:0,y:0};slider.value='1';canvas.hidden=false;controls.hidden=false;draw();
        }catch(e){if(!closed&&selection===revision)status.textContent=words.invalid;}finally{if(!closed)sync();}}
        button(words.local,()=>input.click());
        button(words.gallery,async()=>{try{const assets=await window.AI2AppsGalleryPicker.open({multiple:false,kind:'image'});if(!assets.length||closed)return;const r=await fetch('/v1/platform/gallery/assets/'+encodeURIComponent(assets[0].id)+'/content',{credentials:'same-origin'});if(!r.ok)throw Error(words.invalid);await select(await r.blob());}catch(e){if(!closed)status.textContent=e.message;}});
        input.onchange=()=>{const file=input.files?.[0];input.value='';if(file)void select(file);};
        controls.append(slider);slider.oninput=()=>{state.zoom=Number(slider.value);draw();};
        button(words.rotate,()=>{state.turn=(state.turn+1)%4;state.x=state.y=0;draw();},controls);
        button(words.reset,()=>{state.turn=0;state.zoom=1;state.x=state.y=0;slider.value='1';draw();},controls);
        const position=e=>{const r=canvas.getBoundingClientRect();return {x:(e.clientX-r.left)*300/r.width,y:(e.clientY-r.top)*300/r.height};};
        function start(){const p=[...points.values()];gesture={state:{...state},center:p.length>1?{x:(p[0].x+p[1].x)/2,y:(p[0].y+p[1].y)/2}:p[0],distance:p.length>1?Math.hypot(p[0].x-p[1].x,p[0].y-p[1].y):0};}
        canvas.onpointerdown=e=>{if(busy||!image)return;e.preventDefault();canvas.setPointerCapture(e.pointerId);points.set(e.pointerId,position(e));start();};
        canvas.onpointermove=e=>{if(!points.has(e.pointerId)||busy)return;e.preventDefault();points.set(e.pointerId,position(e));const p=[...points.values()],g=gesture;const center=p.length>1?{x:(p[0].x+p[1].x)/2,y:(p[0].y+p[1].y)/2}:p[0];const zoom=g.distance?Math.max(1,Math.min(4,g.state.zoom*Math.hypot(p[0].x-p[1].x,p[0].y-p[1].y)/g.distance)):g.state.zoom;const ratio=zoom/g.state.zoom;state.zoom=zoom;state.x=center.x-150-(g.center.x-150-g.state.x)*ratio;state.y=center.y-150-(g.center.y-150-g.state.y)*ratio;slider.value=String(zoom);draw();};
        const end=e=>{points.delete(e.pointerId);if(points.size)start();};canvas.onpointerup=end;canvas.onpointercancel=end;canvas.onlostpointercapture=end;
        async function submit(deleting){if(busy||!validRevision(profile)||Date.now()<retryUntil){if(Date.now()<retryUntil)status.textContent=words.retry;return;}
            busy=true;sync();status.textContent=words.saving;
            try{
                // Use the revision the editor read; never silently overwrite a newer avatar.
                const options={method:deleting?'DELETE':'PUT',credentials:'same-origin',headers:{'If-Match':'"avatar-'+profile.avatarRevision+'"'}};
                if(!deleting){const output=document.createElement('canvas');output.width=output.height=300;draw(output.getContext('2d'));const blob=await new Promise(resolve=>output.toBlob(resolve,'image/png'));if(!blob)throw Error(words.failed);const form=new FormData();form.append('file',blob,'avatar.png');options.body=form;}
                const r=await fetch('/v1/platform/cloud/profile/avatar',options);const p=await r.json();
                if(!r.ok){if(r.status===429){const after=r.headers.get('retry-after');retryUntil=Date.now()+(Number(after)||Math.max(1,(Date.parse(after)-Date.now())/1000)||60)*1000;}const err=Error(p.error?.message||p.detail?.message||words.failed);err.status=r.status;throw err;}
                profile=p;updateAvatar(p);showCurrent(p);status.textContent=deleting?words.removed:words.success;
                if(!deleting){busy=false;finish();}
            }catch(e){try{await reload();}catch(_){profile=null;}
                status.textContent=e.status===409?words.conflict:e.status===429?words.retry:!e.status||e.status>=500?words.unknown:e.message;
            }finally{busy=false;if(!closed)sync();}
        }
        const remove=button(words.remove,()=>submit(true),foot);
        button(words.cancel,finish,foot);
        const save=button(words.save,()=>submit(false),foot);save.className='account-avatar-save';
        dialog.append(title,note,current,actions,input,canvas,controls,status,foot);document.body.append(dialog);dialog.addEventListener('cancel',e=>{e.preventDefault();finish();});dialog.showModal();busy=true;sync();
        try{await reload();if(!validRevision(profile))status.textContent=words.old;}catch(e){status.textContent=e.message;}finally{busy=false;sync();}
    }
    window.AI2AppsAccountAvatar={open,bound,validRevision};
})();
