const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.join(__dirname,'..'),read=file=>fs.readFileSync(path.join(root,file),'utf8');
const template=read('web/templates/dashboard/_models.html');
const routes=template.match(/x-for="route in (\[[\s\S]*?\])" :key="route.id"/)[1];
const locales=['en','zh','zh-TW','ja','ko','fr','es','pt-BR','ru','de'];
const keys=['work_chat.title','work_chat.description','work_agent.title','work_agent.description'].map(k=>'models.defaults.'+k);
test('Chat and Agent routing labels use translated keys in all locale catalogs',()=>{
 for(const locale of locales){
  const catalog=JSON.parse(read('web/i18n/'+locale+'.json'));
  for(const key of keys)assert.ok(typeof catalog[key]==='string'&&catalog[key].trim(),locale+': '+key);
  const rows=vm.runInNewContext(routes,{window:{t:key=>catalog[key]||key}});
  assert.equal(rows[0].title,catalog[keys[0]]);assert.equal(rows[0].description,catalog[keys[1]]);
  assert.equal(rows[1].title,catalog[keys[2]]);assert.equal(rows[1].description,catalog[keys[3]]);
  if(locale==='en')assert.ok(!/[\u3400-\u9fff]/.test(JSON.stringify(rows.slice(0,2))));
 }
 assert.ok(!template.includes("title:'Chat 默认模型'"));
 assert.ok(!template.includes("title:'Agent 默认模型'"));
});
test('Alpine renders the localized routing titles and descriptions for every locale',async()=>{
 const {chromium}=require('playwright');const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  for(const locale of locales){
   const catalog=JSON.parse(read('web/i18n/'+locale+'.json')),page=await browser.newPage();
   await page.setContent(`<div x-data="{}"><template x-for="route in ${routes}" :key="route.id"><label><strong x-text="route.title"></strong><p x-text="route.description"></p></label></template></div>`);
   await page.evaluate(catalog=>{window.t=key=>catalog[key]||key;},catalog);
   await page.addScriptTag({content:read('web/static/js/alpine.min.js')});
   await page.locator('label').nth(4).waitFor();
   assert.equal(await page.locator('label strong').nth(0).textContent(),catalog[keys[0]],locale);
   assert.equal(await page.locator('label p').nth(0).textContent(),catalog[keys[1]],locale);
   assert.equal(await page.locator('label strong').nth(1).textContent(),catalog[keys[2]],locale);
   assert.equal(await page.locator('label p').nth(1).textContent(),catalog[keys[3]],locale);
   await page.close();
  }
 } finally {await browser.close();}
});
