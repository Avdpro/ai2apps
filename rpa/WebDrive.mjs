import WebSocket from 'ws';
import { EventEmitter } from 'events';
import { spawn,execFile } from "child_process";
import {AaWebDriveContext} from "./WebDriveContext.mjs";
import { URL } from 'url'
import pathLib from 'path'

const codeURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const codeDirURL=pathLib.dirname(codeURL);
const codeDirPath=codeDirURL.startsWith("file://")?pathLib.fileURLToPath(codeDirURL):codeDirURL;

let AaWebDrive,aaWebDrive;
//-----------------------------------------------------------------------
AaWebDrive=function(){
	this.sysId=null;
	
	this.options={
		timeout:30000
	};
	
	this.messageId = 0;
	this.pendingCommands = new Map();
	
	this.sessionId = null;
	this.connected = false;
	
	this.subscribedEvents = new Set();
	
	this.agentNode=null;
	
	this.actionPms=null;
	this.curAction=null;
	
	this.pageMap=new Map();//ContextId/PageId=>Page
};
aaWebDrive=AaWebDrive.prototype=Object.create(EventEmitter.prototype);
aaWebDrive.constructor = AaWebDrive;

//***************************************************************************
// ===== 启动，消息处理 =====
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDrive.start = async function (sysId,alias,agentNode) {
		if (this.sysId) {
			return;
		}
		this.sysId=sysId;
		this.agentNode=agentNode;
		this.aaeeAlias=alias;
		this.alias=alias;
		this.connected=true;
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.close=async function(){
		return new Promise((resolve,reject)=>{
			//TODO: Call agentNode to close it.
		});
	};
	
	//---------------------------------------------------------------------------
	aaWebDrive.handleEvent = async function (message) {
		const { method, params } = message;
		console.log(`Got WebDriver event: `,message);
		// 发出具体的事件
		this.emit(method, params);
		// 发出通用事件
		this.emit('event', { method, params });
		// 根据事件类型进行分类处理
		const [category] = method.split('.');
		this.emit(`${category}.*`, { method, params });
	};

	//---------------------------------------------------------------------------
	aaWebDrive.sendCommand = async function (method, params = {},timeout=0) {
		if (!this.connected) {
			throw new Error('Not connected to System WebDriver BiDi');
		}
		return await this.agentNode.callHub("WebDriveCommand",{browser:this.sysId,method,params,timeout});
	};
}

//***************************************************************************
// ===== 会话状态 =====
//***************************************************************************
{
	//----------------------------------------------------------------------
	aaWebDrive.getStatus=async function(){
		return this.sendCommand('session.status');
	};
}

//***************************************************************************
// ===== 事件订阅管理 =====
//***************************************************************************
{
	
	//-----------------------------------------------------------------------
	aaWebDrive.subscribe=async function(events) {
		events.forEach(event => this.subscribedEvents.add(event));
		return this.sendCommand('session.subscribe', { events });
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.unsubscribe=async function(events) {
		events.forEach(event => this.subscribedEvents.delete(event));
		return this.sendCommand('session.unsubscribe', { events });
	};
}

//***************************************************************************
// ===== 浏览上下文（页面/iFrame）操作 =====
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDrive.createBrowsingContext= async function(type = 'tab', referenceContext = null) {
		const params = { type };
		if (referenceContext) {
			params.referenceContext = referenceContext;
		}
		return this.sendCommand('browsingContext.create', params);
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.newPage=async function(url){
		let result,page;
		result=await this.createBrowsingContext();
		page=new AaWebDriveContext(this,result.context);
		this.pageMap.set(result.context,page);
		if(url){
			await page.goto(url);
		}
		return page;
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.closeBrowsingContext=async function(context,opts) {
		let promptBeforeUnload = opts?.promptBeforeUnload || false;
		return this.sendCommand('browsingContext.close', { context ,promptBeforeUnload});
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.getBrowsingContextTree=async function(maxDepth = null, root = null) {
		const params = {};
		if (maxDepth !== null) params.maxDepth = maxDepth;
		if (root !== null) params.root = root;
		return this.sendCommand('browsingContext.getTree', params);
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.getPages=async function(){
		let result,contexts,pages,context,page;
		pages=[];
		result=await this.getBrowsingContextTree(1,null);
		contexts=result.contexts;
		for(context of contexts){
			context=context.context;
			page=this.pageMap.get(context);
			if(!page){
				page=new AaWebDriveContext(this,context);
				this.pageMap.set(context,page);
			}
			pages.push(page);
		}
		return pages;
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.navigate=aaWebDrive.goto=async function(context, url, wait = 'complete',timeout=0) {
		return this.sendCommand('browsingContext.navigate', { context, url, wait },timeout);
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.reload=async function(context, ignoreCache = false, wait = 'complete') {
		return this.sendCommand('browsingContext.reload', { context, wait });
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.goBack=async function(context, wait = 'complete') {
		return this.sendCommand('browsingContext.traverseHistory', { context, delta: -1, wait });
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.goForward=async function(context, wait = 'complete') {
		return this.sendCommand('browsingContext.traverseHistory', { context, delta: 1, wait });
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.captureScreenshot=async function(context, options = {}) {
		return this.sendCommand('browsingContext.captureScreenshot', { context, ...options });
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.print=async function(context, options = {}) {
		return this.sendCommand('browsingContext.print', { context, ...options });
	};
}


//***************************************************************************
// ===== 脚本执行 =====
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDrive.evaluateScript = async function (expression, target, opts=null) {
		return this.sendCommand('script.evaluate', {
			expression,
			target,
			...opts
		});
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.callFunction = async function (functionDeclaration, target, arguments_ = [], opts=null) {
		return this.sendCommand('script.callFunction', {
			functionDeclaration,
			target,
			arguments: arguments_,
			...opts
		});
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.disownScript = async function(handles) {
		return this.sendCommand('script.disown', { handles });
	};
}

//***************************************************************************
// ===== 网络操作 =====
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDrive.addIntercept=async function(phases, urlPatterns = []) {
		return this.sendCommand('network.addIntercept', { phases, urlPatterns });
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.removeIntercept=async function(intercept) {
		return this.sendCommand('network.removeIntercept', { intercept });
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.continueRequest=async function(request) {
		return this.sendCommand('network.continueRequest', { request });
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.continueResponse=async function(request) {
		return this.sendCommand('network.continueResponse', { request });
	};
}

//***************************************************************************
// ===== 输入操作 =====
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDrive.startUserAction=async function(context,timeout){
		let call,callback,callerror,timer,action;
		if(this.actionPms){
			await this.actionPms;
		}
		timeout=timeout||60000;
		await this.releaseActions(context);
		this.actionPms=new Promise((resolve, reject)=>{
			callback=resolve;
			callerror=reject;
		});
		setTimeout(()=>{
			call=callback;
			if(call){
				action.live=false;
				callback=null;
				callerror=null;
				this.curAction=null;
				call();
			}
		},timeout);
		action={
			context:context,
			live:true,
			end:()=>{
				call=callback;
				action.live=false;
				clearTimeout(timer);
				if(call){
					callback=null;
					callerror=null;
					this.curAction=null;
					call();
				}
			},
			reject:()=>{
				call=callback;
				clearTimeout(timer);
				action.live=false;
				if(call){
					callback=null;
					callerror=null;
					this.curAction=null;
					call();
				}
			}
		};
		this.curAction=action;
		return action;
	};
	
	
	//-----------------------------------------------------------------------
	aaWebDrive.performActions=async function(action, actions) {
		let context;
		if(action!==this.curAction){
			return;
		}
		return this.sendCommand('input.performActions', { context:action.context, actions });
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.releaseActions=async function(context) {
		return this.sendCommand('input.releaseActions', { context });
	};
}

//***************************************************************************
// ===== 存储操作 =====
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDrive.getCookies=async function(filter = {}) {
		return this.sendCommand('storage.getCookies', filter);
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.setCookie=async function(cookie, partition = {}) {
		return this.sendCommand('storage.setCookie', { cookie, partition });
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.deleteCookies=async function(filter = {}) {
		return this.sendCommand('storage.deleteCookies', filter);
	};
}

//***************************************************************************
// ===== 日志操作/权限操作 =====
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDrive.setLogLevel=async function(level) {
		return this.sendCommand('log.setLevel', { level });
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.setPermission=async function(descriptor, state, origin = null) {
		const params = { descriptor, state };
		if (origin) params.origin = origin;
		return this.sendCommand('permissions.setPermission', params);
	};
}

//***************************************************************************
// ===== 关闭连接/工具方法 =====
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDrive.close=async function() {
		if (this.sessionId) {
			try {
				await this.endSession();
			} catch (error) {
				console.error('Error ending session:', error);
			}
		}
		
		if (this.ws && this.connected) {
			this.ws.close();
		}
		
		this.connected = false;
		this.emit('closed');
	};

	//-----------------------------------------------------------------------
	aaWebDrive.isConnected=function() {
		return this.connected;
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.getSessionId=function() {
		return this.sessionId;
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.getSubscribedEvents=function() {
		return [...this.subscribedEvents];
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.activate=async function(){
		return await this.agentNode.callHub("WebDriveActiveBrowser",{browser:this.sysId});
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.backToApp=async function(){
		return await this.agentNode.callHub("WebDriveBackToApp",{browser:this.sysId});
	};
}

export default AaWebDrive;
export {AaWebDrive};