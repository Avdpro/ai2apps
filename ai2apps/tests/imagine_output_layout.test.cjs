const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const css=fs.readFileSync(__dirname+'/../web/static/css/imagine_studio.css','utf8');
function rule(selector){const start=css.indexOf(selector+'{');assert.notEqual(start,-1,selector);return css.slice(start+selector.length+1,css.indexOf('}',start));}
test('Imagine Output preserves and wraps long JSON model errors within the flexible card column',()=>{
 const error=rule('.is-app .is-image-queue .vs-task-error');
 assert.match(error,/white-space:pre-wrap/);assert.match(error,/overflow-wrap:anywhere/);assert.match(error,/max-width:100%/);
 assert.doesNotMatch(error,/line-clamp|overflow:hidden|text-overflow:ellipsis/);
 assert.match(rule('.is-app .is-image-queue .vs-task-main'),/min-width:0/);
});
test('shared Output inspector title and metadata can shrink without pushing controls out',()=>{
 assert.match(rule('.is-app .is-run-title>div'),/min-width:0;flex:1/);
 assert.match(rule('.is-app .is-run-status'),/flex-shrink:0/);
 assert.match(rule('.is-app .is-step>span'),/min-width:0/);
 assert.match(rule('.is-app .is-artifact-list button'),/minmax\(0,40%\)/);
 assert.match(rule('.is-app .is-artifact-list button span,.is-app .is-artifact-list button small'),/overflow-wrap:anywhere/);
});
