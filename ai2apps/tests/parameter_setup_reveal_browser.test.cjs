const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
for(const mobile of [false,true])test(`explicit setup reveals new/existing ACPF; passive restore preserves position: ${mobile?'Mobile':'Desktop'}`,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1000,height:720},reducedMotion:'reduce'});
  await page.route('https://reveal.fixture/**',route=>{
   if(new URL(route.request().url()).pathname==='/widget.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.resolve(__dirname,'../web/static/js/agent_parameter_forms.js'),'utf8').replace('window.AI2AppsParameterForms=','window.FormView=FormView;window.AI2AppsParameterForms=')});
   return route.fulfill({contentType:'text/html',body:`<html lang="en"><style>body{margin:0}.stream{margin-top:20px;height:500px;overflow:auto}.long{height:1000px}.setup{height:600px}header{position:fixed;top:20px;height:60px;z-index:2;background:white}button{height:40px}#configure{margin-top:80px}</style><header>Toolbar</header><div class="stream"><div id="form"><button id="configure">Configure</button><div class="long"></div></div></div><script src="/widget.js"></script><script>
    window.AI2APPS_MOBILE_SURFACE=${mobile};window.calls=0;window.posts=0;window.starts=0;
    window.AI2AppsCapabilities={runSession(session,app,options){window.starts++;options.root.innerHTML='<section class="setup"><h2>Configuration heading</h2><button>Download and configure</button></section>';return new Promise(()=>{});}};
    window.view=Object.create(FormView.prototype);Object.assign(view,{root:document.querySelector('#form'),state:{install:{appId:'arbitrary.owner'}},url:'/form',save:async()=>{},errorNode:{},request:async(path,opts)=>{window.calls++;if(opts?.method==='POST')window.posts++;return {session:{id:'existing'}};}});
    document.querySelector('#configure').onclick=()=>view.install();
   </script></html>`});
  });
  await page.goto('https://reveal.fixture');
  await page.evaluate(()=>view.resume()); // restored ACPF must not move the reader
  assert.equal(await page.locator('.stream').evaluate(e=>e.scrollTop),0);
  assert.equal(await page.evaluate(()=>starts),1);
  await page.getByRole('button',{name:'Configure',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.agent-parameter-setup')===document.activeElement);
  let position=await page.locator('.agent-parameter-setup').boundingBox();assert.ok(position.y>=95&&position.y<140,JSON.stringify(position));
  assert.equal(await page.evaluate(()=>starts),1); // existing card reused, no second runner
  await page.evaluate(()=>{view.setupRoot.remove();view.setupRoot=null;document.querySelector('.stream').scrollTop=0;});
  await page.getByRole('button',{name:'Configure',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.agent-parameter-setup')===document.activeElement);
  position=await page.locator('.agent-parameter-setup').boundingBox();assert.ok(position.y>=95&&position.y<140,JSON.stringify(position));
  assert.equal(await page.evaluate(()=>starts),2);
  assert.equal(await page.evaluate(()=>posts),mobile?0:2); // never confirms or downloads
  assert.equal(await page.locator('.stream').evaluate(e=>e.scrollLeft),0);
 }finally{await browser.close();}
});
