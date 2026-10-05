const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../web/static/js/agent_mini.js'), 'utf8');
const context = {URL};
vm.runInNewContext(source.slice(source.indexOf('    function navigationMentionedInGoal('), source.indexOf('    async function distillExploration(')) + '\nglobalThis.needs = explorationActionNeedsConfirmation;', context);
const open = url => ({operation:'open', arguments:{url}});
for (const [goal, url] of [
    ['用Google搜索OpenAI上市时间', 'https://www.google.com/search?q=OpenAI'],
    ['用谷歌搜索', 'https://www.google.com/'],
    ['打开 https://example.com/news', 'https://example.com/'],
    ['访问 www.example.net', 'https://example.net/a'],
    ['打开维基百科', 'https://zh.wikipedia.org/'],
]) {
    test('explicitly mentioned website opens without confirmation: ' + goal, () => {
        assert.equal(context.needs(open(url), {}, goal), false);
    });
}
test('unmentioned and lookalike websites still need confirmation', () => {
    for (const url of ['https://other.example/', 'https://google.com.evil.example/', 'https://notgoogle.com/']) {
        assert.equal(context.needs(open(url), {}, '用Google搜索'), true);
    }
});
test('mentioned navigation ignores generic confirmation; other interactions stay unchanged', () => {
    assert.equal(context.needs(open('https://www.google.com/'), {confirmation:{required:true}}, 'Google'), false);
    assert.equal(context.needs({operation:'delete'}, {confirmation:{required:true}}, 'Google'), true);
    for (const operation of ['click','input','delete','page_access']) {
        assert.equal(context.needs({operation}, {}, 'Google'), true);
    }
});
test('requested search input and submit run without generic submit confirmation', () => {
    for (const operation of ['input', 'click']) {
        const step = {operation, target:{intent:'Google search box'},
            description:"Type the query into Google's search box and submit the search."};
        assert.equal(context.needs(step, {confirmation:{required:true,effect:'commit'}},
            '用Google搜索OpenAI上市时间', 'https://www.google.com/'), false);
    }
});
test('search exception excludes lookalike sites, unrelated tasks and consequential targets', () => {
    const step = {operation:'input',target:{intent:'Search box'},description:'Enter query'};
    const decision = {confirmation:{required:true}};
    assert.equal(context.needs(step, decision, '用Google搜索', 'https://google.com.evil.example/'), true);
    assert.equal(context.needs(step, decision, '登录Google', 'https://www.google.com/'), true);
    for (const target of ['Search and purchase', 'Search CAPTCHA', 'Search login password', 'Search and publish']) {
        assert.equal(context.needs({...step,target:{intent:target}}, decision,
            '用Google搜索', 'https://www.google.com/'), true);
    }
});
