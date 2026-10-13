const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const src=fs.readFileSync(require('node:path').join(__dirname,'../browser/list_recovery.py'),'utf8');
const visibility=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8');
const script=src.match(/CANDIDATES_SCRIPT = r'''([\s\S]*?)'''/)[1];
test('unrecognized card classes still yield actual visible links and text',()=>{
  const card={innerText:'Observed body',querySelector:()=>null};
  const anchor={href:'https://example.org/article',innerText:'Observed title',
    getBoundingClientRect:()=>({width:100,height:30}),
    closest:q=>q.startsWith('article')?card:null,getAttribute:()=>null,querySelector:()=>null};
  const context={URL,location:{href:'https://search.example/search'},
    document:{title:'Search',querySelectorAll:q=>{assert.equal(q,'a[href]');return [anchor,anchor];}},
    getComputedStyle:()=>({visibility:'visible',display:'block'})};
  const read=vm.runInNewContext(visibility+';('+script+')',context);
  const result=read(true);
  assert.equal(result.items.length,1);
  assert.equal(result.items[0].url,anchor.href);
  assert.equal(result.items[0].title,'Observed title');
  assert.equal(result.items[0].content,'Observed body');
});
