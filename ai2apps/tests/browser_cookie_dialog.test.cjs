const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=JSON.parse(fs.readFileSync(__dirname+'/../browser/dom_helpers.json'))['handlePageAccess:0'];
function classify(buttons,specific=false){const panel={innerText:'Sign in to X. Cookie policy',matches:()=>specific,querySelectorAll:()=>buttons};return vm.runInNewContext('('+source+')()',{ai2appsDOMVisible:()=>true,document:{querySelectorAll:selector=>selector==='iframe'?[]:[panel],body:{innerText:'Sign in to X'},elementFromPoint:()=>null},innerWidth:800,innerHeight:600});}
const button=name=>({innerText:name,getAttribute:()=>null});
test('login dialog Cookie policy is authentication, not cookie consent',()=>{const result=classify([button('Sign in'),button('Create account')]);assert.equal(result.classification,'needs_user');assert.equal(result.reason,'authentication');});
test('real accept-all choice requires user preference',()=>{const result=classify([button('Accept all cookies')]);assert.equal(result.classification,'needs_user');assert.equal(result.reason,'cookie_consent');});

test('frontend and Local share identical blocker inspector',()=>{
 const sdk=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');
 const method=sdk.slice(sdk.indexOf('        async handlePageAccess('));
 const start=method.indexOf('this.callJSON(')+'this.callJSON('.length;
 const end=method.indexOf('`, [consentFrame,readOnly]',start)+1;
 assert.equal(vm.runInNewContext(method.slice(start,end)).trim(),source.trim());
});

test('optional sign-in promotion with an explicit close can be dismissed without authentication',()=>{
 const close={innerText:'',getAttribute:name=>name==='aria-label'?'Dismiss sign-in info.':null,getBoundingClientRect:()=>({left:30,top:30,right:60,bottom:60}),disabled:false};
 const panel={innerText:'Sign in and save 10% on hotels',querySelectorAll:()=>[close],querySelector:()=>null,matches:()=>false};
 const result=vm.runInNewContext('('+source+')()',{ai2appsDOMVisible:()=>true,document:{querySelectorAll:s=>s==='iframe'?[]:[panel],body:{innerText:panel.innerText},elementFromPoint:()=>close},innerWidth:800,innerHeight:600});
 assert.equal(result.classification,'safe_dismiss');assert.equal(result.reason,'optional_sign_in_prompt');
});

function iconPrompt({attrs={'data-bs-dismiss':'modal'},cls='btn-close',type='button',tag='BUTTON',text='',specific=false,obscured=false,disabled=false,shown=true}={}){
 const close={tagName:tag,type,innerText:'',className:cls,disabled,contains:()=>false,getAttribute:k=>attrs[k]||null,
  getBoundingClientRect:()=>({left:60,top:30,right:100,bottom:70})};
 const panel={innerText:text,id:'promotion',className:'modal newsletter-modal',querySelector:()=>null,
  querySelectorAll:()=>[close],matches:()=>specific};
 return vm.runInNewContext('('+source+')()',{ai2appsDOMVisible:n=>n!==close||shown,
  document:{querySelectorAll:s=>s==='iframe'?[]:[panel],body:{innerText:''},elementFromPoint:()=>obscured?panel:close},innerWidth:800,innerHeight:600});
}
test('unnamed CSS X with Bootstrap dismissal closes an image-only promotion',()=>{
 const result=iconPrompt();assert.equal(result.classification,'safe_dismiss');assert.equal(result.name,'Close');
 assert.equal(result.reason,'dismissible_prompt');
});
test('explicit close class and legacy dismiss semantics work without accessible labels',()=>{
 assert.equal(iconPrompt({attrs:{},cls:'outline modal-close'}).classification,'safe_dismiss');
 assert.equal(iconPrompt({attrs:{'data-dismiss':'modal'},cls:''}).classification,'safe_dismiss');
});
test('do not infer dismiss from arbitrary buttons, links, submit buttons or covered controls',()=>{
 for(const options of [{attrs:{},cls:'x'},{tag:'A'},{type:'submit'},{disabled:true},{shown:false},{obscured:true}]){
  assert.equal(iconPrompt(options).classification,'needs_user');
 }
});
test('unnamed dismiss does not override consent, captcha or paywall guards',()=>{
 assert.equal(iconPrompt({text:'Cookie privacy preferences',specific:true}).reason,'cookie_consent');
 assert.equal(iconPrompt({text:'Verify you are human'}).reason,'captcha');
 assert.equal(iconPrompt({text:'Subscribe to continue'}).reason,'paywall');
});
