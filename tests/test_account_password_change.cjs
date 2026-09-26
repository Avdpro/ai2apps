const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const source = fs.readFileSync(require('path').join(__dirname, '../ai2apps/web/static/js/account.js'), 'utf8');
async function scenario({confirm='new-password', current='old-password', password='new-password', status=200, code='', busy=false}={}) {
    const calls=[];
    const context={document:{documentElement:{lang:'en'}},window:{t:key=>key}, TextEncoder, fetch:async(url, opts)=>{
        calls.push({url, body:JSON.parse(opts.body)});
        return {ok:status<400,status,headers:{get:()=>null},json:async()=>status<400?{changed:true}:{error:{code}}};
    }};
    vm.runInNewContext(source,context);
    const app=context.window.accountApp();
    app.signedIn=true;app.user={id:'user'};
    app.clearCurrency=()=>{};app.clearInstallationAccess=()=>{};app.clearPromotionState=()=>{};app.applyProfile=()=>{};
    Object.assign(app,{currentPassword:current,changeNewPassword:password,confirmNewPassword:confirm,busy});
    await app.changePassword();
    return {app,calls};
}
(async()=>{
    let r=await scenario({confirm:'different'});
    assert.equal(r.calls.length,0);assert.equal(r.app.message,'account.password_change.mismatch');
    r=await scenario({current:'short'});assert.equal(r.calls.length,0);
    r=await scenario({current:'new-password'});assert.equal(r.calls.length,0);
    r=await scenario({busy:true});assert.equal(r.calls.length,0);
    r=await scenario();assert.equal(r.calls.length,1);assert.equal(r.app.signedIn,false);
    assert.deepEqual(r.calls[0].body,{currentPassword:'old-password',newPassword:'new-password'});
    assert.equal(r.app.currentPassword,'');assert.equal(r.app.confirmNewPassword,'');assert.equal(r.app.changeNewPassword,'');
    r=await scenario({status:400,code:'CURRENT_PASSWORD_INVALID'});
    assert.equal(r.app.signedIn,true);assert.equal(r.app.message,'account.password_change.wrong_current');assert.equal(r.app.currentPassword,'');
    r=await scenario({status:503,code:'PASSWORD_CHANGE_UNAVAILABLE'});
    assert.equal(r.app.signedIn,true);assert.equal(r.app.message,'account.password_change.unavailable');
    r.app.currentPassword='temporary';r.app.setSection('overview');assert.equal(r.app.currentPassword,'');
    console.log('Account password change: 8 behavior scenarios passed');
})().catch(error=>{console.error(error);process.exit(1)});
