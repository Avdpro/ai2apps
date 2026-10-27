const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),cp=require('node:child_process'),path=require('node:path');
const {chromium}=require('playwright');
test('X identity extraction excludes side recommendations and confirms explicit profile identity',async()=>{
 const python=path.resolve(__dirname,'../../.venv/bin/python');
 const script=cp.execFileSync(python,['-c',"from ai2apps.browser.social import ACCOUNT_SCRIPT; print(ACCOUNT_SCRIPT)"],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}).trim();
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage();
 await p.route('https://x.com/**',route=>route.fulfill({contentType:'text/html; charset=utf-8',body:'<main><div data-testid="primaryColumn"><div data-testid="UserCell"><a href="/elonmusk">Elon Musk</a><p>@elonmusk</p></div><div data-testid="UserName">Elon Musk<br>@elonmusk</div></div><aside data-testid="sidebarColumn"><div data-testid="UserCell"><a href="/unrelated">Recommendation</a></div></aside></main>'}));
 await p.goto('https://x.com/search?q=Elon&f=user');
 let d=await p.evaluate(`(${script})('Elon')`);assert.deepEqual(d.candidates.map(x=>x.handle),['elonmusk']);
 await p.goto('https://x.com/elonmusk');d=await p.evaluate(`(${script})('@elonmusk')`);assert.deepEqual(d.candidates.map(x=>x.handle),['elonmusk']);
 }finally{await browser.close()}
});

test('X timeline DOM marks old pins and keeps original IDs across overlapping views',async()=>{
 const python=path.resolve(__dirname,'../../.venv/bin/python');
 const script=cp.execFileSync(python,['-c','from ai2apps.browser.social import POSTS_SCRIPT; print(POSTS_SCRIPT)'],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}).trim();
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage();await p.route('https://x.com/**',r=>r.fulfill({contentType:'text/html; charset=utf-8',body:'<article data-testid="tweet"><div data-testid="socialContext">Pinned</div><a href="/user/status/1"><time datetime="2020-01-01T00:00:00Z"></time></a><div data-testid="tweetText">Old pin</div></article><article data-testid="tweet"><a href="/user/status/2"><time datetime="2026-10-22T00:01:00Z"></time></a><div data-testid="tweetText">Today</div></article>'}));await p.goto('https://x.com/user');let d=await p.evaluate(`(${script})()`);assert.equal(d.items[0].pinned,true);assert.deepEqual(d.items.map(x=>x.id),['1','2']);assert.equal(d.items[1].url,'https://x.com/user/status/2');
 }finally{await browser.close()}
});

test('Xiaohongshu and Weibo owner DOM adapters extract observed identities, dates and scoped posts',async()=>{
 const python=path.resolve(__dirname,'../../.venv/bin/python');
 const scripts=JSON.parse(cp.execFileSync(python,['-c','import json; from ai2apps.browser.social_platforms import ACCOUNT_SCRIPT,POSTS_SCRIPT,DETAIL_SCRIPT; print(json.dumps([ACCOUNT_SCRIPT,POSTS_SCRIPT,DETAIL_SCRIPT]))'],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}));
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage({timezoneId:'Asia/Shanghai'});
 const id='1234567890abcdef12345678',note='abcdef1234567890abcdef12';
 await p.route('https://www.xiaohongshu.com/**',r=>r.fulfill({contentType:'text/html; charset=utf-8',body:`<div class="user-info"><a href="/user/profile/${id}"><span class="user-name">测试账号</span></a></div><section class="note-item"><a href="/explore/${note}?xsec_token=observed">Note</a><span class="date">2026-10-22 03:00</span><span class="top-tag">置顶</span><div class="title">Observed note</div></section><div id="noteContainer"><a href="/user/profile/${id}">Author</a><span class="date">编辑于 2026-10-22 03:00 上海</span><div id="detail-desc">Full observed note</div></div>`}));
 await p.goto('https://www.xiaohongshu.com/user/profile/'+id);let d=await p.evaluate(`(${scripts[0]})('xiaohongshu')`);assert.equal(d.candidates[0].handle,id);
 d=await p.evaluate(`(${scripts[1]})('xiaohongshu','${id}')`);assert.equal(d.items[0].id,note);assert.equal(d.items[0].published_at,'2026-10-21T19:00:00.000Z');assert.equal(d.items[0].pinned,true);assert.match(d.items[0].url,/xsec_token=observed/);
 await p.goto('https://www.xiaohongshu.com/explore/'+note);d=await p.evaluate(`(${scripts[2]})('xiaohongshu','${id}','${note}')`);assert.equal(d.text,'Full observed note');assert.equal(d.published_at,'2026-10-21T19:00:00.000Z');
 d=await p.evaluate(`(${scripts[2]})('xiaohongshu','aaaaaaaaaaaaaaaaaaaaaaaa','${note}')`);assert.deepEqual(d,{});
 d=await p.evaluate(`(${scripts[2]})('xiaohongshu','${id}','aaaaaaaaaaaaaaaaaaaaaaaa')`);assert.deepEqual(d,{});
 await p.evaluate(()=>{const hidden=document.querySelector('#noteContainer').cloneNode(true);hidden.style.display='none';hidden.querySelector('#detail-desc').innerText='Wrong hidden text';document.body.prepend(hidden);});
 d=await p.evaluate(`(${scripts[2]})('xiaohongshu','${id}','${note}')`);assert.equal(d.text,'Full observed note');
 await p.route('https://weibo.com/**',r=>r.fulfill({contentType:'text/html; charset=utf-8',body:'<div class="ProfileHeader_main__2xrKh"><a href="/u/1234567890"><span class="ProfileHeader_name">微博测试</span></a></div><div class="card-wrap"><p class="from"><a href="/1234567890/Post123" title="2026-10-22 03:00">Today</a></p><p class="txt">Observed post</p></div>'}));
 await p.goto('https://weibo.com/u/1234567890');d=await p.evaluate(`(${scripts[0]})('weibo')`);assert.equal(d.candidates[0].handle,'1234567890');d=await p.evaluate(`(${scripts[1]})('weibo','1234567890')`);assert.equal(d.items[0].id,'Post123');assert.equal(d.items[0].published_at,'2026-10-21T19:00:00.000Z');
 d=await p.evaluate(`(${scripts[1]})('weibo','9999999999')`);assert.equal(d.outside_scope,true);
 }finally{await browser.close()}
});

test('both Xiaohongshu homes use visible self navigation as login evidence',async()=>{
 const scripts=JSON.parse(cp.execFileSync(path.resolve(__dirname,'../../.venv/bin/python'),['-c','import json; from ai2apps.browser.social_platforms import HOME_SCRIPT,ACCOUNT_SCRIPT; print(json.dumps([HOME_SCRIPT,ACCOUNT_SCRIPT]))'],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}));
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage();const id='1234567890abcdef12345678';
 for(const host of ['www.rednote.com','www.xiaohongshu.com']){
 await p.route('https://'+host+'/**',r=>r.fulfill({contentType:'text/html; charset=utf-8',body:`<a href="/user/profile/${id}">Feed author</a><div class="login-modal" style="display:none">登录</div>`}));
 await p.goto('https://'+host+'/');assert.equal((await p.evaluate(`(${scripts[0]})()`)).state,'unknown');
 await p.evaluate(id=>{document.body.insertAdjacentHTML('beforeend',`<a href="/user/profile/${id}">我</a>`);},id);
 assert.equal((await p.evaluate(`(${scripts[0]})()`)).state,'logged_in');
 await p.evaluate(()=>document.querySelector('.login-modal').style.display='block');assert.equal((await p.evaluate(`(${scripts[0]})()`)).state,'login_required');
 await p.goto('https://'+host+'/user/profile/'+id);
 await p.evaluate(id=>document.body.innerHTML=`<div class="user-info"><a href="/user/profile/${id}"><span class="user-name">测试账号</span></a></div><div class="user"><a href="/user/profile/aaaaaaaaaaaaaaaaaaaaaaaa">我</a></div>`,id);
 assert.deepEqual((await p.evaluate(`(${scripts[1]})('xiaohongshu')`)).candidates.map(c=>c.handle),[id]);
 }
 }finally{await browser.close()}
});

test('Xiaohongshu search ignores self navigation and extracts post author identity, not title mentions',async()=>{
 const script=cp.execFileSync(path.resolve(__dirname,'../../.venv/bin/python'),['-c','from ai2apps.browser.social_platforms import ACCOUNT_SCRIPT;print(ACCOUNT_SCRIPT)'],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}).trim();
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage();const id='1234567890abcdef12345678';
 await p.route('https://www.rednote.com/**',r=>r.fulfill({contentType:'text/html; charset=utf-8',body:`<aside><div class="user"><a href="/user/profile/aaaaaaaaaaaaaaaaaaaaaaaa">我</a></div></aside><nav><div class="user"><a href="/user/profile/bbbbbbbbbbbbbbbbbbbbbbbb">Navigation</a></div></nav><section class="note-item"><div class="title">晃悠的程序员</div><div class="author-wrapper"><a class="author" href="/user/profile/${id}?xsec_token=observed"><span class="name">Observed author</span><span>09-22</span></a></div></section>`}));
 await p.goto('https://www.rednote.com/search_result?keyword=example');let result=await p.evaluate(`(${script})('xiaohongshu')`);
 assert.equal(result.candidates.length,1);assert.equal(result.candidates[0].handle,id);assert.equal(result.candidates[0].name,'Observed author');assert.equal(result.candidates[0].identity_source,'post_author');assert.match(result.candidates[0].url,/xsec_token=observed/);
 await p.evaluate(()=>document.querySelector('.note-item').remove());result=await p.evaluate(`(${script})('xiaohongshu')`);assert.deepEqual(result.candidates,[]);
 }finally{await browser.close()}
});

test('profile-nested Xiaohongshu note URLs are scoped to the confirmed author and keep access parameters',async()=>{
 const script=cp.execFileSync(path.resolve(__dirname,'../../.venv/bin/python'),['-c','from ai2apps.browser.social_platforms import POSTS_SCRIPT;print(POSTS_SCRIPT)'],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}).trim();
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage();const id='1234567890abcdef12345678',note='abcdef1234567890abcdef12';
 await p.route('https://www.rednote.com/**',r=>r.fulfill({contentType:'text/html; charset=utf-8',body:`<section class="note-item"><a href="/user/profile/${id}/${note}?xsec_token=observed">置顶</a><div class="title">Actual note</div></section><section class="note-item"><a href="/user/profile/aaaaaaaaaaaaaaaaaaaaaaaa/${note}">Foreign account</a></section>`}));
 await p.goto('https://www.rednote.com/user/profile/'+id);const result=await p.evaluate(`(${script})('xiaohongshu','${id}')`);
 assert.equal(result.items.length,1);assert.equal(result.items[0].id,note);assert.equal(result.items[0].pinned,true);assert.match(result.items[0].url,/xsec_token=observed/);
 }finally{await browser.close()}
});

test('social image extraction distinguishes X static covers and deduplicates carousel clones',async()=>{
 const scripts=JSON.parse(cp.execFileSync(path.resolve(__dirname,'../../.venv/bin/python'),['-c','import json;from ai2apps.browser.social import POSTS_SCRIPT;from ai2apps.browser.social_platforms import DETAIL_SCRIPT;print(json.dumps([POSTS_SCRIPT,DETAIL_SCRIPT]))'],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}));
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage();
 await p.route('https://x.com/**',r=>r.fulfill({contentType:'text/html',body:'<article data-testid="tweet"><img src="https://cdn.example/avatar"><a href="/fixture/status/123"><time datetime="2026-10-22T00:00:00Z"></time></a><div data-testid="tweetPhoto"><img src="https://cdn.example/photo?name=small"></div><a href="/fixture/status/123/photo/2" style="display:block;width:100px;height:100px">Image</a><a href="/quote/status/999/photo/1">Quote image</a><div data-testid="videoPlayer"><div data-testid="tweetPhoto"><img src="https://cdn.example/video"></div></div></article>'}));
 await p.goto('https://x.com/fixture');let d=await p.evaluate(`(${scripts[0]})()`);assert.deepEqual(d.items[0].images.map(i=>i.src),['https://cdn.example/photo?name=small','https://x.com/fixture/status/123/photo/2','https://cdn.example/video']);assert.equal(d.items[0].images[2].kind,'video_cover');
 const author='1234567890abcdef12345678',id='abcdef1234567890abcdef12';
 await p.route('https://www.rednote.com/**',r=>r.fulfill({contentType:'text/html',body:`<div id="noteContainer"><a href="/user/profile/${author}"><img src="https://cdn.example/avatar"></a><div class="swiper"><div class="swiper-slide"><img src="https://cdn.example/1?token=a"></div><div class="swiper-slide"><img src="https://cdn.example/2"></div><div class="swiper-slide"><img src="https://cdn.example/1?token=b"></div></div></div>`}));
 await p.goto('https://www.rednote.com/explore/'+id);d=await p.evaluate(`(${scripts[1]})('xiaohongshu','${author}','${id}')`);assert.equal(d.images.length,2);assert.deepEqual(d.images.map(i=>i.index),[0,1]);assert.ok(d.images.every(i=>i.ref.startsWith('m')));
 }finally{await browser.close()}
});

test('X photo dialog is bound to the confirmed post and supports CSS image containers',async()=>{
 const script=cp.execFileSync(path.resolve(__dirname,'../../.venv/bin/python'),['-c','from ai2apps.browser.social import X_PHOTO_SCRIPT;print(X_PHOTO_SCRIPT)'],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}).trim();
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage();await p.route('https://x.com/**',r=>r.fulfill({contentType:'text/html',body:'<div role="dialog"><div role="img" style="background-image:url(https://pbs.twimg.com/media/fixture.jpg);width:400px;height:600px"></div><img src="https://pbs.twimg.com/profile_images/avatar.jpg"></div>'}));
 await p.goto('https://x.com/fixture/status/123/photo/1');let d=await p.evaluate(`(${script})('fixture','123')`);assert.equal(d.length,1);assert.equal(d[0].src,'https://pbs.twimg.com/media/fixture.jpg');
 d=await p.evaluate(`(${script})('fixture','999')`);assert.deepEqual(d,[]);
 }finally{await browser.close()}
});

test('X detail binds URL and author without timeline time and distinguishes video covers',async()=>{
 const python=path.resolve(__dirname,'../../.venv/bin/python');
 const script=cp.execFileSync(python,['-c','from ai2apps.browser.social import X_DETAIL_SCRIPT; print(X_DETAIL_SCRIPT)'],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}).trim();
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage();await p.route('https://x.com/**',r=>r.fulfill({contentType:'text/html',body:'<article data-testid="tweet"><div data-testid="User-Name"><a href="/elonmusk">Elon Musk</a></div><div data-testid="tweetText">True</div><div data-testid="tweetPhoto"><img src="https://pbs.twimg.com/media/photo.jpg"></div><div data-testid="videoPlayer"><img src="https://pbs.twimg.com/profile_images/avatar.jpg"><img src="https://pbs.twimg.com/amplify_video_thumb/cover.jpg"><video></video></div></article>'}));
 await p.goto('https://x.com/elonmusk/status/123');let d=await p.evaluate(`(${script})('elonmusk','123')`);assert.equal(d.item.text,'True');assert.deepEqual(d.item.images.map(i=>i.kind),['photo','video_cover']);assert.ok(d.item.images.every(i=>i.ref));
 d=await p.evaluate(`(${script})('other','123')`);assert.equal(d.reason,'post_detail_identity_mismatch');
 await p.locator('[data-testid="User-Name"] a').evaluate(n=>n.href='/other');d=await p.evaluate(`(${script})('elonmusk','123')`);assert.equal(d.reason,'post_detail_author_unverified');
 }finally{await browser.close();}
});

test('X detail separates quoted originals and verifies reply parent without following descendants',async()=>{
 const python=path.resolve(__dirname,'../../.venv/bin/python');
 const script=cp.execFileSync(python,['-c','from ai2apps.browser.social import X_DETAIL_SCRIPT; print(X_DETAIL_SCRIPT)'],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}).trim();
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage();
 const article=(who,id,text,extra='')=>`<article data-testid="tweet"><div data-testid="User-Name"><a href="/${who}">${who}</a></div><a href="/${who}/status/${id}"><time datetime="2026-10-23T00:00:00Z"></time></a><div data-testid="tweetText">${text}</div>${extra}</article>`;
 let body=article('original','10','Parent text','<div data-testid="tweetPhoto"><a href="/original/status/10/photo/1"><img src="https://pbs.twimg.com/media/parent.jpg"></a></div>')+article('reader','20','True','<div>Replying to <a href="/original">@original</a></div><div data-testid="quoteTweet"><a href="/quoted/status/30"><time datetime="2020-01-01T00:00:00Z"></time></a><div data-testid="tweetText">Quoted text</div><div data-testid="tweetPhoto"><img src="https://pbs.twimg.com/media/quote.jpg"></div></div>')+article('unrelated','40','Recommendation');
 await p.route('https://x.com/**',r=>r.fulfill({contentType:'text/html; charset=utf-8',body}));await p.goto('https://x.com/reader/status/20');
 let d=(await p.evaluate(`(${script})('reader','20')`)).item;
 assert.equal(d.text,'True');assert.equal(d.images.length,0);
 assert.deepEqual(d.related_posts.map(r=>[r.id,r.relation,r.text]),[['30','quoted','Quoted text'],['10','reply_to','Parent text']]);
 assert.equal(d.related_posts[0].images.length,1);assert.equal(d.related_posts[1].images.length,1);
 // Another account between the parent and reply must not be skipped to infer
 // a relationship to an older arbitrary article.
 body=article('original','10','Unverified ancestor')+article('other','15','Intervening post')+article('reader','20','Reply','<div>Replying to <a href="/original">@original</a></div>');
 await p.reload();d=(await p.evaluate(`(${script})('reader','20')`)).item;
 assert.equal(d.related_posts[0].context_status,'unavailable');assert.equal(d.related_posts[0].reason,'original_post_not_observed');
 }finally{await browser.close()}
});

test('X href-less quote cards expose a fresh text target, never a social action',async()=>{
 const python=path.resolve(__dirname,'../../.venv/bin/python');
 const scripts=JSON.parse(cp.execFileSync(python,['-c','import json; from ai2apps.browser.social import X_DETAIL_SCRIPT,X_ORIGINAL_TARGET_SCRIPT; print(json.dumps([X_DETAIL_SCRIPT,X_ORIGINAL_TARGET_SCRIPT]))'],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}));
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage();let body='<article data-testid="tweet"><a href="/reader/status/20"><time datetime="2026-10-23T00:00:00Z"></time></a><div data-testid="tweetText">Reply</div><div role="link" tabindex="0"><div data-testid="tweetText"><span>Original text</span></div><button>Like</button></div></article>';
 await p.route('https://x.com/**',r=>r.fulfill({contentType:'text/html',body}));await p.goto('https://x.com/reader/status/20');
 let item=(await p.evaluate(`(${scripts[0]})('reader','20')`)).item;
 assert.equal(item.text,'Reply');assert.equal(item.related_posts[0].reason,'original_post_identity_unavailable');
 let target=await p.evaluate(`(${scripts[1]})(${JSON.stringify(item.related_posts[0].observed_ref)})`);assert.ok(target.rect.width>0);
 assert.equal(await p.evaluate(`(${scripts[1]})('stale-ref')`),null);
 body=body.replace('<span>Original text</span>','<button style="display:block;width:100%">Like</button>');await p.reload();item=(await p.evaluate(`(${scripts[0]})('reader','20')`)).item;
 target=await p.evaluate(`(${scripts[1]})(${JSON.stringify(item.related_posts[0].observed_ref)})`);assert.equal(target,null);
 }finally{await browser.close()}
});

test('social likes preserve exact/approximate/missing values on both XHS origins and Weibo',async()=>{
 const scripts=JSON.parse(cp.execFileSync(path.resolve(__dirname,'../../.venv/bin/python'),['-c','import json;from ai2apps.browser.social_platforms import POSTS_SCRIPT,DETAIL_SCRIPT;print(json.dumps([POSTS_SCRIPT,DETAIL_SCRIPT]))'],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}));
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage(),handle='1234567890abcdef12345678',id='aaaaaaaaaaaaaaaaaaaaaaaa';
 for(const host of ['www.rednote.com','www.xiaohongshu.com']){
 await p.route('https://'+host+'/**',r=>r.fulfill({contentType:'text/html; charset=utf-8',body:`<section class="note-item"><a href="/discovery/item/${id}">Post</a><time datetime="2026-10-25T12:30:00Z"></time><span class="like-wrapper"><span class="count">1.2万</span></span><span class="comment-wrapper"><span class="count">4</span></span><span class="share-wrapper"><span class="count">3</span></span></section>`}));
 await p.goto('https://'+host+'/user/profile/'+handle);
 let d=await p.evaluate(`(${scripts[0]})('xiaohongshu','${handle}')`);assert.equal(d.items[0].published_at,'2026-10-25T12:30:00.000Z');assert.equal(d.items[0].likes.count,12000);assert.equal(d.items[0].likes.status,'approximate');assert.equal(d.items[0].metrics.comments.count,4);assert.equal(d.items[0].metrics.reposts.count,3);
 await p.goto('https://'+host+'/discovery/item/'+id);
 await p.evaluate(({handle})=>document.body.innerHTML=`<div id="noteContainer"><a href="/user/profile/${handle}">Author</a><div id="detail-desc">Post body</div><span class="like-wrapper"><span class="count">23</span></span></div>`,{handle});
 d=await p.evaluate(`(${scripts[1]})('xiaohongshu','${handle}','${id}')`);assert.equal(d.likes.count,23);assert.equal(d.likes.status,'observed');
 await p.evaluate(()=>document.querySelector('.count').textContent='0');d=await p.evaluate(`(${scripts[1]})('xiaohongshu','${handle}','${id}')`);assert.equal(d.likes.count,0);
 await p.evaluate(()=>document.querySelector('.like-wrapper').remove());d=await p.evaluate(`(${scripts[1]})('xiaohongshu','${handle}','${id}')`);assert.equal(d.likes.count,null);assert.equal(d.likes.reason,'like_control_not_observed');
 }
 await p.route('https://weibo.com/**',r=>r.fulfill({contentType:'text/html',body:'<article><a href="/1234567890/Abc" date="1792957770000">Today</a><span class="woo-like-count">1,234</span></article>'}));
 await p.goto('https://weibo.com/u/1234567890');const d=await p.evaluate(`(${scripts[0]})('weibo','1234567890')`);assert.equal(d.items[0].likes.count,1234);
 }finally{await browser.close()}
});
