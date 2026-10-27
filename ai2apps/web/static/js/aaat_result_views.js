/* Data-only AaAT views. Never interpret provider text as markup or commands. */
(function(root){'use strict';
function safeURL(value){if(typeof value!=='string'||/[\u0000-\u0020\\]/.test(value))return '';try{const local=value.startsWith('/')&&!value.startsWith('//');const u=new URL(value,'https://aaat.invalid');return (local||(value.startsWith('https://')&&u.protocol==='https:'))&&!u.username&&!u.password?value:'';}catch{return '';}}
const layouts=new WeakMap();
function masonry(grid){
 const win=grid.ownerDocument.defaultView;
 if(!win?.ResizeObserver||!win.requestAnimationFrame)return ()=>{};
 let frame=0;
 const layout=()=>{frame=0;if(!grid.isConnected)return;for(const card of grid.children){const span=Math.ceil(card.getBoundingClientRect().height+12);const value='span '+span;if(card.style.gridRowEnd!==value)card.style.gridRowEnd=value;}};
 const schedule=()=>{if(!frame)frame=win.requestAnimationFrame(layout);};
 grid.classList.add('aaat-view-masonry');
 const observer=new win.ResizeObserver(schedule);
 for(const card of grid.children)observer.observe(card);
 schedule();
 return ()=>{observer.disconnect();if(frame)win.cancelAnimationFrame(frame);};
}
function render(container,records,options={}){for(const dispose of layouts.get(container)||[])dispose();const cleanups=[];layouts.set(container,cleanups);container.replaceChildren();if(!Array.isArray(records))return;const doc=container.ownerDocument;
const node=(tag,text)=>{const e=doc.createElement(tag);if(text!==undefined)e.textContent=String(text);return e;};
for(const [viewIndex,record] of records.slice(0,8).entries()){const view=record?.view;if(view?.schema!=='ai2apps.aaat-view/v1'||!['table','cards'].includes(view.layout)||!Array.isArray(view.items))continue;
let cardsGrid;const section=node('section');section.className='aaat-result-view';section.dataset.viewId=view.id;section.append(node('h3',view.title));if(view.summary)section.append(node('p',view.summary));
const image=(item,itemIndex)=>{const box=node('div');box.className='aaat-view-image';const placeholder=node('span','无图片');box.append(placeholder);const url=safeURL(item.image?.url);if(url){placeholder.textContent='图片加载中…';const img=node('img');img.alt=item.image.alt||item.title||'';img.loading='lazy';img.referrerPolicy='no-referrer';img.onerror=()=>{img.remove();box.hidden=true;};img.onload=()=>placeholder.hidden=true;if(options.resolveImage){Promise.resolve(options.resolveImage(record,viewIndex,itemIndex)).then(resource=>{if(!resource?.url?.startsWith('blob:'))throw Error('Invalid resolved image');if(!box.isConnected){resource.dispose?.();return;}if(resource.paint){const canvas=node('canvas');canvas.setAttribute('role','img');canvas.setAttribute('aria-label',img.alt);return resource.paint(canvas).then(()=>{if(img.isConnected){img.replaceWith(canvas);placeholder.hidden=true;}}).finally(()=>resource.dispose?.());}const done=img.onload;img.onload=()=>{done();resource.dispose?.();};img.onerror=()=>{resource.dispose?.();img.remove();box.hidden=true;};img.src=resource.url;}).catch(()=>{img.remove();box.hidden=true;});}else img.src=url;box.append(img);}else box.hidden=true;return box;};
const title=item=>{const url=safeURL(item.url);const e=node(url?'a':'strong',item.title);if(url){e.href=url;e.target='_blank';e.rel='noopener noreferrer';}return e;};
const columns=Array.isArray(view.columns)?view.columns.slice(0,8):[];
if(view.layout==='table'){const wrap=node('div');wrap.className='aaat-view-table-scroll';const table=node('table'),head=node('thead'),tr=node('tr');tr.append(node('th','项目 / Item'));for(const c of columns)tr.append(node('th',c.label));head.append(tr);table.append(head);const body=node('tbody');for(const [itemIndex,item] of view.items.slice(0,30).entries()){const row=node('tr'),cell=node('td'),product=node('div');product.className='aaat-view-product';product.append(image(item,itemIndex),title(item));cell.append(product);row.append(cell);for(const c of columns)row.append(node('td',item.fields?.[c.key]??'—'));body.append(row);}table.append(body);wrap.append(table);section.append(wrap);}else{const grid=node('div');grid.className='aaat-view-cards';cardsGrid=grid;for(const [itemIndex,item] of view.items.slice(0,30).entries()){const card=node('article');card.className='aaat-view-card';card.append(image(item,itemIndex),title(item));if(item.summary)card.append(node('p',item.summary));const fields=node('dl');for(const c of columns){const value=item.fields?.[c.key]??'—',detail=node('dd',value);detail.title=String(value);if(c.label)fields.append(node('dt',c.label));else detail.className='aaat-view-unlabelled-value';fields.append(detail);}card.append(fields);grid.append(card);}section.append(grid);}
if(!view.items.length)section.append(node('p','暂无结果 / No results'));container.append(section);if(cardsGrid)cleanups.push(masonry(cardsGrid));}}
root.AI2AppsResultViews={render,safeURL};if(typeof module!=='undefined')module.exports={render,safeURL};
})(typeof window==='undefined'?globalThis:window);
