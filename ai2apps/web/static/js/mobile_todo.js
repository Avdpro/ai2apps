function mobileTodoTree(tasks,query,showCompleted,collapsed){
    const byId=new Map(tasks.map(t=>[t.id,t])),keep=new Set(),matches=new Set();
    for(const t of tasks){if((showCompleted||t.status!=='completed')&&(t.title+' '+(t.description||'')).toLowerCase().includes(query)){matches.add(t.id);let node=t;const seen=new Set();while(node&&!seen.has(node.id)){seen.add(node.id);keep.add(node.id);node=byId.get(node.parent_id);}}}
    const children=new Map();
    for(const t of tasks){if(!keep.has(t.id))continue;const parent=keep.has(t.parent_id)?t.parent_id:null;if(!children.has(parent))children.set(parent,[]);children.get(parent).push(t);}
    for(const list of children.values())list.sort((a,b)=>(a.position||0)-(b.position||0));
    const rows=[],seen=new Set();
    function walk(parent,depth){for(const t of children.get(parent)||[]){if(seen.has(t.id))continue;seen.add(t.id);const hasChildren=children.has(t.id),expanded=!!query||!collapsed.has(t.id);rows.push({task:t,depth,hasChildren,expanded,contextOnly:!matches.has(t.id)});if(hasChildren&&expanded)walk(t.id,depth+1);}}
    walk(null,0);return rows;
}
(() => {
    'use strict';
    const mobileZh=(document.documentElement.lang||'zh').toLowerCase().startsWith('zh');
    const mobileWords={"无高亮": "No highlight", "荧光绿": "Lime", "浅黄": "Pale yellow", "浅橙": "Peach", "浅粉": "Pale pink", "浅蓝": "Pale blue", "浅紫": "Lavender", "高亮颜色已保存": "Highlight saved", "未开始": "Not started", "进行中": "In progress", "已完成": "Completed", "已暂停": "Paused", "任务已在其他页面修改。请返回列表刷新后再编辑。": "This project changed elsewhere. Return to the list and refresh before editing.", "搜索：": "Search: ", "收起": "Collapse", "展开": "Expand", "优先级": "Priority", "状态": "Status", "进度": "Progress", "父级路径": "Parent path", "这里还没有符合条件的任务": "No matching projects", "先创建一个目录，开始记录任务": "Create a directory to start adding projects", "修改项目": "Edit project", "已保存": "Saved", "进度，每步 5%": "Progress, in steps of 5%", "取消": "Cancel", "暂无文本结果": "No text output", "暂无执行记录": "No execution history", "放弃未保存的修改？": "Discard unsaved changes?", "刷新会丢弃未保存的修改，继续？": "Refreshing will discard unsaved changes. Continue?", "已刷新": "Refreshed", "目录名称": "Directory name", "刷新": "Refresh", "目录": "Directory", "新建目录": "New folder", "新建项目": "New project", "搜索项目": "Search projects", "清除": "Clear", "显示已完成": "Show completed", "‹ 返回列表": "‹ Back to list", "任务标题": "Project title", "高亮颜色": "Highlight color", "描述": "Description", "进度 (%)": "Progress (%)", "调整进度，每步 5%": "Adjust progress in steps of 5%", "保存": "Save", "标记完成": "Mark complete", "＋子任务": "+ Subproject", "执行结果": "Execution results", "标题或内容": "Title or content", "输入搜索文本": "Enter search text", "搜索": "Search", "请求失败": "Request failed", "排队中": "Queued", "执行中": "Running", "等待输入": "Waiting for input", "等待能力": "Waiting for capability", "执行结束，待确认": "Ended; awaiting confirmation", "失败": "Failed", "已取消": "Cancelled", "规划中": "Planning"};
    const mt=text=>mobileZh?text:(mobileWords[text]||text);
    const $ = id => document.getElementById(id);
    let data = {directories:[],tasks:[],runs:[]}, current = null, parent = null, busy = false, dirty = false;
    const collapsed = new Set();
    let searchQuery = '';
    const highlights = [['',mt("无高亮"),'transparent'],['lime',mt("荧光绿"),'#e4f8b4'],['yellow',mt("浅黄"),'#fff3b0'],['peach',mt("浅橙"),'#ffe2c6'],['pink',mt("浅粉"),'#fce0ed'],['blue',mt("浅蓝"),'#dceeff'],['lavender',mt("浅紫"),'#ebe1ff']];
    let highlight = '';
    function renderHighlight(){
        $('highlight-colors').replaceChildren(...highlights.map(([value,label,color])=>{
            const button=document.createElement('button');button.type='button';button.className='highlight-swatch';
            button.style.backgroundColor=color;button.textContent=value?'':'∅';button.setAttribute('aria-label',label);button.title=label;
            button.setAttribute('aria-pressed',String(highlight===value));button.disabled=busy;
            button.onclick=async()=>{
                if(busy||highlight===value)return;
                if(!current){highlight=value;dirty=true;renderHighlight();return;}
                busy=true;renderHighlight();notice('');
                try{
                    const body=Object.fromEntries(['title','description','priority','status','progress','revision'].map(k=>[k,current[k]]));
                    const saved=await api('/tasks/'+encodeURIComponent(current.id),'PUT',{...body,highlight:value});
                    current=saved;highlight=value;data.tasks=data.tasks.map(t=>t.id===saved.id?saved:t);render();notice(mt("高亮颜色已保存"));
                }catch(e){notice(e.message);}finally{busy=false;renderHighlight();}
            };return button;
        }));
    }
    const names = {not_started:mt("未开始"),in_progress:mt("进行中"),completed:mt("已完成"),paused:mt("已暂停")};
    let noticeTimer;
    const notice = text => {
        clearTimeout(noticeTimer);
        $('notice').textContent = text;
        if(text) noticeTimer=setTimeout(()=>{ $('notice').textContent=''; },3000);
    };
    async function api(path='', method='GET', body) {
        const response = await fetch('/v1/mobile/todo'+path,{method,credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},body:body ? JSON.stringify(body):undefined});
        const result = await response.json().catch(()=>({}));
        if (!response.ok) throw new Error(response.status===409 ? mt("任务已在其他页面修改。请返回列表刷新后再编辑。") : (typeof result.detail==='string' ? result.detail : result.error?.message || mt('请求失败')+' (HTTP '+response.status+')'));
        return result;
    }
    function render() {
        const selected=$('directory').value;
        $('directory').replaceChildren(...data.directories.map(d=>new Option(d.title,d.id)));
        if(data.directories.some(d=>d.id===selected)) $('directory').value=selected;
        const query=searchQuery.toLowerCase();
        $('search-summary').hidden=!searchQuery;
        $('search-query').textContent=mt("搜索：")+searchQuery;
        const tasks=data.tasks.filter(t=>t.directory_id===$('directory').value);
        const rows=mobileTodoTree(tasks,query,$('show-completed').checked,collapsed);
        $('tasks').replaceChildren();$('tasks').setAttribute('role','tree');
        for(const {task:t,depth,hasChildren,expanded,contextOnly} of rows){
            const row=document.createElement('div');row.className='task-row'+(depth?' child':'')+(contextOnly?' context-only':'');
            const color=highlights.find(([value])=>value===t.highlight)?.[2];
            if(t.highlight&&color){row.classList.add('highlighted');row.style.setProperty('--row-highlight',color);}
            row.style.setProperty('--depth',depth);row.setAttribute('role','treeitem');row.setAttribute('aria-level',depth+1);
            if(hasChildren)row.setAttribute('aria-expanded',String(expanded));
            const fold=document.createElement('button');fold.className='task-fold';fold.type='button';
            fold.textContent=hasChildren?(expanded?'⌄':'›'):'';fold.disabled=!hasChildren;
            fold.setAttribute('aria-label',(expanded?mt("收起"):mt("展开"))+' '+t.title);
            if(!hasChildren)fold.setAttribute('aria-hidden','true');
            fold.onclick=()=>{collapsed.has(t.id)?collapsed.delete(t.id):collapsed.add(t.id);render();};
            const card=document.createElement('div');card.className='task';
            const heading=document.createElement('div');heading.className='task-heading';
            function control(text,field,label){const button=document.createElement('button');button.type='button';button.className='row-edit';button.textContent=text;button.setAttribute('aria-label',label+' · '+t.title);button.onclick=()=>quickEdit(t,field);return button;}
            const title=document.createElement('button');title.type='button';title.className='task-title-link';title.textContent=t.title;title.onclick=()=>edit(t);
            heading.append(control('['+(t.priority||'C')+']','priority',mt("优先级")),title);
            const subtitle=document.createElement('div');subtitle.className='task-subtitle';
            subtitle.append(control(names[t.status],'status',mt("状态")));
            if(t.status!=='not_started'||Number(t.progress)>0){const progress=control((t.progress||0)+'%','progress',mt("进度"));progress.classList.add('task-progress');subtitle.append(progress);}
            if(contextOnly){const context=document.createElement('span');context.textContent=mt("父级路径");subtitle.append(context);}
            card.append(heading,subtitle);row.append(fold,card);$('tasks').append(row);
        }
        if(!rows.length){const p=document.createElement('p');p.className='empty';p.textContent=data.directories.length?mt("这里还没有符合条件的任务"):mt("先创建一个目录，开始记录任务");$('tasks').append(p);}
        $('new-task').disabled=!data.directories.length;
    }
    const quickDialog=document.createElement('dialog');quickDialog.className='quick-edit-dialog';quickDialog.setAttribute('aria-label',mt("修改项目"));document.body.append(quickDialog);
    function quickEdit(task,field){
        if(busy)return;
        quickDialog.replaceChildren();
        const heading=document.createElement('h2');heading.textContent={priority:mt("优先级"),status:mt("状态"),progress:mt("进度")}[field];quickDialog.append(heading);
        async function commit(value){
            if(busy)return;busy=true;quickDialog.querySelectorAll('button,input').forEach(el=>el.disabled=true);
            try{
                const latest=data.tasks.find(t=>t.id===task.id);
                const body=Object.fromEntries(['title','description','priority','status','progress','revision'].map(k=>[k,latest[k]]));
                body[field]=value;
                if(field==='status'){if(value==='completed')body.progress=100;else if(value==='not_started'||body.progress===100)body.progress=0;}
                if(field==='progress'){if(value===100)body.status='completed';else if(body.status==='completed'||(value>0&&body.status==='not_started'))body.status='in_progress';}
                const saved=await api('/tasks/'+encodeURIComponent(task.id),'PUT',body);
                data.tasks=data.tasks.map(t=>t.id===saved.id?saved:t);quickDialog.close();render();notice(mt("已保存"));
            }catch(e){notice(e.message);}finally{busy=false;quickDialog.querySelectorAll('button,input').forEach(el=>el.disabled=false);}
        }
        if(field==='progress'){
            const slider=document.createElement('input');slider.type='range';slider.min=0;slider.max=100;slider.step=5;slider.value=task.progress||0;slider.setAttribute('aria-label',mt("进度，每步 5%"));
            slider.onchange=()=>commit(Number(slider.value));quickDialog.append(slider);
        }else{
            const options=document.createElement('div');options.className='quick-edit-options';
            for(const value of field==='priority'?['U','S','A','B','C','D']:Object.keys(names)){
                const button=document.createElement('button');button.type='button';button.textContent=field==='priority'?'['+value+']':names[value];button.setAttribute('aria-pressed',String(task[field]===value));button.onclick=()=>commit(value);options.append(button);
            }quickDialog.append(options);
        }
        const cancel=document.createElement('button');cancel.type='button';cancel.textContent=mt("取消");cancel.onclick=()=>quickDialog.close();quickDialog.append(cancel);quickDialog.showModal();
    }
    quickDialog.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
    async function refresh(){data=await api();render();}
    function edit(task=null,parentId=null){
        current=task;parent=parentId;dirty=false;notice('');highlight=task?.highlight||'';renderHighlight();
        $('list-view').hidden=true;$('detail-view').hidden=false;
        $('task-title').value=task?.title||'';$('description').value=task?.description||'';$('priority').value=task?.priority||'C';$('task-status').value=task?.status||'not_started';
        $('task-progress').value=task?.progress||0;$('task-progress-slider').value=task?.progress||0;$('task-progress-slider').hidden=true;
        $('new-child').hidden=!task;$('complete').hidden=!task;$('results').hidden=!task;
        $('runs').replaceChildren();
        for(const r of data.runs.filter(r=>r.task_id===task?.id)){
            const section=document.createElement('div');section.className='run';const label=document.createElement('strong');label.textContent=({queued:mt('排队中'),running:mt('执行中'),planning:mt('规划中'),waiting_input:mt('等待输入'),waiting_capability:mt('等待能力'),ended:mt('执行结束，待确认'),completed:mt('已完成'),failed:mt('失败'),cancelled:mt('已取消')})[r.status]||r.status;
            const output=document.createElement('pre');output.textContent=r.output||r.error||mt("暂无文本结果");section.append(label,output);$('runs').append(section);
        }
        if(!$('runs').childElementCount) $('runs').textContent=mt("暂无执行记录");
    }
    function back(){if(busy)return;if(dirty&&!confirm(mt("放弃未保存的修改？")))return;dirty=false;$('detail-view').hidden=true;$('list-view').hidden=false;render();}
    async function save(){
        if(busy||!$('editor').reportValidity())return;
        busy=true;$('save').disabled=true;$('complete').disabled=true;notice('');
        try{
            const body={title:$('task-title').value,description:$('description').value,priority:$('priority').value,status:$('task-status').value,progress:Number($('task-progress').value),highlight};
            if(current)body.revision=current.revision;else{body.directory_id=data.tasks.find(t=>t.id===parent)?.directory_id||$('directory').value;body.parent_id=parent;}
            const saved=await api(current?'/tasks/'+encodeURIComponent(current.id):'/tasks',current?'PUT':'POST',body);
            current=saved;dirty=false;await refresh();edit(saved);notice(mt("已保存"));
        }catch(e){notice(e.message);}finally{busy=false;$('save').disabled=false;$('complete').disabled=false;renderHighlight();}
    }
    const progress=$('task-progress'),slider=$('task-progress-slider');
    function syncProgress(){
        if(progress.value===''||!progress.validity.valid)return;
        const value=Number(progress.value);slider.value=value;
        if(value===100)$('task-status').value='completed';
        else if($('task-status').value==='completed'||(value>0&&$('task-status').value==='not_started'))$('task-status').value='in_progress';
        dirty=true;
    }
    progress.addEventListener('focus',()=>{slider.hidden=false;slider.value=progress.value;});
    progress.addEventListener('input',syncProgress);
    progress.addEventListener('blur',()=>{setTimeout(()=>{if(document.activeElement!==slider)slider.hidden=true;},0);});
    slider.addEventListener('pointerdown',()=>slider.focus());
    slider.addEventListener('input',()=>{progress.value=slider.value;syncProgress();});
    slider.addEventListener('change',()=>{progress.value=slider.value;syncProgress();progress.blur();slider.blur();slider.hidden=true;});
    slider.addEventListener('blur',()=>{slider.hidden=true;});
    $('task-status').addEventListener('change',()=>{
        const status=$('task-status').value;
        if(status==='completed')progress.value=100;
        else if(status==='not_started'||Number(progress.value)===100)progress.value=0;
        slider.value=progress.value;dirty=true;
    });
    $('editor').oninput=()=>{dirty=true;};$('editor').onsubmit=e=>{e.preventDefault();save();};
    $('complete').onclick=()=>{$('task-status').value='completed';$('task-progress').value=100;save();};
    $('back').onclick=back;$('new-task').onclick=()=>edit();
    $('new-child').onclick=()=>{if(!busy&&(!dirty||confirm(mt("放弃未保存的修改？"))))edit(null,current.id);};
    $('refresh').onclick=async()=>{if(busy||(!$('detail-view').hidden&&dirty&&!confirm(mt("刷新会丢弃未保存的修改，继续？"))))return;try{await refresh();if(!$('detail-view').hidden){const task=data.tasks.find(t=>t.id===current?.id);if(task)edit(task);else back();}notice(mt("已刷新"));}catch(e){notice(e.message);}};
    $('add-directory').onclick=async()=>{const title=prompt(mt("目录名称"));if(!title?.trim())return;try{const d=await api('/directories','POST',{title:title.trim()});await refresh();$('directory').value=d.id;render();}catch(e){notice(e.message);}};
    $('search-tasks').onclick=()=>{$('search').value=searchQuery;$('search-dialog').showModal();$('search').focus();};
    $('cancel-search').onclick=()=>$('search-dialog').close();
    $('search-form').onsubmit=e=>{e.preventDefault();searchQuery=$('search').value.trim();$('search-dialog').close();render();};
    $('clear-search').onclick=()=>{searchQuery='';render();};
    for(const id of ['directory','show-completed'])$(id).addEventListener('input',render);
    window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
    refresh().catch(e=>notice(e.message));
})();
