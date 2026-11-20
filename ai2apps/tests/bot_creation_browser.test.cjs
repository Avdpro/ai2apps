const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
test('type menu opens a full sidebar draft; cancel writes nothing and retries create exactly once',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width:900,height:760}}),submissions=[];let failOnce=true,holdOptions=true,releaseOptions;
 await page.route('https://creation.fixture/**',async route=>{
  const u=new URL(route.request().url());
  if(u.pathname==='/entry')return route.fulfill({contentType:'text/html',body:fs.readFileSync(__dirname+'/fixtures/bot_creation_sidebar.html','utf8')});
  if(u.pathname.startsWith('/js/')||u.pathname.startsWith('/css/'))return route.fulfill({path:path.join(__dirname,'../web/static',u.pathname)});
  if(u.pathname.endsWith('/bot-creation/options')){if(holdOptions){holdOptions=false;await new Promise(resolve=>releaseOptions=resolve);}return route.fulfill({json:{default_duty:'Helpful assistant',access:{review_hash:'a'.repeat(64),items:[{app_id:'fixture.app',name:'Fixture App',kind:'app',available:true,selected:false,enabled:false},{app_id:'mini:fixture',name:'Fixture Mini',owner_name:'Fixture Studio',kind:'mini-app',available:true,selected:false,enabled:false}]}}});}
  if(u.pathname.endsWith('/bot-creation')){submissions.push(route.request().postDataJSON());if(failOnce){failOnce=false;return route.fulfill({status:503,json:{error:{message:'Unknown result'}}});}return route.fulfill({status:201,json:{id:'created',name:'My Bot',duty:'Helpful assistant'}});}
  return route.fulfill({json:{}});
 });
 await page.goto('https://creation.fixture/entry');
 await page.getByRole('button',{name:'New Bot',exact:true}).click();
 assert.equal(await page.getByRole('menuitem').count(),7);assert.equal(await page.locator('[role=menuitem]:disabled').count(),2);await page.mouse.click(600,100);assert.equal(await page.getByRole('menu').count(),0);await page.getByRole('button',{name:'New Bot',exact:true}).click();await page.getByRole('menu').waitFor();
 await page.getByRole('menuitem',{name:/Standard Bot/}).click();await page.getByLabel('Name',{exact:true}).fill('Cancelled');await page.getByLabel('Role',{exact:true}).fill('My draft role');releaseOptions();await page.waitForFunction(()=>document.querySelector('.bc-primary')&&!document.querySelector('.bc-primary').disabled);assert.equal(await page.getByLabel('Role',{exact:true}).inputValue(),'My draft role');
 assert.equal(await page.getByText('Existing Bot list',{exact:true}).isVisible(),false);assert.equal(await page.locator('dialog').count(),0);
 await page.getByRole('button',{name:'Cancel',exact:true}).click();assert.equal(submissions.length,0);await page.getByText('Existing Bot list',{exact:true}).waitFor();
 await page.getByRole('button',{name:'New Bot',exact:true}).click();await page.getByRole('menuitem',{name:/Standard Bot/}).click();
 await page.getByLabel('Name',{exact:true}).fill('My Bot');await page.getByRole('checkbox',{name:/Fixture Mini/}).check();await page.getByRole('combobox',{name:'Avatar style'}).selectOption('owl');
 const layout=await page.locator('.bc-create').evaluate(e=>({width:e.scrollWidth,client:e.clientWidth,bottom:e.querySelector('footer').getBoundingClientRect().bottom}));assert(layout.width<=layout.client);assert(layout.bottom<=760);await page.screenshot({path:'/tmp/bot-create-sidebar.png'});
 await page.getByRole('button',{name:'Create Bot',exact:true}).click();await page.getByRole('button',{name:'Retry',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Cancel',exact:true}).isDisabled(),true);
 await page.getByRole('button',{name:'Retry',exact:true}).click();await page.waitForFunction(()=>window.created?.id==='created');assert.equal(submissions.length,2);assert.deepEqual(submissions[0],submissions[1]);assert.equal(submissions[0].avatar.preset,'owl');assert.equal(submissions[0].model_id,'fixture');assert.deepEqual(submissions[0].apps,[{app_id:'mini:fixture',enabled:true}]);
 }finally{await browser.close();}
});

test('Flash creation selects a pinned workflow without model or App access',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width:900,height:760}}),submissions=[];
 await page.route('https://flash.fixture/**',async route=>{
  const u=new URL(route.request().url());
  if(u.pathname==='/entry')return route.fulfill({contentType:'text/html',body:fs.readFileSync(__dirname+'/fixtures/bot_creation_sidebar.html','utf8')});
  if(u.pathname.startsWith('/js/')||u.pathname.startsWith('/css/'))return route.fulfill({path:path.join(__dirname,'../web/static',u.pathname)});
  if(u.pathname.endsWith('/bot-creation/options'))return route.fulfill({json:{default_duty:'Standard duty',flash_workflows:[{id:'calculator',version:'1',name:'数学表达式计算',name_en:'Calculator',description:'Calculate fixed expressions.'}],access:{review_hash:'a'.repeat(64),items:[{app_id:'fixture',name:'Unused App',kind:'app',available:true,selected:true,enabled:true}]}}});
  if(u.pathname.endsWith('/bot-creation')){submissions.push(route.request().postDataJSON());return route.fulfill({status:201,json:{id:'flash-created',name:'Calculator'}});}
  return route.fulfill({json:{}});
 });
 await page.goto('https://flash.fixture/entry');await page.getByRole('button',{name:'New Bot',exact:true}).click();await page.getByRole('menuitem',{name:/Flash-Bot/}).click();
 await page.getByRole('heading',{name:'Create Flash-Bot'}).waitFor();await page.getByLabel('Fixed workflow',{exact:true}).selectOption('calculator');
 assert.equal(await page.getByLabel('Fixed workflow',{exact:true}).inputValue(),'calculator');assert.equal(await page.getByLabel('Name',{exact:true}).inputValue(),'Calculator');
 assert.equal(await page.getByLabel('Conversation model',{exact:true}).count(),0);assert.equal(await page.locator('.bc-access').isVisible(),false);assert.equal(await page.getByLabel('Role',{exact:true}).getAttribute('readonly'),null);
 await page.getByRole('button',{name:'Create Bot',exact:true}).click();await page.waitForFunction(()=>window.created?.id==='flash-created');
 assert.equal(submissions.length,1);assert.equal(submissions[0].bot_type,'flash');assert.equal(submissions[0].model_id,null);assert.deepEqual(submissions[0].apps,[]);assert.deepEqual(submissions[0].definition.config,{workflow_id:'calculator',workflow_version:'1'});
 }finally{await browser.close();}
});

test('custom Flash Role compiles and requires review before creation',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage(),created=[],compiled=[];
 const plan={name:'Japanese translation',usage:'Enter text to translate into Japanese.',input_kind:'text',adapt_input:false,steps:[{kind:'ai',instruction:'Translate into Japanese. Return translation only.',arguments:{}}]};
 await page.route('https://custom.fixture/**',async route=>{
  const u=new URL(route.request().url());
  if(u.pathname==='/entry')return route.fulfill({contentType:'text/html',body:fs.readFileSync(__dirname+'/fixtures/bot_creation_sidebar.html','utf8')});
  if(u.pathname.startsWith('/js/')||u.pathname.startsWith('/css/'))return route.fulfill({path:path.join(__dirname,'../web/static',u.pathname)});
  if(u.pathname.endsWith('/bot-creation/options'))return route.fulfill({json:{flash_workflows:[{id:'calculator',version:'1',name:'Calculator',description:'Calculate.'}],access:{review_hash:'a'.repeat(64),items:[]}}});
  if(u.pathname.endsWith('/flash-workflows/compile')){compiled.push(route.request().postDataJSON());return route.fulfill({json:{review_id:'b'.repeat(64),plan}});}
  if(u.pathname.endsWith('/bot-creation')){created.push(route.request().postDataJSON());return route.fulfill({status:201,json:{id:'custom'}});}
  return route.fulfill({json:{}});
 });
 await page.goto('https://custom.fixture/entry');await page.getByRole('button',{name:'New Bot',exact:true}).click();await page.getByRole('menuitem',{name:/Flash-Bot/}).click();
 await page.getByLabel('Fixed workflow',{exact:true}).waitFor();
 assert.equal(await page.getByLabel('Fixed workflow',{exact:true}).inputValue(),'custom');
 assert.equal(await page.getByLabel('Role',{exact:true}).isEditable(),true);
 await page.getByLabel('Fixed workflow',{exact:true}).selectOption('calculator');
 await page.getByLabel('Name',{exact:true}).fill('Japanese');await page.getByLabel('Role',{exact:true}).fill('Translate text into Japanese.');
 assert.equal(await page.getByLabel('Fixed workflow',{exact:true}).inputValue(),'custom');
 assert.equal(await page.getByLabel(/Execution model/).isEnabled(),true);
 await page.getByRole('button',{name:'Create Bot',exact:true}).click();await page.getByRole('dialog').waitFor();
 assert.equal(created.length,0);
 const layout=await page.locator('dialog').evaluate(e=>({height:e.getBoundingClientRect().height,viewport:innerHeight,scroll:e.scrollWidth,width:e.clientWidth}));assert(layout.height<layout.viewport);assert(layout.scroll<=layout.width);assert.equal(await page.locator('dialog details[open]').count(),0);await page.screenshot({path:'/tmp/flash-review-desktop.png'});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'/tmp/flash-review-mobile.png'});assert.equal(await page.getByRole('button',{name:'Confirm workflow',exact:true}).isVisible(),true);
 assert.equal(compiled[0].model,'fixture');assert.deepEqual(compiled[0].apps,[]);
 await page.getByRole('button',{name:'Edit',exact:true}).click();await page.getByLabel('Role',{exact:true}).fill('Translate text into Japanese, without explanations.');
 await page.getByRole('button',{name:'Create Bot',exact:true}).click();await page.getByRole('button',{name:'Confirm workflow',exact:true}).click();await page.waitForFunction(()=>window.created?.id==='custom');
 assert.equal(compiled.length,2);assert.equal(created.length,1);assert.equal(created[0].definition.config.workflow_id,'custom');assert.deepEqual(created[0].definition.config.plan,plan);
 }finally{await browser.close();}
});

test('Research Bot template is prefilled and creates a separate customizable Standard Bot',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),submissions=[];
  await page.route('https://research.fixture/**',async route=>{
   const u=new URL(route.request().url());
   if(u.pathname==='/entry')return route.fulfill({contentType:'text/html',body:fs.readFileSync(__dirname+'/fixtures/bot_creation_sidebar.html','utf8')});
   if(u.pathname.startsWith('/js/')||u.pathname.startsWith('/css/'))return route.fulfill({path:path.join(__dirname,'../web/static',u.pathname)});
   if(u.pathname.endsWith('/bot-creation/options'))return route.fulfill({json:{
    templates:[{id:'research',name:{en:'Research Bot'},role:{en:'Use public sources and cite findings.'},avatar:{preset:'compass',color:'#2563eb'},app_ids:['search']}],
    access:{review_hash:'a'.repeat(64),items:[
     {app_id:'search',kind:'mini-app',name:'Search All',available:true},
     {app_id:'other',kind:'app',name:'Other App',available:true,selected:true,enabled:true},
    ]},
   }});
   if(u.pathname.endsWith('/bot-creation')){submissions.push(route.request().postDataJSON());return route.fulfill({status:201,json:{id:'custom-research'}});}
   return route.fulfill({json:{}});
  });
  await page.goto('https://research.fixture/entry');
  await page.getByRole('button',{name:'New Bot',exact:true}).click();
  await page.getByRole('menuitem',{name:/Research Bot/}).click();
  await page.waitForFunction(()=>document.querySelector('.bc-primary')?.disabled===false);
  assert.equal(await page.getByLabel('Name',{exact:true}).inputValue(),'Research Bot');
  assert.equal(await page.getByLabel('Role',{exact:true}).inputValue(),'Use public sources and cite findings.');
  assert.equal(await page.getByRole('checkbox',{name:'Search All'}).isChecked(),true);
  assert.equal(await page.getByRole('checkbox',{name:'Other App'}).isChecked(),false);
  await page.getByLabel('Name',{exact:true}).fill('Recipe Research');
  await page.getByLabel('Role',{exact:true}).fill('Compare public recipes.');
  await page.getByRole('checkbox',{name:'Search All'}).uncheck();
  await page.getByRole('button',{name:'Create Bot',exact:true}).click();
  await page.waitForFunction(()=>window.created?.id==='custom-research');
  assert.equal(submissions.length,1);
  assert.equal(submissions[0].bot_type,'standard');
  assert.equal(submissions[0].template_id,'research');
  assert.equal(submissions[0].name,'Recipe Research');
  assert.equal(submissions[0].duty,'Compare public recipes.');
  assert.deepEqual(submissions[0].apps,[]);
 }finally{await browser.close();}
});
