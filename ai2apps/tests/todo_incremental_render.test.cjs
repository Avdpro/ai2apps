const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
test('editing and selection preserve unchanged rows and SVGs; filtering and reordering stay correct',async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
 const page=await browser.newPage();
 await page.setContent('<div id="task-tree"></div><div id="tree-empty"><h2></h2><p></p></div>');
 await page.addScriptTag({path:'web/static/js/lucide.min.js'});
 const source=fs.readFileSync('web/static/js/todo.js','utf8');
 const helpers=source.slice(source.indexOf('function icons()'),source.indexOf('function localize('));
 const render=source.slice(source.indexOf('function renderTree()'),source.indexOf('const highlights='));
 const result=await page.evaluate(({helpers,render})=>{
  window.$=s=>document.querySelector(s);window.tr=s=>s;window.esc=s=>s;
  window.selectedId=null;window.aggregateId=null;window.collapsed=new Set();window.isActiveTask=()=>true;
  window.state={runs:[],attachments:[]};
  window.rows=Array.from({length:1000},(_,i)=>({t:{id:String(i),title:'Project '+i,status:'in_progress',progress:30,schedule:{frequency:'off'}},depth:1}));
  window.visibleRows=()=>rows;
  return eval(helpers+render+`
   renderTree();
   const original=[...$('#task-tree').children],svg=original[10].querySelector('svg');
   rows[3].t.progress=60;let start=performance.now();renderTree();const editMs=performance.now()-start;
   const reused=original.filter((node,i)=>i!==3&&node===$('#task-tree').children[i]).length;
   const svgReused=svg===$('#task-tree').children[10].querySelector('svg');
   selectedId='8';renderTree();const selected=$('#task-tree').querySelector('.selected')?.dataset.task;
   rows=rows.slice(0,10).reverse();renderTree();
   const order=[...$('#task-tree').children].map(n=>n.dataset.task).join(',');
   rows=[];renderTree();const empty=$('#task-tree').children.length;
   ({reused,svgReused,selected,order,empty,editMs})
  `);
 },{helpers,render});
 assert.equal(result.reused,999);assert.equal(result.svgReused,true);assert.equal(result.selected,'8');
 assert.equal(result.order,'9,8,7,6,5,4,3,2,1,0');assert.equal(result.empty,0);
 console.log('1000-row field update (fixture):',result.editMs.toFixed(1)+'ms');
 }finally{await browser.close();}
});
