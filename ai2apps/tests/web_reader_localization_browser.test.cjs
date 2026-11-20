const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
const root=path.join(__dirname,'../web/static/builtin_mini_apps/web-reader/web');
test('reader renders localized accessible controls at Desktop and Mobile widths',async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  for(const width of [390,1100]){
   const page=await browser.newPage({viewport:{width,height:1000}});
   await page.route('**/*',route=>{
    const name=new URL(route.request().url()).pathname.split('/').pop();
    const body=name==='reader.js'?fs.readFileSync(root+'/reader.js','utf8'):name==='web_agent_mini_app_sdk.js'?'window.AI2AppsWebAgent={onTask(){},submit(){throw Error("No task in display test")}};':fs.readFileSync(root+'/index.html','utf8');
    return route.fulfill({contentType:name.endsWith('.js')?'application/javascript':'text/html',body});
   });
   for(const [locale,title] of [['en','Web Reader'],['zh','网页阅读器'],['zh-TW','網頁閱讀器'],['de','Web-Leser'],['es','Lector web'],['fr','Lecteur web'],['ja','ウェブリーダー'],['ko','웹 리더'],['pt-BR','Leitor web'],['ru','Веб-ридер']]){
    await page.goto('http://reader.test/index.html?locale='+locale);
    assert.equal(await page.title(),title);assert.equal(await page.locator('h1').innerText(),title);
    assert.equal(await page.locator('html').getAttribute('lang'),locale);
    assert.equal(await page.locator('#capability option').count(),2);
    assert.equal(await page.locator('#capability').getAttribute('aria-label'),await page.locator('[data-text=capability]').innerText());
    assert.equal((await page.locator('body').innerText()).includes(' / '),false);
    assert.ok(await page.locator('#run').isVisible());
    await page.locator('#capability').selectOption('article');assert.equal(await page.locator('#limit-row').isVisible(),false);
    await page.locator('#capability').selectOption('list');assert.equal(await page.locator('#limit-row').isVisible(),true);
    if(process.env.READER_LOCALE_PROOF_DIR&&['en','zh'].includes(locale))await page.screenshot({path:path.join(process.env.READER_LOCALE_PROOF_DIR,locale+'-'+width+'.png'),fullPage:true});
   }
   await page.close();
  }
 }finally{await browser.close();}
});
