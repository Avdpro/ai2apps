// Build-time extraction only. Browser SDK remains the source of shared DOM helpers.
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'web/static/js/browser_bidi_client.js'),'utf8');
const methods=[...source.matchAll(/^        async (\w+)\(/gm)];
const helpers={};
for(let i=0;i<methods.length;i++){
 const method=methods[i][1], body=source.slice(methods[i].index,methods[i+1]?.index||source.length);
 let n=0;
 for(const match of body.matchAll(/(?:this\.)?callJSON\(\s*(`(?:\\[\s\S]|[^`])*`)/g)){
   const key=method+':'+n++;
   if(match[1].includes('${'))continue;
   helpers[key]=vm.runInNewContext(match[1],{}, {timeout:1000});
 }
}
const output=JSON.stringify(helpers,null,2)+'\n';
const dest=path.join(root,'browser/dom_helpers.json');
if(process.argv.includes('--check')){if(fs.readFileSync(dest,'utf8')!==output)throw Error('Run node scripts/extract_browser_dom_helpers.cjs to synchronize shared DOM helpers');}
else fs.writeFileSync(dest,output);
