const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../web/static/js/agent_mini.js'), 'utf8');
const context = {URL, intent: step => step.target?.accessible_name || step.target?.intent || step.description || ""};
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
    for (const operation of ['click','input','page_access']) {
        assert.equal(context.needs({operation}, {}, 'Google'), false);
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

 test('requested Weibo navigation is preparation even when description mentions publishing', () => {
    const goal = '用附件中的图片（可能是多个）发布微博，内容是：又要过年了。';
    for (const url of ['https://weibo.com/', 'https://www.weibo.com/', 'https://weibo.cn/', 'https://m.weibo.cn/']) {
        assert.equal(context.needs({...open(url), description:'导航到微博主页，为后续点击发布按钮做准备。'},
            {confirmation:{required:true}}, goal), false);
    }
    assert.equal(context.needs(open('https://weibo.com.evil.example/'), {}, goal), true);
    assert.equal(context.needs({operation:'click',target:{intent:'发布微博'}},
        {confirmation:{required:true}}, goal, 'https://weibo.com/'), false);
 });

test('login entry is task preparation; credentials and publishing are separate actions', () => {
    const goal = '用附件发布微博';
    assert.equal(context.needs({operation:'click',target:{intent:'微博登录/注册按钮'}},
        {confirmation:{required:true}},goal,'https://weibo.com/'),false);
    assert.equal(context.needs({operation:'input',target:{intent:'登录密码'}},
        {confirmation:{required:true}},goal,'https://weibo.com/'),false);
    assert.equal(context.needs({operation:'click',target:{intent:'登录并授权付款'}},
        {confirmation:{required:true}},goal,'https://weibo.com/'),true);
});

test('compose input and attachment preparation ignore generic commit descriptions',()=>{
 for(const step of [{operation:'input',target:{intent:'微博发布框'},description:'输入要发布的微博文本'},
 {operation:'click',target:{intent:'图片'},description:'点击微博发布框图片按钮，为上传准备'}]){
 assert.equal(context.needs(step,{confirmation:{required:true}},'发布微博'),false);
 }
});
