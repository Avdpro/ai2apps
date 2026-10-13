/* Trusted host App requests stay inside the manifest's API scope and mount. */
(() => {
 'use strict';
 const config=JSON.parse(document.getElementById('mobile-app-gateway').textContent);
 const nativeFetch=window.fetch.bind(window);
 const encode=bytes=>{let s='';for(let i=0;i<bytes.length;i+=8192)s+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(s);};
 window.MobileAppResource=url=>{
  const u=new URL(url,location.origin);
  return u.origin===location.origin&&u.pathname.startsWith(config.apiPrefix+'/')?config.resourceBase+'api/'+u.pathname.slice(config.apiPrefix.length+1)+u.search:url;
 };
 window.fetch=async(input,options)=>{
  const request=new Request(input,options),url=new URL(request.url);
  if(url.origin!==location.origin||!(url.pathname===config.apiPrefix||url.pathname.startsWith(config.apiPrefix+'/')))return nativeFetch(request);
  const headers={};for(const name of ['content-type','x-intelligence-language','x-ai2apps-app-instance'])if(request.headers.has(name))headers[name]=request.headers.get(name);
  const response=await nativeFetch(config.bridge,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({method:'request',verb:request.method,path:url.pathname+url.search,headers,body:encode(new Uint8Array(await request.arrayBuffer()))})});
  if(!response.ok)return response;
  const result=await response.json(),bytes=Uint8Array.from(atob(result.body),c=>c.charCodeAt(0));
  return new Response(result.status===204?null:bytes,{status:result.status,headers:{'Content-Type':result.contentType}});
 };
})();
