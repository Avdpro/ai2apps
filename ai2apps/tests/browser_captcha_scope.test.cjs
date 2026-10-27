const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),{chromium}=require('playwright');
const base=path.resolve(__dirname,'..');
const inspector=JSON.parse(fs.readFileSync(base+'/browser/dom_helpers.json','utf8'))['handlePageAccess:0'];
const visibility=fs.readFileSync(base+'/web/static/js/browser_dom_visibility.js','utf8');
const article='<article><h1>Independent report</h1><p>'+('Publicly readable evidence and reporting. '.repeat(15))+'</p></article>';
test('reading CAPTCHA requires a blocker while interactive checks stay strict across unrelated sites',async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{for(const host of ['publisher.example','community.example']){
  const page=await browser.newPage({viewport:{width:1000,height:800}});
  let body='';await page.route('https://'+host+'/**',r=>r.fulfill({contentType:'text/html',body}));
  async function inspect(html,readOnly=true){body=html;await page.goto('https://'+host+'/report');await page.addScriptTag({content:visibility+';window.inspectAccess='+inspector});return page.evaluate(readOnly=>inspectAccess(false,readOnly),readOnly);}
  for(const form of ['<form><label>CAPTCHA</label><input><button>Register</button></form>','<div style="height:1500px"></div><form><label>Verify you are human</label></form>']){
   assert.equal((await inspect(article+form)).classification,'none');
   assert.equal((await inspect(article+form,false)).reason,'captcha');
  }
  assert.equal((await inspect(article+'<p>This article explains CAPTCHA and robot verification.</p>')).classification,'none');
  assert.equal((await inspect('<main><h1>Verify you are human</h1><p>'+('Access to this service is protected. '.repeat(30))+'</p></main>')).reason,'captcha');
  assert.equal((await inspect(article+'<dialog open><p>Verify you are human</p></dialog>')).reason,'captcha');
  assert.equal((await inspect(article+'<div style="position:fixed;inset:0;background:white"><iframe title="CAPTCHA challenge" style="width:400px;height:220px" src="about:blank"></iframe></div>')).reason,'captcha');
  assert.equal((await inspect(article+'<form><iframe title="CAPTCHA challenge" style="width:400px;height:220px" src="about:blank"></iframe></form>')).classification,'none');
  assert.equal((await inspect('<article hidden><p>'+('Unavailable evidence. '.repeat(20))+'</p></article><h1>CAPTCHA</h1>')).reason,'captcha');
  await page.close();
 }}finally{await browser.close();}
});
