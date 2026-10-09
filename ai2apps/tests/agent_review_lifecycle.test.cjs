const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/../web/static/js/agent_mini.js', 'utf8');
function context(api) {
  const nodes = new Map();
  const state = {recipe:{id:'recipe'}, review:{source_revision:3}, exploration:{status:'awaiting_review'}};
  const c = {state, api, Promise, saveRecipeEditor:async()=>{}, tr:k=>k, notice(){}, renderRecipeReview(){},
    renderExploration(){}, persistExplorationCheckpoint:async()=>{c.saved=state.exploration.status;},
    $:key=>{if(!nodes.has(key)) nodes.set(key,{scrollIntoView(){c.scrolled=true;}}); return nodes.get(key);}};
  for (const [start,end] of [['async function loadRecipeReview()', 'function rememberRecipe()'],
    ['async function approveRecipeReview()', 'function resultFromRun']]) {
    vm.runInNewContext(source.slice(source.indexOf('    '+start),source.indexOf('    '+end)),c);
  }
  return c;
}
test('restoring a committed recipe synchronizes the exploration checkpoint',async()=>{
  const c=context(async()=>({status:'approved',recipe_status:'committed'}));
  await c.loadRecipeReview();
  assert.equal(c.state.review.status,'approved');
  assert.equal(c.state.review.recipe_status,'committed');
  assert.equal(c.state.exploration.status,'committed');
});
test('approval persists its checkpoint and resets submitting label',async()=>{
  const c=context(async()=>({recipe:{id:'recipe',status:'tested'},review:{status:'approved'}}));
  await c.approveRecipeReview();
  assert.equal(c.saved,'approved');
  assert.equal(c.$('#agent-review-approve').textContent,'agent.mini.review_approve');
});
test('approval failure is brought into view and leaves the review retryable',async()=>{
  const c=context(async()=>{throw Error('revision conflict');});
  await c.approveRecipeReview();
  assert.equal(c.scrolled,true);
  assert.equal(c.state.review.source_revision,3);
  assert.equal(c.$('#agent-review-approve').textContent,'agent.mini.review_approve');
});
