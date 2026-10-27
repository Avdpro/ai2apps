(function () {
    'use strict';
    const zh = (document.documentElement.lang || navigator.language).startsWith('zh');
    const t = (a, b) => zh ? a : b;
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    let appCatalog = window.AI2APPS_SHELL_BOOT?.apps || [];
    const expanded = new Set();
    const label = t('能力与工具', 'Capabilities & Tools');
    function build(data, query) {
        const root = {children: new Map(), tools: [], providers: []};
        const node = name => {
            let n = root;
            for (const segment of name.split('.')) {
                if (!n.children.has(segment)) n.children.set(segment, {children:new Map(), tools:[], providers:[]});
                n = n.children.get(segment);
            }
            return n;
        };
        // Assemble complete functional mappings before filtering. Permissions are
        // metadata on a Tool, never capability-tree membership.
        const groups = new Map();
        for (const tool of data.tools) {
            groups.set(tool.name, {tools:[tool], providers:[]});
        }
        for (const provider of data.providers) {
            if (!groups.has(provider.capability)) groups.set(provider.capability, {tools:[], providers:[]});
            groups.get(provider.capability).providers.push(provider);
        }
        for (const [capability, group] of groups) {
            const searchable = [capability, ...group.tools.map(x => x.name),
                ...group.providers.flatMap(x => [x.id, x.app_id, x.mini_app_id])].join(' ').toLowerCase();
            if (query && !searchable.includes(query)) continue;
            const leaf = node(capability);
            leaf.tools = group.tools;
            leaf.providers = group.providers;
        }
        return root;
    }
    function providerIcon(appId) {
        const app = appCatalog.find(x => x.id === appId);
        const name = appId ? (app?.icon || 'app-window') : 'plug';
        const safe = /^[a-z0-9-]{1,48}$/.test(name) ? name : 'app-window';
        return '<i aria-label="'+esc(appId ? (app?.name || appId) : 'API-Tool')+'" data-lucide="'+safe+'" style="width:24px;height:24px;vertical-align:middle;margin-right:8px"></i>';
    }
    function toolApp(tool) {
        return appCatalog.find(x => x.id === tool.service)?.id || null;
    }
    function render(n, prefix, query) {
        return [...n.children].sort(([a],[b]) => a.localeCompare(b)).map(([name, child]) => {
            const path = prefix ? prefix + '.' + name : name;
            const providers = child.providers.map(p => '<article class="control-card"><div class="capability-provider-heading">' + providerIcon(p.app_id) + '<strong>' + esc(p.id) + '</strong><button type="button" role="switch" aria-checked="'+(p.enabled!==false)+'" aria-label="'+esc(t('启用提供者 ','Enable provider ')+p.id)+'" data-provider-toggle="'+esc(p.id)+'" data-enabled="'+(p.enabled!==false)+'" class="capability-provider-switch"><span class="capability-switch-label">'+(p.enabled!==false?t('已启用','Enabled'):t('已关闭','Disabled'))+'</span><span class="capability-switch-track" aria-hidden="true"><span class="capability-switch-thumb"></span></span></button></div><p>' +
                esc((p.mini_app_id ? 'Mini-App' : 'App') + ' · ' + p.app_id) + '</p><p>' +
                esc(t('默认优先级：','Default priority: ') + p.priority + ' · ' + (p.enabled===false?t('已关闭','Disabled'):p.rank ? t('当前顺序 #','Current rank #') + p.rank : t('冷却中','Cooling down'))) + '</p><p>' +
                esc(p.enabled===false ? t('不参与路由和参数表单选择','Excluded from routing and parameter forms') : p.cooldown_seconds ? t('剩余秒数：','Seconds remaining: ') + p.cooldown_seconds : t('已注册 · 执行时检查权限和依赖','Registered · Permissions and dependencies checked at execution')) + '</p>' +
                (p.success_at ? '<p>' + esc(t('上次成功：','Last success: ') + new Date(p.success_at*1000).toLocaleString()) + '</p>' : '') +
                (p.reason ? '<p>' + esc(t('最近不可用原因：','Last unavailable reason: ') + p.reason) + '</p>' : '') + (p.parameter_contract ? '<details data-provider-parameters="'+esc(p.id)+'"><summary>'+t('Provider 参数与模型','Provider parameters and models')+'</summary><div data-parameter-preview></div></details>' : '') + '</article>').join('');
            const tools = child.tools.map(tool => '<details class="control-card" data-tree-key="' + esc(path+'|'+tool.name) + '" '+(expanded.has(path+'|'+tool.name)?'open':'')+'><summary>' + (child.providers.length ? '' : providerIcon(toolApp(tool))) + esc(tool.name) + (child.providers.length ? '' : ' · ' + (toolApp(tool) ? 'App Tool' : 'API-Tool')) + ' · ' +
                esc(tool.enabled ? t('已启用','Enabled') : t('已禁用','Disabled')) + '</summary><p>' + esc(tool.description) + '</p><p>' + esc(t('所属服务：','Service: ') + tool.service + ' · ' + tool.service_status) + '</p><p>' + esc(t('所需权限：','Required capabilities: ') + tool.capabilities.join(', ')) + '</p><p>' + esc(t('副作用：','Effects: ') + tool.effects.join(', ')) + '</p><h4>' + t('输入参数','Input schema') + '</h4><pre style="white-space:pre-wrap;overflow-wrap:anywhere">' + esc(JSON.stringify(tool.input_schema,null,2)) + '</pre><h4>' + t('返回值','Output schema') + '</h4><pre style="white-space:pre-wrap;overflow-wrap:anywhere">' + esc(JSON.stringify(tool.output_schema,null,2)) + '</pre></details>').join('');
            return '<details data-tree-key="'+esc(path)+'" '+(query || expanded.has(path)?'open':'')+' style="margin:8px 0 8px 14px;border-left:1px solid #8885;padding-left:12px"><summary style="cursor:pointer;padding:8px;overflow-wrap:anywhere"><strong>'+esc(name)+'</strong> <small>'+esc(path)+'</small></summary>'+ ((providers || tools) ? '<h4>'+t('能力提供者','Capability providers')+'</h4>' : '')+ (providers || '') +(tools ? (providers ? '<h4>'+t('Tool 接口详情','Tool interface details')+'</h4>' : '')+tools : '')+render(child,path,query)+'</details>';
        }).join('');
    }
    function mount(host, request) {
        host.innerHTML = '<section data-capability-tree><h2>'+label+'</h2><p>'+t('按功能能力与 Tool 名称分层，搜索保留命中能力的完整提供者。路由优先采用最近成功的提供者，再按默认优先级排序；权限见 Tool 详情。','Grouped by functional capability and Tool name. Search retains all providers of a matching capability. Routing prefers recent success, then default priority. Permissions appear in Tool details.')+'</p><input type="search" aria-label="'+t('搜索能力或 Tool','Search capabilities or Tools')+'" placeholder="'+t('搜索能力、Tool、App…','Search capability, Tool, App…')+'" style="width:100%;padding:10px;margin:8px 0"><button class="control-action" type="button">'+t('刷新状态','Refresh status')+'</button><p role="status"></p><div data-tree-content></div></section>';
        const section=host.firstElementChild, input=section.querySelector('input'), button=section.querySelector('button'), status=section.querySelector('[role=status]'), content=section.querySelector('[data-tree-content]');
        let data=null;
        function draw() { if(data) { content.innerHTML=render(build(data,input.value.trim().toLowerCase()),'',input.value.trim()) || t('没有匹配项','No matches'); window.lucide?.createIcons(); } }
        content.addEventListener('toggle', e => { const key=e.target.dataset.treeKey;if(key) e.target.open?expanded.add(key):expanded.delete(key); },true);
        content.addEventListener('toggle', async event => {
            const details=event.target, provider=details.dataset.providerParameters;
            if (!provider || !details.open || details.dataset.loaded) return;
            details.dataset.loaded='true';
            const preview=details.querySelector('[data-parameter-preview]');
            async function load(model) {
                preview.textContent=t('正在读取模型参数…','Loading model parameters…');
                try {
                    const d=await request('/v1/platform/capability-providers/'+encodeURIComponent(provider)+'/parameters'+(model?'?model='+encodeURIComponent(model):''));
                    preview.replaceChildren();
                    const select=document.createElement('select'); select.setAttribute('aria-label',t('预览模型参数','Preview model parameters'));
                    for(const m of d.models||[]){const o=document.createElement('option');o.value=m.id;o.textContent=m.label+(m.ready?'':t(' · 待安装',' · Needs installation'));select.append(o);}
                    if(select.options.length){select.value=d.model;select.onchange=()=>load(select.value);preview.append(select);}
                    const text=document.createElement('pre');text.style.whiteSpace='pre-wrap';text.style.overflowWrap='anywhere';
                    text.textContent=JSON.stringify({model:d.model,input_schema:d.effective_schema,constraints:d.constraints,warnings:d.warnings},null,2);preview.append(text);
                }catch(error){preview.textContent=error.message;details.dataset.loaded='';}
            }
            await load();
        },true);
        content.addEventListener('click',async event=>{
            const toggle=event.target.closest('[data-provider-toggle]');
            if(!toggle)return;
            event.preventDefault();event.stopPropagation();toggle.disabled=true;
            try {
                await request('/v1/platform/capability-providers/'+encodeURIComponent(toggle.dataset.providerToggle)+'/enabled',
                    {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:toggle.dataset.enabled!=='true'})});
                await refresh();
            }catch(error){status.textContent=t('修改失败：','Update failed: ')+error.message;toggle.disabled=false;}
        });
        input.addEventListener('input',draw);
        async function refresh() {
            button.disabled=true;status.textContent=t('正在读取…','Loading…');
            try {data=await request('/v1/platform/capability-catalog');if(!section.isConnected)return;draw();status.textContent=t('Tool 总数：','Tools: ')+data.tools.length+' · '+t('路由提供者：','Routing providers: ')+data.providers.length+' · '+new Date().toLocaleTimeString();}
            catch(e){status.textContent=t('读取失败：','Failed: ')+e.message;}
            finally{button.disabled=false;}
        }
        button.addEventListener('click',refresh);refresh();
    }
    async function mountSettings(host) {
        if (host.dataset.mounted) return;
        host.dataset.mounted='true';
        const request=async (url,options={})=>{
            const response=await fetch(url,{...options,credentials:'same-origin',headers:{Accept:'application/json',...options.headers}});
            if(!response.ok) throw new Error('HTTP '+response.status);
            return response.json();
        };
        try {
            const catalog=await request('/admin/api/shell/apps');
            appCatalog=(catalog.items || []).map(app=>({...app, id:app.app_key || app.id || app.app_id, name:app.display_name || app.name,
                icon:app.icon || app.navigation?.icon || app.manifest?.navigation?.icon}));
        } catch (_) { /* Generic App icon remains available if catalog is restricted. */ }
        mount(host,request);
    }
    window.AI2AppsCapabilityTree = {label,mount,mountSettings,build,render,providerIcon};
})();
