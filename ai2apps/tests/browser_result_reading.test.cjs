const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const s=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');
function reader(){const context={URL};vm.runInNewContext('globalThis.Reader=class{'+s.slice(s.indexOf('        async readResultPages('),s.indexOf('        async extractArticleList('))+'}',context); const client=new context.Reader(); const visits=[];client.contextId='tab';client.pageState=async()=>({url:'https://www.google.com/search?q=test'});client.connection={command:async(_,p)=>visits.push(p.url)};client.handlePageAccess=async()=>({});client.extractRenderedPage=async()=>({url:visits.at(-1),title:'Page',text:'Body'});return {client,visits};}
test('reads bounded distinct result pages and restores search tab',async()=>{const {client,visits}=reader();const result=await client.readResultPages([{url:'https://a.example/1'},{url:'https://a.example/1'},{url:'https://b.example/2'},{url:'https://c.example/3'}],2);assert.equal(result.articles.length,2);assert.deepEqual(visits,['https://a.example/1','https://b.example/2','https://www.google.com/search?q=test']);});
test('blocked page is recorded and other pages still contribute',async()=>{const {client,visits}=reader();let n=0;client.handlePageAccess=async()=>++n===1?{classification:'restricted',reason:'paywall'}:{};const result=await client.readResultPages([{url:'https://a.example/1'},{url:'https://b.example/2'}]);assert.equal(result.failures[0].reason,'paywall');assert.equal(result.articles.length,1);assert.match(visits.at(-1),/google/);});
test('failed reads restore initial tab and keep failures',async()=>{const {client,visits}=reader();client.extractRenderedPage=async()=>{throw Error('Read failed')};const result=await client.readResultPages([{url:'https://a.example/1'},{url:'javascript:alert(1)'}]);assert.equal(result.articles.length,0);assert.equal(result.failures.length,1);assert.match(visits.at(-1),/google/);});

function consentReader({names=['Deny'], dismisses=true, unrelated=false}={}) {
    let open=true, clicks=[];
    const rect={left:100,right:240,top:100,bottom:140,width:140,height:40};
    const nodes=names.map(name=>({getBoundingClientRect:()=>rect,getAttribute:()=>null,
        innerText:name,textContent:name,title:'',contains:()=>true}));
    const panel={innerText:'This website uses cookies',getBoundingClientRect:()=>rect,querySelectorAll:()=>nodes};
    const context={innerWidth:1152,innerHeight:890,
        getComputedStyle:()=>({display:'block',visibility:'visible',opacity:1}),
        document:{querySelectorAll:()=>open&&!unrelated?[panel]:[],elementFromPoint:()=>nodes[0],body:{innerText:'Article'}}};
    vm.runInNewContext('globalThis.Reader=class{'+s.slice(s.indexOf('        async handlePageAccess('),s.indexOf('        async pickElement('))+'}',context);
    const client=new context.Reader();client.callJSON=async code=>vm.runInNewContext('('+code+')()',context);
    client.naturalPointer=async candidate=>{clicks.push(candidate);if(dismisses)open=false;};
    client.waitForStability=async()=>({stable:true});
    return {client,clicks,nodes,context};
}
test('Cookiebot Deny dismisses consent and verifies the overlay disappeared',async()=>{
    const {client,clicks}=consentReader();const result=await client.handlePageAccess();
    assert.equal(clicks.length,1);assert.equal(clicks[0].name,'Deny');assert.equal(result.classification,'none');assert.equal(result.dismissed,true);
});
test('unknown consent actions require help, never choose Allow all',async()=>{
    const {client,clicks}=consentReader({names:['Allow selection','Allow all']});
    assert.equal((await client.handlePageAccess()).reason,'cookie_consent');assert.equal(clicks.length,0);
});
test('consent click that does not dismiss is bounded and requests assistance',async()=>{
    const {client,clicks}=consentReader({dismisses:false});const result=await client.handlePageAccess();
    assert.equal(clicks.length,3);assert.equal(result.classification,'needs_user');assert.equal(result.reason,'cookie_consent');
});
test('unrelated Deny or Close controls are not consent actions',async()=>{
    const {client,clicks}=consentReader({names:['Deny','Close'],unrelated:true});
    assert.equal((await client.handlePageAccess()).classification,'none');assert.equal(clicks.length,0);
});
test('offscreen consent controls are ignored and partial controls are clipped',async()=>{
    const {client,clicks,nodes}=consentReader({names:['Close','Deny']});
    nodes[0].getBoundingClientRect=()=>({left:1180,right:1212,top:20,bottom:52,width:32,height:32});
    nodes[1].getBoundingClientRect=()=>({left:1135,right:1170,top:20,bottom:52,width:35,height:32});
    await client.handlePageAccess();assert.equal(clicks[0].rect.x,1135);assert.equal(clicks[0].rect.width,17);
});

test('different redirect links resolving to one article do not duplicate summary evidence', async () => {
    const {client} = reader();
    let calls = 0;
    client.extractRenderedPage = async () => ({url:++calls < 3 ? 'https://site.example/one' : 'https://site.example/two',text:'Article'});
    const result = await client.readResultPages([{url:'https://search.example/1'}, {url:'https://search.example/2'}, {url:'https://search.example/3'}], 2);
    assert.equal(result.articles.length, 2);
    assert.equal(calls, 3);
});

test('temporary tabs close even on read failure and restore context without navigating search',async()=>{
 const {client}=reader(),commands=[];let serial=0;
 client.connection={command:async(method,params)=>{commands.push({method,params});return method==='browsingContext.create'?{context:'child'+(++serial)}:{}}};
 client.extractRenderedPage=async()=>{throw Error('read error')};
 const result=await client.readResultPages([{url:'https://a.example/1'},{url:'https://b.example/2'}],2,{newTab:true});
 assert.equal(result.failures.length,2);assert.equal(client.contextId,'tab');
 assert.deepEqual(commands.filter(c=>c.method==='browsingContext.close').map(c=>c.params.context),['child1','child2']);
 assert.equal(commands.filter(c=>c.method==='browsingContext.navigate').length,2);
 assert.equal(commands.at(-1).method,'browsingContext.activate');
});

test('Google external headings and opaque goto results survive, navigation links do not',async()=>{
 const heading={tagName:'H3',textContent:'BiDi reference'};
 const anchor=(url,h)=>({href:url,getAttribute:()=>null,querySelector:selector=>selector==='h1,h2,h3,h4'&&h?heading:null,closest:()=>null,getBoundingClientRect:()=>({width:120,height:40}),textContent:'BiDi reference',innerText:'BiDi reference'});
 const context={URL,getComputedStyle:()=>({display:'block',visibility:'visible'}),location:{hostname:'www.google.com',pathname:'/search',origin:'https://www.google.com',href:'https://www.google.com/search?q=bidi'},document:{title:'Search',querySelector:()=>({querySelectorAll:selector=>selector==='h1,h2,h3,h4'?[]:[anchor('https://developer.mozilla.org/en-US/docs/Web/WebDriver',true),anchor('https://www.google.com/goto?url=opaque',true),anchor('https://www.google.com/search?q=other',true)]}),querySelectorAll:()=>[anchor('https://developer.mozilla.org/en-US/docs/Web/WebDriver',true),anchor('https://www.google.com/goto?url=opaque',true),anchor('https://www.google.com/search?q=other',true)]}};
 vm.runInNewContext('globalThis.Reader=class{'+s.slice(s.indexOf('        async extractArticleList('),s.indexOf('        async handlePageAccess('))+'}',context);
 const client=new context.Reader();client.callJSON=async code=>vm.runInNewContext('('+code+')()',context);
 const result=await client.extractArticleList(5);assert.equal(result.items.length,2);
});
