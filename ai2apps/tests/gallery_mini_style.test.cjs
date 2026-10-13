const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
test('Mini-Entry touch handle is isolated and never enabled by narrow desktop width',()=>{
 const read=file=>fs.readFileSync(path.join(__dirname,'../web',file),'utf8');
 const shared=read('static/css/gallery.css'),mini=read('static/css/gallery_mini.css'),template=read('templates/system_apps/gallery_mini.html');
 assert.ok(!shared.includes('.gallery-touch-drag'));
 assert.match(mini,/\.gallery-mini\[data-gallery-surface="mini-entry"\] \.gallery-touch-drag\{display:none\}/);
 assert.match(mini,/@media\(pointer:coarse\)/);
 assert.ok(!mini.includes('max-width'));
 assert.match(template,/static\('css\/gallery_mini.css'\)/);
 assert.match(template,/@dragstart="dragAsset\(\$event,asset\)"/);
});
