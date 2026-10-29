/* Presentation only: browser work and run state remain owned by Local Tasks. */
(function(global){'use strict';
 function canonical(raw){let u;try{u=new URL(raw);}catch(_){return null;}if(!['http:','https:'].includes(u.protocol)||u.username||u.password)return null;
 u.hash='';for(const key of [...u.searchParams.keys()])if(/^utm_/i.test(key)||['gclid','fbclid','msclkid'].includes(key.toLowerCase()))u.searchParams.delete(key);
 const host=u.hostname.replace(/^www\./,'');
 if(['x.com','twitter.com'].includes(host)){const id=u.pathname.match(/^\/[^/]+\/status\/(\d+)\/?$/);if(id)return 'x:status:'+id[1];}
 if(host==='xiaohongshu.com'||host==='rednote.com'){const id=u.pathname.match(/^\/(?:explore|search_result)\/([a-zA-Z0-9]+)\/?$/);if(id)return 'xiaohongshu:note:'+id[1];}
 if(host==='youtu.be')return 'youtube:video:'+u.pathname.slice(1);
 if(host==='youtube.com'&&u.pathname==='/watch'&&u.searchParams.get('v'))return 'youtube:video:'+u.searchParams.get('v');
 u.searchParams.sort();return u.href;
 }
 function kind(item,source){const u=new URL(item.url),host=u.hostname.replace(/^www\./,'');
 if(host==='youtu.be'||(host==='youtube.com'&&u.pathname==='/watch')||(host==='bilibili.com'&&u.pathname.startsWith('/video/')))return 'video';
 if(['x','weibo','xiaohongshu'].includes(source))return 'post';
 return ['web','post','video'].includes(item.kind)?item.kind:'web';}
 function merge(groups){const merged=[],seen=new Map(),size=Math.max(0,...groups.map(g=>g.items?.length||0));
 for(let index=0;index<size;index++)for(const group of groups){const item=group.items?.[index];if(!item||typeof item.url!=='string'||typeof item.title!=='string'||!item.title.trim())continue;const key=canonical(item.url);if(!key)continue;
 const origin={source:group.source,provider:group.provider||group.source,url:item.url};let existing=seen.get(key);
 if(existing){const category=kind(item,group.source);if(category!=='web')existing.kind=category;if(!existing.sources.some(s=>s.source===origin.source&&s.provider===origin.provider))existing.sources.push(origin);for(const field of ['summary','content','image_url','image_data_url','author','published_at','duration','view_count','like_count','repost_count','comment_count'])if(!existing[field]&&item[field])existing[field]=item[field];continue;}
 existing={...item,title:item.title,url:item.url,summary:String(item.summary||''),kind:kind(item,group.source),sources:[origin]};seen.set(key,existing);merged.push(existing);
 }return merged;}
 global.SearchAllResults=Object.freeze({canonical,merge});
})(typeof window==='undefined'?globalThis:window);
