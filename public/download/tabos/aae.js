//This file is helper API talk with AI2Apps Chrome extension:
let nextCallId=0;
let nextWatchId=0;
let callMap=new Map();
let watchMap=new Map();
const AAE={
	//------------------------------------------------------------------------
	getVersion:async function(){
		return await this.call("CONTENT","GetVersion");
	},
	
	//------------------------------------------------------------------------
	getTabId:async function(){
		return await this.call("CONTENT","GetTabId");
	},
	
	//------------------------------------------------------------------------
	connect:async function(){
		return await this.call("CONTENT","Connect");
	},

	//------------------------------------------------------------------------
	openClient:async function(url,scripts){
		return await this.call("CONENT","OpenClient",{href:url,scripts:scripts});
	},

	//------------------------------------------------------------------------
	waitPageLoad:async function(tabId,timeout=30){
		return await this.call("PORT","WaitPageLoad",{tabId:tabId,timeout:Math.floor(timeout*1000)});
	},
	
	//------------------------------------------------------------------------
	//Read client DOM-View:
	readPageView:async function(client){
		return await this.call("CLIENT","ReadPageView",{$client:client});
	},

	//------------------------------------------------------------------------
	//Query client DOM Nodes:
	quaeryNodes:async function(client,selector){
		return await this.call("CLIENT","QueryNodes",{$client:client,selector:selector});
	},
	
	//------------------------------------------------------------------------
	//Query client DOM Node:
	quaeryNodes:async function(client,selector){
		return await this.call("CLIENT","QueryNode",{$client:client,selector:selector});
	},

	//------------------------------------------------------------------------
	//Find a node that best match with condition
	matchNode:async function(client,condition){
		return await this.call("CLIENT","MatchNode",{$client:client,condition:condition});
	},
	
	//------------------------------------------------------------------------
	//Get node attribute:
	getNodeAttribute:async function(client,aaeNodeId,key){
		return await this.call("CLIENT","GetNodeAttribute",{$client:client,AAEId:aaeNodeId,key:key});
	},
	
	//------------------------------------------------------------------------
	//Set node attribute:
	setNodeAttribute:async function(client,aaeNodeId,key,value){
		return await this.call("CLIENT","SetNodeAttribute",{$client:client,AAEId:aaeNodeId,key:key,value:value});
	},
	
	//------------------------------------------------------------------------
	_addWatch:function(watchId,callback){
		watchMap.set(watchId,callback);
	},
	
	//------------------------------------------------------------------------
	cancelWatch:async function(client,watchId){
		await this.post("CLIENT","CancelWatch",{$client:client,$watchId:watchId});
		watchMap.delete(watchId);
	},
	
	//------------------------------------------------------------------------
	//Watch client DOM changes:
	watchNode:async function(client,aaeNodeId,callback,opts={}){
		let watchId=""+(nextWatchId++);
		this._addWatch(watchId,callback);
		await this.call("CLIENT","WatchNode",{$client:client,node:aaeNodeId,options:opts,$watchId:watchId});
		return watchId;
	},

	//------------------------------------------------------------------------
	//Watch client user actions:
	watchUserAction:async function(client,callback,opts={}){
		let watchId=""+(nextWatchId++);
		this._addWatch(watchId,callback);
		await this.call("CLIENT","WatchAction",{$client:client,options:opts,$watchId:watchId});
		return watchId;
	},

	//------------------------------------------------------------------------
	//Simulate an user action:
	runAction:async function(client,action){
		return await this.call("CLIENT","RunAction",{$client:client,action:action});
	},

	//------------------------------------------------------------------------
	//ClosePage
	closePage:async function(client){
		await this.post("CLIENT","Close",{$client:client});
	},

	//------------------------------------------------------------------------
	call:async function(target,msg,data){
		let type,pms,tabId;
		switch(target){
			case "CONTENT":
			default:
				type="PAGE_CONTENT";
				break;
			case "WORKER":
				type="PAGE_WORKER";
				break;
			case "PORT":
				type="HOST_PORT";
				break;
			case "CLIENT":
				type="HOST_CLIENT";
				tabId=target;
				break;
		}
		pms=new Promise((resolve,reject)=>{
			let callId=""+(nextCallId++);
			if(data){
				data = {AAEType:type, AAEMsg:msg, $callId:callId, ...data};
			}else{
				data = {AAEType:type, AAEMsg:msg, $callId:callId};
			}
			window.postMessage(data, "*");
			callMap.set(callId,{resolve:resolve,reject:reject});
		});
		return await pms;
	},
	
	//------------------------------------------------------------------------
	send:async function(target,msg,data){
		let type,pms,tabId;
		switch(target){
			case "CONTENT":
			default:
				type="PAGE_CONTENT";
				break;
			case "WORKER":
				type="PAGE_WORKER";
				break;
			case "PORT":
				type="HOST_PORT";
				break;
			case "CLIENT":
				type="HOST_CLIENT";
				tabId=target;
				break;
		}
		pms=new Promise((resolve,reject)=>{
			if(data){
				data = {AAEType:type, AAEMsg:msg, ...data};
			}else{
				data = {AAEType:type, AAEMsg:msg};
			}
			window.postMessage(data, "*");
		});
		return await pms;
	},
};
AAE.post=AAE.send;

window.addEventListener("message", function(event) {
	let data=event.data;
    // We only accept messages from extension to page:
	console.log("AAEHost got message:");
	console.log(data);
    if (data.AAEType && (data.AAEType.endsWith("_PAGE") || data.AAEType.endsWith("_HOST"))){
		switch(data.AAEMsg){
			case "$ReturnCall$":{
				let callId=data.$callId;
				let stub=callMap.get(callId);
				if(stub){
					stub.resolve(data.data);
					callMap.delete(callId);
				}
				return;
			}
			case "$RejectCall$":{
				let callId=data.$callId;
				let stub=callMap.get(callId);
				if(stub){
					stub.reject(data.data);
					callMap.delete(callId);
				}
				return;
			}
			case "$Action$":
			case "$Watch$":{
				let watchId=data.$watchId;
				let stub=watchMap.get(watchId);
				if(stub){
					stub(data.action);
				}
				return;
			}
			default:{
				//TODO: call handlers:
			}
		}
    }
});

export default AAE;
export {AAE}