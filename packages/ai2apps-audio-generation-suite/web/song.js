(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    const miniApp = 'ai2apps.audio-generation.song', capability = 'audio.song_generation', installOption = '__install_model__';
    const fields = ['prompt','lyrics','planning','limit','abc','seed','steps','guidance'];
    const messages = {
        en: {title:'Song Creation',model:'Song model',install:'Install model…',none:'Select a song model',notReady:' — setup required',prompt:'Musical direction',promptHint:'Describe the genre, mood, instruments, singing style and tempo.',lyrics:'Lyrics',sections:'Insert a section',verse:'Verse',chorus:'Chorus',bridge:'Bridge',outro:'Outro',lyricsHint:'Use section labels to structure your song. Leave blank for instrumental music.',planning:'Musical planning',full:'Melody and chords',melody:'Melody only',off:'Direct generation',limit:'Maximum length (seconds)',lengthHint:'The song can end earlier. Reaching the limit may cut off the ending. Maximum 120 seconds.',scoreOptions:'Use an existing score (optional)',scoreHint:'Paste or import ABC notation to use in place of automatic score planning. Maximum 128 KiB.',scoreOff:'Direct generation does not use a score. Your score stays in the draft.',import:'Import ABC score',abc:'ABC notation',clearScore:'Clear score',advanced:'Advanced',seed:'Seed',steps:'Synthesis steps',guidance:'Guidance (optional)',advancedHint:'Keep 32 steps for the verified default. Leave guidance blank for the model default. Reusing a seed helps reproduce results with identical settings.',generate:'Create song',cancel:'Cancel',save:'Save draft',outputHint:'Listen, save and drag the song from Voice Studio’s shared Preview & Output.',stage0:'Plan',stage1:'Generate music',stage2:'Synthesize',stage3:'Decode',stage4:'Save output',stages:'Generation stages',connecting:'Connecting to Voice Studio…',setup:'Install YuE2 for lyrics and score planning. Review its model terms before downloading.',ready:'Ready to create a song.',running:'Creating your song…',saving:'Saving draft…',saved:'Draft saved.',installing:'Preparing song models…',cancelled:'Generation cancelled.',complete:'Song added to Preview & Output.',limited:'Song added to Preview & Output. It reached the length limit; its ending may be cut off.',failed:'The operation failed. Please retry.',scoreLarge:'ABC score exceeds 128 KiB.',scoreInvalid:'Choose a nonempty UTF-8 ABC or text file.',imported:'Score imported.',scoreCleared:'Score cleared.',draftInvalid:'The saved draft could not be restored. Your existing draft was not overwritten.',unsupported:'Selected model does not support this planning mode.'},
        zh: {title:'歌曲创作',model:'歌曲模型',install:'安装模型…',none:'选择歌曲模型',notReady:' — 需要配置',prompt:'音乐方向',promptHint:'描述曲风、情绪、乐器、人声风格和节奏。',lyrics:'歌词',sections:'插入段落',verse:'主歌',chorus:'副歌',bridge:'桥段',outro:'尾声',lyricsHint:'使用段落标签组织歌曲；留空可生成纯音乐。',planning:'音乐规划',full:'旋律与和弦',melody:'仅旋律',off:'直接生成',limit:'最长时长（秒）',lengthHint:'歌曲可以提前自然结束；达到上限可能截断结尾。最长 120 秒。',scoreOptions:'使用已有乐谱（可选）',scoreHint:'粘贴或导入 ABC 乐谱，代替自动乐谱规划。文件不超过 128 KiB。',scoreOff:'直接生成不会使用乐谱；已有乐谱仍保留在草稿中。',import:'导入 ABC 乐谱',abc:'ABC 乐谱内容',clearScore:'清空乐谱',advanced:'高级选项',seed:'随机种子',steps:'合成步数',guidance:'引导强度（可选）',advancedHint:'默认 32 步已通过验证。引导强度留空使用模型默认值；相同设置和种子有助于复现结果。',generate:'创作歌曲',cancel:'取消',save:'保存草稿',outputHint:'在语音工坊共享「预览与输出」中试听、保存和拖出歌曲。',stage0:'规划乐谱',stage1:'生成音乐',stage2:'声学合成',stage3:'解码音频',stage4:'保存输出',stages:'生成阶段',connecting:'正在连接语音工坊…',setup:'安装 YuE2，使用歌词与乐谱规划。下载前请确认模型许可。',ready:'可以开始创作歌曲。',running:'正在创作歌曲…',saving:'正在保存草稿…',saved:'草稿已保存。',installing:'正在配置歌曲模型…',cancelled:'已取消生成。',complete:'歌曲已加入预览与输出。',limited:'歌曲已加入预览与输出；已达到时长上限，结尾可能被截断。',failed:'操作失败，请重试。',scoreLarge:'ABC 乐谱超过 128 KiB。',scoreInvalid:'请选择非空的 UTF-8 ABC 或文本文件。',imported:'乐谱已导入。',scoreCleared:'乐谱已清空。',draftInvalid:'无法恢复已保存的草稿，原草稿未被覆盖。',unsupported:'所选模型不支持此规划模式。'}
    };
    let locale='en', port, serial=0, models=[], currentModel='', busy=false, cancelling=false, status='connecting', stage=-1;
    const pending=new Map(), t=key=>messages[locale][key]||messages.en[key]||key;
    const selected=()=>models.find(m=>m.id===$('model').value);
    function state(){
        $('inputs').disabled=busy; $('save').disabled=!port||busy;
        $('generate').disabled=!port||busy||!selected()?.ready||!$('prompt').value.trim();
        $('cancel').disabled=!busy||cancelling||status!=='running';
        $('status').textContent=status==='running' && stage>=0?t('stage'+stage)+'…':t(status);
        for(const el of document.querySelectorAll('[data-stage]')){
            const n=Number(el.dataset.stage); el.classList.toggle('done',n<stage||status==='complete'||status==='limited');
            if(n===stage && status==='running')el.setAttribute('aria-current','step');else el.removeAttribute('aria-current');
        }
    }
    function planningChanged(){
        const off=$('planning').value==='off';for(const id of ['abc','abc-file','clear-score'])$(id).disabled=off;
        $('score-note').textContent=t(off?'scoreOff':'scoreHint');state();
    }
    function options(previous){
        $('model').replaceChildren(); if(!models.length)$('model').add(new Option(t('none'),''));
        for(const m of models)$('model').add(new Option(m.label+(m.ready?'':t('notReady')),m.id));
        $('model').add(new Option(t('install'),installOption));
        $('model').value=models.some(m=>m.id===previous)?previous:(models.find(m=>m.ready)?.id||models[0]?.id||'');
        currentModel=$('model').value;
        const m=selected();$('model-note').textContent=m?(m.ready?t('ready'):t('setup')):t('setup');
        $('limit').max=Math.min(120,m?.maximumSeconds||120,Math.floor((m?.maximumTokens||3000)/25));
        $('limit').value=Math.min(Number($('limit').value)||120,Number($('limit').max));
        planningChanged();
    }
    function localize(value){locale=String(value||'').toLowerCase().startsWith('zh')?'zh':'en';document.documentElement.lang=locale;document.title=t('title');document.querySelectorAll('[data-text]').forEach(el=>{el.textContent=t(el.dataset.text);});$('stages').setAttribute('aria-label',t('stages'));options(currentModel);}
    function call(operation,data={}){return new Promise((resolve,reject)=>{if(!port)return reject(new Error(t('connecting')));const id=++serial;pending.set(id,{resolve,reject});port.postMessage({id,operation,capability,...data});});}
    async function refresh(){models=(await call('audio-generation.models')).items||[];options(currentModel);}
    const draft=()=>({schema:'ai2apps.mini-app-draft/v1',miniApp,model:currentModel,...Object.fromEntries(fields.map(k=>[k,$(k).value]))});
    async function save(){await call('draft.set',{value:JSON.stringify(draft())});}
    async function setup(){if(busy)return;busy=true;status='installing';$('error').textContent='';state();try{await save();await call('setup',{installMore:true});await refresh();status=selected()?.ready?'ready':'setup';}catch(error){$('error').textContent=error.message;status='setup';}finally{busy=false;state();}}
    $('install').onclick=setup;
    $('model').onchange=()=>{if($('model').value===installOption){$('model').value=currentModel;void setup();}else options($('model').value);};
    $('planning').onchange=planningChanged;$('prompt').oninput=state;
    for(const button of document.querySelectorAll('[data-section]'))button.onclick=()=>{const box=$('lyrics');const tag=`\n[${button.dataset.section}]\n`;if(box.value.length+tag.length>4096)return;box.setRangeText(tag,box.selectionStart,box.selectionEnd,'end');box.focus();};
    $('clear-score').onclick=()=>{$('abc').value='';$('abc-file').value='';$('file-name').textContent='';status='scoreCleared';state();};
    $('abc-file').onchange=async()=>{const file=$('abc-file').files?.[0];if(!file)return;try{if(file.size>131072)throw new Error(t('scoreLarge'));const value=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer());if(!value.trim())throw new Error(t('scoreInvalid'));$('abc').value=value;$('file-name').textContent=file.name;status='imported';$('error').textContent='';}catch(error){$('error').textContent=error instanceof TypeError?t('scoreInvalid'):error.message;}finally{$('abc-file').value='';state();}};
    $('save').onclick=async()=>{if(busy)return;busy=true;status='saving';$('error').textContent='';state();try{await save();status='saved';}catch(error){status='failed';$('error').textContent=error.message;}finally{busy=false;state();}};
    $('form').onsubmit=async event=>{
        event.preventDefault();if(busy||!selected()?.ready||!$('form').reportValidity())return;
        $('error').textContent='';const model=selected(),mode=$('planning').value;
        if(!model.planningModes?.includes(mode)){$('error').textContent=t('unsupported');return;}
        if(new TextEncoder().encode($('abc').value).length>131072){$('error').textContent=t('scoreLarge');return;}
        const generation={planning_mode:mode,max_semantic_tokens:Math.floor(Number($('limit').value)*25),max_abc_tokens:4096};
        if(mode!=='off'&&$('abc').value.trim())generation.abc=$('abc').value;
        if($('guidance').value!=='')generation.guidance_scale=Number($('guidance').value);
        const payload={schema:'ai2apps.audio-generation/v2',duration_mode:'auto',model:model.id,prompt:$('prompt').value.trim(),lyrics:$('lyrics').value,seed:Number($('seed').value),steps:Number($('steps').value),generation};
        busy=true;cancelling=false;stage=-1;status='running';$('prepared-prompt').textContent=model.preferredPromptLanguage==='en'?(locale==='zh'?'生成前会通过简单 Task 模型翻译并润色音乐方向。':'The Simple Task model translates and polishes the description before generation.'):'';state();
        try{await save();if(cancelling)throw new Error(t('cancelled'));const result=await call('audio-generation.generate',{payload});$('prepared-prompt').textContent=result.preparedPrompt?(locale==='zh'?'实际生成提示词：':'Generation prompt: ')+result.preparedPrompt:'';status=result.reachedLimit?'limited':'complete';stage=4;}
        catch(error){status=cancelling?'cancelled':'failed';if(!cancelling)$('error').textContent=error.message;}
        finally{busy=false;cancelling=false;state();}
    };
    $('cancel').onclick=async()=>{cancelling=true;state();try{await call('audio-generation.cancel');}catch(error){$('error').textContent=error.message;}};
    function accept(event){
        if(event.source!==window.parent||event.data?.type!=='ai2apps:studio-connected'||event.data.version!==1||!event.ports?.[0])return;
        window.removeEventListener('message',accept);port=event.ports[0];localize(event.data.locale);
        port.onmessage=event=>{
            const data=event.data;
            if(data?.type==='ai2apps:studio-locale'){localize(data.locale);return;}
            if(data?.type==='ai2apps:studio-progress'){if(status==='running'&&Number.isInteger(data.progress?.phaseIndex)&&data.progress.phaseIndex>=0&&data.progress.phaseIndex<=4){stage=data.progress.phaseIndex;state();}return;}
            const task=pending.get(data?.id);if(!task)return;pending.delete(data.id);data.error?task.reject(new Error(data.error)):task.resolve(data.value);
        };
        (async()=>{await refresh();const raw=await call('draft.get');if(typeof raw==='string'){
            try{const d=JSON.parse(raw);if(d.schema!=='ai2apps.mini-app-draft/v1'||d.miniApp!==miniApp)throw new Error();
                for(const k of fields)if(typeof d[k]==='string')$(k).value=d[k];options(d.model);
            }catch(_){$('error').textContent=t('draftInvalid');}
        }status=selected()?.ready?'ready':'setup';state();})().catch(error=>{status='failed';$('error').textContent=error.message;state();});
    }
    localize(new URLSearchParams(location.search).get('locale')||'en');window.addEventListener('message',accept);
    window.addEventListener('load',()=>window.parent.postMessage({type:'ai2apps:studio-connect',version:1},'*'),{once:true});
    new ResizeObserver(()=>window.parent.postMessage({type:'ai2apps:mini-app-resize',version:1,height:document.documentElement.scrollHeight},'*')).observe(document.body);
})();
