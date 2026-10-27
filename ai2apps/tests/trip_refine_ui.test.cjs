const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../../packages/ai2apps-trip-planner/web');
for(const width of [390,1100])test('Refine saved offers, confirm affected requery, edit dates and restore at '+width,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script[^>]*src="[^"]*"[^>]*><\/script>/g,'').replace(/<link[^>]*>/g,'');
  await page.route('https://trip.test/**',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('https://trip.test/?locale=zh');await page.addStyleTag({path:path.join(root,'travel.css')});
  await page.evaluate(()=>{
   const trip={origin:'SFO',destination:'Beijing',departure:'2027-06-01',return_date:'2027-06-05',hotel_checkin:'2027-06-01',hotel_checkout:'2027-06-05',nights:4,adults:1,purpose:'leisure',preferences:'',hotel_area:'Summer Palace',flight_cabin:'economy',nonstop_only:false,hotel_bed:'any',hotel_breakfast:'any',hotel_near_transit:false,airline_preference:''};
   const item={id:'a',title:'Observed direct flight',details:'United Nonstop',quote:'United Nonstop $900 round trip',price_text:'$900',price_basis:'round trip',recommended:true,url:'https://www.google.com/travel/flights'};
   const hotel={...item,id:'h',title:'Saved hotel near metro',details:'1 king bed Subway Access',quote:'1 king bed Subway Access $300',url:'https://www.booking.com/hotel/cn/example.html'};
   window.tasks={oldflight:{id:'oldflight',status:'completed',capability:'query',result:{items:[item],status:'complete'}},oldhotel:{id:'oldhotel',status:'completed',capability:'query',result:{items:[hotel],status:'complete'}}};window.calls=[];window.trip=trip;window.item=item;
   window.persisted=JSON.stringify({schema:'ai2apps.mini-app-draft/v1',miniApp:'ai2apps.trip-planner',workflowSchema:'trip/v1',trip,form:trip,profile:'default',jobs:[{id:'oldflight',requestId:'f',provider:'google_flights',leg:'outbound',trip,status:'completed'},{id:'oldhotel',requestId:'h',provider:'booking',trip,status:'completed'}],sources:['google_flights','booking']});
   window.nextRefine={action:'filter',sort_by:'price_asc',trip:{...trip,nonstop_only:true},sources:[],questions:[],explanation:'从已读取航班中筛选直飞',selection:[{task_id:'oldflight',item_id:'a',item,provider:'google_flights',leg:'outbound',reason:'已观察到 Nonstop'}]};
   window.AI2AppsWebAgent={startup:async()=>({profiles:[{key:'default',is_default:true}],draft:window.persisted}),saveDraft:async v=>{window.persisted=JSON.stringify(v)},onTask:cb=>window.cb=cb,watch:async()=>{},task:async id=>window.tasks[id],openResult:async()=>{},submit:async(capability,parameters,options)=>{window.calls.push({capability,parameters,options});const id='new'+window.calls.length;const result=capability==='refine'?window.nextRefine:{items:[{...item,title:parameters.leg==='return'?'Observed return flight':'Updated outbound flight'}],status:'complete',leg:parameters.leg};return window.tasks[id]={id,capability,status:'completed',result};}};
  });
  for(const f of ['i18n.js','travel.js'])await page.addScriptTag({path:path.join(root,f)});
  await page.getByText('Saved hotel near metro',{exact:true}).waitFor();
  await page.getByRole('button',{name:'查看 / 查询返程航班'}).click();await page.getByText('Observed return flight',{exact:true}).waitFor();
  assert.deepEqual((await page.evaluate(()=>window.calls)).map(c=>c.parameters.leg),['return']);
  await page.locator('#refine-request').fill('找最便宜的直飞');await page.locator('#refine').click();
  await page.getByText('优化后的候选',{exact:true}).waitFor();assert.equal(await page.locator('#tasks').isHidden(),true);
  assert.equal((await page.evaluate(()=>window.calls)).filter(c=>c.capability==='query').length,1);
  await page.locator('#show-original').click();assert.equal(await page.locator('#tasks').isVisible(),true);
  await page.evaluate(()=>window.cb(Object.values(window.tasks).find(t=>t.capability==='refine')));assert.equal(await page.locator('#tasks').isVisible(),true);
  await page.evaluate(()=>window.nextRefine={action:'requery',sort_by:'price_asc',trip:{...window.trip,flight_cabin:'business'},sources:['google_flights'],selection:[],questions:[],explanation:'商务舱需要重新查询'});
  await page.locator('#refine-request').fill('有没有便宜的商务舱');await page.locator('#refine').click();
  await page.getByRole('button',{name:'确认修改并重查'}).waitFor();assert.equal((await page.evaluate(()=>window.calls)).filter(c=>c.capability==='query').length,1);
  assert.match(await page.locator('#proposal').textContent(),/经济舱.*商务舱/s);
  await page.getByRole('button',{name:'确认修改并重查'}).dblclick();await page.getByText('Observed return flight',{exact:true}).waitFor();
  let calls=await page.evaluate(()=>window.calls);let queries=calls.filter(c=>c.capability==='query');assert.equal(queries.length,3);assert.deepEqual(queries.slice(1).map(c=>c.parameters.leg),['outbound','return']);assert.ok(queries.slice(1).every(c=>c.parameters.trip.flight_cabin==='business'));
  assert.equal(calls[2].parameters.previous_refinement,'new2');await page.getByText('Saved hotel near metro',{exact:true}).waitFor();
  await page.locator('#result-dates').evaluate(n=>n.open=true);await page.locator('#result-hotel_checkout').fill('2027-06-06');await page.locator('#refresh-hotels').click();
  await page.getByRole('button',{name:'确认修改并重查'}).waitFor();assert.equal((await page.evaluate(()=>window.calls)).filter(c=>c.capability==='query').length,3);
  await page.getByRole('button',{name:'确认修改并重查'}).click();await page.waitForFunction(()=>window.calls.filter(c=>c.capability==='query').length===4);
  queries=(await page.evaluate(()=>window.calls)).filter(c=>c.capability==='query');assert.equal(queries[3].parameters.provider,'booking');assert.equal(queries[3].parameters.trip.hotel_checkout,'2027-06-06');assert.equal(queries[3].parameters.trip.return_date,'2027-06-05');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.locator('#show-history').click();await page.locator('#history').getByText('Saved hotel near metro',{exact:true}).waitFor();
  const stored=await page.evaluate(()=>({draft:window.persisted,tasks:window.tasks}));
  await page.reload();await page.addStyleTag({path:path.join(root,'travel.css')});await page.evaluate(stored=>{window.submits=0;window.AI2AppsWebAgent={startup:async()=>({profiles:[{key:'default',is_default:true}],draft:stored.draft}),saveDraft:async()=>{},onTask:()=>{},watch:async()=>{},task:async id=>stored.tasks[id],submit:async()=>{window.submits++;throw Error('unexpected search')}};},stored);
  for(const f of ['i18n.js','travel.js'])await page.addScriptTag({path:path.join(root,f)});
  await page.getByText('Observed return flight',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>window.submits),0);assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
