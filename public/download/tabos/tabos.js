import {tabNT,webFetch} from "./tabos_nt.js";
import {makeObjEventEmitter,makeNotify} from "./utils/events.js";
let JAXDisk=null;
let tabFS,tabTask,theSW,swControler;
let tabOS={
	shareFS:true,//If used shared FS by parent
	rootOS:null,//Root page's tabOS
	homePath:"/",
	fs:null,
	sw:null,
	swClient:null,
	task:null,
	heartBeat:true,
	allowRoot:false
};

async function createFS(){
	return (await import("./tabos_fs.js")).default;
};

//****************************************************************************
//Service worker client:
//****************************************************************************
let setupSWClient;
let swClient={
	uuid:crypto.randomUUID?crypto.randomUUID():(""+Date.now()+Math.floor(Math.random()*1000))
};
{
	let heartBeating=false;
	let heartTimer=null;
	let listenCnt=0;
	let handleMessage;
	//------------------------------------------------------------------------
	function _heartBeat(){
		if(!heartBeating){
			clearInterval(heartTimer);
			return;
		}
		fetch("/heart-beat").then(res=>{
			if(!res.ok){
				console.log("SW-heat-beat failed");
			}
		});
	}
	
	//------------------------------------------------------------------------
	swClient.startHeartBeat=function(){
		if(heartBeating)
			return;
		heartBeating=1;
		heartTimer=setInterval(_heartBeat,5000);
	};

	//------------------------------------------------------------------------
	swClient.stopHeartBeat=function(){
		heartBeating=0;
	};
	
	//------------------------------------------------------------------------
	swClient.startListen=function(heartBeat){
		if(!theSW){
			return;
		}
		if(!listenCnt){
			listenCnt=1;
			theSW.addEventListener("message",handleMessage);
			if(heartBeat && swControler){//Only root/page tabos need heart-beat
				this.startHeartBeat();
			}
		}else {
			listenCnt++;
		}
	};

	//------------------------------------------------------------------------
	swClient.stopListenSW=function(){
		if(!theSW){
			return;
		}
		if(listenCnt>0) {
			listenCnt--;
			if(!listenCnt){
				theSW.removeEventListener("message",handleMessage);
			}
		}
	};
	
	//------------------------------------------------------------------------
	swClient.postMessage=function(msg,vo){
		swControler && swControler.postMessage({...vo,msg:msg});
	};
	
	//------------------------------------------------------------------------
	handleMessage=function(event){
		let data=event.data;
		let msg=data.msg;
		swClient && swClient.emit(msg,data);
	};
	
	//------------------------------------------------------------------------
	setupSWClient=async function(heartBeat){
		if(!swClient)
			return;
		makeObjEventEmitter(swClient);
		tabOS.swClient=swClient;
		swClient && swClient.startListen(heartBeat);
	};
}

//****************************************************************************
//Route API:
//****************************************************************************
{
	let routeAPIReady=false;
	let routeRegs={};

	//------------------------------------------------------------------------
	function routeStart(data){
		let path=data.path;
		let stub=routeRegs[path];
		stub.routeId=data.routeId;
		if(stub && stub.resolveCallback){
			stub.resolveCallback(stub);
		}
	}
	//------------------------------------------------------------------------
	async function routeCall(data){
		let path=data.path;
		let stub=routeRegs[path];
		let callId=data.callId;
		if(!swControler)
			return;
		if(!stub){
			swControler.postMessage({msg:"RouteRes",callId:data.callId,res:{code:404,body:"Route not found."}});
		}else{
			let req,request,ret,method,initVO;
			req=data.request;
			method=req.method||"GET";
			initVO={
				method:method,
				referrer:req.referrer,
				headers:req.headers||{}
			};
			if(method==="POST"){
				initVO.body=req.body;
			}
			request=new Request(req.url,initVO);
			try {
				ret = stub.callback(request);
				if(ret instanceof Promise){
					ret.then(async res=>{
						if(res instanceof Response){
							let body;
							if(res.bodyUsed){
								body=await readStream(res.body);
							}else{
								body=null;
							}
							res={
								body:body,
								code:res.status,
								headers:Object.assign({},res.headers),
							}
							swControler.postMessage({ msg: "RouteRes", callId: data.callId, res: res });
						}else {
							swControler.postMessage({ msg: "RouteRes", callId: data.callId, res: res });
						}
					}).catch((err)=>{
						swControler.postMessage({ msg: "RouteRes", callId: data.callId, res: {code:500,body:""+err} });
					});
				}else{
					let res=ret;
					if(res instanceof Response){
						let body;
						if(res.bodyUsed){
							body=await readStream(res.body);
						}else{
							body=null;
						}
						res={
							body:body,
							code:res.status,
							headers:Object.assign({},res.headers),
						}
						swControler.postMessage({ msg: "RouteRes", callId: data.callId, res: res });
					}else {
						swControler.postMessage({ msg: "RouteRes", callId: data.callId, res: res });
					}
				}
			}catch(err){
				swControler.postMessage({ msg: "RouteRes", callId: data.callId, res: {code:500,body:""+err} });
			}
		}
	}

	//------------------------------------------------------------------------
	tabOS.regRoute=async function(path,callback){
		if(!swControler){
			return;
		}
		if(!tabOS.swClient){
			throw new Error("service worker client not ready: "+path);
		}
		if(!routeAPIReady){
			swClient.on("RouteStart",routeStart);
			swClient.on("RouteCall",routeCall);
		}
		return new Promise((resolve,reject)=>{
			if(routeRegs[path]){
				throw Error(`Route path ${path} already taken!`);
			}
			routeRegs[path]={
				path: path,
				callback: callback,
				resolveCallback: resolve,
				routeId: 0
			};
			swControler.postMessage({msg:"RouteOn",path:path});
		});
	};
		
	//-----------------------------------------------------------------------
	tabOS.stopRoute=function(path,callback){
		let stub;
		if(!swControler){
			return;
		}
		stub=routeRegs[path];
		if(stub){
			if(callback && callback!==stub.callback){
				return;
			}
			swControler.postMessage({msg:"RouteOff",path:path});
			delete stub[path];
		}
	};
}

//****************************************************************************
//Watch API:
//****************************************************************************
{
	let watching=false;
	let watchCallReady=false;
	let watchList=[];
	let watchClientId=null;
	let watchStubId=0;
	let watchResolveCallback=null;
	let watchResolveStubId=0;

	//-----------------------------------------------------------------------
	//Watch a path for changes:
	tabOS.watch=async function(path,callback){
		let stub;
		if(!swClient){
			throw new Error("Watch without swClient, path: "+path);
		}
		stub={
			path:path,
			callback:callback,
			id:(++watchStubId)
		};
		watchList.push(stub);
		return new Promise((resolve,reject)=>{
			if(!watching){
				watching=true;
				//Reigster watch handlers:
				if(!watchCallReady){
					watchCallReady=true;
					swClient.on("WatchOK",(data)=>{
						watchClientId=data.watchId;
						watchResolveCallback && watchResolveCallback(""+watchClientId+"-"+watchResolveStubId);
					});
					swClient.on("WatchAct",(data)=>{
						let act=data.act;
						let path=data.path;
						let actor=data.actor;
						let stub;
						for(let i=0,n=watchList.length;i<n;i++){
							stub=watchList[i];
							if(path.startsWith(stub.path)) {
								stub.callback(act, path, actor);
							}
						}
					});
				}
				//Send watch to Service-Worker
				watchResolveCallback=resolve;
				watchResolveStubId=stub.id;
				swControler.postMessage({msg:"Watch"});
			}else{
				resolve(""+watchClientId+"-"+stub.id);
			}
		});
	};
	
	//-----------------------------------------------------------------------
	//Unwatch:
	tabOS.unwatch=function(path,callback){
		let stub;
		for(let i=0,n=watchList.length;i<n;i++){
			stub=watchList[i];
			if(stub.path===path && stub.callback===callback){
				watchList.splice(i,1);
				i--;n--;
			}
		}
		if(!watchList.length){
			swControler.postMessage({msg:"Unwatch",watchId:watchClientId});
			watching=false;
		}
	};
}

//****************************************************************************
//OS features and API:
//****************************************************************************
{
	let setupPms=null,setupRootOS,setupFrameOS,setupPageOS;
	
	//------------------------------------------------------------------------
	setupRootOS=async function(){
		tabOS.rootOS=tabOS;//This is the root OS
		setupSWClient(tabOS.heartBeat);//Start SWClient with heart beat
		tabFS=await createFS();
		tabOS.fs=tabFS;
		await tabFS.init(swClient);
		
		tabOS.osTag=""+Date.now()+"-"+Math.trunc(Math.random()*1000);
		
		//init task:
		tabTask.initTask();
		tabOS.task=tabTask;

		//Fin:
		tabFS=tabOS.fs;
		tabFS.swClient=tabOS.swClient;
		tabFS.swControler=swControler;
		tabFS.regRoute=tabOS.regRoute;
		tabFS.stopRoute=tabOS.stopRoute;
		tabFS.watch=tabOS.watch.bind(tabOS);
		tabFS.unwatch=tabOS.unwatch.bind(tabOS);
		window.tabOS=tabOS;
	};
	
	//------------------------------------------------------------------------
	setupPageOS=async function(){
		let parentOS=window.parentTabOS;
		if(!parentOS){
			let rootWin;
			//wait parentTabOS;
			//alert("Refresh tabos app window or open tabos app manually will break the task management chain.");
			//rootWin=window.open("","TabOSHome");
			rootWin=window.opener;
			if(rootWin && rootWin.openTabOSAppPage){
				//Post a message to root win to open this app
				console.log("Will call root-win to open app");
				rootWin.openTabOSAppPage(document.location.href,window.name);
			}else{
				await setupRootOS();
				return;
			}
			window.close();
			throw "Wait home";
		}
		setupSWClient(true);//Start SWClient with heart beat
		tabOS.rootOS=parentOS.rootOS;
		tabOS.fs=await createFS();//Always create own FS
		tabOS.osTag=tabOS.rootOS.osTag;

		//init task:
		tabTask.initTask();
		tabOS.task=tabTask;

		//Fin:
		tabFS=tabOS.fs;
		tabFS.swClient=tabOS.swClient;
		tabFS.swControler=swControler;
		tabFS.regRoute=tabOS.regRoute;
		tabFS.stopRoute=tabOS.stopRoute;
		tabFS.watch=tabOS.watch.bind(tabOS);
		tabFS.unwatch=tabOS.unwatch.bind(tabOS);
		window.tabOS=tabOS;
	};
	
	//------------------------------------------------------------------------
	setupFrameOS=async function(){
		let win,parentOS;
		win=window;
		do{
			win=win.parent;
			parentOS=win.tabOS;
			if(win.parent===win){
				break;
			}
		}while(!parentOS && win);
		if(!parentOS){
			return await setupRootOS();
		}
		setupSWClient(false);//Start SWClient without heart beat
		tabOS.rootOS=parentOS.rootOS;
		tabOS.homePath=tabOS.rootOS.homePath||"/";
		tabOS.heartBeat=false;
		if(tabOS.shareFS){
			tabOS.fs=parentOS.fs;
		}else{
			tabOS.fs=await createFS();
		}
		tabOS.osTag=tabOS.rootOS.osTag;

		//init task:
		//tabTask.initTask();
		//tabOS.task=tabTask;
		tabOS.task=tabOS.rootOS.task;
		//Fin:
		tabFS=tabOS.fs;
		if(!tabOS.shareFS){
			tabFS.swClient=tabOS.swClient;
			tabFS.swControler=swControler;
			tabFS.regRoute=tabOS.regRoute;
			tabFS.stopRoute=tabOS.stopRoute;
			tabFS.watch=tabOS.watch.bind(tabOS);
			tabFS.unwatch=tabOS.unwatch.bind(tabOS);
		}
		window.tabOS=tabOS;
	};

	//------------------------------------------------------------------------
	tabOS.setup=async function(isRoot){
		if(setupPms){
			return setupPms;//Already
		}
		makeObjEventEmitter(tabOS);
		makeNotify(tabOS);
		//Check service worker:
		theSW=navigator.serviceWorker||null;
		if(theSW){
			swControler=theSW.controller;
		}else{
			if(!window.webkit){
				throw Error("Missing TabOS service worker.");
			}
		}
		if(window.parent===window) {
			//We are the root:
			setupPms=setupRootOS();
			await setupPms;
		}else{
			setupPms=setupFrameOS();
			await setupPms;
		}
		swClient.on("GlobalNotify",(msg)=>{
			tabOS.emitNotify(msg.message);
		});
	};
	
	//------------------------------------------------------------------------
	tabOS.emitGlobalNotify=async function(msg){
		let gMsg;
		if(swClient){
			gMsg={client:swClient.uuid,message:msg};
			swClient.postMessage("GlobalNotify",gMsg);
		}else{
			tabOS.emitNotify(msg);
		}
	};
}

//****************************************************************************
//Task register, active and query:
//****************************************************************************
{
	let localTaskStub;
	let taskActive,getTasks;
	let taskReqId=0;
	let taskReqs={};
	tabTask={};
	tabTask.initTask=function(){
		let winName,icon;
		winName = window.name;
		if(!swControler){
			return;
		}
		if (!winName) {
			let time, cnt;
			time = Date.now();
			winName = "TabOSWindow" + time + Math.trunc(1000 * Math.random());
			window.name = winName;
		}
		icon = document.head.querySelector("link[rel*='icon']");
		icon = icon ? icon.href : "";
		localTaskStub = {
			osTag:tabOS.osTag,
			windowName: winName,
			icon: icon,
			title: document.title,
		};
		taskActive();
		let el=document.getElementsByTagName("title")[0];
		if(el){
			let pl=el.parentElement;
			pl.addEventListener("DOMSubtreeModified",(evt)=>{
				let t = evt.target;
				if (t === el || (t.parentNode && t.parentNode === el)) {
					localTaskStub.title=document.title;
					taskActive();
				}
			});
		}

		//Send active message when page-window focused:
		window.addEventListener("focus", () => {
			localTaskStub.windowName=window.name;
			taskActive();
		});

		//Listen serviceWorkerClient's "Tasks" message:
		swClient.on("Tasks",(data)=>{
			let tasks=data.tasks;
			let req,reqId;
			reqId=data.reqId;
			req=taskReqs[reqId];
			if(req){
				req(tasks);
				delete taskReqs[reqId];
			}
		});
	};

	//------------------------------------------------------------------------
	tabTask.taskActive=taskActive=function(){
		swClient.postMessage("TaskActive",{msg:"TaskActive",stub:localTaskStub});
	};
	
	//-----------------------------------------------------------------------
	//Get all active tasks:
	tabTask.getTasks=getTasks=async function(){
		if(!swControler){
			return [];
		}
		return new Promise((resolve,reject)=>{
			let reqId=""+(taskReqId++);
			let timer=setTimeout(()=>{
				resolve(null);
				delete taskReqs[reqId];
			},500)
			taskReqs[reqId]=(tasks)=>{
				let osTag=tabOS.osTag;
				clearTimeout(timer)
				tasks=tasks.filter(task=>{return task.osTag===osTag});
				resolve(tasks);
			};
			swClient.postMessage("GetTasks",{msg:"GetTasks", reqId:reqId});
		});
	};
}
export {tabOS,tabFS,tabTask,tabNT,webFetch};