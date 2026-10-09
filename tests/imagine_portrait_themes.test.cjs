const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx={window:{},document:{documentElement:{lang:'en'}},structuredClone,console};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../ai2apps/web/static/js/imagine_studio.js','utf8'),ctx);
const a=ctx.window.imagineStudioApp();a.miniAppId='ai2apps.imagine.portrait';
a.icons=()=>{};a.scheduleDraftSave=()=>{};a.reconcileSelectedModel=()=>{};
a.clearReference=i=>{a.referenceFiles[i]=null;};a.referenceFiles=[{name:'person.png'}];
assert.equal(a.portraitOptions.portraitMode.length,8);
a.portraitModeChanged('career');
assert.equal(a.portraitThemes.length,26);
assert.equal(new Set(a.portraitThemes.map(item=>item.id)).size,26);
a.portraitModeChanged('cinema');
assert.equal(a.portraitThemes.length,24);
assert.equal(new Set(a.portraitThemes.map(item=>item.id)).size,24);
for(const id of ['shining','conjuring','ring','grudge','scream','halloween','nightmare','silent-hill']) {
 a.portraitThemeId=id;a.portraitThemeChanged();
 assert.match(a.portraitPrompt(),/original guest character/);
 assert.match(a.portraitPrompt(),/subject recognizable and unharmed/);
 assert.match(a.portraitPrompt(),/No blood, gore/);
}
a.portraitThemeId='titanic';a.portraitThemeChanged();
assert.doesNotMatch(a.portraitPrompt(),/Build suspense/);
for(const id of ['star-wars','titanic','alien','terminator']) {
 a.portraitThemeId=id;a.portraitThemeChanged();
 assert.match(a.portraitPrompt(),/original guest character/);
 assert.match(a.portraitPrompt(),/do not copy an actor's face/);
 assert.match(a.portraitPrompt(),/No film title, credits, subtitles/);
}
for(const mode of ['career','sport','cinema','chinese','festival']){
 a.portraitModeChanged(mode);assert.equal(a.portraitReady,true);
 for(const theme of a.portraitThemes){
  a.portraitThemeId=theme.id;a.portraitThemeChanged();
  for(const locale of ['en','zh']){a.locale=locale;assert.notEqual(a.tr(theme.key),theme.key);}
  for(const kind of ['scene','outfit','action'])for(const item of theme[kind]){
   a['portraitTheme'+kind[0].toUpperCase()+kind.slice(1)]=item.id;
   assert.ok(a.portraitPrompt().includes(item.prompt));
   assert.notEqual(a.tr(item.key),item.key);
  }
  assert.doesNotMatch(a.portraitPrompt(),/undefined/);
 }
}
a.portraitModeChanged('sport');assert.equal(a.portraitThemes.length,20);assert.equal(a.portraitFraming,'full');
a.portraitThemeId='baseball';a.portraitThemeChanged();a.portraitThemeAction='1';assert.match(a.portraitPrompt(),/batting/);
a.editSubmissionPrompt('Manual override');a.portraitThemeId='basketball';a.portraitThemeChanged();a.syncSubmissionPrompt();assert.notEqual(a.submissionPrompt,'Manual override');assert.doesNotMatch(a.portraitPrompt(),/batting/);
a.portraitThemeScene='custom';assert.equal(a.portraitReady,false);a.portraitThemeSceneText='A rooftop court';assert.equal(a.portraitReady,true);
a.portraitThemeOutfit='custom';a.portraitThemeOutfitChanged();assert.equal(a.referenceSlotCount,2);assert.equal(a.portraitReady,false);a.referenceFiles[1]={name:'jersey.png'};assert.equal(a.portraitReady,true);assert.match(a.portraitPrompt(),/Image 2 is CLOTHING ONLY/);
const draft=a.portraitDraft();a.portraitModeChanged('career');a.restorePortraitDraft(draft);assert.equal(a.portraitThemeId,'basketball');assert.equal(a.portraitThemeSceneText,'A rooftop court');assert.equal(a.portraitClothing,'custom');
a.portraitModeChanged('festival');a.portraitGreeting='生日快乐';assert.ok(a.portraitPrompt().includes('生日快乐'));a.portraitModeChanged('cinema');assert.ok(!a.portraitPrompt().includes('生日快乐'));
console.log('Portrait themes: all presets, bilingual options, linked resets, custom references, draft and prompt invalidation passed');
