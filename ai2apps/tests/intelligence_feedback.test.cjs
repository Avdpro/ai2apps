const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/intelligence.js','utf8');
test('reason choices escape model text and restore selected reasons',()=>{
 const env={esc:s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;')};Object.assign(env,require('./intelligence_test_env.cjs'));vm.createContext(env);
 vm.runInContext(source.slice(source.indexOf('function reasonOptions('),source.indexOf('async function dislikeDialog(')),env);
 const html=env.reasonOptions(['<script>','不关注追针'],['不关注追针']);
 assert.doesNotMatch(html,/<script>/);assert.match(html,/&lt;script>/);assert.match(html,/value="不关注追针" checked/);
});
