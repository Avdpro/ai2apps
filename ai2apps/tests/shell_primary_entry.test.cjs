const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.resolve(__dirname,'../web/static/js/shell.js'),'utf8');
const functions=source.slice(source.indexOf('    function primaryAppOrder('),source.indexOf('    function readWarmApps('));
const ids=['ai2apps.messager','ai2apps.general-chat','ai2apps.ai-browser','custom.a','custom.b'];
function fixture(pins,order,status='active') {
 const data=new Map([['pins',JSON.stringify(pins)],['order',JSON.stringify(order)]]);
 const apps=ids.map(id=>({id,status:id==='ai2apps.messager'?status:'active',pinnedDefault:true}));
 const context={apps,byId:new Map(apps.map(app=>[app.id,app])),storage:{pinned:'pins',order:'order',primaryEntry:'migration'},localStorage:{getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v)},defaultDockOrder:ids,previousDefaultDockOrder:["old.default"]};
 vm.createContext(context);vm.runInContext(functions,context);
 return {data,context};
}
test('migration pins Messager first and relocates Chat while retaining custom order',()=>{
 const {data,context}=fixture(['custom.b','ai2apps.general-chat','custom.a','ai2apps.ai-browser'],['custom.b','ai2apps.general-chat','custom.a','ai2apps.ai-browser']);
 context.migratePrimaryEntry();
 const expected=['ai2apps.messager','custom.b','custom.a','ai2apps.ai-browser','ai2apps.general-chat'];
 assert.deepEqual(JSON.parse(data.get('pins')),expected);
 assert.deepEqual(JSON.parse(data.get('order')),expected);
 data.set('order',JSON.stringify(['custom.a','ai2apps.messager']));
 context.migratePrimaryEntry();
 assert.deepEqual(JSON.parse(data.get('order')),['custom.a','ai2apps.messager']);
});
test('unavailable catalog does not consume migration',()=>{
 const {data,context}=fixture([],[],'development');context.migratePrimaryEntry();assert.equal(data.has('migration'),false);
});
