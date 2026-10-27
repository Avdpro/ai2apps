const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/account_avatar.js'),'utf8');
const window={};vm.runInNewContext(source,{window,document:{documentElement:{lang:'en'}}});
const {bound,validRevision}=window.AI2AppsAccountAvatar;
test('portrait/landscape and rotated crops cover all edges without stretching',()=>{
 for(const [width,height] of [[1200,600],[600,1200],[300,300]])for(const turn of [0,1,2,3])for(const zoom of [1,2,4]){
  const s=bound({width,height,turn,zoom,x:99999,y:-99999});const w=turn%2?height:width,h=turn%2?width:height;
  assert.ok(w*s.scale>=300);assert.ok(h*s.scale>=300);
  assert.ok(Math.abs(s.x)<= (w*s.scale-300)/2);assert.ok(Math.abs(s.y)<=(h*s.scale-300)/2);
 }
});
test('legacy or malformed revisions never default to zero',()=>{
 for(const v of [undefined,null,-1,1.5,'1',true,Infinity])assert.equal(validRevision({avatarRevision:v}),false);
 assert.equal(validRevision({avatarRevision:0}),true);
});
