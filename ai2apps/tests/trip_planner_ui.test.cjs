const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../../packages/ai2apps-trip-planner/web');
for(const words of [['Summer Palace','A hotel near the palace'],['Option alpha','Option beta']])test('Recycled option meaning invalidates its old ref: '+words[0],async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.setContent('<div role="option" tabindex="0"></div><input aria-label="City" value="original">');
 const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8'),snapshot=fs.readFileSync(__dirname+'/../web/static/js/browser_snapshot.js','utf8');
 const result=await page.evaluate(({visible,snapshot,words})=>{window.ai2appsDOMVisible=eval('('+visible+')');const read=()=>eval('('+snapshot+')')({maxItems:20,maxText:1000,maxHtml:3000,htmlMode:'visible'});document.querySelector('[role=option]').textContent=words[0];const before=read();document.querySelector('[role=option]').textContent=words[1];document.querySelector('input').value='edited';return {before,after:read()};},{visible,snapshot,words});
 assert.notEqual(result.before.items.find(x=>x.role==='option').ref,result.after.items.find(x=>x.role==='option').ref);
 assert.equal(result.before.items.find(x=>x.editable).ref,result.after.items.find(x=>x.editable).ref);
 }finally{await browser.close();}
});
test('Travel reader includes selected trip type and cabin without hidden menu choices',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.setContent('<div role="combobox">One way</div><div role="combobox">Business</div><div hidden><div role="combobox">First class</div></div><li>United Airlines Nonstop 11 hr 30 min PEK–SFO 834 kg CO2e $673</li>');
 const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8');
 const script=fs.readFileSync(__dirname+'/../browser/travel_reader.py','utf8').match(/SCRIPT = r'''([\s\S]*?)'''/)[1];
 const result=await page.evaluate(({visible,script})=>{window.ai2appsDOMVisible=eval('('+visible+')');return eval('('+script+')')('google_flights');},{visible,script});
 assert.deepEqual(result.controls.map(x=>x.value),['One way','Business']);
 assert.equal(result.observed_items.length,1);
 }finally{await browser.close();}
});
for(const width of [390,1100])test('Trip Planner progressive source results, manual summary and restoration at '+width,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage({viewport:{width,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 let html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script[^>]*src="[^"]*"[^>]*><\/script>/g,'').replace(/<link[^>]*>/g,'');
 await page.route('https://trip.test/**',route=>route.fulfill({contentType:'text/html',body:html}));await page.goto('https://trip.test/?locale=zh');await page.addStyleTag({path:path.join(root,'travel.css')});
 await page.evaluate(()=>{
 window.mockTasks={};window.calls=[];window.opened=[];window.persisted=null;
 const trip={origin:'SFO',destination:'Tokyo (NRT)',departure:'2027-06-01',return_date:'2027-06-05',hotel_checkin:'2027-06-02',hotel_checkout:'2027-06-05',nights:4,adults:1,purpose:'business',preferences:'会场附近'};
 window.AI2AppsWebAgent={startup:async()=>({profiles:[{key:'default',is_default:true}],draft:window.persisted}),saveDraft:async value=>{window.persisted=JSON.stringify(value);},onTask:cb=>window.taskCallback=cb,watch:async()=>{},task:async id=>window.mockTasks[id],location:async()=>({latitude:37.77,longitude:-122.42,accuracy_m:1500}),openResult:async(id,url)=>window.opened.push([id,url]),submit:async(capability,parameters,options)=>{window.calls.push({capability,parameters,options});const id='task'+window.calls.length;let result={};let status='queued';if(capability==='prepare'){status='completed';result={assigned:{trip_prepare:{trip,sources:['google_flights','booking'],questions:['请确认东京机场'],notes:'已整理'}}};}if(capability==='summarize'){status='completed';result={assigned:{itinerary:{summary:'根据已读取的酒店安排',days:[{day:'第一天',plan:'入住并预留交通时间'}],limitations:'机票仍未完成'}}};}return window.mockTasks[id]={id,status,capability,result};}};
 });
 await page.addScriptTag({path:path.join(root,'i18n.js')});await page.addScriptTag({path:path.join(root,'travel.js')});
 await page.waitForFunction(()=>!document.getElementById('profile').disabled);assert.equal(await page.locator('#status').textContent(),'');
 await page.locator('#request').fill('去东京出差四晚，看看机票酒店');await page.locator('#prepare').click();await page.getByText('请确认东京机场',{exact:false}).waitFor();
 assert.equal(await page.locator('#hotel_checkin').inputValue(),'2027-06-02');
 await page.locator('#destination_airport').fill('虹桥');await page.locator('#excluded_airports').fill('浦东, PVG');await page.locator('[name=source][value=sights]').uncheck();await page.locator('#search').click();await page.waitForFunction(()=>window.calls.filter(c=>c.capability==='query').length===3);
 assert.equal(await page.locator('.source').count(),3);
 const ids=await page.evaluate(()=>Object.values(window.mockTasks).filter(t=>t.capability==='query').map(t=>t.id));
 await page.evaluate(id=>window.taskCallback({...window.mockTasks[id],status:'completed',result:{provider:'booking',url:'https://www.booking.com/searchresults.html',criteria_note:'已读取酒店，日期请核对',criteria_verified:true,status:'complete',items:[{title:'Sakura Hotel',details:'车站附近',quote:'Sakura Hotel USD 240',price_text:'USD 240',price_basis:'per night',recommended:true,recommendation_reason:'Near requested landmark'}]}}),ids[2]);
 await page.getByText('Sakura Hotel',{exact:true}).waitFor();assert.equal(await page.locator('.source .badge').first().textContent(),'排队中');assert.equal(await page.locator('#summarize').isEnabled(),true);
 await page.evaluate(id=>window.taskCallback({...window.mockTasks[id],status:'completed',result:{status:'partial',items:[],criteria_note:'Home page has no matching flights'}}),ids[0]);await page.getByText('未查到匹配结果',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'重试此来源'}).count(),1);
 await page.getByRole('button',{name:'打开来源网站'}).click();assert.equal((await page.evaluate(()=>window.opened)).length,1);
 await page.locator('#summarize').click();await page.getByText('根据已读取的酒店安排',{exact:true}).waitFor();
 const calls=await page.evaluate(()=>window.calls);assert.equal(calls.filter(c=>c.capability==='query').length,3);assert.equal(calls.at(-1).capability,'summarize');assert.deepEqual(calls.at(-1).parameters.source_tasks,[ids[0],ids[2]]);
 assert.equal(calls[1].parameters.trip.hotel_checkin,'2027-06-02');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 if(width===390)await page.screenshot({path:'/tmp/trip-planner-mobile.png',fullPage:true});
 const stored=await page.evaluate(()=>({draft:window.persisted,tasks:window.mockTasks}));
 // Model the existing Task store and draft across a fresh client page.
 stored.tasks[ids[2]].status='completed';stored.tasks[ids[2]].result={provider:'booking',url:'https://www.booking.com/searchresults.html',criteria_note:'已读取酒店',items:[{title:'Sakura Hotel',details:'车站附近',quote:'Sakura Hotel USD 240',price_text:'USD 240',price_basis:'per night',recommended:true,recommendation_reason:'Near requested landmark'}]};
 await page.reload();await page.addStyleTag({path:path.join(root,'travel.css')});
 await page.evaluate(stored=>{window.resumeSubmits=0;window.AI2AppsWebAgent={startup:async()=>({profiles:[{key:'default',is_default:true}],draft:stored.draft}),saveDraft:async()=>{},onTask:cb=>window.taskCallback=cb,watch:async()=>{},task:async id=>stored.tasks[id],submit:async()=>{window.resumeSubmits++;throw Error('must not resubmit');}};},stored);
 await page.addScriptTag({path:path.join(root,'i18n.js')});await page.addScriptTag({path:path.join(root,'travel.js')});
 await page.getByText('Sakura Hotel',{exact:true}).waitFor();await page.getByText('根据已读取的酒店安排',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>window.resumeSubmits),0);
 assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
test('Device location requires explicit consent, rounds coordinates and cancels without browser access',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.route('https://location.test',r=>r.fulfill({body:'<html lang="zh"><body></body></html>',contentType:'text/html'}));await page.goto('https://location.test');
 const source=fs.readFileSync(path.resolve(__dirname,'../web/static/js/studio_mini_apps.js'),'utf8');const start=source.indexOf('    async function requestDeviceLocation('),end=source.indexOf('\n    function mobileResultURL',start);await page.addScriptTag({content:source.slice(start,end)+'\nwindow.requestLocation=requestDeviceLocation;'});
 await page.evaluate(()=>{window.geoCalls=0;Object.defineProperty(navigator,'geolocation',{value:{getCurrentPosition(ok){window.geoCalls++;ok({coords:{latitude:37.7749295,longitude:-122.4194155,accuracy:10}});}}});window.locationResult=null;window.requestLocation().then(v=>window.locationResult=v).catch(e=>window.locationError=e.message);});
 assert.equal(await page.evaluate(()=>window.geoCalls),0);await page.getByRole('button',{name:'取消',exact:true}).click();await page.waitForFunction(()=>window.locationError);assert.equal(await page.evaluate(()=>window.geoCalls),0);
 await page.evaluate(()=>{void window.requestLocation().then(v=>window.locationResult=v);});await page.getByRole('button',{name:'使用当前位置',exact:true}).click();await page.waitForFunction(()=>window.locationResult);assert.deepEqual(await page.evaluate(()=>window.locationResult),{latitude:37.77,longitude:-122.42,accuracy_m:1500});assert.equal(await page.locator('dialog').count(),0);
 }finally{await browser.close();}
});

test('Shared browser snapshot exposes autocomplete options and prioritizes an open listbox',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.setContent('<nav>'+Array.from({length:30},(_,i)=>'<button>Background '+i+'</button>').join('')+'</nav><div role="listbox"><div role="option">Beijing, China · all airports</div><div role="option" hidden>Hidden airport</div><div role="option">Beijing Capital PEK</div></div>');
 const source=fs.readFileSync(path.resolve(__dirname,'../web/static/js/browser_snapshot.js'),'utf8'),visibility=fs.readFileSync(path.resolve(__dirname,'../web/static/js/browser_dom_visibility.js'),'utf8');
 const result=await page.evaluate(({source,visibility})=>{window.ai2appsDOMVisible=eval('('+visibility+')');return eval(source)({maxItems:3,maxText:1000,maxHtml:10000,htmlMode:'visible'});},{source,visibility});
 assert.equal(result.items[0].role,'option');assert.match(result.items[0].text,/Beijing, China/);assert.ok(!result.items.some(r=>r.text==='Hidden airport'));
 }finally{await browser.close();}
});

test('Shared snapshot includes current ordinary form values but suppresses passwords and OTP',async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{const page=await browser.newPage();await page.setContent('<input aria-label="Origin" value="San Francisco"><input type="password" value="private-pass"><input autocomplete="one-time-code" value="123456">');
 const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8');
 const snapshot=fs.readFileSync(__dirname+'/../web/static/js/browser_snapshot.js','utf8');
 const result=await page.evaluate(({visible,snapshot})=>{window.ai2appsDOMVisible=eval('('+visible+')');return eval('('+snapshot+')')({maxItems:20,maxText:1000,maxHtml:3000,htmlMode:'visible'});},{visible,snapshot});
 assert.equal(result.items.find(r=>r.text==='Origin').value,'San Francisco');
 assert.ok(result.items.filter(r=>r.sensitive).every(r=>r.value===''));
 }finally{await browser.close();}
});

test('Shared snapshot keeps visible dialog completion ahead of long offscreen calendars',async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{const page=await browser.newPage({viewport:{width:800,height:600}});await page.setContent('<div role="dialog"><div style="height:400px;overflow:auto">'+Array.from({length:300},(_,i)=>'<button style="display:block;height:30px">Date '+i+'</button>').join('')+'</div><button>Done</button></div>');
 const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8');const snapshot=fs.readFileSync(__dirname+'/../web/static/js/browser_snapshot.js','utf8');
 const result=await page.evaluate(({visible,snapshot})=>{window.ai2appsDOMVisible=eval('('+visible+')');return eval('('+snapshot+')')({maxItems:40,maxText:1000,maxHtml:4000,htmlMode:'visible'});},{visible,snapshot});
 assert.ok(result.items.some(r=>r.text==='Done'));
 }finally{await browser.close();}
});

test('Ctrip visible flight/hotel cards preserve quotes and exclude hidden offers',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage();
  await page.route('https://flights.ctrip.com/**',r=>r.fulfill({contentType:'text/html; charset=utf-8',body:'<input value="北京(BJS)"><input value="上海(SHA)"><input value="2027-06-01"><div class="flight-box">中国联合航空<br>KN5977 波音737(中)<br>20:45<br>大兴国际机场<br>22:55<br>浦东国际机场T1<br>¥770起<br>往返总价<br><span>选为去程</span></div><div hidden class="flight-box">Hidden flight KN1111 ¥1 20:45 22:55</div>'}));
  await page.goto('https://flights.ctrip.com/online/list/round-bjs-sha');
  const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8');
  const script=fs.readFileSync(__dirname+'/../browser/travel_reader.py','utf8').match(/SCRIPT = r'''([\s\S]*?)'''/)[1];
  const read=provider=>page.evaluate(({visible,script,provider})=>{window.ai2appsDOMVisible=eval('('+visible+')');return eval('('+script+')')(provider);},{visible,script,provider});
  let result=await read('ctrip_flights');assert.equal(result.observed_items.length,1);assert.match(result.observed_items[0].quote,/往返总价/);
  await page.setContent('<input id="destinationInput" value="北京"><section><div aria-label="Photo gallery for 颐和园附近测试酒店"></div><p>测试酒店 4.8分 500条点评 近颐和园 · 地铁 大床房</p><button>查看地图</button><button>查看详情</button><button>登录以查看会员价</button></section><section hidden>隐藏酒店 1条点评<button>查看地图</button><button>查看详情</button></section>');
  result=await read('ctrip_hotels');assert.equal(result.observed_items.length,1);assert.equal(result.observed_items[0].title,'颐和园附近测试酒店');assert.match(result.observed_items[0].quote,/登录以查看会员价/);assert.doesNotMatch(result.observed_items[0].quote,/隐藏酒店/);
 }finally{await browser.close();}
});
for(const width of [390,1100])test('China trip defaults to Ctrip and explicit sources override at '+width,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width,height:900}});
  const html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script[^>]*src="[^"]*"[^>]*><\/script>/g,'').replace(/<link[^>]*>/g,'');
  await page.route('https://trip.test/**',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('https://trip.test/?locale=zh');
  await page.evaluate(()=>{window.calls=[];window.AI2AppsWebAgent={startup:async()=>({profiles:[{key:'default',is_default:true}]}),saveDraft:async()=>{},onTask:()=>{},watch:async()=>{},submit:async(capability,parameters)=>{window.calls.push(parameters);return {id:'t'+window.calls.length,status:'completed',result:{items:[],status:'partial'}};}};});
  for(const f of ['i18n.js','travel.js'])await page.addScriptTag({path:path.join(root,f)});
  await page.locator('#profile').waitFor();await page.locator('#origin').fill('北京');await page.locator('#destination').fill('上海');await page.locator('#destination_airport').fill('虹桥');await page.locator('#excluded_airports').fill('浦东，PVG');await page.locator('#departure').fill('2027-06-01');await page.locator('#nights').fill('3');await page.locator('#return_date').fill('2027-06-04');await page.locator('#hotel_checkin').fill('2027-06-01');await page.locator('#hotel_checkout').fill('2027-06-04');
  await page.locator('[name=source][value=sights]').uncheck();await page.locator('#search').click();
  await page.waitForFunction(()=>window.calls.length===3);assert.deepEqual(await page.evaluate(()=>window.calls.map(c=>c.provider)),['ctrip_flights','ctrip_flights','ctrip_hotels']);assert.deepEqual(await page.evaluate(()=>window.calls[0].trip.excluded_airports),['浦东','PVG']);assert.equal(await page.evaluate(()=>window.calls[0].trip.destination_airport),'虹桥');
  await page.locator('[name=source][value=google_flights]').check();assert.equal(await page.locator('[name=source][value=auto]').isChecked(),false);
  await page.locator('#search').click();await page.waitForFunction(()=>window.calls.length===5);assert.deepEqual(await page.evaluate(()=>window.calls.slice(3).map(c=>c.provider)),['google_flights','google_flights']);
 }finally{await browser.close();}
});

test('Shared snapshot exposes pointer list controls and deduplicates their text spans',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.setContent('<ul><li style="cursor:pointer"><span>Option alpha</span></li><li style="cursor:pointer"><span>Option beta</span></li><li hidden style="cursor:pointer">Hidden option</li><li>ordinary content</li></ul>');
 const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8'),snapshot=fs.readFileSync(__dirname+'/../web/static/js/browser_snapshot.js','utf8');
 const result=await page.evaluate(({visible,snapshot})=>{window.ai2appsDOMVisible=eval('('+visible+')');return eval('('+snapshot+')')({maxItems:100,maxText:1000,maxHtml:4000,htmlMode:'visible'});},{visible,snapshot});
 assert.deepEqual(result.items.map(x=>[x.tag,x.text]),[['li','Option alpha'],['li','Option beta']]);
 assert.ok(result.items.every(x=>x.ref&&x.rect[2]>0));
 }finally{await browser.close();}
});

test('Focused roleless autocomplete rows precede navigation without inventing page controls',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.setContent('<nav>'+Array.from({length:30},(_,i)=>`<a href="/n${i}">Navigation ${i}</a>`).join('')+'</nav><section><input aria-label="Workspace"><div tabindex="-1"><div><div><i>Workspace</i><span>Alpha</span><span>(all teams)</span><span>AAA</span></div><ul><li><span>Alpha</span><span>Team one</span><span>A1</span></li><li hidden>Hidden team</li></ul></div></div></section><aside tabindex="-1"><div>Unrelated page text</div></aside>');
 await page.locator('input').focus();
 const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8'),snapshot=fs.readFileSync(__dirname+'/../web/static/js/browser_snapshot.js','utf8');
 const result=await page.evaluate(({visible,snapshot})=>{window.ai2appsDOMVisible=eval('('+visible+')');return eval('('+snapshot+')')({maxItems:3,maxText:1000,maxHtml:4000,htmlMode:'visible'});},{visible,snapshot});
 assert.match(result.items[0].text,/Workspace.*Alpha.*all teams.*AAA/s);
 assert.equal(result.items[1].tag,'li');assert.match(result.items[1].text,/Alpha.*Team one.*A1/s);
 assert.ok(result.controls_truncated);assert.ok(!result.items.some(x=>/Hidden team|Unrelated/.test(x.text)));
 }finally{await browser.close();}
});
test('Roleless pointer calendar cells are observed without exposing plain table content',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.setContent('<table><tr><td style="cursor:pointer"><span>17</span></td><td>18</td><td hidden style="cursor:pointer">19</td></tr></table><a style="cursor:pointer">Next month</a>');
 const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8'),snapshot=fs.readFileSync(__dirname+'/../web/static/js/browser_snapshot.js','utf8');
 const result=await page.evaluate(({visible,snapshot})=>{window.ai2appsDOMVisible=eval('('+visible+')');return eval('('+snapshot+')')({maxItems:20,maxText:1000,maxHtml:4000,htmlMode:'visible'});},{visible,snapshot});
 assert.deepEqual(result.items.map(x=>[x.tag,x.text]),[['td','17'],['a','Next month']]);
 }finally{await browser.close();}
});
test('Input-anchored portal calendar exposes complete visible rows without cursor or ARIA',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.setContent('<input aria-label="Choose period" style="position:absolute;top:20px;left:40px;width:150px;height:25px"><div style="position:absolute;top:55px;left:20px;width:300px;z-index:10"><div><div><span>2031</span><span>April</span></div><div><div><span>17</span><span>$42</span></div><div hidden>18</div></div></div></div><div style="position:absolute;top:700px;left:20px;z-index:10"><div>Unrelated footer</div></div>');
 await page.locator('input').focus();
 const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8'),snapshot=fs.readFileSync(__dirname+'/../web/static/js/browser_snapshot.js','utf8');
 const result=await page.evaluate(({visible,snapshot})=>{window.ai2appsDOMVisible=eval('('+visible+')');return eval('('+snapshot+')')({maxItems:20,maxText:1000,maxHtml:4000,htmlMode:'visible'});},{visible,snapshot});
 assert.deepEqual(result.items.slice(0,2).map(x=>x.text),['2031April','17$42']);
 assert.ok(!result.items.some(x=>/Unrelated|^18$/.test(x.text)));
 }finally{await browser.close();}
});
test('Native pointer anchors roleless non-editor menus; synthetic events do not grant an anchor',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.setContent('<div id="opener" style="position:absolute;left:40px;top:20px;width:160px;height:30px">Choose category</div><div style="position:absolute;left:40px;top:55px;z-index:10"><div><span>Category alpha</span></div><div><span>Category beta</span></div></div>');
 const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8'),snapshot=fs.readFileSync(__dirname+'/../web/static/js/browser_snapshot.js','utf8');
 const read=()=>page.evaluate(({visible,snapshot})=>{window.ai2appsDOMVisible=eval('('+visible+')');return eval('('+snapshot+')')({maxItems:20,maxText:1000,maxHtml:4000,htmlMode:'visible'});},{visible,snapshot});
 assert.equal((await read()).items.length,0);
 await page.locator('#opener').dispatchEvent('pointerdown');assert.equal((await read()).items.length,0);
 await page.locator('#opener').click();
 assert.deepEqual((await read()).items.map(x=>x.text),['Category alpha','Category beta']);
 }finally{await browser.close();}
});
test('Visible decorative native control icons remain observable but hidden wrappers stay excluded',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.setContent('<style>i{display:inline-block;width:24px;height:24px;cursor:pointer;background:#aaa}</style><div tabindex="0"><i id="minus" aria-hidden="true" onclick="this.nextElementSibling.textContent=String(Number(this.nextElementSibling.textContent)-1)"></i><span>2</span><i id="plus" aria-hidden="true"></i></div><div aria-hidden="true"><button><i id="hidden"></i></button></div><div><i id="decoration" aria-hidden="true"></i></div>');
 const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8'),snapshot=fs.readFileSync(__dirname+'/../web/static/js/browser_snapshot.js','utf8');
 const result=await page.evaluate(({visible,snapshot})=>{window.ai2appsDOMVisible=eval('('+visible+')');return {snapshot:eval('('+snapshot+')')({maxItems:30,maxText:1000,maxHtml:4000,htmlMode:'visible'}),defaultVisible:ai2appsDOMVisible(document.querySelector('#minus'))};},{visible,snapshot});
 const icons=result.snapshot.items.filter(x=>x.tag==='i');assert.equal(icons.length,2);assert.ok(icons.every(x=>!x.text));assert.equal(result.defaultVisible,false);
 assert.ok(!result.snapshot.html.includes('id="hidden"'));assert.ok(!result.snapshot.html.includes('id="decoration"'));
 await page.locator('[data-ai2apps-ref="'+icons[0].ref+'"]').click();assert.equal(await page.locator('#minus + span').innerText(),'1');
 }finally{await browser.close();}
});
test('Serialized target refs are exactly bounded by the same Probe seen by the compiler',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.setContent(Array.from({length:20},(_,i)=>`<button>Navigation ${i}</button>`).join('')+'<div role="grid"><div role="gridcell">17</div><div role="gridcell">18</div><div role="gridcell">19</div></div>');
 const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8'),snapshot=fs.readFileSync(__dirname+'/../web/static/js/browser_snapshot.js','utf8');
 const result=await page.evaluate(({visible,snapshot})=>{window.ai2appsDOMVisible=eval('('+visible+')');return eval('('+snapshot+')')({maxItems:2,maxText:1000,maxHtml:20000,htmlMode:'visible'});},{visible,snapshot});
 assert.deepEqual(result.items.map(x=>x.text),['17','18']);
 const htmlRefs=[...result.html.matchAll(/data-ai2apps-ref="([^"]+)"/g)].map(x=>x[1]);
 assert.deepEqual(new Set(htmlRefs),new Set(result.items.map(x=>x.ref)));assert.ok(result.controls_truncated);
 }finally{await browser.close();}
});

test('shared access classifier distinguishes dedicated login, OTP tab, navbar and CAPTCHA',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();
 const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8');
 const sdk=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');
 for(const fixture of [
  {path:'/user/login',html:'<title>登录首页</title><h2>账号密码登录</h2><input type="password"><button>登录</button><a>验证码登录</a>',reason:'authentication'},
  {path:'/search',html:'<title>Search</title><nav><a>登录</a></nav><main>Hotel results</main>',reason:undefined},
  {path:'/challenge',html:'<title>Access</title><main>Verify you are human</main>',reason:'captcha'}]){
 await page.route('https://arbitrary.test/**',route=>route.fulfill({contentType:'text/html; charset=utf-8',body:fixture.html}));await page.goto('https://arbitrary.test'+fixture.path);
 const result=await page.evaluate(async({visible,sdk})=>{window.ai2appsDOMVisible=eval('('+visible+')');eval(sdk);const c=new window.AI2AppsBiDi.AI2AppsPageClient({});c.callJSON=async(source,args)=>eval('('+source+')')(...args);return c.handlePageAccess();},{visible,sdk});
 assert.equal(result.reason,fixture.reason);await page.unroute('https://arbitrary.test/**');
 }
 }finally{await browser.close();}
});
