/* Ordered, inert source structure shared by native BiDi clients. */
function ai2appsArticleDocument(article,maxChars=20000){
 const root=document.createElement('template');root.innerHTML=String(article.content||'');
 for(const node of root.content.querySelectorAll('script,style,noscript,template,nav,header,footer,aside,form,[hidden],[aria-hidden=true]'))node.remove();
 const blocks=[];let used=0,last=null;
 const emit=text=>{text=String(text||'').trim().replace(/\s+/g,' ');if(!text||used>=maxChars||blocks.length>=256)return;const part=text.slice(0,Math.min(12000,maxChars-used));used+=part.length;last='sp_'+blocks.length;blocks.push({type:'paragraph',id:last,text:part});};
 const image=node=>{
  if(used>=maxChars||blocks.length>=256)return;
  const candidates=['data-src','data-lazy-src','data-original','src'].map(key=>node.getAttribute(key)).filter(Boolean);
  for(const key of ['srcset','data-srcset','data-lazy-srcset'])for(const part of (node.getAttribute(key)||'').split(',')){const url=part.trim().split(/\s+/)[0];if(url)candidates.push(url);}
  for(const candidate of candidates){try{const url=new URL(candidate,location.href);if(!['http:','https:'].includes(url.protocol))continue;blocks.push({type:'image',url:url.href,alt:(node.getAttribute('alt')||'').slice(0,300),paragraph_id:last});return;}catch(_){}}
 };
 const walk=node=>{if(node.nodeType===3){emit(node.textContent);return;}if(node.nodeType!==1&&node.nodeType!==11)return;if(node.nodeType===1&&node.tagName==='IMG'){image(node);return;}if(node.nodeType===1&&/^(P|H[1-6]|LI|PRE|FIGCAPTION|TD|TH)$/.test(node.tagName)){emit(node.textContent);for(const img of node.querySelectorAll('img'))image(img);return;}for(const child of node.childNodes)walk(child);};
 walk(root.content);return blocks;
}
