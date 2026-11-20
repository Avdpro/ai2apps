const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/intelligence.js','utf8');
function fixture(){
 const nodes={};const node=()=>({dataset:{},classList:{toggle(){}},options:[{cloneNode(){return {value:'',textContent:'Default',cloneNode:this.cloneNode};}}],replaceChildren(...children){this.options=children;},value:''});
 const chats={a:{loaded:true,loading:false,sending:false,model:'model-a',models:[{id:'model-a',name:'Model A'}],draft:'Keep draft',turns:[]},b:{loaded:true,model:'',models:[],turns:[],draft:''}};
 const surface={model:node(),reset:node(),renderTurns(){}};
 const env={channelId:'a',channel:()=>({id:env.channelId}),conversationState:id=>chats[id],syncMobile(){},mobilePanel:false,readerMode:'chat',selectedId:null,previewDraft:null,busy:true,state:{articles:[],runs:[{channel_id:'b',status:'running'}]},channelSurface:surface,window:{IntelligenceI18n:{format:k=>k}},document:{createElement:node},$:id=>nodes[id]??=node(),lt:s=>s,loadConversation(){throw Error('unexpected load');},loadChannelModels(){throw Error('unexpected catalog load');}};
 vm.createContext(env);vm.runInContext(source.slice(source.indexOf('function renderChannelChat(){'),source.indexOf("\n$('#channel-chat-question').oninput")),env);
 return {env,chats,nodes,surface};
}
test('collection refresh never locks another channel chat or loses typed draft',()=>{
 const f=fixture();f.env.renderChannelChat();
 assert.equal(f.nodes['#channel-chat-question'].disabled,false);assert.equal(f.nodes['#send-channel-chat'].disabled,false);assert.equal(f.surface.model.disabled,false);assert.equal(f.surface.model.value,'model-a');
 f.nodes['#channel-chat-question'].value='Typing during refresh';f.env.renderChannelChat();assert.equal(f.nodes['#channel-chat-question'].value,'Typing during refresh');
 f.env.state.runs.push({channel_id:'a',status:'running'});f.env.renderChannelChat();assert.equal(f.nodes['#send-channel-chat'].disabled,false);
});
test('only the active conversation request locks controls; switching channel releases them',()=>{
 const f=fixture();f.chats.a.sending=true;f.env.renderChannelChat();assert.equal(f.surface.model.disabled,true);assert.equal(f.nodes['#channel-chat-question'].disabled,true);
 f.env.channelId='b';f.env.renderChannelChat();assert.equal(f.surface.model.disabled,false);assert.equal(f.nodes['#send-channel-chat'].disabled,false);
});
test('sending freezes the selected model and article across navigation',async()=>{
 const f=fixture(),calls=[];let release;
 f.env.crypto={randomUUID:()=> 'request-123456789'};
 f.env.api=async(...args)=>{calls.push(args);await new Promise(r=>release=r);return {id:'turn',answer:'Answer'};};
 vm.runInContext(source.slice(source.indexOf("$('#channel-chat-form').onsubmit="),source.indexOf('\nasync function readArticle(')),f.env);
 f.env.renderChannelChat();f.nodes['#channel-chat-question'].value='Question';f.env.selectedId='article-a';
 const pending=f.nodes['#channel-chat-form'].onsubmit({preventDefault(){}});
 assert.equal(calls[0][0],'/channels/a/conversation');assert.equal(calls[0][2].model,'model-a');assert.equal(calls[0][2].article_id,'article-a');
 f.env.channelId='b';f.env.selectedId='article-b';f.env.renderChannelChat();release();await pending;
 assert.equal(f.chats.a.turns.length,1);assert.equal(f.chats.b.turns.length,0);assert.equal(f.chats.a.sending,false);assert.equal(f.nodes['#channel-chat-question'].disabled,false);
});
