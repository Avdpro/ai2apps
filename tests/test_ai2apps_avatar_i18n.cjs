const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict'), path=require('node:path');
const web=path.join(__dirname,'../packages/ai2apps-avatar-studio-suite/web');
const ctx={window:{location:{search:'?locale=zh-TW'},dispatchEvent(){},addEventListener(){}},navigator:{language:'en'},document:{documentElement:{},querySelectorAll:()=>[]},Event:class {},URLSearchParams};
for(const name of ['locales.js','i18n.js']) vm.runInNewContext(fs.readFileSync(path.join(web,name),'utf8'),ctx);
const {AvatarLocales:catalogs,AvatarI18n:i}=ctx.window;
assert.equal(ctx.document.documentElement.lang,'zh-TW');
assert.equal(Object.keys(catalogs).length,9);
const placeholders=s=>[...s.matchAll(/\{(\w+)\}/g)].map(x=>x[1]).sort();
for(const [lang,strings] of Object.entries(catalogs)) {
 assert.deepEqual(Object.keys(strings).sort(),Object.keys(catalogs.en).sort());
 i.setLocale(lang);
 for(const [key,value] of Object.entries(strings)) {assert(value.trim(),`${lang}.${key}`);assert.deepEqual(placeholders(value),placeholders(catalogs.en[key]));}
 assert(!i.t('limits',{min:1,max:10}).includes('{'));
 assert(!i.presetLabel('Standard (4 steps)').includes('{'));
 for(const name of ['photo-speaking.html','index.html']) {
  const html=fs.readFileSync(path.join(web,name),'utf8');
  for(const match of html.matchAll(/data-i18n(?:-aria-label|-alt)?="([^"]+)"/g)) assert(strings[match[1]],`${lang}.${match[1]}`);
 }
}
assert.equal(i.normalize('zh-Hant-HK'),'zh-TW');assert.equal(i.normalize('zh-CN'),'zh');assert.equal(i.normalize('pt-PT'),'pt-BR');assert.equal(i.normalize('de'),'en');
i.setLocale('en');assert.equal(i.t('generate'),'Generate video');assert.equal(i.presetLabel('custom preset'),'custom preset');
console.log('PASS: nine complete catalogs, placeholders, markup, locale aliases and fallback');
