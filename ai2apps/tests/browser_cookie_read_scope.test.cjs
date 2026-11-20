const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),{chromium}=require('playwright');
const base=path.resolve(__dirname,'..'),inspector=JSON.parse(fs.readFileSync(base+'/browser/dom_helpers.json'))['handlePageAccess:0'],visibility=fs.readFileSync(base+'/web/static/js/browser_dom_visibility.js','utf8');
const content='<main><h1>Public article for independent readers</h1><p>'+('Visible source material and public reporting. '.repeat(18))+'</p><h2>Further public details and evidence</h2></main>';
const cookie=(buttons,extra='',style='position:fixed;bottom:10px;right:10px;width:280px;background:white;padding:15px')=>`<div role="dialog" ${extra} style="${style}"><p>Cookies and privacy preferences</p>${buttons.map(s=>`<button onclick="window.chosen=this.textContent">${s}</button>`).join('')}</div>`;
test('read-only Cookie handling preserves meaningful consent and unrelated-site isolation',async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{for(const host of ['journal.example','independent.example']){
  const page=await browser.newPage({viewport:{width:1000,height:800}});let body='';await page.route('https://'+host+'/**',r=>r.fulfill({contentType:'text/html; charset=utf-8',body}));
  async function inspect(html,readOnly=true,frame=false){body=html;await page.goto('https://'+host+'/article');await page.addScriptTag({content:visibility+';window.inspectCookie='+inspector});return page.evaluate(([readOnly,frame])=>inspectCookie(frame,readOnly),[readOnly,frame]);}
  for(const label of ['Accept necessary','Accept necessary cookies','Accept only essential cookies','Allow only necessary','Necessary cookies only','仅接受必要Cookie']){
   const result=await inspect(content+cookie(['Accept all',label]));assert.equal(result.classification,'safe_dismiss',label);assert.equal(result.name,label);
  }
  assert.equal((await inspect(content+cookie(['Accept necessary']))).classification,'safe_dismiss');
  assert.equal((await inspect(content+cookie(['Accept all']))).classification,'none');assert.equal(await page.evaluate(()=>window.chosen),undefined);
  assert.equal((await inspect(content+cookie(['Accept all']),false)).reason,'cookie_consent');
  assert.equal((await inspect(content+cookie(['Accept all'],'aria-modal="true"'))).reason,'cookie_consent');
  assert.equal((await inspect(content+cookie(['Accept all'],'','position:fixed;inset:0;background:white'))).reason,'cookie_consent');
  assert.equal((await inspect(content+'<div style="position:fixed;inset:0;background:#aaa8">'+cookie(['Accept all'])+'</div>')).reason,'cookie_consent');
  assert.equal((await inspect('<main hidden>'+content+'</main>'+cookie(['Accept all']))).reason,'cookie_consent');
  assert.equal((await inspect(content+cookie(['Accept all']),true,true)).reason,'cookie_consent');
  const frame=style=>`<iframe title="Cookie consent" src="about:blank" style="${style}"></iframe>`;
  assert.equal((await inspect(content+frame('position:fixed;right:10px;bottom:10px;width:280px;height:150px'))).classification,'none');
  assert.equal((await inspect(content+frame('position:fixed;right:10px;bottom:10px;width:280px;height:150px'),false)).reason,'cookie_consent');
  assert.equal((await inspect(content+frame('position:fixed;inset:0;width:100%;height:100%'))).reason,'cookie_consent');
  assert.notEqual((await inspect(content+cookie(['Accept necessary and marketing']))).classification,'safe_dismiss');
  await page.close();
 }}finally{await browser.close();}
});
