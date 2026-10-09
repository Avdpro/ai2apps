function aiBrowserApp() {
    return {
        profiles: [], loading: true, busyKey: '', notice: '', noticeTone: 'success', noticeTimer: null,
        showCreate: false, creating: false, newName: '', deleteTarget: null,
        tr(key, values = {}) {
            const text = window.t(key);
            return text.replace(/\{(\w+)\}/g, (match, name) =>
                Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match);
        },
        domainSettings:{}, domains: [], drafts: [], tasks: [], settings: {global_limit:4,profile_limit:1},
        navTab:'domains', view:'domain', selectedDomain:'', selectedProfile:null, selectedCapability:null,
        selectedAgentId:'', selectedTask:null, taskRun:null, taskStream:null, taskTab:'active', taskResult:'', runProfile:'default',
        showDomain:false,newDomain:'',refreshing:false,syncing:false,frameVisible:false,
        metadataTimer:null, worker:crypto.randomUUID(), frames:new Map(), sessions:new Map(), profileStates:{}, profileBindings:{}, statusConnection:null, editorSessions:new Map(),
        deletingDrafts:[], schedulerStatus:'', dispatching:false, eventStream:null, eventCursor:0, streamState:'connecting', timer:null, parameterValues:{},
        terminal(status) { return ['completed','failed','cancelled'].includes(status); },
        get activeTasks() { return this.tasks.filter(t=>!this.terminal(t.status)); },
        get recentTasks() { return this.tasks.filter(t=>this.terminal(t.status)).slice(0,40); },
        statusLabel(status, task={}) { if(task.status_label)return this.localTaskText(task.status_label); return ({queued:this.tr('ai_browser.workspace.queued'),starting:this.tr('ai_browser.workspace.starting'),running:this.tr('ai_browser.workspace.running'),waiting_input:this.tr('ai_browser.workspace.waiting_input'),interrupted:this.tr('ai_browser.workspace.interrupted'),completed:this.tr('ai_browser.workspace.completed'),failed:this.tr('ai_browser.workspace.failed'),cancelled:this.tr('ai_browser.workspace.cancelled')})[status]||status; },
        localTaskText(text) {
            const labels = { '等待协助':'waiting_help', '等待确认':'waiting_confirmation',
                '等待浏览器响应':'waiting_browser', '等待响应':'waiting_input',
                '浏览器操作正在执行，无需人工介入。':'browser_busy' };
            return labels[text] ? this.tr('ai_browser.workspace.' + labels[text]) : text;
        },
        profileName(key) { return this.profiles.find(p=>p.key===key)?.name||key; },
        profileTaskCount(key) { return this.activeTasks.filter(t=>t.profile_key===key&&t.status!=='queued').length; },
        profileState(key) { return this.profileStates[key]||{label:this.tr('ai_browser.workspace.unconnected'),tabs:null}; },
        async request(path, method='GET', data) {
            const response=await fetch('/v1/platform'+path,{method,credentials:'same-origin',...(data!==undefined?{headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{})});
            const body=await response.json();
            if(!response.ok){const error=Error(typeof body.detail==='string'?body.detail:body.error?.message||this.tr('ai_browser.request_failed',{status:response.status}));error.status=response.status;throw error;}
            return body;
        },
        async init() {
            await this.loadProfiles();
            await this.refresh();
            void this.connectProfileStatus();
            this.connectWorkspaceEvents();
            this.onWorkspaceFocus=()=>{void this.refresh();};
            window.addEventListener('focus',this.onWorkspaceFocus);
            window.addEventListener('pagehide',()=>this.destroy(),{once:true});
        },
        destroy() { this.clearNotice();this.taskStream?.close();clearTimeout(this.metadataTimer);this.eventStream?.close();this.eventStream=null;window.removeEventListener?.('focus',this.onWorkspaceFocus);clearInterval(this.timer);void this.statusConnection?.close(); for(const session of this.sessions.values()) void session.connection.close(); },
        async refresh({manual=false}={}) {
            // Background polling must not animate or dim the manual refresh button.
            if(this.syncing){if(manual)this.refreshing=true;return;}
            this.syncing=true;this.refreshing=manual;
            try {
                const [workspace,drafts,catalog,recipes]=await Promise.all([
                    this.request('/browser-workspace'),this.request('/agent-drafts'),this.request('/agent-capabilities'),this.request('/agent-recipes'),
                ]);
                this.domainSettings=workspace.domain_settings||{};this.tasks=workspace.tasks;if(this.view!=='settings')this.settings=workspace.settings;this.drafts=[...(drafts.items||[]),...(recipes.items||[]).filter(recipe=>!recipe.committed_draft_id).map(recipe=>({...recipe,recipe_only:true}))];
                const expanded=new Map(this.domains.map(d=>[d.name,d.expanded]));
                const groups=new Map(workspace.domains.map(name=>[name,[]]));
                const domainFor=draft=>draft.site_key||(draft.site_scope||[]).map(scope=>{try{return new URL(scope.replace(/\*/g,'')).hostname;}catch(_){return '';}}).find(Boolean);
                for(const draft of this.drafts){const name=domainFor(draft);if(name&&!groups.has(name))groups.set(name,[]);}
                for(const cap of catalog.items||[]){
                    if(cap.agent_id?.startsWith('builtin:'))continue;
                    const draft=this.drafts.find(d=>d.id===cap.agent_id);const name=draft&&domainFor(draft);
                    if(name&&groups.has(name))groups.get(name).push({...cap,title:cap.title||draft.source?.capabilities?.find(c=>c.name===cap.name)?.title||draft.name});
                }
                // Catalog contains enabled exports only; saved drafts must remain discoverable.
                const exportedAgents=new Set((catalog.items||[]).map(cap=>cap.agent_id));
                for(const draft of this.drafts){
                    const name=domainFor(draft);
                    if(!name||!groups.has(name)||exportedAgents.has(draft.id))continue;
                    groups.get(name).push({agent_id:draft.id,title:draft.name,draft_only:true,
                        availability:draft.recipe_only?this.tr('ai_browser.workspace.recipe_pending'):draft.status==='compiled'?this.tr('ai_browser.workspace.compiled_pending'):this.tr('ai_browser.workspace.pending_compile')});
                }
                this.domains=[...groups].sort((a,b)=>a[0].localeCompare(b[0])).map(([name,capabilities])=>({name,icon:workspace.domain_icons?.[name]||'',capabilities,expanded:expanded.get(name)??true}));
                if(!this.selectedDomain&&this.domains.length)this.selectedDomain=this.domains[0].name;
                if(this.selectedTask)this.selectedTask=this.tasks.find(t=>t.id===this.selectedTask.id)||this.selectedTask;
                this.schedulerStatus=this.tr('ai_browser.workspace.scheduler_summary',{count:this.activeTasks.length,limit:this.settings.global_limit});
                this.settleTaskFrames();
                await this.refreshProfileStates();
                this.updateFrames();
                void this.dispatch();
            } catch(error){this.schedulerStatus=this.tr('ai_browser.workspace.connection_error');this.fail(error,this.tr('ai_browser.workspace.load_workspace_failed'));}
            finally{this.refreshing=false;this.syncing=false;}
        },
        settleTaskFrames(){
            for(const task of this.tasks)if(this.terminal(task.status)&&this.frames.has(task.id)){this.frames.get(task.id).frame.remove();this.frames.delete(task.id);const session=this.sessions.get(task.id);if(session){void session.connection.close();this.sessions.delete(task.id);}if(this.selectedTask?.id===task.id)void this.observeTask(task);}
        },
        applyTaskProjection(tasks){
            const active=tasks.filter(task=>!this.terminal(task.status));
            const recent=tasks.filter(task=>this.terminal(task.status)).sort((a,b)=>b.created_at-a.created_at).slice(0,200);
            this.tasks=[...active,...recent].sort((a,b)=>b.created_at-a.created_at);
            if(this.selectedTask)this.selectedTask=tasks.find(task=>task.id===this.selectedTask.id)||this.selectedTask;
            this.schedulerStatus=this.tr('ai_browser.workspace.scheduler_summary',{count:this.activeTasks.length,limit:this.settings.global_limit});
            this.settleTaskFrames();this.updateFrames();
            if(this.selectedTask?.run_id&&this.view==='task'&&!this.taskStream&&!this.taskRun)void this.observeTask(this.selectedTask);
        },
        connectWorkspaceEvents(){
            this.eventStream?.close();
            const stream=new EventSource('/v1/platform/browser-workspace/events',{withCredentials:true});
            this.eventStream=stream;this.streamState='connecting';
            stream.onopen=()=>{if(this.eventStream!==stream)return;this.streamState='connected';this.schedulerStatus=this.tr('ai_browser.workspace.scheduler_summary',{count:this.activeTasks.length,limit:this.settings.global_limit});};
            stream.onerror=()=>{if(this.eventStream!==stream)return;this.streamState='reconnecting';this.schedulerStatus=this.tr('ai_browser.workspace.reconnecting');};
            const receive=(event,snapshot)=>{
                if(this.eventStream!==stream)return;
                try{
                    const cursor=Number(event.lastEventId);
                    if(!snapshot&&cursor<=this.eventCursor)return;
                    const value=JSON.parse(event.data);this.eventCursor=cursor;
                    if(snapshot){if(this.view!=='settings')this.settings=value.settings;this.applyTaskProjection(value.tasks);}
                    else if(value.payload?.task){
                        const task=value.payload.task;
                        this.applyTaskProjection([task,...this.tasks.filter(item=>item.id!==task.id)].sort((a,b)=>b.created_at-a.created_at));
                    }else if(value.payload?.settings_changed){void this.refresh();}
                }catch(error){this.fail(error,this.tr('ai_browser.workspace.read_events_failed'));}
            };
            stream.addEventListener('browser.workspace.snapshot',event=>receive(event,true));
            stream.addEventListener('browser.workspace.changed',event=>receive(event,false));
        },
        async addDomain(){try{await this.request('/browser-workspace/domains','POST',{domain:this.newDomain});this.showDomain=false;this.newDomain='';await this.refresh();}catch(error){this.fail(error,this.tr('ai_browser.workspace.add_site_failed'));}},
        canDeleteDomain(){return Boolean(this.selectedDomain)&&!this.domainDrafts().length&&!(this.domains.find(d=>d.name===this.selectedDomain)?.capabilities.length);},
        domainMode(){return this.domainSettings[this.selectedDomain]?.interaction_mode || 'natural';},
        async saveDomainMode(mode){
            const domain=this.selectedDomain;
            try{const saved=await this.request('/browser-workspace/domains/'+encodeURIComponent(domain)+'/settings','PUT',{interaction_mode:mode});
                this.domainSettings[domain]=saved;this.succeed(this.tr('ai_browser.workspace.mode_saved'));
            }catch(error){this.showNotice(error.message,'error');}
        },
        async deleteDomain(){
            const domain=this.selectedDomain;
            if(!this.canDeleteDomain()||!window.confirm(this.tr('ai_browser.workspace.delete_site_confirm',{domain})))return;
            try{await this.request('/browser-workspace/domains/'+encodeURIComponent(domain),'DELETE');this.selectedDomain='';await this.refresh();}
            catch(error){this.fail(error,this.tr('ai_browser.workspace.delete_site_failed'));}
        },
        savedAgentStatus(draft){
            if(draft.recipe_only)return this.tr('ai_browser.workspace.recipe_pending');
            return ({editing:this.tr('ai_browser.workspace.editing_draft'),compiled:this.tr('ai_browser.workspace.compiled_pending'),active:this.tr('ai_browser.workspace.runnable'),archived:this.tr('ai_browser.workspace.deleted_status')})[draft.status]||draft.status;
        },
        savedAgentDeleteLabel(draft){return draft.recipe_only||draft.status==='editing'?this.tr('ai_browser.workspace.delete_draft'):this.tr('ai_browser.workspace.delete_agent');},
        domainDrafts(){return this.drafts.filter(d=>d.site_key===this.selectedDomain||(d.site_scope||[]).some(s=>s.includes('://'+this.selectedDomain+'/')));},
        async deleteSavedDraft(draft){
            if(this.deletingDrafts.includes(draft.id))return;
            this.deletingDrafts.push(draft.id);
            try{
                // Alpine card callbacks may retain an older object after background refresh.
                // Read the current revision before showing the deletion confirmation.
                const latest=draft.recipe_only
                    ?(await this.request('/agent-recipes')).items.find(item=>item.id===draft.id)
                    :await this.request('/agent-drafts/'+encodeURIComponent(draft.id));
                if(!latest){await this.refresh();return;}
                if(!draft.recipe_only&&!['editing','compiled','active'].includes(latest.status))
                    throw Error(this.tr('ai_browser.workspace.draft_changed'));
                const kind=draft.recipe_only||latest.status==='editing'?this.tr('ai_browser.workspace.draft'):'Agent';
                if(!window.confirm(this.tr('ai_browser.workspace.delete_item_confirm',{kind,name:latest.name})))return;
                await this.request((draft.recipe_only?'/agent-recipes/':'/agent-drafts/')+encodeURIComponent(draft.id)+'/archive','POST',{expected_revision:latest.revision});
                const key='editor:'+draft.id;const item=this.frames.get(key);
                if(item){item.frame.remove();this.frames.delete(key);}
                if(this.editorKey===key){this.editorKey='';this.view='domain';}
                if(this.selectedAgentId===draft.id){this.selectedAgentId='';this.view='domain';}
                await this.refresh();
            }catch(error){
                if(error.status===409){await this.refresh();this.fail(Error(this.tr('ai_browser.workspace.delete_conflict')),this.tr('ai_browser.workspace.delete_draft_failed'));}
                else this.fail(error,this.tr('ai_browser.workspace.delete_draft_failed'));
            }finally{this.deletingDrafts=this.deletingDrafts.filter(id=>id!==draft.id);}
        },
        get selectedAgent(){return this.drafts.find(d=>d.id===this.selectedAgentId)||null;},
        get agentCapabilities(){
            const agent=this.selectedAgent;if(!agent)return [];
            const exports=(this.domains.find(d=>d.name===this.selectedDomain)?.capabilities||[]).filter(c=>c.agent_id===agent.id&&!c.draft_only);
            const authored=agent.source?.capabilities;
            if(Array.isArray(authored))return authored.map(cap=>({...cap,title:cap.title||cap.name,
                runnable:exports.find(item=>item.name===cap.name)||null}));
            if(exports.length)return exports.map(cap=>({...cap,runnable:cap}));
            return [{id:'legacy',title:agent.source?.provenance?.capability_metadata?.title||agent.name,
                description:agent.source?.provenance?.capability_metadata?.description||agent.description,runnable:null}];
        },
        openAgent(draft){this.selectedAgentId=draft.id;this.view='agent';this.updateFrames();},
        backToAgent(){
            const agentId=this.selectedCapability?.agent_id;
            if(!agentId)return;
            this.selectedAgentId=agentId;this.view='agent';this.updateFrames();
        },
        openAgentForCapability(cap,domain){this.selectedDomain=domain;this.openAgent({id:cap.agent_id});},
        async activateAgent(){
            const agent=this.selectedAgent;if(!agent||agent.recipe_only||this.busyKey)return;
            this.busyKey='activate';
            try{
                const generation=await this.request('/agent-drafts/'+encodeURIComponent(agent.id)+'/compile','POST',{});
                if(!['validated','active'].includes(generation.status))throw Error(this.tr('ai_browser.workspace.compile_rejected'));
                await this.request('/agent-drafts/'+encodeURIComponent(agent.id)+'/generations/'+encodeURIComponent(generation.id)+'/activate','POST',{});
                await this.refresh();this.succeed(this.tr('ai_browser.workspace.agent_enabled'));
            }catch(error){this.fail(error,this.tr('ai_browser.workspace.activate_failed'));}
            finally{this.busyKey='';}
        },
        selectProfile(profile){this.selectedProfile=profile;this.view='profile';this.updateFrames();},
        selectCapability(cap,domain){if(cap.draft_only){this.editAgent(cap.agent_id,domain);return;}this.selectedCapability=cap;this.selectedDomain=domain;this.view='capability';this.updateFrames();this.$nextTick(()=>this.renderParameters(cap.input_schema||{properties:{}}));},
        renderParameters(schema){
            const root=document.getElementById('aib-inputs');if(!root)return;root.replaceChildren();this.parameterValues={};
            for(const key of [...new Set([...(schema['x-ai2apps-order']||[]),...Object.keys(schema.properties||{})])].filter(key=>Object.hasOwn(schema.properties||{},key))){
                const prop=schema.properties[key];
                const label=document.createElement('label');const title=document.createElement('span');title.textContent=(prop.title||key)+(schema.required?.includes(key)?' *':'');label.append(title);
                const desc=document.createElement('small');desc.textContent=prop.description||key;label.append(desc);
                this.parameterValues[key]=prop.default??(prop.type==='array'?[]:prop.type==='object'?{}:prop.type==='boolean'?false:'');
                if(prop['x-ai2apps-file']||prop.items?.['x-ai2apps-file']){
                    const multiple=prop.type==='array';const list=document.createElement('div');list.className='aib-files';
                    const render=()=>{list.replaceChildren();const items=multiple?this.parameterValues[key]:(this.parameterValues[key]?.asset_id?[this.parameterValues[key]]:[]);
                        items.forEach((file,index)=>{const card=document.createElement('div');card.className='aib-file';if(file.media_type?.startsWith('image/')){const image=document.createElement('img');image.src='/v1/platform/gallery/assets/'+encodeURIComponent(file.asset_id)+'/content';image.alt=file.name||'';card.append(image);}const name=document.createElement('span');name.textContent=file.name||file.asset_id||file.url;card.append(name);const remove=document.createElement('button');remove.type='button';remove.textContent=this.tr('ai_browser.workspace.remove');remove.onclick=()=>{if(multiple)this.parameterValues[key].splice(index,1);else this.parameterValues[key]=null;render();};card.append(remove);list.append(card);});};render();
                    const add=files=>{this.parameterValues[key]=multiple?[...this.parameterValues[key],...files]:files[0]||null;render();};
                    const upload=document.createElement('input');upload.type='file';upload.multiple=multiple;upload.onchange=async()=>{upload.disabled=true;try{const files=[];for(const file of upload.files){const body=new FormData();body.append('file',file);body.append('sourceAppId','ai2apps.ai-browser');const response=await fetch('/v1/platform/gallery/assets/import',{method:'POST',body,credentials:'same-origin'});const result=await response.json();if(!response.ok)throw Error(result.error?.message||result.detail||this.tr('ai_browser.workspace.upload_failed'));files.push(this.fileReference(result.asset));}add(files);}catch(error){this.fail(error,this.tr('ai_browser.workspace.add_attachment_failed'));}finally{upload.value='';upload.disabled=false;}};
                    label.append(list,upload);
                    if(window.AI2AppsGalleryPicker){const pick=document.createElement('button');pick.type='button';pick.textContent=this.tr('ai_browser.workspace.choose_gallery');pick.onclick=async()=>{try{const assets=await window.AI2AppsGalleryPicker.open({multiple,maxSelection:8});if(assets.length)add(assets.map(a=>this.fileReference(a)));}catch(error){this.fail(error,this.tr('ai_browser.workspace.choose_attachment_failed'));}};label.append(pick);}
                }else{
                    const input=document.createElement(prop.enum||prop.type==='boolean'?'select':['object','array'].includes(prop.type)?'textarea':'input');
                    if(input.tagName==='SELECT'){for(const value of prop.enum||[true,false])input.add(new Option(String(value),String(value)));}
                    else if(['integer','number'].includes(prop.type)){input.type='number';input.step=prop.type==='integer'?'1':'any';}
                    input.value=['object','array'].includes(prop.type)?JSON.stringify(this.parameterValues[key],null,2):String(this.parameterValues[key]);
                    input.required=!!schema.required?.includes(key);input.oninput=()=>{try{this.parameterValues[key]=prop.type==='boolean'?input.value==='true':['number','integer'].includes(prop.type)?Number(input.value):['object','array'].includes(prop.type)?JSON.parse(input.value):input.value;input.setCustomValidity('');}catch(_){input.setCustomValidity(this.tr('ai_browser.workspace.invalid_json'));}};label.append(input);
                }
                root.append(label);
            }
        },
        fileReference(asset){return {asset_id:asset.id,url:'/v1/platform/gallery/assets/'+encodeURIComponent(asset.id)+'/content',name:asset.name,media_type:asset.media_type,size_bytes:asset.size_bytes};},
        async enqueue(){this.busyKey='enqueue';try{const cap=this.selectedCapability;const task=await this.request('/browser-workspace/tasks','POST',{profile_key:this.runProfile,agent_id:cap.agent_id,capability:cap.name,name:cap.title||cap.name,input:this.parameterValues});this.tasks.unshift(task);this.openTask(task);this.succeed(this.tr('ai_browser.workspace.enqueued'));void this.dispatch();}catch(error){this.fail(error,this.tr('ai_browser.workspace.start_task_failed'));}finally{this.busyKey='';}},
        async browserSession(profileKey){
            const marker=location.origin+'/admin/static/favicon.svg#browser-workspace-'+crypto.randomUUID();
            const launch=await this.request('/client/browser-profiles/'+encodeURIComponent(profileKey)+'/launch','POST',{initial_url:marker});
            const connection=new window.AI2AppsBiDi.AI2AppsBiDiConnection();
            try{await connection.connect();let matches=[];for(let attempt=0;attempt<20;attempt++){const tree=await connection.command('browsingContext.getTree',{maxDepth:0});matches=(tree.contexts||[]).filter(c=>c.url===marker);if(matches.length)break;if(launch.user_context){const reference=(tree.contexts||[]).find(c=>c.userContext===launch.user_context);const created=await connection.command('browsingContext.create',{type:'tab',userContext:launch.user_context,...(reference?{referenceContext:reference.context}:{}),background:true});await connection.command('browsingContext.navigate',{context:created.context,url:marker,wait:'interactive'});matches=[{context:created.context,userContext:launch.user_context}];break;}await new Promise(r=>setTimeout(r,250));}if(matches.length!==1)throw Error(this.tr('ai_browser.workspace.page_not_found'));
                const session={connection,context:matches[0].context,userContext:matches[0].userContext,profileKey,url:marker};return session;
            }catch(error){await connection.close();throw error;}
        },
        async dispatch(){ /* Task admission and execution are owned by Local. */ },
        mountFrame(key,query,context){
            if(this.frames.has(key))return;
            const frame=document.createElement('iframe');frame.title=query.workspace_task?this.tr('ai_browser.workspace.webagent_task'):this.tr('ai_browser.workspace.webagent_editor');
            frame.src='/admin/agent-mini?'+new URLSearchParams(query)+'#'+new URLSearchParams(context);
            frame.className='aib-frame';frame.style.display='none';document.getElementById('aib-frames').append(frame);this.frames.set(key,{frame});this.updateFrames();
        },
        updateFrames(){let visible=false;for(const [key,item] of this.frames){const show=this.view==='editor'&&key===this.editorKey||this.view==='task'&&key===this.selectedTask?.id;item.frame.style.display=show?'block':'none';visible||=show;}this.frameVisible=visible;document.getElementById('aib-frames')?.classList.toggle('is-visible',visible);},
        async editAgent(id,domain,capability=''){
            const key='editor:'+(id||domain);this.editorKey=key;this.view='editor';
            if(this.frames.has(key)){this.updateFrames();return;}
            const profileKey=this.runProfile;
            this.mountFrame(key,{workspace_editor:'1',...(this.drafts.find(d=>d.id===id)?.recipe_only?{workspace_create:'1',recipe_id:id}:id?{draft_id:id}:{workspace_create:'1'}),...(capability?{capability_id:capability}:{})},{url:'https://'+domain+'/',title:domain,profile_key:profileKey,agent_context_lock:'1'});
            // Same-origin editor asks its host for a page only on an explicit browser action.
            this.frames.get(key).frame.ai2appsEnsureBrowserContext=(selectedProfile=profileKey)=>this.ensureEditorSession(key+':profile:'+selectedProfile,selectedProfile,domain);
            this.frames.get(key).frame.ai2appsWorkspaceChanged=()=>{clearTimeout(this.metadataTimer);this.metadataTimer=setTimeout(()=>{void this.refresh();},150);};
            this.frames.get(key).frame.ai2appsReturnToWorkspace=async()=>{
                if(this.view!=='editor'||this.editorKey!==key)return;
                await this.request('/client/shell/focus','POST',{});
            };
        },
        async ensureEditorSession(key,profileKey,domain){
            if(!this.editorSessions.has(key))this.editorSessions.set(key,(async()=>{
                if(this.sessions.has(key)){
                    const session=this.sessions.get(key);
                    const tree=await session.connection.command('browsingContext.getTree',{maxDepth:0});
                    if((tree.contexts||[]).some(context=>context.context===session.context))
                        return {bidi_context:session.context,url:session.url,profile_key:profileKey};
                    this.sessions.delete(key);
                    await session.connection.close().catch(()=>{});
                }
                const session=await this.browserSession(profileKey);
                try{session.url='https://'+domain+'/';await session.connection.command('browsingContext.navigate',{context:session.context,url:session.url,wait:'interactive'});this.sessions.set(key,session);
                    return {bidi_context:session.context,url:session.url,profile_key:profileKey};
                }catch(error){await session.connection.close();throw error;}
            })().finally(()=>this.editorSessions.delete(key)));
            return this.editorSessions.get(key);
        },
        openTask(task){this.selectedTask=task;this.taskResult='';this.taskRun=null;this.view='task';this.updateFrames();void this.observeTask(task);},
        async observeTask(task){
            this.taskStream?.close();this.taskStream=null;
            if(!task.run_id)return;
            const stream=new EventSource('/v1/platform/agent-runs/'+encodeURIComponent(task.run_id)+'/events');this.taskStream=stream;
            let busy=false,changed=false;
            const refresh=async()=>{if(this.taskStream!==stream)return;if(busy){changed=true;return;}busy=true;
                try{const run=await this.request('/agent-draft-runs/'+encodeURIComponent(task.run_id));if(this.taskStream!==stream)return;this.taskRun=run;
                    this.taskResult=run.output?JSON.stringify(run.output.result||run.output,null,2):run.error?.message||'';
                    if(this.terminal(run.status)){stream.close();this.taskStream=null;}
                }catch(error){this.fail(error,this.tr('ai_browser.workspace.read_task_failed'));}finally{busy=false;if(changed){changed=false;void refresh();}}};
            for(const type of ['agent.status','agent.run.running','agent.run.waiting_input','agent.run.completed','agent.run.failed','agent.run.cancelled','agent.run.paused','agent.input.request','agent.approval.request','agent.interaction.submitted'])stream.addEventListener(type,refresh);
            stream.onopen=refresh;void refresh();
        },
        get humanInteractions(){return (this.taskRun?.interactions||[]).filter(item=>item.status==='pending'&&['browser_user_assistance','agent_confirmation'].includes(item.request?.control));},
        async respondTask(interaction,approve=true){try{await this.request('/agent-draft-runs/'+encodeURIComponent(this.selectedTask.run_id)+'/interactions/'+encodeURIComponent(interaction.id)+'/respond','POST',{response:interaction.request.control==='agent_confirmation'?{decision:approve?'approve':'deny'}:{continued:true},response_id:crypto.randomUUID()});}catch(error){this.fail(error,this.tr('ai_browser.workspace.continue_failed'));}},
        async showTaskPage(task){let connection;try{connection=new window.AI2AppsBiDi.AI2AppsBiDiConnection();await connection.connect();const context=task.browser_context?.bidi_context;if(!context)throw Error(this.tr('ai_browser.workspace.page_not_created'));await connection.command('browsingContext.activate',{context});}catch(error){this.fail(error,this.tr('ai_browser.workspace.open_task_failed'));}finally{await connection?.close();}},
        async resumeTask(task){try{const resumed=await this.request('/browser-workspace/tasks/'+task.id+'/resume','POST',{worker:'local-background'});this.selectedTask=resumed;void this.observeTask(resumed);}catch(error){this.fail(error,this.tr('ai_browser.workspace.resume_failed'));}},
        async cancelTask(task){try{await this.request('/browser-workspace/tasks/'+task.id+'/cancel','POST');const item=this.frames.get(task.id);if(item){item.frame.remove();this.frames.delete(task.id);}await this.refresh();}catch(error){this.fail(error,this.tr('ai_browser.workspace.cancel_failed'));}},
        async connectProfileStatus(){
            try{
                await this.statusConnection?.close();this.statusConnection=null;const connection=new window.AI2AppsBiDi.AI2AppsBiDiConnection();await connection.connect();this.statusConnection=connection;
                for(const profile of this.profiles){const binding=await this.request('/client/browser-profiles/'+profile.key+'/binding','POST',{});if(binding.user_context)this.profileBindings[profile.key]=binding.user_context;}
                await this.refreshProfileStates();
            }catch(error){this.fail(error,this.tr('ai_browser.workspace.profile_status_failed'));}
        },
        async refreshProfileStates(){
            if(this.statusConnection){try{const tree=await this.statusConnection.command('browsingContext.getTree',{maxDepth:0});for(const [key,userContext] of Object.entries(this.profileBindings)){const tabs=(tree.contexts||[]).filter(c=>c.userContext===userContext);this.profileStates[key]={label:tabs.length?this.tr('ai_browser.workspace.opened'):this.tr('ai_browser.workspace.closed'),tabs:tabs.length};}}catch(_){this.statusConnection=null;}}
            for(const session of this.sessions.values()){try{const tree=await session.connection.command('browsingContext.getTree',{maxDepth:0});const contexts=tree.contexts||[];
                if(session.userContext){const tabs=contexts.filter(c=>c.userContext===session.userContext);this.profileStates[session.profileKey]={label:tabs.length?this.tr('ai_browser.workspace.opened'):this.tr('ai_browser.workspace.closed'),tabs:tabs.length};}
                else{this.profileStates[session.profileKey]={label:contexts.some(c=>c.context===session.context)?this.tr('ai_browser.workspace.opened'):this.tr('ai_browser.workspace.unknown_state'),tabs:null};}
            }catch(_){this.profileStates[session.profileKey]={label:this.tr('ai_browser.workspace.connection_lost'),tabs:null};}}
        },
        async saveSettings(){try{this.settings=await this.request('/browser-workspace/settings','PUT',this.settings);this.succeed(this.tr('ai_browser.workspace.settings_saved'));void this.dispatch();}catch(error){this.fail(error,this.tr('ai_browser.workspace.save_failed'));}},
        async renameProfile(profile){const name=window.prompt(this.tr('ai_browser.workspace.profile_name'),profile.name);if(!name)return;try{const updated=await this.request('/client/browser-profiles/'+profile.key,'PATCH',{name});Object.assign(profile,updated);}catch(error){this.fail(error,this.tr('ai_browser.workspace.rename_failed'));}},

        async loadProfiles() {
            this.loading = true;
            try {
                const response = await fetch('/v1/platform/client/browser-profiles');
                if (!response.ok) throw new Error(await this.readError(response));
                this.profiles = (await response.json()).map(profile => ({...profile, lastStatus: ''}));
                this.refreshIcons();
            } catch (error) { this.fail(error, this.tr('ai_browser.load_failed')); }
            finally { this.loading = false; }
        },
        async createProfile() {
            const name = this.newName.replace(/\s+/g, ' ').trim();
            if (!name || Array.from(name).length > 80) {
                this.fail(null, this.tr('ai_browser.invalid_name'));
                return;
            }
            this.creating = true; this.clearNotice();
            try {
                const response = await fetch('/v1/platform/client/browser-profiles', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name})});
                if (!response.ok) throw new Error(await this.readError(response));
                this.profiles.push({...await response.json(), lastStatus: ''});
                this.newName = ''; this.showCreate = false; void this.connectProfileStatus(); this.succeed(this.tr('ai_browser.created')); this.refreshIcons();
            } catch (error) { this.fail(error, this.tr('ai_browser.create_failed')); }
            finally { this.creating = false; }
        },
        async launch(profile) {
            this.busyKey=profile.key;
            try { const result=await this.request('/client/browser-profiles/'+encodeURIComponent(profile.key)+'/launch','POST',{});if(result.user_context)this.profileBindings[profile.key]=result.user_context;await this.refreshProfileStates();this.succeed(this.tr('ai_browser.workspace.browser_opened')); }
            catch(error){this.fail(error,this.tr('ai_browser.workspace.open_browser_failed'));}
            finally{this.busyKey='';}
        },
        requestDelete(profile) { if(this.activeTasks.some(t=>t.profile_key===profile.key)){this.fail(null,this.tr('ai_browser.workspace.finish_profile_tasks'));return;} if (!profile.is_default) this.deleteTarget = profile; },
        async deleteProfile() {
            const profile = this.deleteTarget; if (!profile || profile.is_default) return;
            this.busyKey = profile.key; this.clearNotice();
            try {
                const response = await fetch(`/v1/platform/client/browser-profiles/${encodeURIComponent(profile.key)}`, {method: 'DELETE'});
                if (!response.ok) throw new Error(await this.readError(response));
                this.profiles = this.profiles.filter(item => item.key !== profile.key);
                this.deleteTarget = null; this.succeed(this.tr('ai_browser.deleted')); this.refreshIcons();
            } catch (error) { this.fail(error, this.tr('ai_browser.delete_failed')); }
            finally { this.busyKey = ''; }
        },
        clearNotice() { clearTimeout(this.noticeTimer); this.noticeTimer = null; this.notice = ''; },
        showNotice(message, tone = 'success') {
            this.clearNotice();
            this.noticeTone = tone; this.notice = message;
            if (message) this.noticeTimer = setTimeout(() => this.clearNotice(), tone === 'error' ? 8000 : 5000);
        },
        succeed(message) { this.showNotice(message); },
        fail(error, fallback) {
            // Native fetch errors vary by browser and ignore the app's locale.
            const detail = error?.name === 'TypeError' ? this.tr('ai_browser.network_error') : error?.message;
            this.showNotice(detail ? `${fallback}: ${detail}` : fallback, 'error');
            this.refreshIcons();
        },
        refreshIcons() { this.$nextTick(() => window.lucide?.createIcons()); },
        async readError(response) {
            let detail = '';
            try {
                const body = await response.json();
                detail = typeof body.detail === 'string' ? body.detail : '';
            } catch (_) { /* Non-JSON failures still get a localized HTTP message. */ }
            const knownErrors = {
                'Profile name must contain 1 to 80 characters': 'invalid_name',
                'Browser Profile not found': 'not_found',
                'Browser Profile ID is invalid': 'not_found',
                'The default browser Profile cannot be deleted': 'default_protected',
                'AppShell did not acknowledge the browser request': 'timeout',
                'Shell browser request expired': 'timeout',
            };
            // Python KeyError includes quotes around its message.
            const known = knownErrors[detail.replace(/^['"]|['"]$/g, '')];
            const statusKey = {
                401: 'unauthorized', 403: 'unauthorized', 404: 'not_found',
                409: 'invalid_request', 422: 'invalid_name',
                502: 'unavailable', 503: 'unavailable', 504: 'timeout',
            }[response.status];
            const reason = known || statusKey;
            const summary = this.tr('ai_browser.request_failed', {status: response.status});
            return reason ? `${this.tr(`ai_browser.${reason}`)} ${summary}` : summary;
        },
    };
}
