const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const script=fs.readFileSync(path.join(__dirname,'../web/static/js/x_post_snapshot.js'),'utf8');
function node(tag,text='',attrs={}){
 return {localName:tag,innerText:text,classList:[],hasAttribute:a=>a in attrs,getAttribute:a=>attrs[a],
  getBoundingClientRect:()=>({height:100}),querySelector:()=>null,querySelectorAll:()=>[],matches:s=>s.includes(attrs['data-testid']||'nomatch')};
}
function card(id,text,photos=[],changed=false){
 const root=node('article',text,{role:'article'}),time={dateTime:'2026-10-11T00:00:00Z'};
 const anchor=node('a','',{href:'/Formula1/status/'+id});anchor.pathname='/Formula1/status/'+id;anchor.querySelector=()=>time;anchor.closest=()=>root;
 const body=node('p',text,{'data-testid':changed?'newBody':'tweetText',lang:'en'}),author=node('div','Formula 1 @Formula1',{'data-testid':'User-Name'});
 const images=photos.map(src=>Object.assign(node('img'),{src,alt:'F1 photo'}));
 root.querySelector=s=>root.querySelectorAll(s)[0]||null;
 root.querySelectorAll=s=>s==='a[href]'?[anchor]:s==='img'?images:s.includes('newBody')?changed?[body]:[]:s==='p,[lang]'?[body]:s==='p'||s.includes('tweetText')?changed?[]:[body]:s.includes('User-Name')?[author]:s.includes('[lang]')||s.includes('[data-testid]')?[body,author]:[];
 return {root,anchor};
}
function context(cards){
 const ctx={location:{hostname:'x.com',href:'https://x.com/Formula1'},CSS:{escape:s=>s},document:{querySelectorAll:s=>s==='a[href]'?cards.map(c=>c.anchor):s.includes('article')?cards.map(c=>c.root):[]}};
 vm.createContext(ctx);vm.runInContext(script,ctx);return ctx;
}
const rule={card:'article',link:'a[href]',text:'[data-testid="tweetText"]',author:'[data-testid="User-Name"]',photo:'img'};
test('X visible extraction deduplicates and preserves only post photos',()=>{
 const ctx=context([card('1','F1 news',['https://pbs.twimg.com/media/f1.jpg','https://example.com/ad.jpg']),card('1','duplicate'),card('2',' Second post '),card('3','')]);
 const r=JSON.parse(JSON.stringify(vm.runInContext('xPostSnapshot()',ctx)));
 assert.deepEqual(r.items.map(p=>p.post_id),['1','2']);assert.equal(r.items[1].text,'Second post');
 assert.deepEqual(r.items[0].images,[{url:'https://pbs.twimg.com/media/f1.jpg',alt:'F1 photo'}]);
 assert.ok(r.x_observed.text.some(o=>o.selector.includes('tweetText')));
 ctx.location.hostname='evil.example';assert.throws(()=>vm.runInContext('xPostSnapshot()',ctx),/x_origin_required/);
});
test('compiled selector extraction skips AI observations while valid',()=>{
 const ctx=context([card('1','News')]);ctx.rule=rule;
 const r=vm.runInContext('xPostSnapshot(rule)',ctx);assert.equal(r.x_rule_valid,true);assert.equal(r.x_observed,null);assert.equal(r.items[0].post_id,'1');
});
test('changed body attributes trigger semantic fallback with fresh selector observations',()=>{
 const ctx=context([card('1','Changed page news',[],true)]);ctx.rule=rule;
 const r=vm.runInContext('xPostSnapshot(rule)',ctx);assert.equal(r.x_rule_valid,false);assert.equal(r.items[0].text,'Changed page news');
 assert.ok(r.x_observed.text.some(o=>o.selector.includes('newBody')));
 ctx.rule={...rule,text:'[data-testid="newBody"]'};assert.equal(vm.runInContext('xPostSnapshot(rule)',ctx).x_rule_valid,true);
});
