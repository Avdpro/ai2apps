const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const s=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');
function reader(){const context={URL};vm.runInNewContext('globalThis.Reader=class{'+s.slice(s.indexOf('        async readResultPages('),s.indexOf('        async extractArticleList('))+'}',context); const client=new context.Reader(); const visits=[];client.contextId='tab';client.pageState=async()=>({url:'https://www.google.com/search?q=test'});client.connection={command:async(_,p)=>visits.push(p.url)};client.handlePageAccess=async()=>({});client.extractRenderedPage=async()=>({url:visits.at(-1),title:'Page',text:'Body'});return {client,visits};}
test('reads bounded distinct result pages and restores search tab',async()=>{const {client,visits}=reader();const result=await client.readResultPages([{url:'https://a.example/1'},{url:'https://a.example/1'},{url:'https://b.example/2'},{url:'https://c.example/3'}],2);assert.equal(result.articles.length,2);assert.deepEqual(visits,['https://a.example/1','https://b.example/2','https://www.google.com/search?q=test']);});
test('blocked page is recorded and other pages still contribute',async()=>{const {client,visits}=reader();let n=0;client.handlePageAccess=async()=>++n===1?{classification:'restricted',reason:'paywall'}:{};const result=await client.readResultPages([{url:'https://a.example/1'},{url:'https://b.example/2'}]);assert.equal(result.failures[0].reason,'paywall');assert.equal(result.articles.length,1);assert.match(visits.at(-1),/google/);});
test('failed reads restore initial tab and keep failures',async()=>{const {client,visits}=reader();client.extractRenderedPage=async()=>{throw Error('Read failed')};const result=await client.readResultPages([{url:'https://a.example/1'},{url:'javascript:alert(1)'}]);assert.equal(result.articles.length,0);assert.equal(result.failures.length,1);assert.match(visits.at(-1),/google/);});

test('access helper ignores offscreen close controls and clips partial controls', async () => {
    const node = rect => ({
        getBoundingClientRect: () => rect,
        getAttribute: () => null,
        innerText: 'Close', textContent: 'Close', title: '',
    });
    const context = {
        innerWidth: 1152, innerHeight: 890,
        getComputedStyle: () => ({display:'block', visibility:'visible', opacity:1}),
        document: {querySelectorAll: () => [
            node({left:1180, right:1212, top:20, bottom:52, width:32, height:32}),
            node({left:1135, right:1170, top:20, bottom:52, width:35, height:32}),
        ], body: {innerText:'Article'}},
    };
    vm.runInNewContext('globalThis.Reader=class{'+s.slice(s.indexOf('        async handlePageAccess('), s.indexOf('        async pickElement('))+'}', context);
    const client = new context.Reader();
    client.callJSON = async code => vm.runInNewContext('('+code+')()', context);
    let clicked;
    client.naturalPointer = async candidate => { clicked = candidate; };
    await client.handlePageAccess();
    assert.equal(clicked.rect.x, 1135);
    assert.equal(clicked.rect.width, 17);
});

test('different redirect links resolving to one article do not duplicate summary evidence', async () => {
    const {client} = reader();
    let calls = 0;
    client.extractRenderedPage = async () => ({url:++calls < 3 ? 'https://site.example/one' : 'https://site.example/two',text:'Article'});
    const result = await client.readResultPages([{url:'https://search.example/1'}, {url:'https://search.example/2'}, {url:'https://search.example/3'}], 2);
    assert.equal(result.articles.length, 2);
    assert.equal(calls, 3);
});
