const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/intelligence.js','utf8');
function setup(api){
 const elements=new Map(),chats=new Map();
 const $=selector=>{if(!elements.has(selector))elements.set(selector,{value:'',dataset:{},classList:{toggle(){}},focus(){}});return elements.get(selector);};
 const env={$,channelId:'a',selectedId:null,readerMode:'chat',mobilePanel:false,state:{articles:[]},
  channel:()=>({id:env.channelId}),conversationState:id=>{if(!chats.has(id))chats.set(id,{turns:[],draft:'',loaded:true});return chats.get(id);},
  api,esc:s=>String(s).replace(/</g,'&lt;'),empty:()=>'',icons(){},crypto:{randomUUID:()=> 'unique-request'},renderReader(){}};
 Object.assign(env,require('./intelligence_test_env.cjs'));vm.createContext(env);vm.runInContext(source.slice(source.indexOf('async function loadConversation('),source.indexOf('async function readArticle(')),env);
 return {env,$,chats,submit:()=>$('#channel-chat-form').onsubmit({preventDefault(){}})};
}
test('switching channels while awaiting an answer preserves separate drafts and histories',async()=>{
 let resolve;const {env,$,chats,submit}=setup(()=>new Promise(r=>resolve=r));
 $('#channel-chat-question').value='question A';const pending=submit();
 assert.equal(chats.get('a').sending,true);
 env.channelId='b';env.conversationState('b').draft='draft B';env.renderChannelChat();
 resolve({id:'turn-a',question:'question A',answer:'answer A',references:[]});await pending;
 assert.equal(chats.get('a').turns.length,1);assert.equal(chats.get('b').turns.length,0);
 assert.equal($('#channel-chat-question').value,'draft B');
});
test('retry reuses request and selected article; editing a question starts a new context',async()=>{
 const calls=[];let fails=true;const {env,$,chats,submit}=setup(async(path,method,body)=>{calls.push({...body});if(fails)throw Error('offline');return {id:'turn',question:body.question,answer:'ok',references:[]};});
 env.selectedId='article-a';$('#channel-chat-question').value='question';await submit();
 env.selectedId='article-b';fails=false;await submit();
 assert.deepEqual(calls[0],calls[1]);assert.equal(chats.get('a').turns.length,1);
 $('#channel-chat-question').value='new question';$('#channel-chat-question').oninput();await submit();
 assert.equal(calls[2].article_id,'article-b');
});
test('history and citation titles are escaped in the transcript',()=>{
 const {env,$}=setup(async()=>({turns:[]}));
 env.conversationState('a').turns=[{question:'<script>',answer:'<img>',references:[{number:1,article_id:'a',title:'<bad>'}]}];
 env.renderChannelChat();
 const html=$('#channel-chat-messages').innerHTML;
 assert(!html.includes('<script>'));assert(!html.includes('<img>'));assert(html.includes('&lt;bad>'));
});
