const {test}=require('node:test');
const assert=require('node:assert/strict');
const {labelFor}=require('../web/static/js/chat_button_hints.js');
const control=(attrs={},innerText='')=>({getAttribute:k=>attrs[k]??null,innerText});
test('state-specific localized titles take precedence over generic labels',()=>{
 assert.equal(labelFor(control({title:'已复制','aria-label':'复制'})),'已复制');
});
test('icon controls use accessible names; streamed text controls need no registration',()=>{
 assert.equal(labelFor(control({'aria-label':'发送消息'})),'发送消息');
 assert.equal(labelFor(control({},'  继续任务  ')),'继续任务');
});
test('empty controls have no invented tooltip',()=>{
 assert.equal(labelFor(control()),'');
});
test('Chat mount installs once and dynamic controls show and restore their native title',()=>{
 const saved={document:global.document,addEventListener:global.addEventListener,innerWidth:global.innerWidth};
 const handlers={};let appended=0;
 const tip={style:{},setAttribute(){},getBoundingClientRect:()=>({width:200,height:30})};
 global.document={createElement:()=>tip,body:{appendChild(){appended++;}},addEventListener(){}};
 global.addEventListener=()=>{};global.innerWidth=800;
 const shell={dataset:{},contains:()=>true,addEventListener:(name,fn)=>handlers[name]=fn};
 const attrs={title:'添加附件'};
 const button={innerText:'',getAttribute:k=>attrs[k]??null,hasAttribute:k=>k in attrs,
  setAttribute:(k,v)=>attrs[k]=v,removeAttribute:k=>delete attrs[k],contains:()=>false,
  closest:selector=>selector==='button, select, [role="button"]'?button:null,
  getBoundingClientRect:()=>({left:10,width:32,top:400,bottom:432})};
 try {
  global.AI2AppsChatButtonHints.install(shell);global.AI2AppsChatButtonHints.install(shell);
  assert.equal(appended,1);
  handlers.focusin({target:button});
  assert.equal(tip.textContent,'添加附件');assert.equal(tip.hidden,false);
  assert.equal(tip.style.left,'8px');assert.equal(tip.style.top,'362px');
  assert.equal(attrs['aria-describedby'],'chat-button-hint');assert.equal(attrs.title,undefined);
  handlers.mouseout({relatedTarget:null});
  assert.equal(tip.hidden,true);assert.equal(attrs.title,'添加附件');assert.equal(attrs['aria-describedby'],undefined);
 } finally {for(const [key,value] of Object.entries(saved)) {if(value===undefined)delete global[key];else global[key]=value;}}
});
