const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../packages/ai2apps-media-voice-studio-suite/web/mini-app.js'),'utf8');
const elements=[];
function node(tag){const el={tag,children:[],handlers:{},append(...v){this.children.push(...v)},replaceChildren(...v){this.children=v},setAttribute(){},addEventListener(k,f){this.handlers[k]=f}};elements.push(el);return el;}
const state={result:{language:'en',duration:3,segments:[{start:0,end:3,text:'Original',speaker:'a',words:[{word:'Original'}]}]},roles:[{id:'a',name:'Alice'},{id:'b',name:'Bob'}]};
const context={state,node,document:{createElement:node},resultPanel:node('panel'),clock:String,speakerName:x=>x,setStatus(){}};
vm.runInNewContext(source.slice(source.indexOf('  function renderTranscript()'),source.indexOf('  function mountedCapabilityUrl('))+';renderTranscript();',context);
const text=elements.find(e=>e.tag==='textarea');text.value='Corrected';text.handlers.input();
assert.equal(state.result.segments[0].text,'Corrected');assert.equal(state.result.segments[0].words,undefined);assert.equal(state.result.segments[0].start,0);assert.equal(state.result.segments[0].end,3);
const speaker=elements.find(e=>e.tag==='select');speaker.value='b';speaker.handlers.change();assert.equal(state.result.segments[0].speaker,'b');
context.config={fields:[],roles:true,id:'transcription',capabilities:[]};
vm.runInNewContext(source.slice(source.indexOf('  function collect()'),source.indexOf('  function clock('))+';globalThis.draft=collect();',context);
assert.equal(context.draft.result.segments[0].text,'Corrected');assert.equal(context.draft.result.segments[0].speaker,'b');
console.log('PASS: transcript edits, speaker reassignment, word alignment invalidation and draft persistence');
