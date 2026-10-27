(function(){
'use strict';
const t=window.VisitorSpaceI18n?.t||((value,params={})=>value.replace(/\{(\w+)\}/g,(_,key)=>params[key]??'{'+key+'}'));
const $=id=>document.getElementById(id);if(!$('visitor-editor'))return;
let state,apps=[],draft,dirty=false,busy=false,autoRunAsset=null;
const aiConversations=new WeakMap();
const notice=(text,kind='info')=>{const el=$('vs-notice');el.textContent=text;el.dataset.kind=kind;};
async function request(path,method='GET',body){const r=await fetch('/v1/platform/remote/visitor-space'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const data=await r.json();if(!r.ok)throw new Error(typeof data.error?.message==='string'?data.error.message:typeof data.detail==='string'?data.detail:t("操作失败，请刷新重试"));return data;}
function preview(){if(!draft)return;draft.title=$('vs-title').value;draft.description=$('vs-description').value;draft.theme=$('vs-theme').value;window.renderVisitorSpace($('vs-preview-content'),draft,{preview:true,autoRunAsset,ownerAvatarUrl:state?.ownerAvatarUrl,resourceUrl:id=>'/v1/platform/remote/visitor-space/assets/'+id});}
function changed(){dirty=true;preview();notice(t("有未保存的草稿修改"));}
function updateState(){ document.querySelectorAll('#visitor-editor input,#visitor-editor textarea,#visitor-editor select,#visitor-editor [data-add]').forEach(el=>el.disabled=busy); const appButton=document.querySelector('[data-add=app]');if(appButton)appButton.disabled=busy||!state?.appGatewayReady||!apps.length; $('vs-toggle').disabled=busy||!state;$('vs-toggle').textContent=state?.enabled?t("关闭访客空间"):state?.revision?t("开启访客空间"):t("发布并开启访客空间");$('vs-state').textContent=(state?.enabled?t("已开放"):t("已关闭"))+' · '+t("发布版本 {n}",{n:state?.revision||0});$('vs-save').disabled=busy;$('vs-publish').disabled=busy;}
function field(parent,label,value,onchange,kind='input') {const l=document.createElement('label');l.textContent=label;const input=document.createElement(kind);input.value=value||'';input.addEventListener('input',()=>{onchange(input.value);changed();});l.append(input);parent.append(l);return input;}
const labels={text:t("文字"),link:t("网页链接"),app:t("应用"),image:t("图片"),video:t("视频"),html:t("HTML 作品"),article:t("稿件"),carousel:t("轮播")};
function newCard(kind){return {kind,title:'',text:'',...(kind==='link'?{url:''}:kind==='app'?{appKey:''}:kind==='carousel'?{cards:[],autoplay:false,interval:5}:kind==='article'?{body:''}:{})};}
function addButton(parent,label,fn){const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=()=>{if(!busy)return fn();};parent.append(b);return b;}
async function upload(kind,file){const limit={image:20,video:100,html:10}[kind]*1024*1024;if(file.size>limit)throw new Error(t("文件超过大小限制"));const r=await fetch('/v1/platform/remote/visitor-space/assets/'+kind,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/octet-stream'},body:file});const data=await r.json();if(!r.ok)throw new Error(data.detail||t("素材导入失败"));return data;}
function assetField(el,card,key,kind){
    const group=document.createElement('div');group.className='vs-actions';el.append(group);
    const status=document.createElement('small');status.textContent=card[key]?t("已选择素材（发布时公开副本）"):key==='coverId'?t("可选封面"):t("尚未选择素材");el.append(status);
    const accept=kind==='html'?'.html,.htm,text/html':kind==='video'?'video/mp4,video/webm':'image/*';
    addButton(group,key==='coverId'?t("选择封面"):t("选择本地文件"),()=>{const input=document.createElement('input');input.type='file';input.accept=accept;input.onchange=()=>{if(input.files[0])action(async()=>{const asset=await upload(kind,input.files[0]);card[key]=asset.id;drawCards();changed();});};input.click();});
    if(kind!=='html')addButton(group,t("从 Gallery 选择"),async()=>{try{const items=await window.AI2AppsGalleryPicker.open({multiple:false,kind});if(items?.length)await action(async()=>{const asset=await request('/gallery','POST',{assetId:items[0].id,kind});card[key]=asset.id;drawCards();changed();});}catch(e){notice(t(e.message),'error');}});
    if(card[key])addButton(group,t("移除素材"),()=>{delete card[key];drawCards();changed();});
    if(kind==='html'){
        const ai=document.createElement('details');ai.className='vs-html-ai';ai.open=true;
        const summary=document.createElement('summary');summary.textContent=t("与 AI 创作");ai.append(summary);
        let conversation=aiConversations.get(card);if(!conversation){conversation={history:[],prompt:'',previous:null};aiConversations.set(card,conversation);}
        const transcript=document.createElement('div');transcript.className='vs-ai-transcript';
        for(const message of conversation.history){const p=document.createElement('p');p.textContent=message;transcript.append(p);}ai.append(transcript);
        const prompt=document.createElement('textarea');prompt.rows=3;prompt.maxLength=8000;prompt.placeholder=t("例如：让一段文字在星空里缓慢飞翔，手指滑动可以改变方向…");prompt.value=conversation.prompt;prompt.oninput=()=>conversation.prompt=prompt.value;ai.append(prompt);
        const hint=document.createElement('small');hint.textContent=t("使用标准任务默认模型 / API Default；当前代码与需求会发送给所选模型。生成后应用到草稿，发布后访客可见。");ai.append(hint);
        const aiStatus=document.createElement('p');aiStatus.className='vs-ai-status';aiStatus.setAttribute('role','status');aiStatus.setAttribute('aria-live','polite');aiStatus.textContent=conversation.status||'';aiStatus.dataset.kind=conversation.statusKind||'info';ai.append(aiStatus);
        const generate=addButton(ai,card.assetId?t("发送需求并修改"):t("生成并启用"),()=>action(async()=>{
            const label=generate.textContent;
            const show=(text,kind='info')=>{conversation.status=text;conversation.statusKind=kind;aiStatus.textContent=text;aiStatus.dataset.kind=kind;};
            try{
            if(!prompt.value.trim())throw new Error(t("请先描述你想要的内容"));
            generate.disabled=true;generate.textContent=t("正在生成…");ai.classList?.add('is-generating');
            show(t("AI 正在编写 HTML，通常需要几十秒；完成后会自动应用并预览，请勿重复点击。"));
            notice(t("AI 正在编写 HTML…"));
            const result=await request('/html-ai','POST',{prompt:prompt.value,history:conversation.history.slice(-12),assetId:card.assetId||null,height:card.height||360});
            conversation.previous=card[key]||null;conversation.history.push(prompt.value);conversation.prompt='';card[key]=result.asset.id;autoRunAsset=result.asset.id;
            show(t("已生成并应用到草稿，右侧可预览；可以继续提出修改要求。"),'success');
            drawCards();changed();autoRunAsset=null;notice(t("AI 作品已应用到草稿并开始预览，可继续对话修改；发布后访客可见。"),'success');
            }catch(error){show(t(error.message)||t("生成失败，请重试"),'error');throw error;}
            finally{generate.disabled=false;generate.textContent=label;ai.classList?.remove('is-generating');}
        }));
        if(conversation.previous)addButton(ai,t("恢复上个版本"),()=>{card[key]=conversation.previous;conversation.previous=null;drawCards();changed();});
        if(conversation.history.length)addButton(ai,t("清空对话"),()=>{conversation.history=[];conversation.prompt='';drawCards();});
        el.append(ai);
        const source=document.createElement('textarea');source.placeholder=t("粘贴完整 HTML 或 data:text/html…（UTF-8，最多 10 MB）");source.rows=5;el.append(source);
        addButton(el,t("采用 HTML 内容"),()=>action(async()=>{let value=source.value;if(value.startsWith('data:')){const comma=value.indexOf(',');const head=value.slice(0,comma);if(comma<0||!/^data:text\/html(?:;charset=utf-8)?(?:;base64)?$/i.test(head))throw new Error(t("仅支持 HTML Data URL"));value=head.endsWith(';base64')?new TextDecoder('utf-8',{fatal:true}).decode(Uint8Array.from(atob(value.slice(comma+1)),c=>c.charCodeAt(0))):decodeURIComponent(value.slice(comma+1));}const asset=await upload('html',new Blob([value],{type:'text/html'}));card[key]=asset.id;drawCards();changed();}));
    }
}
function drawCards(){
    const root=$('vs-cards');root.replaceChildren();
    function draw(list,parent,nested=false){list.forEach((card,i)=>{
        const el=document.createElement('section');el.className='vs-card';const heading=document.createElement('h4');heading.textContent=labels[card.kind];el.append(heading);
        const hiddenLabel=document.createElement('label');const hidden=document.createElement('input');hidden.type='checkbox';hidden.checked=!!card.hidden;hidden.onchange=()=>{card.hidden=hidden.checked;changed();};hiddenLabel.append(hidden,document.createTextNode(t(" 暂时隐藏此卡片")));el.append(hiddenLabel);
        field(el,t("标题"),card.title,v=>card.title=v);field(el,t("说明 / 摘要"),card.text,v=>card.text=v,'textarea');
        if(card.kind==='link')field(el,t("HTTPS 链接（支持 YouTube、B站等）"),card.url,v=>card.url=v);
        if(['link','article','video','html'].includes(card.kind))assetField(el,card,'coverId','image');
        if(['image','video','html'].includes(card.kind))assetField(el,card,'assetId',card.kind);
        if(card.kind==='image'){const select=field(el,t("图片布局"),card.fit||'contain',v=>card.fit=v,'select');for(const [value,label] of [['contain',t("完整显示")],['cover',t("裁切铺满")]]){const o=document.createElement('option');o.value=value;o.textContent=label;select.append(o);}select.value=card.fit||'contain';}
        if(card.kind==='html'){const label=document.createElement('label');const check=document.createElement('input');check.type='checkbox';check.checked=!!card.autoload;check.onchange=()=>{card.autoload=check.checked;changed();};label.append(check,document.createTextNode(t(" 默认自动加载（进入可视区域时启动）")));el.append(label);const input=field(el,t("展示高度（160–800）"),card.height||360,v=>card.height=Number(v));input.type='number';input.min=160;input.max=800;}
        if(card.kind==='article'){const input=field(el,t("正文（Markdown：标题、粗体、代码和 HTTPS 链接；不执行 HTML）"),card.body,v=>card.body=v,'textarea');input.rows=12;}
        if(card.kind==='app'){const select=field(el,t("开放应用"),card.appKey,v=>card.appKey=v,'select');const empty=document.createElement('option');empty.value='';empty.textContent=t("请选择 Open-Entry 应用");select.append(empty);for(const app of apps){const o=document.createElement('option');o.value=app.appKey;o.textContent=app.title;select.append(o);}select.value=card.appKey||'';}
        if(card.kind==='carousel'){
            const check=document.createElement('input');check.type='checkbox';check.checked=!!card.autoplay;check.onchange=()=>{card.autoplay=check.checked;changed();};const label=document.createElement('label');label.append(check,document.createTextNode(t(" 自动轮播")));el.append(label);
            const interval=field(el,t("间隔秒数（3–30）"),card.interval||5,v=>card.interval=Number(v));interval.type='number';interval.min=3;interval.max=30;
            const children=document.createElement('div');children.className='vs-children';el.append(children);draw(card.cards||(card.cards=[]),children,true);
            const select=document.createElement('select');for(const [kind,title] of Object.entries(labels)){if(kind==='carousel')continue;const o=document.createElement('option');o.value=kind;o.textContent=title;select.append(o);}el.append(select);
            const add=addButton(el,t("添加轮播内容（最多 8 个）"),()=>{if(card.cards.length<8){card.cards.push(newCard(select.value));drawCards();changed();}});add.disabled=card.cards.length>=8;
        }
        const actions=document.createElement('div');actions.className='vs-actions';for(const [title,offset] of [[t("上移"),-1],[t("下移"),1],[t("删除"),0]]){const b=addButton(actions,title,()=>{if(offset)[list[i],list[i+offset]]=[list[i+offset],list[i]];else list.splice(i,1);drawCards();changed();});b.disabled=offset!==0&&(i+offset<0||i+offset>=list.length);}
        el.append(actions);parent.append(el);
    });}
    draw(draft.cards,root);preview();
}
async function action(fn){if(busy)return;busy=true;updateState();try{await fn();}catch(e){notice(t(e.message),'error');}finally{busy=false;updateState();}}
async function save(){preview();state={...state,...await request('/draft','PUT',{version:state.version,draft})};dirty=false;notice(t("草稿已保存，访客页面未改变"),'success');}
$('vs-save').onclick=()=>action(save);
async function publish(){if(dirty)await save();state={...state,...await request('/publish','POST',{version:state.version})};}
$('vs-publish').onclick=()=>action(async()=>{await publish();notice(state.enabled?t("新内容已发布"):t("内容已发布。开启访客空间后，访客即可访问。"),'success');});
$('vs-toggle').onclick=()=>action(async()=>{if(!state.enabled&&!state.revision)await publish();state={...state,...await request('/enabled','PUT',{version:state.version,enabled:!state.enabled})};notice(state.enabled?t("访客空间已开启"):t("访客空间已关闭，已有访问已撤销"),'success');});
for(const id of ['vs-title','vs-description','vs-theme'])$(id).addEventListener('input',changed);
$('vs-width').onchange=()=>$('vs-preview').className='vs-preview '+$('vs-width').value;
document.querySelectorAll('[data-add]').forEach(b=>b.onclick=()=>{if(!draft)return;if(draft.cards.length>=30){notice(t("最多添加 30 张卡片"),'error');return;}draft.cards.push(newCard(b.dataset.add));drawCards();changed();});
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
action(async()=>{state=await request('');try{const r=await fetch('/v1/platform/cloud/profile',{credentials:'same-origin'});if(r.ok)state.ownerAvatarUrl=(await r.json()).avatarUrl;}catch(_){}apps=state.apps;draft=structuredClone(state.draft);$('vs-title').value=draft.title;$('vs-description').value=draft.description;$('vs-theme').value=draft.theme;if(state.userUrl){$('vs-url').href=state.userUrl;$('vs-url').textContent=state.userUrl;$('vs-qr').src=state.qr;}else{$('vs-url').textContent=t("登录 AI2Apps 账户后可获取空间链接");$('vs-qr').hidden=true;}$('vs-app-note').textContent=state.appGatewayReady?t("仅展示已安装、显式声明零权限 Open-Entry 的应用。"):t("访客 App 通道待 Cloud 部署；目前可发布文字与链接。");if(!state.contentGatewayReady)$('vs-app-note').textContent+=t(" 图片、视频和 HTML 可编辑预览；公开素材通道待部署。");drawCards();});
})();
