const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
function extract(file, start, end) {
 const s=fs.readFileSync(file,'utf8'), a=s.indexOf(start), b=s.indexOf(end,a);
 assert(a>=0 && b>a);
 return s.slice(a,b).trim().replace(/,$/,'').replace(/^async (?!function)/,'async function ');
}
const sources=[extract('ai2apps/web/static/js/capability_provisioning.js','async function confirmLicenseChallenges(','    const stepPhaseOrder'),
 extract('ai2apps/web/static/js/dashboard.js','async confirmCheckpointLicenses(','            async startDynaInstall(')];
async function scenario(source,index,decision) {
 const nodes=new Map(),radios=[];let overlay;
 const node=()=>({style:{},checked:false,listeners:{},append(){},remove(){this.removed=true;},
  addEventListener(t,f){this.listeners[t]=f;},querySelector(){return radios.find(r=>r.checked);}});
 const document={body:{appendChild(v){overlay=v;}},querySelector(){return null;},createElement(tag){
  const n=node();if(tag==='input')radios.push(n);
  if(tag==='div')n.querySelector=s=>{if(s.includes('radio'))return radios.find(r=>r.checked);
   if(!nodes.has(s)){const c=node();if(s.includes('action="accept"'))c.disabled=true;nodes.set(s,c);}return nodes.get(s);};return n;}};
 const fn=vm.runInNewContext('('+source+')',{document,tr:s=>s});
 const c={distributionId:'exact-distribution',manifestDigest:'sha256:manifest',license:{termsHash:'sha256:terms'},
  acceptanceOptions:['accepted_license_terms','obtained_separate_license']};
 let resolved=false;const promise=fn([c]).then(r=>{resolved=true;return r;});
 const checkbox=nodes.get(index===0?'.acpf-license-confirm input':'[data-license-confirm]');
 const options=nodes.get(index===0?'.acpf-license-options':'[data-license-options]');
 const accept=nodes.get('[data-license-action="accept"]');
 assert(radios.every(r=>!r.checked),'no preselected legal declaration');assert(accept.disabled);
 checkbox.checked=true;checkbox.listeners.change();assert(accept.disabled,'checkbox alone insufficient');
 checkbox.checked=false;checkbox.listeners.change();radios[decision].checked=true;options.listeners.change();assert(accept.disabled,'decision alone insufficient');
 checkbox.checked=true;checkbox.listeners.change();assert.equal(accept.disabled,false);
 await Promise.resolve();assert.equal(resolved,false,'no automatic acceptance');
 overlay.listeners.click({target:{closest:()=>({dataset:{licenseAction:'accept'}})}});
 assert.deepEqual(JSON.parse(JSON.stringify(await promise)),[{distributionId:c.distributionId,manifestDigest:c.manifestDigest,
  termsHash:c.license.termsHash,decision:c.acceptanceOptions[decision],confirmed:true}]);assert(overlay.removed);
}
(async()=>{for(const [i,s] of sources.entries()){await scenario(s,i,0);await scenario(s,i,1);}
 console.log('Four cases passed: explicit decision + confirmation, no preselection, exact consent binding.');})()
 .catch(e=>{console.error(e);process.exitCode=1;});
