console.log("CokeCodes disk SW: Start!");

class Store {
	constructor(dbName = 'keyval-store', storeName = 'keyval') {
		this.storeName = storeName;
		this._dbp = new Promise((resolve, reject) => {
			const openreq = indexedDB.open(dbName, 1);
			openreq.onerror = () => reject(openreq.error);
			openreq.onsuccess = () => resolve(openreq.result);
			// First time setup: create an empty object store
			openreq.onupgradeneeded = () => {
				//openreq.result.createObjectStore(storeName);
			};
		});
	}
	_withIDBStore(type, callback) {
		return this._dbp.then(db => new Promise((resolve, reject) => {
			const transaction = db.transaction(this.storeName, type);
			transaction.oncomplete = () => resolve();
			transaction.onabort = transaction.onerror = () => reject(transaction.error);
			callback(transaction.objectStore(this.storeName));
		}));
	}
}
let store;
function getDefaultStore() {
	if (!store)
		store = new Store();
	return store;
}
function get(key, store = getDefaultStore()) {
	let req;
	return store._withIDBStore('readonly', store => {
		req = store.get(key);
	}).then(() => req.result);
}
function set(key, value, store = getDefaultStore()) {
	return store._withIDBStore('readwrite', store => {
		store.put(value, key);
	});
}
function del(key, store = getDefaultStore()) {
	return store._withIDBStore('readwrite', store => {
		store.delete(key);
	});
}
function clear(store = getDefaultStore()) {
	return store._withIDBStore('readwrite', store => {
		store.clear();
	});
}
function keys(store = getDefaultStore()) {
	const keys = [];
	return store._withIDBStore('readonly', store => {
		// This would be store.getAllKeys(), but it isn't supported by Edge or Safari.
		// And openKeyCursor isn't supported by Safari.
		(store.openKeyCursor || store.openCursor).call(store).onsuccess = function () {
			if (!this.result)
				return;
			keys.push(this.result.key);
			this.result.continue();
		};
	}).then(() => keys);
}

var sysStore=new Store('CokeCodes', "System");
var diskStores={};
//var scriptURL=new URL(self.serviceWorker.scriptURL);
var hostOrigin=self.origin;

//---------------------------------------------------------------------------
//Start SW
self.addEventListener('install',function(evt){
	console.log("Disk SW: Install!");
	evt.waitUntil(
		get("disks", sysStore).then(list=>{
			if (Array.isArray(list)) {
				console.log("Disk SW: Disk database ready!");
			} else {
				set("disks", [], JAXDisk.sysStore).then(() => {
					console.log("Disk SW: Disk database installed!");
				});
			}
		})
	);
});

let routes={
};
let routeCalls={};
let nextCallIdx=1;
let routeClientId=0;

let Clients=self.clients;
function checkZombieStub(stub,checkTime){
	return Clients.get(stub.client.id).then(c=>{
		if(!c){
			stub.deadOut=true;
		}else{
			stub.lastCheck=checkTime;
		}
	});
}

const checkZombieTime=60000;//We check client alive every 60 sec.

async function routeCall(evt){
	let url,pathName,request,pos,list,routeLead,routeObj;
	let callId=""+(nextCallIdx++);
	let reqData;
	let headers;
	let timeNow=Date.now();
	request=evt.request;
	url=new URL(request.url);
	pathName=url.pathname;
	pos=pathName.indexOf("/",2);//url should starts with: /+
	if(pos>0){
		routeLead=pathName.substring(0,pos);
	}else{
		routeLead=pathName;
	}
	list=routes[routeLead];
	if(list){
		let i,n,path,stub,len,maxLen=0,maxObj=null;
		n=list.length;
		for(i=0;i<n;i++){
			stub=list[i];
			if(stub.deadOut){
				list.splice(i,1);
				n--;i--;
			}else {
				path = stub.path;
				if (pathName.startsWith(path)) {
					len = path.length;
					if (len >= maxLen) {
						maxLen = len;
						maxObj = stub;
					}
				}
			}
		}
		routeObj=maxObj;
	}
	if(!routeObj){
		return new Response("Can not find route handler.", {
			status: 404,
			headers: { "content-type": "text/html" },
		});
	}
	headers={};
	let keys;
	keys=request.headers.keys();
	for(let key of keys){
		headers[key]=request.headers.get(key);
	}
	reqData=await request.arrayBuffer();
	if(routeObj.lastCheck-timeNow>checkZombieTime) {
		checkZombieStub(routeObj,timeNow);
	}
	//Check if route client still online:
	let client=await Clients.get(routeObj.client.id);
	if(!client){
		return new Response("Can not find route handler.", {
			status: 404,
			headers: { "content-type": "text/html" },
		});
	}
	return new Promise((resolve,reject)=>{
		//register callback stub:
		if(routeObj) {
			//Check if client alive:
			routeCalls[callId] = {
				callId: callId,
				resolve: function (vo) {
					let res;
					res = new Response(vo.body, {
						status: vo.code,
						headers: vo.headers,
					});
					resolve(res);
				}
			};
			//send the request to route client:
			client.postMessage({ msg: "RouteCall", path:routeObj.orgPath,callId:callId,
				request:{
					url:request.url,
					method:request.method,
					referrer:request.referrer,
					headers:headers,
					body:reqData
				}
			});
		}else{
			let res=new Response('Can not find route handler.', {
				status: 404,
				headers: { 'Content-Type': 'text/html' }
			});
			resolve(res);
		}
	});
}

//---------------------------------------------------------------------------
//Fetch event handler:
self.addEventListener('fetch', async (evt)=>{
	var req,pos,reqURLObj,refURLObj,fullPath,ext;
	
	//Return a local-disk-path file respond:
	async function respondLocal(disk,filePath){
		let diskStore;
		FindLocal:{
			diskStore = diskStores[disk];
			if (!diskStore) {
				let list=await get("disks",sysStore);
				if(list){
					if(list.indexOf(disk)<0){
						break FindLocal;
					}
				}
				diskStores[disk] = diskStore = new Store('Disk_' + disk, disk);
			}
			return get(filePath, diskStore).then(fileObj => {
				let contentType,cache;
				if (fileObj instanceof Uint8Array) {
					[contentType,cache]=getCntType(filePath);
					return new Response(fileObj, {
						status: 200,
						headers: {
							'Content-Type': contentType,
							'cache-control': cache
						}
					});
				} else {
					return new Response('<p>Can not find disk file!</p>', {
						status: 404,
						headers: { 'Content-Type': 'text/html' }
					});
				}
			});
		}
		//When reach here, no local file, 404:
		return new Response(`<p>Can not find disk file: /${disk}/${filePath}!</p>`, {
			status: 404,
			headers: { 'Content-Type': 'text/html' }
		});
	}
	
	//Parse tagName@pkgName or tag@pkgName/fileName to localDB-disk URL.
	async function loadSysPackage(pkgName,filePath,tagName,diskName,dbStore,dir){
		let fileObj,refOrg,jsonPath;
		refOrg=refURLObj.origin;
		//Try package-export location first:
		jsonPath=""+dir+"/"+pkgName+".json";
		fileObj=await get(jsonPath,dbStore);
		if(!fileObj){
			//Get installed package-info-file coke.json:
			jsonPath=""+dir+"/"+pkgName+"/coke.json";
			fileObj=await get(jsonPath,dbStore);
		}
		if(fileObj instanceof Uint8Array){
			//Parse coke.json
			let enc = new TextDecoder("utf-8");
			let cokeJSON=enc.decode(fileObj);
			try {
				cokeJSON = JSON.parse(cokeJSON);
			}catch(e){
				console.log("Parse json error: /"+diskName+"/"+jsonPath);
				cokeJSON={};
			}
			let tags=cokeJSON.tags;
			if(!tags){
				//This should be a pkg-link rather than a installed package:
				let mainPath,rootPath,exports;
				mainPath=cokeJSON.main;
				rootPath=cokeJSON.path;
				if(filePath) {
					if (!rootPath) {
						let pos=mainPath.lastIndexOf("/");
						rootPath=mainPath.substring(pos);
					}
					//Use pkg-related path:
					exports=cokeJSON.exports;
					if(exports){
						let exportPath=exports[filePath];
						if(exportPath){
							if(rootPath.startsWith("/")){
								//Use absolute path:
								return `${refOrg}/${rootPath}/${exportPath}`;
							}
							return `${refOrg}//${diskName}/${dir}/${pkgName}/${rootPath}/${exportPath}`;
						}
					}
					if(rootPath.startsWith("/")){
						//Use absolute path:
						return `${refOrg}/${rootPath}/${filePath}`;
					}
					//Use pkg-related path:
					return `${refOrg}//${diskName}/${dir}/${pkgName}/${rootPath}/${filePath}`;
				}else{
					if(mainPath.startsWith("/")){
						//Use absolute path:
						return `${refOrg}/${mainPath}`;
					}
					//Use pkg-related path:
					return `${refOrg}//${diskName}/${dir}/${pkgName}/${cokeJSON.main}`;
				}
			}else if(!tagName){
				//Installed package, tagName is not provided, use default tag:
				if(filePath){
					let exports;
					tagName=cokeJSON.tag;
					let tagObj=tags[tagName];
					exports=tagObj.exports;
					if(exports){
						let exportPath=exports[filePath];
						if(exportPath){
							return `${refOrg}//${diskName}/${dir}/${pkgName}/${tagName}/${exportPath}`;
						}
					}
					return `${refOrg}//${diskName}/${dir}/${pkgName}/${cokeJSON.tag}/${filePath}`;
				}else {
					let mainPath;
					mainPath=cokeJSON.main;
					if(mainPath.startsWith("/")){
						//Use absolute path:
						return `${refOrg}/${mainPath}`;
					}
					//Use pkg-related path:
					return `${refOrg}//${diskName}/${dir}/${pkgName}/${cokeJSON.main}`;
				}
			}else{
				let tagObj=tags[tagName];
				if(tagObj){
					let rdt=tagObj.redirect;
					//The target tag is installed on disk, use it:
					if(rdt){
						return loadSysPackage(pkgName,filePath,rdt,diskName,dbStore,dir);
					}else {
						if (filePath) {
							let exports;
							exports=tagObj.exports;
							if(exports){
								let exportPath=exports[filePath];
								if(exportPath){
									return `${refOrg}//${diskName}/${dir}/${pkgName}/${tagName}/${exportPath}`;
								}
							}
							return `${refOrg}//${diskName}/${dir}/${pkgName}/${tagName}/${filePath}`;
						} else {
							let mainPath;
							mainPath = tagObj.main;
							if (mainPath.startsWith("/")) {
								//Use absolute path:
								return `${refOrg}/${mainPath}`;
							}
							//Use pkg-related path:
							return `${refOrg}//${diskName}/${dir}/${pkgName}/${tagName}/${tagObj.main}`;
						}
					}
				}else{
					//The target tag is not installed on disk, try find a compatible tag:
					let tagName,name,maxName,maxIdx,maxVO;
					maxIdx=-1;
					maxVO=null;
					for(tagName in tags){
						name=tagName;
						tagObj=tags[name];
						if(tagObj.cmpTags && tagObj.cmpTags.indexOf(name)>=0 && !tagObj.redirect){
							//Find the max versionIdx, or maybe we just break and use the first compatible one we meet:
							if(tagObj.versionIdx>maxIdx){
								maxIdx=tagObj.versionIdx;
								maxName=name;
								maxVO=tagObj;
							}
						}
					}
					if(maxVO){
						if(filePath) {
							let exports;
							exports=maxVO.exports;
							if(exports){
								let exportPath=exports[filePath];
								if(exportPath){
									return `${refOrg}//${diskName}/${dir}/${pkgName}/${maxName}/${exportPath}`;
								}
							}
							return `${refOrg}//${diskName}/${dir}/${pkgName}/${maxName}/${filePath}`;
						}else {
							return `${refOrg}//${diskName}/${dir}/${pkgName}/${maxName}/${maxVO.main}`;
						}
					}
				}
			}
		}
		return null;
	}
	
	//Genderate a 302 redirect response:
	function makeRedirect(path){
		return new Response("",{
			status:302,
			headers: {
				'Location':path
			}
		});
	}
	
	//Find a coke-package:
	async function findPackage(pkgPath,tagName="",diskName,dbStore,refPath,tgtDir="lib",urlObj){
		let pkgName,pkgFilePath;
		let fileObj,filePath,disk,diskStore;
		let ref,pts,refPkgName,refPkgTag,jsonPath;
		let diskJSON;
		let refOrg=refURLObj.origin;
		if(tgtDir!=="bin"){
			tgtDir="lib";
		}
		pos=pkgPath.indexOf("/");
		if(pos>0){//Has file pathname in path
			pkgFilePath=pkgPath.substring(pos+1);
			pkgName=pkgPath.substring(0,pos);
		}else{//Load default main-entry-file:
			pkgName=pkgPath;
		}
		//If we load package from user-disk, read disk.json, see if there is a tag require:
		if(diskName!=="coke"){
			fileObj = await get("disk.json", dbStore);
			if (fileObj instanceof Uint8Array) {
				//Parse coke.json
				let enc = new TextDecoder("utf-8");
				diskJSON = enc.decode(fileObj);
				try {
					diskJSON = JSON.parse(diskJSON);
				}catch(err){
					diskJSON=null;
				}
				//If tagName is not included in pkgPath, check if local disk has the package's link:
				if(diskJSON && !tagName){
					let pkgLnks=diskJSON.pkg;
					if(pkgLnks){
						let jumpPath;
						let pkgVO=pkgLnks[pkgName];
						if(pkgVO){
							let pkgRoot,pkgMain;
							//Generate jump path:
							pkgMain=pkgVO.main;
							if(pkgVO.path){
								pkgRoot=pkgVO.path;
							}else{
								let pos=pkgMain.lastIndexOf("/");
								if(pos>=0){
									pkgRoot=pkgMain.substring(pos);
								}else{
									pkgRoot="";
								}
							}
							if(!pkgRoot.startsWith("/")) {
								pkgRoot = `/${diskName}/${pkgRoot}`;
							}
							if(pkgFilePath){
								jumpPath=`${refOrg}/${pkgRoot}/${pkgFilePath}`;
							}else{
								if(pkgMain.startsWith("/")){
									jumpPath=`${refOrg}/${pkgMain}`;
								}else{
									jumpPath=`${refOrg}//${diskName}/${pkgMain}`;
								}
							}
							return makeRedirect(jumpPath+urlObj.search+urlObj.hash);
						}
					}
				}
			}
		}
		findTag:{
			//If tag is missing, get tag from local disk.json
			if (!tagName) {
				if (diskName === "coke") {
					//From coke system disk, find package tag:
					ref = refPath;
					pts = ref.split("/");
					if (pts[0] === "lib" || pts[0] === "bin") {
						refPkgName = pts[1];
						refPkgTag = pts[2];
						//If the refer-file is in a package's tag dir-tree, read disk.json in that tag folder
						if (refPkgName && refPkgTag) {
							jsonPath = pts[0] + "/" + refPkgName + "/" + refPkgTag + "/disk.json";
							fileObj = await get(jsonPath, dbStore);
							if (fileObj instanceof Uint8Array) {
								//Parse disk.json
								let enc = new TextDecoder("utf-8");
								let pkgJSON = enc.decode(fileObj);
								try {
									pkgJSON = JSON.parse(pkgJSON);
									let imports = pkgJSON.imports;
									if (imports) {
										tagName = imports[pkgName] || "";
										break findTag;
									}
								}catch(err){
									tagName = "";
									break findTag;
								}
							}
						}
					}
				} else {
					//From local none-coke disk, tag is in disk.json
					if(diskJSON) {
						let imports = diskJSON.imports;
						if (imports) {
							tagName = imports[pkgName] || "";
							break findTag;
						}
					}
				}
			}
			//When got here, set tagName to "", so use the default tag in package:
			if(!tagName) {
				tagName = "";
			}
		}//findTag
		
		//Check system lib disk has tagName@pkgName:
		disk="coke";
		diskStore = diskStores[disk];
		if(!diskStore){
			diskStores[disk]=diskStore=new Store('Disk_'+disk, disk);
		}
		filePath=await loadSysPackage(pkgName,pkgFilePath,tagName,disk,diskStore,tgtDir);
		if(filePath){
			//make 302 res:
			return makeRedirect(filePath+urlObj.search+urlObj.hash);
		}
		
		//Can't locate file:
		return new Response('<p>Can not find package file!</p>',{
			status:404,
			headers: {'Content-Type': 'text/html'}
		});
	}
	
	//Check if the URL is a disk path:
	function checkLeadDiskPath(urlObj,lead,disk,prefix=""){
		let refFile,pos;
		let pathname;
		pathname=decodeURI(urlObj.pathname);
		if(!pathname.startsWith(lead)){
			return false;
		}
		pathname = pathname.substring(lead.length);
		refFile=null;
		if(!disk) {
			pos = pathname.indexOf('/');
			if (pos > 0) {
				disk = pathname.substring(0, pos);
				pathname = pathname.substring(pos + 1);
			} else {
				return false;
			}
		}else{
			pathname=prefix+pathname;
		}
		//Trim URL:
		pos=pathname.indexOf("?");
		if(pos>0){
			pathname=pathname.substring(0,pos);
		}
		pos=pathname.indexOf("#");
		if(pos>0){
			pathname=pathname.substring(0,pos);
		}
		//respondWith diskStore file:
		evt.respondWith(respondLocal(disk,pathname));
		return true;
	}
	
	//Check if the URL is a package-path:
	function checkLeadPath(urlObj,lead) {
		let ref, pkgText, refFile, dir, pos;
		let pathname, disk, diskStore,refPathName;
		//pathname = urlObj.pathname;
		pathname=decodeURI(urlObj.pathname);
		if (!pathname.startsWith(lead)) {
			return false;
		}
		pkgText = pathname.substring(lead.length);
		dir = "lib";
		
		//Parse ref disk from req.referrer:
		refPathName=refURLObj.pathname
		ref = refPathName;
		disk = null;
		refFile = null;
		if (ref.startsWith('/jaxweb/disks/')) {
			ref = ref.substring('/jaxweb/disks/'.length);
			pos = ref.indexOf("?");
			if (pos >= 0) {
				ref = ref.substring(0, pos);
			}
			pos = ref.indexOf('/');
			if (pos > 0) {
				disk = ref.substring(0, pos);
				refFile = ref.substring(pos + 1);
			}
		} else if(ref.startsWith('//')){
			ref=ref.substring('//'.length);
			pos=ref.indexOf("?");
			if(pos>=0){
				ref=ref.substring(0,pos);
			}
			pos=ref.indexOf('/');
			if(pos>0) {
				disk=ref.substring(0,pos);
				refFile=ref.substring(pos+1);
			}
		}
		
		if(!disk){
			disk="coke";
			refFile="";
		}
		diskStore = diskStores[disk];
		if(!diskStore){//Disk should be ready when got here:
			diskStores[disk]=diskStore=new Store('Disk_'+disk, disk);
		}
		let pts,tagName,pkgName;
		//Get tag from URL
		pts=pkgText.split("@");
		if(pts[1]){
			tagName=pts[0];
			pkgName=pts[1];
		}else{
			tagName="";
			pkgName=pts[0];
		}
		//Trim URL:
		pos=pkgName.indexOf("?");
		if(pos>0){
			pkgName=pkgName.substring(0,pos);
		}
		pos=pkgName.indexOf("#");
		if(pos>0){
			pkgName=pkgName.substring(0,pos);
		}
		evt.respondWith(findPackage(pkgName,tagName,disk,diskStore,refFile,dir,urlObj));
		return true;
	}
	
	//get content-type by path's extname:
	function getCntType(path){
		let pos,ext,contentType,cache;
		pos = path.lastIndexOf('.');
		if (pos >= 0) {
			ext = path.substring(pos + 1).toLowerCase();
			switch (ext) {
				default:
					contentType = 'application/octet-stream';
					cache="no-store";
					break;
				case 'txt':
				case 'text':
					contentType = "text/plain";
					cache="no-store";
					break;
				case 'css':
					contentType = "text/css";
					cache="no-store";
					break;
				case 'json':
					contentType = "application/json";
					cache="no-store";
					break;
				case 'js':
				case 'mjs':
					contentType = "text/javascript";
					cache="no-store";
					break;
				case 'png':
					contentType = 'image/png';
					cache="max-age=90, public"
					break;
				case 'jpg':
					contentType = 'image/jpeg';
					cache="max-age=90, public"
					break;
				case 'jpeg':
					contentType = 'image/jpeg';
					cache="max-age=90, public"
					break;
				case 'svg':
					contentType = 'image/svg+xml';
					cache="max-age=90, public"
					break;
				case 'html':
				case 'htm':
					contentType = 'text/html';
					cache="no-store";
					break;
				case 'wasm':
					contentType='application/wasm';
					cache="no-store";
					break;
			}
		}
		return [contentType,cache];
	}
	
	function heartBeat(){
		return new Promise((resolve,reject)=>{
			resolve(new Response("",{
				status:200,	headers: {}
			}));
		});
	}
	
	req=evt.request;
	//console.log("Service worker on fetch: "+req.url);
	fullPath=req.url;
	reqURLObj=new URL(fullPath);
	if(reqURLObj.origin!==hostOrigin){
		evt.respondWith(fetch(evt.request));
		return;
	}
	if(req.referrer) {
		refURLObj = new URL(req.referrer);
	}else{
		refURLObj = reqURLObj;
	}
	fullPath=reqURLObj.pathname;
	
	//Get ext-name:
	pos=fullPath.lastIndexOf('.');
	if(pos>=0) {
		ext = fullPath.substring(pos + 1).toLowerCase();
	}else{
		ext="";
	}
	if(fullPath==="/heart-beat"){
		evt.respondWith(heartBeat());
		return;
	}
	
	if(fullPath.startsWith("/+")){
		evt.respondWith(routeCall(evt));
		return;
	}
	
	if(checkLeadPath(reqURLObj,"/@")){
		return;
	}
	
	//No a package-file, local-disk-file or fetch online:
	if(checkLeadDiskPath(reqURLObj,'/~/')){
		return;
	}

	if(checkLeadDiskPath(reqURLObj,'//')){
		return;
	}
	if(reqURLObj.origin.startsWith("http://localhost")){
		//Develop-Env:
	}else{
		//Cloud-Env:
		if(checkLeadDiskPath(reqURLObj,'/jaxweb/cody/',"-cody","")){
			return;
		}
		if(checkLeadDiskPath(reqURLObj,'/jaxweb/',"-jaxweb","")){
			return;
		}
	}
	
	evt.respondWith(fetch(evt.request));
});

let watchClients=[];
let watchIdName=0;

let taskHash={
};
let taskSet=new Set();

async function getTasks(){
	let clients,clientId,client,list,stub;
	
	//First, check closed clients:
	list=[];
	clients=taskSet.values();
	for(clientId of clients){
		client=await Clients.get(clientId);
		if(client){
			stub=taskHash[clientId];
			if(stub) {
				list.push(stub);
			}
		}else{
			taskSet.delete(clientId);
			delete taskHash[clientId];
		}
	}
	return list;
}

//---------------------------------------------------------------------------
//Handle client messages:
self.addEventListener('message', function(event) {
	let data=event.data;
	let msg=data.msg;
	let path;
	let timeNow=Date.now();

	//TODO: Remove zombie clients:
	switch(msg){
		case "Watch":
			event.source.postMessage({msg:"WatchOK",watchId:(++watchIdName)});
			watchClients.push({client:event.source,id:watchIdName,lastCheck:timeNow});
			break;
		case "Unwatch":{
			let clientId,stub;
			clientId=data.watchId;
			for(let i=0,n=watchClients.length;i<n;i++){
				stub=watchClients[i];
				if(stub.id===clientId){
					watchClients.splice(i,1);
					//console.log("Found unwatch client, watched.");
					stub.client.postMessage({msg:"UnwatchOK"});
					return;
				}
			}
			break;
		}
		case "RouteOn": {
			let orgPath,path,stub,pos,lead,list;
			orgPath=path=data.path;
			if(path[0]!=="/"){
				path="/"+path;
			}
			pos=path.indexOf("/",1);
			if(pos>0){
				lead=path.substring(0,pos);
			}else{
				lead=path;
			}
			stub={
				path:path,
				orgPath:orgPath,
				client:event.source,
				routeId:(++routeClientId),
				lastCheck:timeNow
			};
			list=routes[lead];
			if(!list) {
				routes[lead] = [stub];
			}else {
				ReplaceRoute:{
					for (let i = 0, n = list.length; i < n; i++) {
						if (stub.path === list[i].path) {
							list[i] = stub;
							break ReplaceRoute;
						}
					}
					list.push(stub);
				}
			}
			stub.client.postMessage({msg:"RouteStart",path:orgPath,routeId:stub.routeId});
			break;
		}
		case "RouteOff":
			let orgPath,path,pos,lead,list;
			orgPath=path=data.path;
			if(path[0]!=="/"){
				path="/"+path;
			}
			pos=path.indexOf("/",1);
			if(pos>0){
				lead=path.substring(0,pos);
			}else{
				lead=path;
			}
			list=routes[lead];
			if(list) {
				let clientId=event.source.id;
				RemoveRoute:{
					for (let i = 0, n = list.length; i < n; i++) {
						if (clientId === list[i].client.id) {
							list.splice(i,1);
							if(!list.length){
								routes[lead]=null;
							}
							break RemoveRoute;
						}
					}
				}
			}
			break;
		case "RouteRes": {
			let callId,callStub;
			callId=data.callId;
			callStub=routeCalls[callId];
			if(callStub){
				callStub.resolve(data.res);//data.res:{code:200,contentType:"text/plain",content:"Hello world",headers:{}}
				delete routeCalls[callId];
			}
			break;
		}
		case "WatchAct": {
			let path,stub;
			path=data.path;
			for (let i = 0, n = watchClients.length; i < n; i++) {
				stub = watchClients[i];
				if(stub.deadOut){
					watchClients.splice(i,1);
					n--;i--;
				}else {
					stub.client.postMessage({ msg: "WatchAct", act: data.act, path: path, actor: data.actor });
					if(timeNow-stub.lastCheck>checkZombieTime){
						checkZombieStub(stub,timeNow);
					}
				}
			}
			break;
		}
		case "TaskActive":{
			let client,clientId,stub;
			client=event.source;
			clientId=event.source.id;
			
			stub=taskHash[clientId];
			if(stub){
				Object.assign(stub,data.stub);
			}else{
				taskHash[clientId]=data.stub;
			}
			//Make sure order:
			taskSet.delete(clientId);
			taskSet.add(clientId);
			break;
		}
		case "GetTasks": {
			let client=event.source;
			let reqId=data.reqId;
			console.log("Get tasks: ");
			getTasks().then((tasks)=>{
				tasks.reverse();
				client.postMessage({msg:"Tasks",tasks:tasks,reqId:reqId});
			});
		}
	}
});