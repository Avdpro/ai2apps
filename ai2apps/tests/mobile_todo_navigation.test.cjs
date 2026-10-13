const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/mobile_todo.js'),'utf8');
test('back waits for history, switches once, and can reject unsaved changes',()=>{
 const elements={'detail-view':{hidden:false},'list-view':{hidden:true}};let listener,backs=0;
 const history={state:{ai2appsMobileTodo:{view:'detail'}},back(){backs++},pushState(s){this.state=s},replaceState(s){this.state=s}};
 const c={clearTimeout,emojiSaveTimer:null,shellHosted:false,history,$:id=>elements[id],window:{addEventListener:(_,fn)=>listener=fn,scrollTo(){}},mt:t=>t,confirm:()=>false,busy:false,dirty:true,listScroll:250,historyKey:'ai2appsMobileTodo',current:{id:'one'},parent:null,data:{tasks:[]},edit(){}};
 vm.createContext(c);vm.runInContext(source.slice(source.indexOf('    function showList()'),source.indexOf('    async function save()')),c);
 c.back();assert.equal(backs,0);c.confirm=()=>true;c.back();c.back();assert.equal(backs,1);assert.equal(elements['detail-view'].hidden,false);
 listener({state:{ai2appsMobileTodo:{view:'list'}}});assert.equal(elements['detail-view'].hidden,true);assert.equal(elements['list-view'].hidden,false);
});
test('Todo opens details without a document request or gesture interception',()=>{
 const app=source.slice(source.indexOf('function mobileTodoTree'));
 assert.doesNotMatch(app,/location\.(assign|replace)\(/);
 assert.doesNotMatch(app,/addEventListener\('touch/);
 assert.match(app,/history\.pushState\(next/);
});
