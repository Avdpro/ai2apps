(function () {
    'use strict';
    const API = '/v1/platform/cloud';
    const tr = (key) => typeof window.t === 'function' ? window.t(key) : key;
    async function request(path, options) {
        const response = await fetch(API + path, { credentials: 'same-origin', headers: { Accept: 'application/json', ...((options?.body) ? { 'Content-Type': 'application/json' } : {}) }, ...(options || {}), body: options?.body ? JSON.stringify(options.body) : undefined });
        const payload = response.status === 204 ? null : await response.json().catch(() => null);
        if (!response.ok) { const error = new Error(payload?.error?.message || payload?.detail?.message || tr('messager.error.request_failed')); error.status = response.status; error.code = payload?.error?.code || payload?.detail?.code; throw error; }
        return payload;
    }
    async function localRequest(path, options) {
        const response = await fetch('/v1/platform/messager' + path, { credentials: 'same-origin', headers: { Accept: 'application/json', ...((options?.body) ? { 'Content-Type': 'application/json' } : {}) }, ...(options || {}), body: options?.body ? JSON.stringify(options.body) : undefined });
        const payload = await response.json().catch(() => null);
        if (!response.ok) { const error = new Error(payload?.error?.message || (typeof payload?.detail==='string'?payload.detail:payload?.detail?.message) || tr('messager.error.request_failed')); error.status = response.status; error.code = payload?.error?.code; error.retryable = Boolean(payload?.error?.retryable); throw error; }
        return payload;
    }
    async function uploadRequest(file) {
        const body = new FormData();
        body.append('file', file, file.name || 'attachment');
        const response = await fetch(API + '/system-message-attachments', { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' }, body });
        const payload = await response.json().catch(() => null);
        if (!response.ok) { const error = new Error(payload?.error?.message || payload?.detail?.message || tr('messager.error.request_failed')); error.status = response.status; error.code = payload?.error?.code || payload?.detail?.code; throw error; }
        return payload;
    }
    function orderBots(bots,order){
        const rank=new Map(order.map((id,index)=>[id,index]));
        return bots.slice().sort((a,b)=>(rank.get(a.id)??Infinity)-(rank.get(b.id)??Infinity));
    }
    window.messagerApp = function () { let controller=null, generation=0, listTimer=null, taskTimer=null, chatRoot=null, configurationListener=null, appAccessListener=null,memoryChangeListener=null, accessDialogRoot=null, sidebarResize=null, rightSidebarResize=null, noticeTimer=null, noticeRevision=0,taskBrowseRevision=0,creationMenu=null,creationForm=null,botOrder=[],botListLoad=0,botPointer=null; return {
        statisticsPeriod:'today',statisticsTimezone:Intl.DateTimeFormat().resolvedOptions().timeZone,statisticsRequest:0,botStatistics:null,statisticsBusy:false,statisticsLoadedAt:0,groupDragId:null,groupDropId:null,groupDropAfter:false,botGroups:[],groupRemoval:null,groupBusy:false,botDropGroup:null,botDragClickUntil:0,botOrderSaving:false,botDragId:null,botDropId:null,botDropAfter:false,botTasksUnavailable:false,
        localNotices:[],localUnreadCount:0,localNoticesMore:false,notificationPolicy:null,notificationRevision:0,notificationBusy:false,focusedTask:null,
        memories:[],memoryText:'',memoryBusy:false,pendingMemories:null,cleanupReview:null,cleanupAction:'',cleanupBusy:false,cleanupLoading:false,cleanupTargetId:null,cleanupShortcutName:null,cleanupDeleteTasks:false,cleanupClearMemory:false,cleanupRevokeAccess:false,archivedBots:[],showArchivedBots:false,
        botTaskAccessPolicies:[],botTasks:[],botTasksMore:false,taskCandidates:[],taskCandidatesMore:false,taskChooser:false,taskSelection:'',taskBusy:false, accessDialogMode:'',accessChooserKind:'app',accessQuery:'',accessRemoval:null,botUseAccess:null,botUseBusy:false,botUseTarget:'',botUseCaller:'',botUseLoad:0,botAccess:[],botApprovalRule:null,botApprovalBusy:false,accessRevision:0,accessReviewHash:'',accessBusy:false,accessLoaded:false, bots: [], botsAvailable:false, currentBot:null, creatingBot:false, botName:'', botDuty:'', botSaving:false,
        realtimeSettings:null,realtimeCatalog:{stt:[],tts:[],profiles:[]},realtimeBusy:false,realtimeNotice:'',realtimeApplied:null,voiceAppliedSettings:null,voiceSaveState:'',voiceInstallBusy:false,voiceSettings:null,voiceModels:[],voiceProfiles:[],voiceBusy:false,voiceLoaded:false,voiceCatalogNotice:false,sidebarWidth:260,rightSidebarWidth:300,tab: 'bots',rightTab:'bot',galleryUrl:'',galleryLoading:false,galleryError:'', leftOpen:true,rightOpen:true,botEditName:'',botEditDuty:'',avatarBusy:false,avatarPreset:'spark',avatarColor:'#6366f1',botTaskSessionBrowse:[],botTaskBrowseArchived:false,botTaskBrowseMore:false,botTaskBrowseOpen:false,botTaskBrowseLoading:false,botSessionId:null,botTaskSessions:[],botTaskSessionDetail:null,botModelInstallBusy:false,botAppliedModel:'',botModels:[],botModel:'',botModelNotice:'',botReasoningEffort:'',botReasoningLevels:[],botModelSaving:false,botRuns:[], busy: false, notice: '', noticeTone: '', identifier: '', lookupProfile: null, lookupRelationship: null,
        friends: [], incomingRequests: [], outgoingRequests: [], inbox: [], unreadCount: 0, selected: null, draft: '', storedMessages: [], draftClientMessageId: '', draftSnapshot: '', draftRecipientUserId: '', draftAttachment: null, draftAttachmentToken: '', draftSnapshotAttachmentToken: '', uploadedAttachment: null, draftPreviewUrl: '', attachmentObjectUrls: [],
        tr,
        ui(zh,en){return (document.documentElement.lang||navigator.language).startsWith('zh')?zh:en;},
        async init() { await this.$nextTick();sidebarResize=window.AI2AppsMessagerSidebar.mount({handle:this.$refs.sidebarHandle,shell:this.$refs.messagerShell,rightWidth:()=>this.rightOpen?(this.$refs.messagerDetails?.getBoundingClientRect().width||0):0,onWidth:value=>this.setSidebarWidth(value)});rightSidebarResize=window.AI2AppsMessagerSidebar.mount({side:'right',handle:this.$refs.rightSidebarHandle,shell:this.$refs.messagerShell,rightWidth:()=>this.leftOpen?this.sidebarWidth:0,onWidth:value=>{this.rightSidebarWidth=value;}});configurationListener=e=>this.refreshConfiguredBot(e.detail);window.addEventListener('ai2apps:bot-configuration-applied',configurationListener);appAccessListener=e=>{if(e.detail?.botId===this.currentBot?.id)this.loadBotAccess();};window.addEventListener('ai2apps:bot-app-access-changed',appAccessListener);memoryChangeListener=e=>{if(e.detail?.botId===this.currentBot?.id)this.loadMemories();};window.addEventListener('ai2apps:bot-memory-changed',memoryChangeListener);window.addEventListener('beforeunload', () => this.revokeObjectUrls(), { once: true }); await Promise.all([this.refresh(),this.loadBots(),this.loadLocalNotices()]);await this.openNotificationRoute(); taskTimer=setInterval(()=>{if(!document.hidden){this.loadLocalNotices();if(this.tab==='bots'){this.loadBotTasks();this.loadBots();this.loadBotUseAccess();if(this.rightOpen)this.loadBotStatistics();if(this.rightOpen&&this.rightTab==='bot'&&!this.accessBusy&&!this.accessDialogMode)this.loadBotAccess();}}},5000); },
        async loadBots(preferredId) {
            if(this.botOrderSaving||this.groupBusy||this.groupDragId||this.botDragId)return;const load=++botListLoad;
            try { const value=await localRequest('/bots?language='+this.ui('zh','en'));const groups=await localRequest('/bot-groups');if(load!==botListLoad||this.botOrderSaving||this.groupBusy||this.groupDragId||this.botDragId)return;this.bots=value.items;this.botGroups=groups.items;this.botsAvailable=true;if(this.tab==='bots'&&!this.currentBot&&this.bots.length)await this.openBot(this.bots.find(b=>b.id===preferredId)||this.bots.find(b=>b.is_default)||this.bots[0]); }
            catch(error) { if(error.status!==404)this.fail(error); }
        },
        startGroupDrag(event,group){
            if(group.id==='ungrouped'||this.botOrderSaving||this.groupBusy){event.preventDefault();return;}
            this.groupDragId=group.id;event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',group.id);
        },
        trackGroupDrag(event,group){
            if(!this.groupDragId||group.id==='ungrouped')return;
            event.preventDefault();event.dataTransfer.dropEffect='move';
            this.groupDropId=group.id;const rect=event.currentTarget.getBoundingClientRect();this.groupDropAfter=event.clientY>rect.top+rect.height/2;
        },
        finishGroupDrag(){this.groupDragId=null;this.groupDropId=null;this.botDragClickUntil=Date.now()+350;},
        async dropGroup(event,group){
            if(!this.groupDragId)return;event.preventDefault();this.trackGroupDrag(event,group);
            const source=this.groupDragId,target=this.groupDropId,after=this.groupDropAfter;this.finishGroupDrag();
            if(!target||source===target)return;
            const ids=this.botGroups.map(g=>g.id).filter(id=>id!==source);ids.splice(ids.indexOf(target)+(after?1:0),0,source);
            this.groupBusy=true;try{const value=await localRequest('/bot-groups-order',{method:'PUT',body:{ids}});this.botGroups=value.items;}catch(error){this.fail(error);}finally{this.groupBusy=false;}
        },
        startBotDrag(event){
            if(this.botOrderSaving||event.button!==0||event.pointerType==='touch'||botPointer)return;
            const id=event.target.closest('[data-bot-order-id]')?.dataset.botOrderId;
            if(id)botPointer={id,pointerId:event.pointerId,x:event.clientX,y:event.clientY};
        },
        trackBotDrag(event){
            if(botPointer?.pointerId!==event.pointerId)return;
            if(!this.botDragId){
                if(Math.hypot(event.clientX-botPointer.x,event.clientY-botPointer.y)<6)return;
                event.currentTarget.setPointerCapture(event.pointerId);
                this.botDragId=botPointer.id;
            }
            const hit=document.elementFromPoint(event.clientX,event.clientY);
            const card=hit?.closest('[data-bot-order-id]');
            const group=hit?.closest('[data-bot-group-id]');
            this.botDropGroup=group&&event.currentTarget.contains(group)?group.dataset.botGroupId:null;
            const id=card?.dataset.botOrderId;
            this.botDropId=card&&event.currentTarget.contains(card)&&id!==this.botDragId?id:null;
            if(this.botDropId){const rect=card.getBoundingClientRect();this.botDropAfter=event.clientY>rect.top+rect.height/2;}
        },
        async dropBot(event){
            if(botPointer?.pointerId!==event.pointerId)return;
            if(this.botDragId)this.trackBotDrag(event);
            if(this.botDragId)this.botDragClickUntil=Date.now()+350;
            const source=this.botDragId,target=this.botDropId,after=this.botDropAfter,group=this.botDropGroup;
            this.finishBotDrag();
            if(!target&&group===null)return;
            const ids=this.bots.map(bot=>bot.id);
            if(!ids.includes(source)||(target&&!ids.includes(target)))return;
            const next=ids.filter(id=>id!==source);
            if(target)next.splice(next.indexOf(target)+(after?1:0),0,source);else next.push(source);
            const move=group!==null?{bot_id:source,group_id:group==='ungrouped'?null:group}:null;
            if(next.every((id,index)=>id===ids[index])&&(!move||this.botGroupKey(this.bots.find(b=>b.id===source))===group))return;
            botOrder=[...next,...botOrder.filter(id=>!ids.includes(id))];
            this.bots=orderBots(this.bots,botOrder);if(move)this.bots.find(b=>b.id===source).group_id=move.group_id;
            this.botOrderSaving=true;botListLoad++;
            try{const value=await localRequest('/bots-order',{method:'PUT',body:{ids:next,...(move?{move}:{})}});this.bots=value.items;}catch(error){this.fail(error);}finally{botOrder=[];this.botOrderSaving=false;await this.loadBots();}
        },
        finishBotDrag(){
            botPointer=null;
            this.botDragId=null;this.botDropId=null;this.botDropAfter=false;this.botDropGroup=null;
        },
        botGroupKey(bot){if(!bot)return 'ungrouped';return ('group_id' in bot?bot.group_id:(['flash','app_shortcut'].includes(bot.definition?.execution_mode)?'quick':null))||'ungrouped';},
        get sidebarGroups(){return [{id:'ungrouped',name:this.ui('无分组','Ungrouped'),collapsed:false,permanent:true},...this.botGroups];},
        groupBots(group){return this.bots.filter(b=>this.botGroupKey(b)===group.id);},
        groupLabel(group){return group.id==='quick'?this.ui('快捷Bot','Quick Bots'):group.name;},
        async toggleGroup(group){if(this.groupBusy)return;this.groupBusy=true;try{this.botGroups=(await localRequest('/bot-groups/'+group.id,{method:'PATCH',body:{revision:group.revision,collapsed:!group.collapsed}})).items;}catch(e){this.fail(e);}finally{this.groupBusy=false;}},
        openGroupDialog(group=null,mode=group?'delete':'create'){
            if(mode!=='delete'){
                window.AI2AppsTextInputDialog.open({
                    title:group?this.ui('重新命名分组','Rename group'):this.ui('新建分组','New group'),
                    label:this.ui('分组名称','Group name'),
                    value:group?.name,
                    maxLength:64,
                    submitLabel:group?this.ui('保存','Save'):this.ui('创建','Create'),
                    cancelLabel:this.ui('取消','Cancel'),
                    onSubmit:name=>this.saveGroup(group,name),
                });
                return;
            }
            this.groupRemoval={...group};
            this.$nextTick(()=>{
                this.$refs.botGroupDialog.showModal();
                this.$refs.botGroupDialog.querySelector('[data-group-cancel]')?.focus();
            });
        },
        async saveGroup(group,name){
            this.groupBusy=true;
            try{
                this.botGroups=(await localRequest(group?'/bot-groups/'+group.id:'/bot-groups',{
                    method:group?'PATCH':'POST',
                    body:group?{revision:group.revision,name}:{name},
                })).items;
            }finally{this.groupBusy=false;}
        },
        openGroupMenu(anchor,group){
            if(anchor.getAttribute('aria-expanded')==='true'){creationMenu?.dispose();return;}
            creationMenu?.dispose();
            const onClose=()=>{creationMenu=null;};
            creationMenu=window.AI2AppsBotCreation.groupMenu(anchor,{
                onClose,
                onCreate:()=>{creationMenu=window.AI2AppsBotCreation.menu(anchor,{
                    grouped:true, below:true, onClose,
                    onChoose:type=>this.beginBotCreation(type,group.id),
                });},
                onRename:()=>this.openGroupDialog(group,'rename'),
                onDelete:()=>this.openGroupDialog(group),
            });
        },
        openShortcutMenu(anchor,bot){
            if(anchor.getAttribute('aria-expanded')==='true'){creationMenu?.dispose();return;}
            creationMenu?.dispose();
            creationMenu=window.AI2AppsBotCreation.shortcutMenu(anchor,{
                onClose:()=>{creationMenu=null;},
                onRename:()=>this.renameShortcut(bot),
                onDelete:()=>this.reviewCleanup('archive',bot),
            });
        },
        renameShortcut(bot){
            window.AI2AppsTextInputDialog.open({
                title:this.ui('快捷 Bot 改名','Rename shortcut Bot'),
                label:this.ui('Bot 名称','Bot name'),
                value:bot.name,
                maxLength:64,
                submitLabel:this.ui('保存','Save'),
                cancelLabel:this.ui('取消','Cancel'),
                onSubmit:async name=>{
                    if(name===bot.name)return;
                    const changed=await localRequest('/bots/'+encodeURIComponent(bot.id),{
                        method:'PATCH',body:{name,duty:bot.duty},
                    });
                    // Invalidate any older polling response before updating the visible name.
                    botListLoad++;
                    const entry=this.bots.find(item=>item.id===bot.id);
                    if(entry)entry.name=changed.name;
                    if(this.currentBot?.id===bot.id){
                        this.currentBot.name=changed.name;
                        this.botEditName=changed.name;
                    }
                    await this.loadBots();
                },
            });
        },
        closeGroupDialog(){
            if(this.groupBusy)return;
            this.$refs.botGroupDialog?.close();
            this.groupRemoval=null;
        },
        async commitGroup(){
            if(this.groupBusy||!this.groupRemoval)return;
            this.groupBusy=true;
            try{
                const group=this.groupRemoval;
                this.botGroups=(await localRequest('/bot-groups/'+group.id,{
                    method:'DELETE',body:{revision:group.revision},
                })).items;
                this.groupBusy=false;
                this.closeGroupDialog();
                await this.loadBots();
            }catch(error){this.fail(error);}
            finally{this.groupBusy=false;}
        },
        get sidebarCompact(){return this.sidebarWidth<168;},
        setSidebarWidth(width){
            this.sidebarWidth=width;
            if(this.sidebarCompact&&this.tab!=='bots')this.switchTab('bots');
        },
        switchTab(tab) {
            if(tab!=='bots'&&this.sidebarCompact)return;
            if(tab===this.tab)return;
            this.finishBotDrag();
            generation++;controller?.dispose();controller=null;this.currentBot=null;
            this.tab=tab;
            clearInterval(listTimer);
            if(tab==='bots'){this.loadBots();listTimer=setInterval(()=>{if(!document.hidden)this.loadBots();},5000);}
        },
        destroy() { creationMenu?.dispose();creationForm?.dispose();this.closeAccessDialog();accessDialogRoot=null;noticeRevision++;clearTimeout(noticeTimer);sidebarResize?.dispose();rightSidebarResize?.dispose();window.removeEventListener('ai2apps:bot-configuration-applied',configurationListener);window.removeEventListener('ai2apps:bot-app-access-changed',appAccessListener);window.removeEventListener('ai2apps:bot-memory-changed',memoryChangeListener);generation++;clearInterval(taskTimer);clearInterval(listTimer);controller?.dispose({discard:true});window.AI2AppsBotConversation.invalidate?.(chatRoot); },
        expandSidebar(){sidebarResize?.expand();},
        refreshSidebarWidth(){rightSidebarResize?.refresh();sidebarResize?.refresh();},
        sidebarUnread(person){const value=Number(person?.unreadCount??person?.unread_count??person?.unreadMessageCount);return Number.isFinite(value)?Math.max(0,Math.floor(value)):(person?.hasUnread||person?.has_unread?1:0);},
        sidebarAssistance(bot){return !!bot?.needs_user_assistance||['waiting_input','waiting_capability'].includes(bot?.reply_status)||['waiting_input','waiting_capability'].includes(bot?.task_status);},
        sidebarReply(bot){return !!bot?.reply_status&&!['completed','failed','cancelled','interrupted','timed_out','waiting_input','waiting_capability'].includes(bot.reply_status);},
        sidebarTask(bot){return ['queued','running','planning'].includes(bot?.task_status);},
        sidebarTaskLabel(bot){const status=bot?.task_status;if(status==='queued')return this.ui('任务排队中','Task queued');if(status?.startsWith('waiting'))return this.ui('任务等待确认或回复','Task waiting for input');return this.ui('正在执行任务','Running task');},
        sidebarBadge(person){const count=this.sidebarUnread(person);if(person?.unreadCount==null&&person?.unread_count==null&&person?.unreadMessageCount==null)return '•';return count>99?'99+':String(count);},
        async showRightTab(tab){this.rightTab=tab==='gallery'?'gallery':'bot';if(this.rightTab==='gallery')await this.mountBotGallery();},
        async mountBotGallery(force=false){if(this.galleryLoading||(this.galleryUrl&&!force))return;this.galleryLoading=true;this.galleryError='';try{const bridge=window.ai2appsShell;let url='/admin/app-content/ai2apps.gallery?surface=mini';if(bridge?.mountMiniEntry){const mount=await bridge.mountMiniEntry({appId:'ai2apps.gallery',placement:'sidebar',requestedBy:'ai2apps.messager'});if(!mount?.content_url)throw Error(this.ui('素材库入口不可用','Gallery entry unavailable'));url=mount.content_url;}this.galleryUrl=url;}catch(e){this.galleryError=e.message;}finally{this.galleryLoading=false;}},
        botStatus(bot) {
            const state=bot.task_status||bot.last_status;
            if(!state)return '';
            if(state.startsWith('waiting'))return tr('messager.bot.waiting');
            if(state==='completed')return tr('messager.bot.done');
            if(['failed','interrupted','cancelled','timed_out'].includes(state))return tr('messager.bot.stopped');
            return tr('messager.bot.working');
        },
        scheduledBotTasks(){
            return this.botTasks.filter(task=>task.scheduled&&!task.archived_at&&task.next_due)
                .sort((a,b)=>Date.parse(a.next_due)-Date.parse(b.next_due));
        },
        nextTaskRunLabel(value, now=Date.now()){
            const date=new Date(value);
            const withinDay=date.getTime()-now<24*60*60*1000 && date.getTime()>=now;
            const options=withinDay
                ? {hour:'2-digit',minute:'2-digit',hourCycle:'h23'}
                : {month:'short',day:'numeric'};
            return date.toLocaleString(document.documentElement.lang || undefined,options);
        },
        linkedTaskEntry(task){
            return {id:task.id,title:task.title,status:task.run?.status,
                updated_at:task.run?.finished_at||task.run?.started_at||task.updated_at,linked:task};
        },
        taskOverview(){
            const terminal=new Set(['completed','failed','cancelled','interrupted','timed_out']);
            const linked=this.botTasks.filter(task=>!task.task_session_id&&!task.archived_at).map(task=>this.linkedTaskEntry(task));
            const tasks=[...this.botTaskSessions,...linked];
            const priority=entry=>['waiting_input','waiting_capability'].includes(entry.status)?0:1;
            const byRecent=(a,b)=>(Date.parse(b.updated_at)||0)-(Date.parse(a.updated_at)||0);
            const active=tasks.filter(entry=>this.taskActive({run:{status:entry.status}})||entry.status==='waiting_collaboration')
                .sort((a,b)=>priority(a)-priority(b)||byRecent(a,b));
            const scheduled=this.scheduledBotTasks().map(task=>({...this.linkedTaskEntry(task),planned:true}));
            const ended=this.botTaskSessions.filter(entry=>terminal.has(entry.status));
            for(const entry of linked){
                const task=entry.linked;
                const run=terminal.has(entry.status)?task.run:task.previous_finished_run;
                if(run)ended.push({...this.linkedTaskEntry({...task,run}),receipt:task.scheduled});
                else if(!task.scheduled&&!task.run&&terminal.has(task.status))ended.push({...entry,status:task.status});
            }
            return [
                {kind:'active',label:this.ui('进行中','In progress'),entries:active},
                {kind:'scheduled',label:this.ui('计划中','Scheduled'),entries:scheduled},
                {kind:'ended',label:this.ui('已结束','Ended'),entries:ended.sort(byRecent).slice(0,3)},
            ].filter(group=>group.entries.length);
        },
        continueBotTask(entry){controller?.continueTask(entry);},
        taskRowAction(entry){
            if(['waiting_input','waiting_capability'].includes(entry.status)&&controller?.focusTaskInteraction(entry))return;
            void this.inspectBotTask(entry);
        },
        async browseBotTasks(archived=false,more=false){
            const token=generation,session=this.botSessionId,bot=this.currentBot?.id;
            if(!session||!bot||(more&&this.botTaskBrowseLoading))return;
            const revision=++taskBrowseRevision;this.botTaskBrowseLoading=true;
            const offset=more?this.botTaskSessionBrowse.length:0;
            if(!more){
                this.botTaskSessionDetail=null;this.botTaskBrowseOpen=true;this.botTaskBrowseArchived=archived;
                this.botTaskSessionBrowse=[];this.botTaskBrowseMore=false;
            }
            try{
                const result=await localRequest('/bots/'+bot+'/task-sessions?session_id='+encodeURIComponent(session)+'&archived='+archived+'&offset='+offset);
                if(token!==generation||revision!==taskBrowseRevision||!this.botTaskBrowseOpen||this.botTaskBrowseArchived!==archived)return;
                this.botTaskSessionBrowse=more?[...this.botTaskSessionBrowse,...result.items]:result.items;
                this.botTaskBrowseMore=result.has_more;
            }catch(error){if(token===generation&&revision===taskBrowseRevision)this.fail(error);}
            finally{if(token===generation&&revision===taskBrowseRevision)this.botTaskBrowseLoading=false;}
        },
        botSessionLabel(entry){const labels={waiting_collaboration:['等待协作','Waiting for collaboration'],completed:['已完成','Completed'],running:['处理中','Working'],planning:['准备中','Preparing'],queued:['等待执行','Queued'],waiting_input:['等待你的回复','Waiting for your reply'],waiting_capability:['等待授权','Waiting for authorization'],failed:['未完成','Failed'],cancelled:['已停止','Stopped'],interrupted:['已中断','Interrupted'],timed_out:['已超时','Timed out']};const value=labels[entry.status];return value?this.ui(...value):entry.status;},
        async stopBotSession(entry){const step=(entry.runs||[]).find(s=>!['completed','cancelled','failed','interrupted','timed_out'].includes(s.status));const job=step?.id||(entry.status==='waiting_collaboration'?entry.last_job:null);if(!job)return;try{await localRequest('/bots/'+this.currentBot.id+'/dialogue/jobs/'+job+'/cancel',{method:'POST',body:{}});await controller?.refresh();}catch(error){this.fail(error);}},
        async inspectBotTask(entry){
            const token=generation,bot=this.currentBot?.id;
            if(entry.linked){
                this.botTaskSessionDetail=entry;
                try{
                    const statistics=await localRequest('/bots/'+bot+'/statistics?todo_task_id='+encodeURIComponent(entry.id));
                    const detail=this.botTaskSessionDetail;
                    if(token===generation&&detail?.id===entry.id&&detail.planned===entry.planned&&detail.receipt===entry.receipt)
                        this.botTaskSessionDetail={...detail,statistics};
                }catch(error){if(token===generation)this.fail(error);}
                return;
            }
            this.botTaskSessionDetail=entry;
            try{
                const detail=await localRequest('/bots/'+bot+'/task-sessions/'+encodeURIComponent(entry.id));
                if(token===generation&&this.botTaskSessionDetail?.id===entry.id)this.botTaskSessionDetail=detail;
            }catch(error){if(token===generation)this.fail(error);}
        },
        async manageBotTaskSession(entry,action){
            const token=generation,bot=this.currentBot?.id;
            try{
                await localRequest('/bots/'+bot+'/task-sessions/'+entry.id+'/'+action,{method:'POST',body:{}});
                if(token!==generation)return;
                await controller?.refresh();
                if(this.botTaskBrowseOpen)await this.browseBotTasks(this.botTaskBrowseArchived);
                else if(action==='archive')this.botTaskSessionDetail=null;
                else if(this.botTaskSessionDetail?.id===entry.id)await this.inspectBotTask(entry);
            }catch(error){if(token===generation)this.fail(error);}
        },
        async openBot(bot, {manage=false,focusFrom}={}) {
            if(bot.definition?.execution_mode==='app_shortcut'&&!manage){try{await window.AI2AppsAppShortcuts.open(bot.id);}catch(error){this.fail(error);}return;}
            const token=++generation;controller?.dispose();controller=null;this.botTasksUnavailable=false;
            chatRoot=chatRoot||this.$refs.botChat;if(!chatRoot)throw Error('Bot conversation mount unavailable');this.currentBot=bot;this.botTaskBrowseOpen=false;this.botTaskBrowseLoading=false;this.botTaskSessionBrowse=[];this.botSessionId=null;this.botTaskSessions=[];this.botTaskSessionDetail=null;this.botEditName=bot.name;this.botEditDuty=bot.duty;this.avatarPreset=bot.avatar?.preset||'spark';this.avatarColor=bot.avatar?.color||'#6366f1';
            this.botSkills=null;
            this.closeBotSkillPicker();
            if(bot.definition?.execution_mode==='agent'&&this.$refs.botSkillsPanel?.open)this.loadBotSkills();
            if(bot.definition?.execution_mode==='app_shortcut'){chatRoot.replaceChildren();const info=document.createElement('p');info.textContent=this.ui('ASC-Bot：点击列表直接打开保存的 App 设置。','ASC-Bot: click the list entry to open the saved App settings.');chatRoot.append(info);return;}
            this.voiceSettings=null;this.voiceAppliedSettings=null;this.voiceSaveState='';this.voiceLoaded=false;this.loadBotVoice();this.focusedTask=null;this.notificationPolicy=null;this.loadNotificationPolicy();this.memories=[];this.pendingMemories=null;this.memoryText='';this.closeCleanup();this.loadMemories();this.botTaskAccessPolicies=[];this.botTasks=[];this.taskChooser=false;this.taskSelection='';this.loadBotTasks();this.closeAccessDialog();this.botAccess=[];this.botApprovalRule=null;this.accessLoaded=false;this.loadBotAccess();this.botUseAccess=null;this.botUseTarget='';this.botUseCaller='';this.loadBotUseAccess();this.botStatistics=null;this.statisticsLoadedAt=0;this.loadBotStatistics();
            try {
                const chat=await window.AI2AppsBotConversation.create({bot,root:chatRoot,bots:()=>this.bots,focusFrom,isActive:()=>token===generation,
                    onPendingMemories:items=>{if(token===generation)this.pendingMemories=items.sort((a,b)=>Number(b.state==='review')-Number(a.state==='review'));},
                    onState:value=>{if(token===generation){this.botTaskAccessPolicies=value.accessPolicies||[];this.botModels=value.models;this.botModel=value.model;this.botAppliedModel=value.model;this.botModelNotice=value.modelNotice||'';this.botReasoningEffort=value.reasoningEffort||'';this.botReasoningLevels=value.supportedReasoningEfforts||[];this.botModelSaving=Boolean(value.profileSaving);this.botRuns=value.runs;const entry=this.bots.find(b=>b.id===bot.id);if(entry){if(value.unreadCount!==undefined)entry.unread_count=value.unreadCount;entry.needs_user_assistance=value.runs.some(r=>['waiting_input','waiting_capability'].includes(r.status));entry.reply_status=value.runs.find(r=>r.dialogue&&!['completed','failed','cancelled','interrupted','timed_out'].includes(r.status))?.status||null;}this.botSessionId=value.sessionId;this.botTaskSessions=value.taskSessions||[];const detail=this.botTaskSessionDetail;const updated=detail&&!detail.linked&&this.botTaskSessions.find(task=>task.id===detail.id);if(updated)this.botTaskSessionDetail={...detail,...updated,summary:detail.updated_at===updated.updated_at?detail.summary:updated.summary};const latest=value.runs.at(-1);if(latest&&this.currentBot?.id===bot.id)this.currentBot.last_status=latest.status;}},
                    onError:error=>{if(token===generation)this.fail(error);}});
                if(token!==generation || this.tab!=='bots'){chat?.dispose({skipCache:true});return;}
                controller=chat;
            } catch(error){if(token===generation)this.fail(error);}
        },
        botSkills:null,
        botSkillBusy:null,
        botSkillSelection:[],
        botSkillPickerError:'',
        botSkillPickerLoading:false,
        botSkillRead:0,
        get addedBotSkills(){return (this.botSkills||[]).filter(item=>item.added);},
        get availableBotSkills(){return (this.botSkills||[]).filter(item=>!item.added&&!item.unsupported.length);},
        async loadBotSkills({picker=false}={}) {
            const bot=this.currentBot;
            if(bot?.definition?.execution_mode!=='agent')return;
            const token=generation, read=++this.botSkillRead;
            try {
                const value=await localRequest('/bots/'+bot.id+'/skills');
                if(token===generation&&read===this.botSkillRead&&!this.botSkillBusy)this.botSkills=value.items;
            }catch(error){
                if(token!==generation||read!==this.botSkillRead)return;
                if(picker)this.botSkillPickerError=error.message;
                else this.fail(error);
            }finally{
                if(token===generation&&read===this.botSkillRead)this.botSkillPickerLoading=false;
            }
        },
        openBotSkillPicker(){
            const dialog=this.$refs.botSkillPicker;
            if(this.botSkillBusy||!dialog||dialog.open)return;
            this.botSkillSelection=[];
            this.botSkillPickerError='';
            this.botSkillPickerLoading=true;
            dialog.showModal();
            this.loadBotSkills({picker:true});
        },
        closeBotSkillPicker(){
            this.$refs.botSkillPicker?.close();
            this.botSkillSelection=[];
            this.botSkillPickerError='';
            this.botSkillPickerLoading=false;
        },
        async addSelectedBotSkills(){
            const bot=this.currentBot, token=generation;
            const ids=this.availableBotSkills.filter(item=>this.botSkillSelection.includes(item.id)).map(item=>item.id);
            if(!bot||!this.$refs.botSkillPicker?.open||this.botSkillBusy||this.botSkillPickerLoading||!ids.length)return;
            this.botSkillRead++;
            this.botSkillBusy=true;
            this.botSkillPickerError='';
            try{
                for(const id of ids){
                    const value=await localRequest('/bots/'+bot.id+'/skills/'+encodeURIComponent(id),{method:'PUT',body:{enabled:true}});
                    if(token!==generation)return;
                    this.botSkills=value.items;
                    this.botSkillSelection=this.botSkillSelection.filter(selected=>selected!==id);
                }
            }catch(error){
                if(token===generation)this.botSkillPickerError=error.message;
                return;
            }finally{
                this.botSkillBusy=null;
                if(token!==generation&&this.$refs.botSkillsPanel?.open)this.loadBotSkills();
            }
            this.$nextTick(()=>{if(token===generation)this.closeBotSkillPicker();});
        },
        async saveBotSkill(item, enabled, input=null) {
            const bot=this.currentBot;
            if(bot?.definition?.execution_mode!=='agent'||this.botSkillBusy){
                if(input)input.checked=item.enabled;
                return;
            }
            const token=generation;
            this.botSkillRead++;
            this.botSkillBusy=item.id;
            try {
                const value=await localRequest('/bots/'+bot.id+'/skills/'+encodeURIComponent(item.id),
                    enabled===null?{method:'DELETE'}:{method:'PUT',body:{enabled}});
                if(token===generation)this.botSkills=value.items;
            }catch(error){if(token===generation){if(input)input.checked=item.enabled;this.fail(error);}}
            finally {
                this.botSkillBusy=null;
                if(token!==generation&&this.$refs.botSkillsPanel?.open)this.loadBotSkills();
            }
        },
        async refreshConfiguredBot(detail){if(detail?.status!=='applied')return;await this.loadBots();if(this.currentBot?.id!==detail.botId)return;const fresh=this.bots.find(b=>b.id===detail.botId);if(fresh){Object.assign(this.currentBot,fresh);this.botEditName=fresh.name;this.botEditDuty=fresh.duty;}await Promise.all([this.loadMemories(),this.loadBotTasks()]);},
        get inboxUnread(){return this.unreadCount+this.localUnreadCount;},
        publishInboxBadge(){window.parent?.postMessage({type:'ai2apps.shell.set-badge',targetAppId:'ai2apps.messager',badge:this.inboxUnread?(this.inboxUnread>99?'99+':String(this.inboxUnread)):''},location.origin);},
        async loadLocalNotices(){try{const value=await localRequest('/notices');this.localNotices=value.items;this.localUnreadCount=value.unread_count;this.localNoticesMore=value.has_more;this.publishInboxBadge();}catch(e){if(e.status!==404)this.fail(e);}},
        async loadNotificationPolicy(){const id=this.currentBot?.id;if(!id)return;try{const value=await localRequest('/bots/'+id+'/notification-policy');if(this.currentBot?.id===id){this.notificationPolicy=value.policy;this.notificationRevision=value.revision;}}catch(e){this.fail(e);}},
        async saveNotificationPolicy(){const id=this.currentBot?.id;if(!id||!this.notificationPolicy||this.notificationBusy)return;this.notificationBusy=true;try{const value=await localRequest('/bots/'+id+'/notification-policy',{method:'PUT',body:{revision:this.notificationRevision,policy:{...this.notificationPolicy}}});if(this.currentBot?.id===id){this.notificationPolicy=value.policy;this.notificationRevision=value.revision;}this.success(this.ui('提醒策略已保存','Notification settings saved'));}catch(e){this.fail(e);await this.loadNotificationPolicy();}finally{this.notificationBusy=false;}},
        async openBotNotice(id){try{const value=await localRequest('/notices/'+encodeURIComponent(id)+'/open',{method:'POST',body:{}});await this.loadBots();const bot=this.bots.find(b=>b.id===value.bot_id);if(!bot)throw Error(this.ui('原 Bot 不可用','Original Bot is unavailable'));this.tab='bots';this.rightTab='bot';this.rightOpen=true;await this.openBot(bot);this.focusedTask=value.task;controller?.focusTaskRun?.(value.todo_run_id);await this.loadLocalNotices();}catch(e){this.fail(e);}},
        async openNotificationRoute(){const query=new URLSearchParams(location.search),hash=new URLSearchParams(location.hash.slice(1));const get=k=>hash.get(k)||query.get(k);if(get('notification-route')==='bot-notice'&&get('notification-resource'))await this.openBotNotice(get('notification-resource'));},
        async readAllLocalNotices(){await localRequest('/notices/read-all',{method:'POST',body:{}});await this.loadLocalNotices();},
        accessScope(profile){if(profile.scope==='owned_inbox')return this.ui('仅在你的 Todo 收件箱创建普通待办；不修改、删除或启动任务','Create ordinary items in your Todo Inbox only; no edits, deletion or execution');if(profile.scope==='self_local_inbox')return this.ui('仅给自己保存站内提醒；内容留在本机，不发送给好友','Self reminders only; content stays local and is never sent to friends');return this.ui('只读 · 你拥有的数据','Read only · Your owned data');},
        async loadMemories(){const id=this.currentBot?.id;if(!id)return;try{const value=await localRequest('/bots/'+id+'/memories');if(this.currentBot?.id===id)this.memories=value.items;}catch(e){this.fail(e);}},
        async saveMemory(note,deleted=false){const id=this.currentBot?.id;if(!id||this.memoryBusy)return;this.memoryBusy=true;try{await localRequest('/bots/'+id+'/memories'+(note?'/'+note.id:''),{method:note?'PUT':'POST',body:note?{text:note.text,revision:note.revision,deleted}:{text:this.memoryText}});if(this.currentBot?.id===id){if(!note)this.memoryText='';await this.loadMemories();}return true;}catch(e){this.fail(e);return false;}finally{this.memoryBusy=false;}},
        closeCleanup(){this.$root?.querySelector('.bot-cleanup-dialog')?.close();this.cleanupReview=null;this.cleanupTargetId=null;this.cleanupShortcutName=null;this.cleanupDeleteTasks=false;this.cleanupClearMemory=false;this.cleanupRevokeAccess=false;},
        cancelCleanup(){if(!this.cleanupBusy)this.closeCleanup();},
        async reviewCleanup(action,shortcut=null){
            if(shortcut&&(action!=='archive'||shortcut.definition?.execution_mode!=='app_shortcut'))return;
            const id=shortcut?.id||this.currentBot?.id;if(!id||this.cleanupBusy||this.cleanupLoading)return;
            this.cleanupLoading=true;
            try{
                const value=await localRequest('/bots/'+id+'/cleanup');
                if(!shortcut&&this.currentBot?.id!==id)return;
                this.cleanupShortcutName=shortcut?.name??null;
                this.cleanupReview=value;this.cleanupAction=action;this.cleanupTargetId=id;this.cleanupDeleteTasks=false;this.cleanupClearMemory=false;this.cleanupRevokeAccess=false;
                this.$root.querySelector('.bot-cleanup-dialog').showModal();
            }catch(e){this.closeCleanup();this.fail(e);}finally{this.cleanupLoading=false;}
        },
        cleanupLabel(action){const labels={clear_memory:['清除长期记忆','Clear long-term memory'],clear_dialogue:['清除对话记录','Clear conversation'],restore_dialogue:['恢复上一份对话','Restore previous conversation'],archive:['删除 Bot（可恢复）','Delete Bot (recoverable)'],reset:['重置 Bot','Reset Bot']};return labels[action]?this.ui(...labels[action]):action;},
        cleanupSelectionSummary(){const tasks=this.cleanupDeleteTasks?this.ui('同时删除 Bot 后台任务，记录可恢复，恢复后保持停用；','also deletes Bot background tasks; restored records stay disabled; '):this.ui('保留后台任务记录；','keeps background task records; ');return tasks+this.ui('本次将清除对话；','This clears the conversation; ')+(this.cleanupClearMemory?this.ui('同时清除长期记忆；','also clears long-term memory; '):this.ui('保留长期记忆；','keeps long-term memory; '))+(this.cleanupRevokeAccess?this.ui('同时撤销 App / Mini-App 访问权限。恢复对话不会恢复这些权限。','also revokes App / Mini-App access. Restoring the conversation will not restore these permissions.'):this.ui('保留 App / Mini-App 访问权限。','keeps App / Mini-App access.'))+(this.cleanupClearMemory?this.ui('恢复对话不会恢复已清除的长期记忆。',' Restoring the conversation will not restore cleared long-term memory.'):'');},
        cleanupConfirmLabel(){if(this.cleanupShortcutName!==null)return this.ui('删除快捷 Bot','Delete shortcut Bot');if(this.cleanupAction==='clear_dialogue'&&this.cleanupDeleteTasks)return this.ui('确认清理所选内容并删除后台任务','Clear selected content and delete background tasks');if(this.cleanupAction!=='clear_dialogue')return this.ui('确认执行上述操作','Confirm these changes');if(this.cleanupRevokeAccess)return this.cleanupClearMemory?this.ui('清除对话、记忆并撤销权限','Clear conversation, memory and access'):this.ui('清除对话并撤销权限','Clear conversation and access');return this.cleanupClearMemory?this.ui('清除对话和记忆','Clear conversation and memory'):this.ui('确认清除对话','Clear conversation');},
        async applyCleanup(){
            const id=this.cleanupTargetId,review=this.cleanupReview,action=this.cleanupAction;
            const shortcut=this.cleanupShortcutName!==null;
            if(!id||!review||(!shortcut&&this.currentBot?.id!==id)||this.cleanupBusy)return;
            const choices=action==='clear_dialogue'?{clear_memory:this.cleanupClearMemory,revoke_access:this.cleanupRevokeAccess,delete_tasks:this.cleanupDeleteTasks}:{};
            this.cleanupBusy=true;
            try{
                await localRequest('/bots/'+id+'/cleanup/'+action,{method:'POST',body:{review_hash:review.review_hash,...choices}});
                this.closeCleanup();
                window.AI2AppsBotConversation.invalidate?.(chatRoot,id);
                if(this.currentBot?.id===id){
                    generation++;controller?.dispose({discard:true});controller=null;
                    // Invalidate old polls before removing their messages, attachments and materials.
                    chatRoot?.replaceChildren();
                    this.currentBot=null;
                    await this.loadBots(action==='archive'?null:id);
                    if(action==='archive')await this.loadArchivedBots();
                    if(!shortcut)this.success(action==='clear_dialogue'?(choices.clear_memory||choices.revoke_access||choices.delete_tasks?this.ui('已按所选范围清理','Selected cleanup completed'):this.ui('对话已清空','Conversation cleared')):this.ui('已处理。原任务回执保留；恢复不会重新授予权限或启动任务。','Updated. Original task receipts are retained; restore never reactivates access or work.'));
                }else if(shortcut){
                    await this.loadBots();
                    await this.loadArchivedBots();
                }
                if(shortcut)this.success(this.ui('快捷 Bot 已删除，可在「已删除 Bot」中恢复。','Shortcut deleted. You can restore it from Deleted Bots.'));
            }catch(e){this.closeCleanup();this.fail(e);}finally{this.cleanupBusy=false;}
        },
        toggleBotCreation(anchor){if(creationMenu){creationMenu.dispose();creationMenu=null;return;}if(this.sidebarWidth<168)this.expandSidebar();creationMenu=window.AI2AppsBotCreation.menu(anchor,{onAddGroup:()=>this.openGroupDialog(),onClose:()=>{creationMenu=null;},onChoose:type=>{creationMenu=null;this.beginBotCreation(type);}});},
        beginBotCreation(botType='standard',groupId=null){if(this.sidebarWidth<168)this.expandSidebar();this.creatingBot=true;this.$nextTick(()=>{creationForm?.dispose();creationForm=window.AI2AppsBotCreation.mount(this.$refs.botCreationHost,{botType,request:(path,method='GET',body)=>localRequest(path==='/options'?'/bot-creation/options':path==='/submit'?'/bot-creation':path,{method,body:path==='/submit'&&groupId?{...body,group_id:groupId}:body}),models:()=>window.AI2AppsBotModelSelection.resolve(''),onCancel:()=>this.cancelBotCreation(),onCreated:bot=>{this.cancelBotCreation();this.bots.push(bot);this.openBot(bot).catch(e=>this.fail(e));}});});},
        cancelBotCreation(){creationForm?.dispose();creationForm=null;this.creatingBot=false;},
        async toggleArchivedBots(){if(this.sidebarWidth<168)this.expandSidebar();this.showArchivedBots=!this.showArchivedBots;if(this.showArchivedBots){await this.loadArchivedBots();this.$nextTick(()=>this.$refs.botArchiveList?.scrollIntoView({block:'nearest'}));}},
        async loadArchivedBots(){try{this.archivedBots=(await localRequest('/bots-archive')).items;}catch(e){this.fail(e);}},
        async restoreBot(bot){try{await localRequest('/bots-archive/'+bot.id+'/restore',{method:'POST',body:{revision:bot.revision}});await this.loadArchivedBots();await this.loadBots();}catch(e){this.fail(e);}},
        reviewRemoveBotUse(target){if(this.botUseBusy||!this.currentBot||!this.botUseAccess)return;this.accessRemoval={bot_id:this.currentBot.id,target_id:target.id,name:target.name,revision:this.botUseAccess.revision};this.accessDialogMode='remove-bot';this.$nextTick(()=>{accessDialogRoot=this.$refs.accessDialog;accessDialogRoot?.showModal();accessDialogRoot?.querySelector('[data-bot-use-cancel]')?.focus();});},
        async removeBotUse(){const removal=this.accessRemoval,id=this.currentBot?.id;if(this.accessDialogMode!=='remove-bot'||!removal||id!==removal.bot_id||this.botUseBusy)return;this.botUseBusy=true;this.botUseLoad++;try{const result=await localRequest('/bots/'+id+'/bot-access/targets/'+encodeURIComponent(removal.target_id),{method:'DELETE',body:{revision:removal.revision,enabled:false}});if(this.currentBot?.id===id){this.botUseAccess=result;this.closeAccessDialog();}}catch(e){if(this.currentBot?.id===id)this.fail(e);}finally{this.botUseBusy=false;if(this.currentBot?.id===id)await this.loadBotUseAccess();}},
        async loadBotUseAccess(){const id=this.currentBot?.id;if(!id||this.botUseBusy)return;const turn=++this.botUseLoad;try{const value=await localRequest('/bots/'+id+'/bot-access');if(this.currentBot?.id===id&&turn===this.botUseLoad&&!this.botUseBusy)this.botUseAccess=value;}catch(e){if(this.currentBot?.id===id)this.fail(e);}},
        async setBotUse(kind,peer,enabled){const id=this.currentBot?.id,value=this.botUseAccess;if(!id||!value||this.botUseBusy)return;this.botUseBusy=true;this.botUseLoad++;try{const path=kind==='exposure'?'exposure':kind+'/'+encodeURIComponent(peer);const body=kind==='exposure'?{revision:value.revision,mode:value.mode}:{revision:value.revision,enabled};const result=await localRequest('/bots/'+id+'/bot-access/'+path,{method:'PUT',body});if(this.currentBot?.id===id){this.botUseAccess=result;this.botUseTarget='';this.botUseCaller='';}}catch(e){this.fail(e);}finally{this.botUseBusy=false;if(this.currentBot?.id===id)await this.loadBotUseAccess();}},
        async saveBotApprovalRule(mode) {
            const botId = this.currentBot?.id;
            if (!botId || !this.botApprovalRule || this.botApprovalBusy) return;
            this.botApprovalBusy = true;
            try {
                const rule = await localRequest('/bots/'+botId+'/app-access/approval-rule', {
                    method:'PUT', body:{mode,revision:this.botApprovalRule.revision},
                });
                if (this.currentBot?.id === botId) this.botApprovalRule = rule;
            } catch (error) {
                if (this.currentBot?.id === botId) this.fail(error);
            } finally {
                this.botApprovalBusy = false;
                await this.loadBotAccess();
            }
        },
        async loadBotAccess(){const id=this.currentBot?.id;if(!id)return;try{const value=await localRequest('/bots/'+id+'/app-access');if(value.items.some(p=>!['app','mini-app','unavailable'].includes(p.kind))){this.accessLoaded=false;throw Error(this.ui('本地服务需要重载，才能使用新的 App/Mini-App 权限目录。','Reload Local to use the new App/Mini-App access catalog.'));}if(this.currentBot?.id===id&&!this.botApprovalBusy&&value.approval_rule&&(!this.botApprovalRule||value.approval_rule.revision>=this.botApprovalRule.revision))this.botApprovalRule=value.approval_rule;if(this.currentBot?.id===id&&!this.accessBusy&&(!this.accessLoaded||value.revision>=this.accessRevision)){this.botAccess=value.items;this.accessRevision=value.revision;this.accessReviewHash=value.review_hash;this.accessLoaded=true;this.$nextTick?.(()=>window.lucide?.createIcons());}}catch(e){if(this.currentBot?.id===id)this.fail(e);}},
        get selectedBotApps(){return this.botAccess.filter(p=>p.selected&&p.kind!=='mini-app');},
        get selectedBotMiniApps(){return this.botAccess.filter(p=>p.selected&&p.kind==='mini-app');},
        get accessCandidates(){const query=this.accessQuery.trim().toLowerCase();return this.botAccess.filter(p=>!p.selected&&p.available&&p.kind===this.accessChooserKind&&(!query||String(p.name).toLowerCase().includes(query)||(p.hosts||[]).join(' ').toLowerCase().includes(query)));},
        openAccessChooser(kind='app'){if(this.accessBusy||!this.accessLoaded)return;this.accessChooserKind=kind;this.accessQuery='';this.accessDialogMode='add';this.$nextTick(()=>{accessDialogRoot=this.$refs.accessDialog;accessDialogRoot?.showModal();window.lucide?.createIcons();});},
        async restoreTemplateRole(){
            const bot=this.currentBot,draft=this.botEditDuty;if(!bot?.template_id||this.botSaving)return;
            try{const value=await localRequest('/bot-creation/options');const template=value.templates?.find(t=>t.id===bot.template_id);
                if(template&&this.currentBot?.id===bot.id&&this.botEditDuty===draft)this.botEditDuty=this.ui(template.role.zh,template.role.en);
            }catch(e){this.fail(e);}
        },
        async reviewRestoreTemplateAccess(){
            const bot=this.currentBot;if(!bot?.template_id||this.accessBusy||!this.accessLoaded)return;
            try{const value=await localRequest('/bot-creation/options');const template=value.templates?.find(t=>t.id===bot.template_id);
                if(!template||this.currentBot?.id!==bot.id||this.accessBusy||this.accessDialogMode)return;
                const items=this.botAccess.map(p=>{const enabled=p.available&&template.app_ids.includes(p.app_id);return {...p,selected:enabled,enabled};});
                const changes=items.flatMap((p,i)=>{const before=this.botAccess[i];return p.selected!==before.selected||p.enabled!==before.enabled?[{id:p.app_id,name:p.name,enabled:p.enabled}]:[];});
                this.accessRemoval={bot_id:bot.id,revision:this.accessRevision,review_hash:this.accessReviewHash,items,changes};this.accessDialogMode='restore-template';
                this.$nextTick(()=>{accessDialogRoot=this.$refs.accessDialog;accessDialogRoot?.showModal();});
            }catch(e){this.fail(e);}
        },
        async restoreTemplateAccess(){
            const review=this.accessRemoval;if(this.accessDialogMode!=='restore-template'||review?.bot_id!==this.currentBot?.id||!review.changes.length)return;
            if(await this.commitBotAccess(review.items,review))this.closeAccessDialog();
        },
        reviewRemoveAccess(profile){if(this.accessBusy)return;this.accessRemoval={app_id:profile.app_id,name:profile.name,bot_id:this.currentBot?.id};this.accessDialogMode='remove';this.$nextTick(()=>{accessDialogRoot=this.$refs.accessDialog;accessDialogRoot?.showModal();window.lucide?.createIcons();});},
        closeAccessDialog(){accessDialogRoot?.close();this.accessDialogMode='';this.accessRemoval=null;},
        async commitBotAccess(items,review=null){const bot=this.currentBot;if(!bot||this.accessBusy||!this.accessLoaded)return false;this.accessBusy=true;try{const value=await localRequest('/bots/'+bot.id+'/app-access',{method:'PUT',body:{revision:review?.revision??this.accessRevision,review_hash:review?.review_hash??this.accessReviewHash,apps:items.filter(p=>p.selected).map(p=>({app_id:p.app_id,enabled:p.enabled}))}});if(this.currentBot?.id!==bot.id)return false;this.botAccess=value.items;this.accessRevision=value.revision;this.accessReviewHash=value.review_hash;this.$nextTick?.(()=>window.lucide?.createIcons());return true;}catch(e){this.fail(e);if(this.currentBot?.id===bot.id)await this.loadBotAccess();return false;}finally{this.accessBusy=false;}},
        async addBotAccess(profile){if(!profile.available||profile.selected)return;const items=this.botAccess.map(p=>p.app_id===profile.app_id?{...p,selected:true,enabled:true}:p);if(await this.commitBotAccess(items))this.closeAccessDialog();},
        async removeBotAccess(){const removal=this.accessRemoval;if(!removal||this.currentBot?.id!==removal.bot_id)return;const items=this.botAccess.map(p=>p.app_id===removal.app_id?{...p,selected:false,enabled:false}:p);if(await this.commitBotAccess(items))this.closeAccessDialog();},
        async saveBotAccess(){await this.commitBotAccess(this.botAccess);},
        async disableTaskAccess(policy){const bot=this.currentBot?.id;if(!bot)return;try{await localRequest('/bots/'+bot+'/task-access/'+policy.id+'/revoke',{method:'POST',body:{}});if(this.currentBot?.id===bot){this.botTaskAccessPolicies=this.botTaskAccessPolicies.filter(p=>p.id!==policy.id);await this.loadBotTasks();}}catch(e){this.fail(e);}},
        async loadBotStatistics(force=false){const id=this.currentBot?.id,period=this.statisticsPeriod;if(!id||(!force&&this.statisticsBusy)||(!force&&Date.now()-this.statisticsLoadedAt<30000))return;const request=++this.statisticsRequest;this.statisticsBusy=true;try{const value=await localRequest('/bots/'+id+'/statistics?period='+period+'&timezone_name='+encodeURIComponent(this.statisticsTimezone));if(this.currentBot?.id===id&&this.statisticsPeriod===period&&request===this.statisticsRequest){this.botStatistics=value;this.statisticsLoadedAt=Date.now();}}catch(e){if(force&&request===this.statisticsRequest)this.fail(e);}finally{if(request===this.statisticsRequest)this.statisticsBusy=false;}},
        taskUsageRows(value){
            return [['task','任务自身','Task itself'],['aaat','AaAT','AaAT'],['delegated','委派 Bot','Delegated Bots'],['total','总计','Total']]
                .map(([key,zh,en])=>({key,label:this.ui(zh,en),...value[key]}));
        },
        formatUsageAmount(amount, lowerBound = false) {
            return window.formatMessagerUsage(amount, lowerBound);
        },
        taskUsageValue(value,known){
            if (value != null) return this.formatUsageAmount(value);
            if (known != null) return '>' + this.formatUsageAmount(known, true);
            return this.ui('未知', 'Unk.');
        },
        statisticsRange(){const v=this.botStatistics;if(!v)return '';return (v.start?new Date(v.start).toLocaleString():this.ui('全部历史','All history'))+' — '+new Date(v.end).toLocaleString();},
        async loadBotTasks(){
            const id=this.currentBot?.id;
            if(!id)return;
            try{
                const value=await localRequest('/bots/'+id+'/tasks');
                if(this.currentBot?.id!==id)return;
                this.botTasksUnavailable=false;
                this.botTasks=value.items;
                this.botTasksMore=value.has_more;
                const detail=this.botTaskSessionDetail;
                if(detail?.linked&&!detail.receipt){
                    const refreshed=value.items.find(task=>task.id===detail.id);
                    if(refreshed)this.botTaskSessionDetail={...detail,...this.linkedTaskEntry(refreshed)};
                }
                const status=value.items.find(task=>this.taskActive(task))?.run?.status||null;
                this.currentBot.task_status=status;
                this.bots.forEach(bot=>{if(bot.id===id)bot.task_status=status;});
            }catch(error){
                if(this.currentBot?.id!==id)return;
                if(error.status===503)this.botTasksUnavailable=true;
                else this.fail(error);
            }
        },
        async chooseBotTask(){const id=this.currentBot?.id;if(!id)return;try{const value=await localRequest('/bots/'+id+'/task-candidates');if(this.currentBot?.id===id){this.taskCandidates=value.items;this.taskCandidatesMore=value.has_more;this.taskChooser=true;this.taskSelection='';}}catch(e){this.fail(e);}},
        async assignBotTask(){const id=this.currentBot?.id,task=this.taskSelection;if(!id||!task||this.taskBusy)return;this.taskBusy=true;try{await localRequest('/bots/'+id+'/tasks',{method:'POST',body:{task_id:task}});if(this.currentBot?.id===id){this.taskChooser=false;await this.loadBotTasks();}}catch(e){this.fail(e);}finally{this.taskBusy=false;}},
        async stopBotTask(task){const id=this.currentBot?.id;if(!id||!task.run||this.taskBusy)return;this.taskBusy=true;try{await localRequest('/bots/'+id+'/task-runs/'+task.run.id+'/cancel',{method:'POST',body:{}});if(this.currentBot?.id===id)await this.loadBotTasks();}catch(e){this.fail(e);}finally{this.taskBusy=false;}},
        async removeBotTask(task){const id=this.currentBot?.id;if(!id||this.taskBusy)return;this.taskBusy=true;try{await localRequest('/bots/'+id+'/tasks/'+encodeURIComponent(task.id),{method:'DELETE'});if(this.currentBot?.id===id)await this.loadBotTasks();}catch(e){this.fail(e);}finally{this.taskBusy=false;}},
        taskActive(task){return ['queued','running','planning','waiting_input','waiting_capability'].includes(task.run?.status);},
        taskLabel(task){const status=task.run?.status||task.status;const labels={queued:['排队中','Queued'],running:['执行中','Running'],planning:['规划中','Planning'],waiting_input:['等待回复','Waiting for reply'],waiting_capability:['等待授权','Waiting for permission'],completed:['已完成','Completed'],failed:['失败','Failed'],cancelled:['已取消','Cancelled'],interrupted:['已中断','Interrupted'],timed_out:['已超时','Timed out'],awaiting_acceptance:['待验收','Awaiting acceptance'],not_started:['尚未执行','Not started'],in_progress:['进行中','In progress']};return labels[status]?this.ui(...labels[status]):status;},
        todoTaskUrl(task){return '/admin/app-content/ai2apps.todo?task='+encodeURIComponent(task.id);},
        botAvatar(bot){return window.AI2AppsBotAvatars.url(bot);},
        async saveAvatar(avatar){if(!this.currentBot||this.avatarBusy)return;const bot=this.currentBot;this.avatarBusy=true;try{const value=await localRequest('/bots/'+bot.id+'/avatar',{method:'PUT',body:avatar});Object.assign(bot,value);this.bots=this.bots.map(b=>b.id===bot.id?{...b,...value}:b);}catch(e){this.fail(e);}finally{this.avatarBusy=false;}},
        async presetAvatar(){await this.saveAvatar({kind:'preset',preset:this.avatarPreset,color:this.avatarColor});},
        async galleryAvatar(){const botId=this.currentBot?.id;try{const selected=await window.AI2AppsGalleryPicker.open({kind:'image',multiple:false});if(selected.length&&this.currentBot?.id===botId)await this.saveAvatar({kind:'image',asset_id:selected[0].id});}catch(e){this.fail(e);}},
        async uploadAvatar(file){if(!file)return;if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>5*1024*1024){this.fail(Error(this.ui('请选择5MB以内PNG/JPEG/WebP图片','Choose a PNG/JPEG/WebP image up to 5 MB')));return;}const bot=this.currentBot;try{const form=new FormData();form.append('file',file);form.append('sourceAppId','ai2apps.messager');const r=await fetch('/v1/platform/gallery/assets/import',{method:'POST',credentials:'same-origin',body:form});const value=await r.json();if(!r.ok)throw Error(value.error?.message||'Upload failed');if(this.currentBot?.id===bot?.id)await this.saveAvatar({kind:'image',asset_id:value.asset.id});}catch(e){this.fail(e);}},
        async dropAvatar(event){event.preventDefault();try{const ids=window.AI2AppsGalleryPicker.droppedAssetIds(event.dataTransfer);if(ids.length)await this.saveAvatar({kind:'image',asset_id:ids[0]});else await this.uploadAvatar(event.dataTransfer.files[0]);}catch(e){this.fail(e);}},
        async loadBotVoice(){void this.loadRealtimeVoice();const bot=this.currentBot;if(!bot)return;try{const [settings,catalog]=await Promise.all([window.AI2AppsBotVoice.load(bot.id),window.AI2AppsBotVoice.catalog()]);if(this.currentBot?.id!==bot.id)return;this.voiceSettings=settings;this.voiceAppliedSettings={...settings};this.voiceSaveState='saved';this.voiceModels=catalog.models;this.voiceProfiles=catalog.profiles;this.voiceCatalogNotice=!!catalog.error;this.voiceLoaded=true;}catch(e){if(this.currentBot?.id===bot.id)this.fail(e);}},
        async loadRealtimeVoice(){const id=this.currentBot?.id;this.realtimeSettings=null;this.realtimeNotice='';if(!id||this.currentBot.definition?.execution_mode!=='agent')return;try{const [settings,catalog]=await Promise.all([window.AI2AppsBotRealtimeSettings.load(id),window.AI2AppsBotRealtimeSettings.catalog()]);if(this.currentBot?.id!==id)return;this.realtimeCatalog=catalog;this.realtimeSettings=settings;this.realtimeApplied={...settings};}catch(error){if(this.currentBot?.id===id)this.realtimeNotice=error.message;}},
        get realtimeVoices(){return this.realtimeCatalog.tts.find(m=>m.id===this.realtimeSettings?.tts_model_id)?.audio_capabilities?.tts?.named_voices?.voices||[];},
        get realtimeProfiles(){return this.realtimeCatalog.profiles.filter(p=>(p.model_id||p.modelId)===this.realtimeSettings?.tts_model_id);},
        get realtimeNeedsProfile(){const t=this.realtimeCatalog.tts.find(m=>m.id===this.realtimeSettings?.tts_model_id)?.audio_capabilities?.tts||{};return !!(t.instructions?.required||(t.voice_profiles?.reference_audio&&!this.realtimeVoices.length));},
        async changeRealtimeModel(kind){if(this.realtimeSettings[kind]==='__install__'){this.realtimeSettings[kind]=this.realtimeApplied?.[kind]||null;await this.installRealtimeModel(kind);return;}if(kind==='tts_model_id'){this.realtimeSettings.voice=this.realtimeVoices[0]||null;this.realtimeSettings.profile_id=null;}await this.saveRealtimeVoice();},
        async installRealtimeModel(kind){if(this.realtimeBusy)return;const id=this.currentBot?.id;this.realtimeBusy=true;try{const result=await window.AI2AppsBotVoice.install(kind==='stt_model_id'?'speech_recognition':'speech_generation');if(this.currentBot?.id!==id)return;const catalog=await window.AI2AppsBotRealtimeSettings.catalog();if(this.currentBot?.id!==id)return;this.realtimeCatalog=catalog;const selected=result?.provider?.modelId||result?.session?.provider?.modelId;if(selected&&catalog[kind==='stt_model_id'?'stt':'tts'].some(m=>m.id===selected)){this.realtimeSettings[kind]=selected;if(kind==='tts_model_id'){this.realtimeSettings.voice=this.realtimeVoices[0]||null;this.realtimeSettings.profile_id=null;}}}catch(error){if(this.currentBot?.id===id)this.realtimeNotice=error.message;}finally{this.realtimeBusy=false;}},
        async saveRealtimeVoice(){const id=this.currentBot?.id,s=this.realtimeSettings;if(!s||this.realtimeBusy)return;if((!s.stt_model_id&&!s.tts_model_id)||(s.tts_model_id&&this.realtimeNeedsProfile&&!s.profile_id)){this.realtimeNotice=this.ui('请选择识别模型或读出模型；仅输入不需要读出模型。','Choose recognition or speech output; input-only mode needs no speech output model.');return;}this.realtimeBusy=true;try{const saved=await window.AI2AppsBotRealtimeSettings.save(id,{...s});if(this.currentBot?.id!==id)return;this.realtimeSettings=saved;this.realtimeApplied={...saved};this.realtimeNotice=saved.ready?this.ui(saved.speech_ready!==false?'已就绪，输入区可开启对话模式。':'已就绪，仅语音输入，不自动读出。',saved.speech_ready!==false?'Ready. Start conversation mode in the composer.':'Ready for voice input without automatic readout.'):this.ui('读出已配置；语音输入还需选择识别模型。','Readout configured; select a recognition model for voice input.');window.dispatchEvent(new CustomEvent('bot-realtime-settings',{detail:{botId:id}}));}catch(error){if(this.currentBot?.id===id)this.realtimeNotice=error.message;}finally{this.realtimeBusy=false;}},
        changeVoiceMode(){if(!this.voiceSettings)return;this.voiceSettings.model_id=null;this.voiceSettings.voice=null;this.voiceSettings.profile_id=null;this.saveBotVoice();},
        changeVoiceModel(){if(this.voiceSettings.model_id==='__install__'){this.voiceSettings.model_id=this.voiceAppliedSettings?.mode==='model'?this.voiceAppliedSettings.model_id:null;this.installBotVoice();return;}this.voiceSettings.voice=this.voiceModels.find(m=>m.id===this.voiceSettings.model_id)?.voices[0]||null;this.saveBotVoice();},
        async installBotVoice(){if(this.voiceInstallBusy)return;this.voiceInstallBusy=true;try{await window.AI2AppsBotVoice.install();const catalog=await window.AI2AppsBotVoice.catalog();this.voiceModels=catalog.models;this.voiceProfiles=catalog.profiles;this.voiceCatalogNotice=!!catalog.error;}catch(e){if(!/取消|cancel/i.test(e.message||''))this.fail(e);}finally{this.voiceInstallBusy=false;}},
        get botVoicePresets(){return this.voiceModels.find(m=>m.id===this.voiceSettings?.model_id)?.voices||[];},
        async saveBotVoice(){const bot=this.currentBot;if(!bot||!this.voiceLoaded||this.voiceBusy)return;const draft={...this.voiceSettings};if((draft.mode==='profile'&&!draft.profile_id)||(draft.mode==='model'&&!draft.model_id)){this.voiceSaveState='incomplete';return;}this.voiceBusy=true;this.voiceSaveState='saving';try{const saved=await window.AI2AppsBotVoice.save(bot.id,draft);if(this.currentBot?.id===bot.id){this.voiceSettings=saved;this.voiceAppliedSettings={...saved};this.voiceSaveState='saved';}}catch(e){this.fail(e);if(this.currentBot?.id===bot.id){this.voiceSettings={...this.voiceAppliedSettings};this.voiceSaveState='error';if(/changed|reload/i.test(e.message||''))await this.loadBotVoice();}}finally{this.voiceBusy=false;}},
        selectBotModel(select){if(this.botModel==='__install_more__'){this.botModel=this.botAppliedModel;if(select)select.value=this.botAppliedModel||'';void this.installBotModel();return;}controller?.setModel(this.botModel);},
        selectBotReasoning(value){void controller?.setReasoningEffort(value||null);},
        botReasoningLabel(level){return window.AI2AppsConversationModelPolicy.reasoningLabel(level,document.documentElement.lang);},
        async installBotModel(){if(this.botModelInstallBusy)return;const id=this.currentBot?.id;this.botModelInstallBusy=true;try{const result=await window.AI2AppsBotModelSelection.install();if(result?.status==='ready'&&this.currentBot?.id===id)await controller?.refreshModels?.();}catch(e){if(!/取消|cancel/i.test(e.message||''))this.fail(e);}finally{this.botModelInstallBusy=false;}},
        async saveBot(){if(!this.currentBot||this.botSaving)return;this.botSaving=true;try{if(this.currentBot.definition?.execution_mode==='flash'&&this.botEditDuty.trim()!==this.currentBot.duty){const m=this.currentBot.definition.config.model||(await window.AI2AppsBotModelSelection.resolve('')).selected;const access=await localRequest('/bots/'+this.currentBot.id+'/app-access');const apps=access.items.filter(a=>a.enabled).map(a=>({app_id:a.app_id,enabled:true}));const reviewed=await window.AI2AppsBotCreation.reviewWorkflow({request:(path,method='GET',body)=>localRequest(path,{method,body}),role:this.botEditDuty.trim(),model:m,apps});if(!reviewed)return;this.currentBot.definition=await localRequest('/bots/'+this.currentBot.id+'/flash-workflow',{method:'POST',body:{role:this.botEditDuty.trim(),model:m,apps,review_id:reviewed.review_id,expected_revision:this.currentBot.definition.revision}});}const b=await localRequest('/bots/'+this.currentBot.id,{method:'PATCH',body:{name:this.botEditName,duty:this.botEditDuty}});Object.assign(this.currentBot,b);await this.loadBots();}catch(e){this.fail(e);}finally{this.botSaving=false;}},
        showNotice(text,tone='error'){text=String(text||'');if(text===this.notice&&tone===this.noticeTone)return;clearTimeout(noticeTimer);const revision=++noticeRevision;this.notice=text;this.noticeTone=tone;if(text)noticeTimer=setTimeout(()=>{if(revision===noticeRevision)this.dismissNotice();},6000);},
        dismissNotice(){noticeRevision++;clearTimeout(noticeTimer);noticeTimer=null;this.notice='';},
        success(text) { this.showNotice(text,'success'); },
        fail(error) { this.showNotice(error.message || String(error),'error'); },
        async rotateIdentity() {
            const dialog = this.$refs.identityRotationDialog;
            if (!dialog.open || this.busy) return;
            this.busy = true;
            this.dismissNotice();
            try {
                await localRequest('/device-key/rotate', { method: 'POST' });
                this.success(tr('messager.success.identity_rotated'));
            } catch (error) {
                this.fail(error);
            } finally {
                this.busy = false;
                this.$nextTick(() => dialog.close());
            }
        },
        async refresh() { this.busy = true; this.notice = ''; try { const [friends, incoming, outgoing, inbox, unread] = await Promise.all([request('/social/friends?limit=50'), request('/social/friend-requests?direction=incoming&limit=50'), request('/social/friend-requests?direction=outgoing&limit=50'), request('/system-messages?state=all&limit=50'), request('/system-messages/unread-count')]); this.friends = friends?.items || []; this.incomingRequests = incoming?.items || []; this.outgoingRequests = outgoing?.items || []; this.inbox = inbox?.items || []; this.unreadCount = Number(unread?.unreadCount || unread?.count || 0); } catch (error) { this.fail(error); } finally { this.busy = false; } },
        async lookup() { this.busy = true; this.notice = ''; try { this.lookupProfile = await request('/public/profiles/lookup', { method: 'POST', body: { identifier: this.identifier } }); this.lookupRelationship = await request('/social/relationships/' + encodeURIComponent(this.lookupProfile.userId)); } catch (error) { this.lookupProfile = null; this.lookupRelationship = null; this.fail(error); } finally { this.busy = false; } },
        async requestFriend() { if (!this.lookupProfile) return; this.busy = true; try { await request('/social/friend-requests/' + encodeURIComponent(this.lookupProfile.userId), { method: 'POST' }); this.lookupRelationship = await request('/social/relationships/' + encodeURIComponent(this.lookupProfile.userId)); this.success(tr('messager.success.friend_requested')); await this.refresh(); } catch (error) { this.fail(error); } finally { this.busy = false; } },
        async actRequest(item, action) { this.busy = true; try { await request('/social/friend-requests/' + encodeURIComponent(item.requestId) + '/' + action, { method: 'POST' }); await this.refresh(); } catch (error) { if (error.status === 409) await this.refresh(); this.fail(error); } finally { this.busy = false; } },
        async openFriend(friend) { this.busy = true; try { this.selected = { ...friend }; await this.loadConversation(); } catch (error) { this.fail(error); } finally { this.busy = false; } },
        async loadConversation() { this.revokeMessageObjectUrls(); if (!this.selected) { this.storedMessages = []; return; } const result = await localRequest('/conversations/' + encodeURIComponent(this.selected.userId) + '/messages?limit=200'); this.storedMessages = result?.items || []; await Promise.all(this.storedMessages.map(item => this.loadAttachment(item))); },
        get conversationMessages() { return this.storedMessages.map(item => ({ ...item, outgoing: item.direction === 'outgoing' })); },
        async send() { if(this.tab==='bots')return; const body = this.draft.trim(); if ((!body && !this.draftAttachment) || !this.selected) return; if (!this.draftClientMessageId || this.draftSnapshot !== body || this.draftRecipientUserId !== this.selected.userId || this.draftSnapshotAttachmentToken !== this.draftAttachmentToken) { this.draftClientMessageId = crypto.randomUUID(); this.draftSnapshot = body; this.draftRecipientUserId = this.selected.userId; this.draftSnapshotAttachmentToken = this.draftAttachmentToken; this.uploadedAttachment = null; } const clientMessageId = this.draftClientMessageId; this.busy = true; try { if (!this.draftAttachment) { try { await localRequest('/send', { method: 'POST', body: { recipientUserId: this.selected.userId, clientMessageId, body } }); await this.loadConversation(); this.clearDraft(); this.success(tr('messager.success.sent_local')); return; } catch (error) { if (error.code === 'messager_result_unknown') { this.fail(new Error(tr('messager.error.local_result_unknown'))); return; } if (!error.retryable) throw error; } } if (this.draftAttachment && !this.uploadedAttachment) this.uploadedAttachment = await uploadRequest(this.draftAttachment); const payload = { recipientUserId: this.selected.userId, clientMessageId, ...(body ? { body } : {}), ...(this.uploadedAttachment ? { attachmentId: this.uploadedAttachment.id } : {}) }; await request('/system-messages/offline', { method: 'POST', body: payload }); await this.loadConversation(); this.clearDraft(); this.success(tr('messager.success.sent_cloud')); } catch (error) { if (this.uploadedAttachment && error.code === 'SYSTEM_MESSAGE_ATTACHMENT_NOT_AVAILABLE') { this.showNotice(tr('messager.error.attachment_result_unknown'),'error'); } else this.fail(error); } finally { this.busy = false; } },
        selectAttachment(event) { const file = event.target.files?.[0] || null; event.target.value = ''; if (!file) return; if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { this.fail(new Error(tr('messager.error.attachment_type'))); return; } if (file.size > 2 * 1024 * 1024) { this.fail(new Error(tr('messager.error.attachment_size'))); return; } if (this.draftPreviewUrl) URL.revokeObjectURL(this.draftPreviewUrl); this.draftAttachment = file; this.draftAttachmentToken = crypto.randomUUID(); this.uploadedAttachment = null; this.draftPreviewUrl = URL.createObjectURL(file); },
        removeAttachment() { if (this.draftPreviewUrl) URL.revokeObjectURL(this.draftPreviewUrl); this.draftPreviewUrl = ''; this.draftAttachment = null; this.draftAttachmentToken = ''; this.uploadedAttachment = null; },
        clearDraft() { this.draft = ''; this.draftClientMessageId = ''; this.draftSnapshot = ''; this.draftRecipientUserId = ''; this.draftSnapshotAttachmentToken = ''; this.removeAttachment(); },
        async loadAttachment(item) { if (!item.attachment?.id) return; try { const response = await fetch(API + '/system-message-attachments/' + encodeURIComponent(item.attachment.id) + '/content', { credentials: 'same-origin', headers: { Accept: item.attachment.mediaType || 'image/*' }, cache: 'no-store' }); if (!response.ok) throw new Error(tr('messager.error.attachment_load')); const url = URL.createObjectURL(await response.blob()); this.attachmentObjectUrls.push(url); item.attachmentObjectUrl = url; } catch (error) { item.attachmentError = error.message || tr('messager.error.attachment_load'); } },
        revokeMessageObjectUrls() { this.attachmentObjectUrls.forEach(url => URL.revokeObjectURL(url)); this.attachmentObjectUrls = []; },
        revokeObjectUrls() { this.revokeMessageObjectUrls(); if (this.draftPreviewUrl) URL.revokeObjectURL(this.draftPreviewUrl); },
        async readMessage(item) { if (!item.readAt) { try { const updated = await request('/system-messages/' + encodeURIComponent(item.id) + '/read', { method: 'POST' }); Object.assign(item, updated); this.unreadCount = Math.max(0, this.unreadCount - 1); } catch (error) { this.fail(error); } } },
        async readAll() { try { await Promise.all([request('/system-messages/read-all', { method: 'POST' }),this.readAllLocalNotices()]); this.inbox.forEach(item => { if (!item.readAt) item.readAt = new Date().toISOString(); }); this.unreadCount = 0; } catch (error) { this.fail(error); } },
        initials(item) { return String(item?.displayName || '?').trim().slice(0, 2).toUpperCase(); },
        shortId(value) { const text = String(value || ''); return text.length > 14 ? text.slice(0, 7) + '…' + text.slice(-5) : text; },
        kindLabel(kind) { return kind === 'user.offline_message' ? tr('messager.kind.offline') : kind === 'social.friend_request' ? tr('messager.kind.friend_request') : tr('messager.kind.system'); },
        formatTime(value) { const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value || '') : date.toLocaleString(); },
    }; };
})();
