const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
test('Dock keeps one insertion marker and cleans up missing-leave, SVG crossings, drop and cancellation',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage();
  await page.setContent('<div id="dock">'+['a','b','c','d'].map(id=>'<div draggable="true" class="dock-app-wrap" data-dock-drag-id="'+id+'"><button><svg><path d="M0 0"></path></svg></button></div>').join('')+'</div><div id="outside"></div>');
  const source=fs.readFileSync(path.join(__dirname,'../web/static/js/shell.js'),'utf8');
  const block=source.slice(source.indexOf('    function clearDockDropMarkers('),source.indexOf("    document.addEventListener('pointerdown'",source.indexOf('    function clearDockDropMarkers(')));
  await page.addScriptTag({content:'(()=>{const dockApps=document.querySelector("#dock");let dockDraggingId=null,suppressDockClick=false,dockOrder=["a","b","c","d"];const hideDockTooltip=()=>{},closeDockContextMenu=()=>{},persist=()=>window.saved=dockOrder,renderDock=()=>{};'+block+'window.dragState=()=>({dockDraggingId,dockOrder});})();'});
  const result=await page.evaluate(()=>{
   const dock=document.querySelector('#dock'),el=id=>dock.querySelector('[data-dock-drag-id="'+id+'"]'),dt=new DataTransfer();
   const event=(node,type,extra={})=>node.dispatchEvent(new DragEvent(type,{bubbles:true,cancelable:true,dataTransfer:dt,...extra}));
   const count=()=>dock.querySelectorAll('.drop-before,.drop-after').length,counts=[];
   event(el('a'),'dragstart');
   for(const id of ['b','c','d']){event(el(id).querySelector('path'),'dragover');counts.push(count());}
   // Moving between descendants of the same button must not flicker the marker.
   event(el('d').querySelector('svg'),'dragleave',{relatedTarget:el('d').querySelector('path')});counts.push(count());
   event(el('a'),'dragover');counts.push(count());
   event(el('c'),'dragover');event(document.querySelector('#outside'),'dragover');counts.push(count());
   event(el('c'),'dragover',{clientX:10000});event(el('c'),'drop',{clientX:10000});
   const afterDrop={count:count(),dragging:dragState().dockDraggingId,saved:[...saved],source:dock.querySelectorAll('.is-dragging').length};
   event(el('d'),'dragstart');event(el('b'),'dragover');event(el('d'),'dragend');
   const cancelled={count:count(),dragging:dragState().dockDraggingId};
   event(el('d'),'dragstart');event(el('b'),'dragover');event(document.querySelector('#outside'),'drop');
   return {counts,afterDrop,cancelled,outside:{count:count(),dragging:dragState().dockDraggingId}};
  });
  assert.deepEqual(result.counts,[1,1,1,1,0,0]);
  assert.deepEqual(result.afterDrop,{count:0,dragging:null,saved:['b','c','a','d'],source:0});
  assert.deepEqual(result.cancelled,{count:0,dragging:null});
  assert.deepEqual(result.outside,{count:0,dragging:null});
 }finally{await browser.close();}
});
