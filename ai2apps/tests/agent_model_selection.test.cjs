const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/../web/static/js/agent_mini.js', 'utf8');
const context = {};
vm.runInNewContext(source.slice(source.indexOf('    function builderModelSupportsVisionChat('), source.indexOf('    async function loadBuilderModels(')) + '\nglobalThis.accepts=builderModelSupportsVisionChat;', context);
test('builder lists vision conversation models across catalog formats', () => {
 for (const model of [
  {model_type:'vlm'},
  {model_type:'vlm', capabilities:['conversation','image_recognition']},
  {model_type:'llm', capabilities:{conversation:true,imageInput:true}},
  {capabilities:{chat_completions:true},input_modalities:['text','image']},
  {capabilities:{textOutput:true,imageInput:true}},
 ]) assert.equal(context.accepts({id:'model',...model}),true,JSON.stringify(model));
});
test('builder excludes text-only, image generation, speech, embeddings and unknown models', () => {
 for (const model of [
  {model_type:'llm', capabilities:['conversation']},
  {model_type:'image', capabilities:['image_generation','image_recognition']},
  {model_type:'vlm', capabilities:{imageInput:true,imageOutput:true}},
  {model_type:'vlm', capabilities:{conversation:false,imageInput:true}},
  {model_type:'tts', capabilities:['speech_generation']},
  {model_type:'embedding'},
  {},
  {model_type:'vlm',endpoints:['images']},
 ]) assert.equal(context.accepts({id:'model',...model}),false,JSON.stringify(model));
});
test('system strengths precede models in high medium low order with medium selected', () => {
 const template = fs.readFileSync(__dirname + '/../web/templates/system_apps/agent_mini.html','utf8');
 const selection = template.slice(template.indexOf('id="agent-builder-model"'),template.indexOf('</select>',template.indexOf('id="agent-builder-model"')));
 assert.ok(selection.indexOf('tier:complex') < selection.indexOf('tier:standard'));
 assert.ok(selection.indexOf('tier:standard') < selection.indexOf('tier:simple'));
 assert.ok(selection.includes('option selected value="tier:standard"'));
 assert.ok(source.includes('.filter(builderModelSupportsVisionChat)'));
});
