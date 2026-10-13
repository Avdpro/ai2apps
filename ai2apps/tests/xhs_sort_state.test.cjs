const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const visibility=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8');
const source=fs.readFileSync(__dirname+'/../browser/search.py','utf8').split("XHS_SORT_STATE_SCRIPT = r'''")[1].split("'''")[0];
function read(order,{hiddenClone=true,opacity='0.00001',ariaHidden=true,selected='likes',hiddenReal=false}={}){
 const nodes=[];
 function node(text='',parent=null,attrs={},style={}){const n={innerText:text,parentElement:parent,children:[],className:attrs.class||'',hidden:false,getAttribute:key=>attrs[key]??null,style:{display:'block',visibility:'visible',opacity:'1',...style},getBoundingClientRect:()=>({width:100,height:20,toJSON:()=>({x:10,y:20,width:100,height:20})}),contains(other){for(let p=other;p;p=p.parentElement)if(p===this)return true;return false;}};if(parent)parent.children.push(n);nodes.push(n);return n;}
 const group=node('排序依据 综合 最新 最多点赞');node('排序依据',group);const row=node('综合 最新 最多点赞',group);
 for(const [key,label] of [['general','综合'],['latest','最新'],['likes','最多点赞']]){
  if(hiddenClone){const copy=node(label,row,{'aria-hidden':ariaHidden?'true':null,class:key==='general'?'tags active':'tags'},{opacity});node(label,copy);}
  const real=node(label,row,{class:key===selected?'tags active':'tags'},{display:hiddenReal?'none':'block'});node(label,real);
 }
 node('筛选');
 const topical=node('综合',null,{class:'tab active'});node('综合',topical);
 return vm.runInNewContext(`${visibility};(${source})`,{location:{hostname:'www.xiaohongshu.com',pathname:'/search_result'},document:{querySelectorAll:()=>nodes},getComputedStyle:n=>n.style})(order);
}
test('XHS verifies real selected sort despite stale aria-hidden duplicate controls',()=>{const s=read('likes');assert.equal(s.verified,true);assert.equal(s.selected_order,'最多点赞');});
test('XHS ignores transparent duplicate controls even without aria-hidden',()=>{assert.equal(read('likes',{ariaHidden:false}).verified,true);});
test('XHS never treats hidden stale general selection or unrelated topic tab as selected',()=>{assert.equal(read('general').verified,false);});
test('XHS verifies general and latest real selection',()=>{for(const order of ['general','latest'])assert.equal(read(order,{selected:order}).verified,true);});
test('XHS refuses a hidden real option and a stale selected clone',()=>{assert.equal(read('general',{selected:'general',hiddenReal:true}).verified,false);});
test('X sort verification also ignores stale hidden duplicate tabs',()=>{
 const xSource=fs.readFileSync(__dirname+'/../browser/search.py','utf8').split("X_SEARCH_SORT_SCRIPT = r'''")[1].split("'''")[0];
 const tab=(hidden,selected)=>({parentElement:hidden?{getAttribute:k=>k==='aria-hidden'?'true':null}:null,innerText:'Latest',getAttribute:k=>k==='aria-selected'?String(selected):null,matches:()=>true,href:'https://x.com/search?q=coffee&f=live',getBoundingClientRect:()=>({width:40,height:20,toJSON:()=>({width:40,height:20})})});
 const context={URL,location:{hostname:'x.com',pathname:'/search',href:'https://x.com/search?q=coffee&f=live'},getComputedStyle:()=>({display:'block',visibility:'visible'}),document:{querySelectorAll:()=>[tab(true,true),tab(false,false)]}};
 const read=vm.runInNewContext(visibility+';('+xSource+')',context);assert.equal(read('latest','coffee').verified,false);context.document.querySelectorAll=()=>[tab(true,false),tab(false,true)];assert.equal(read('latest','coffee').verified,true);
});
