import WebSocket from 'ws';
import { EventEmitter } from 'events';
import { spawn } from "child_process";
import {AaWebDriveContext} from "./WebDriveContext.mjs";

let AaWebDrive,aaWebDrive;
//-----------------------------------------------------------------------
AaWebDrive=function(){
	this.firefox=null;
	this.ws=null;
	this.url=null;
	this.port=9222;
	
	this.options={
		timeout:30000
	};
	
	this.waitStart=null;
	this.startCallback=null;
	this.startCallerror=null;
	
	this.messageId = 0;
	this.pendingCommands = new Map();
	
	this.sessionId = null;
	this.connected = false;
	this.reconnectAttempts = 0;
	this.subscribedEvents = new Set();
	
	// 绑定方法以保持this上下文
	this.handleMessage = this.handleMessage.bind(this);
	this.handleClose = this.handleClose.bind(this);
	this.handleError = this.handleError.bind(this);
	
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
	aaWebDrive.start = async function (pathToFireFox, pathToData, port = 9222,alias=null) {
		let firefox, pms, waitApp, args;
		if (this.waitStart) {
			return await this.waitStart;
		}
		if (!pathToFireFox) {
			pathToFireFox = process.env.WEBDRIVE_APP;
		}
		if (!pathToFireFox) {
			throw Error("Missing Firefox app path.");
		}
		this.port = port;
		pms = this.waitStart = new Promise((resolve, reject) => {
			this.startCallback = resolve;
			this.startCallerror = reject;
		});
		this.waitToStart = pms;
		
		waitApp = true;
		if (pathToData) {
			args = ['-no-remote', `--remote-debugging-port=${port}`, `--profile`, pathToData, `about:blank`];//TODO: Code this;
		} else {
			args = [`--remote-debugging-port=${port}`, `about:blank`];
		}
		
		//这里是在本地启动的，所以URL是在localhost里：
		this.url = `ws://localhost:${port}/session`;
		
		firefox = this.firefox = spawn(
			`${pathToFireFox}/Contents/MacOS/firefox`,
			args,
			{ stdio: ['ignore', 'pipe', 'pipe'] }
		);
		
		let buffer = '';
		
		firefox.stdout.on('data', data => {
			console.log('[firefox]', data.toString());
			if (!waitApp)
				return;
		});
		
		firefox.stderr.on('data', data => {
			console.error('[firefox:stderr]', data.toString());
			if (!waitApp) {
				return;
			}
			buffer += data.toString();
			// 检测启动成功标志
			if (buffer.includes('WebDriver BiDi listening on')) {
				console.log('✅ Firefox WebDriver BiDi 已启动');
				waitApp = false;
				// 调用连接 BiDi 的方法
				this.connect().then(() => {
					let callback;
					callback = this.startCallback;
					if (callback) {
						this.startCallback = null;
						this.startCallerror = null;
					}
					callback();
				}).catch((err) => {
					let callback;
					callback = this.startCallerror;
					if (callback) {
						this.startCallback = null;
						this.startCallerror = null;
					}
					callback(err);
				});
			}
		});
		
		firefox.on('exit', code => {
			console.log(`Firefox exited with code ${code}`);
			this.emit("browser.exit");
		});
		//Alias for AAEE-Driver
		this.aaeeAlias=alias;
		return await pms;
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.close=async function(){
		let timer;
		return new Promise((resolve,reject)=>{
			this.emit("browser.willExit");
			if(!this.firefox){
				reject(new Error("Browser is not alive."));
			}
			this.firefox.on('exit',()=>{
				this.firefox=null;
				if(timer){
					clearTimeout(timer);
				}
				resolve();
			});
			this.firefox.kill('SIGTERM');
			timer=setTimeout(()=>{
				if(this.firefox){
					this.firefox.kill('SIGKILL');
				}
			},5000);//Wait 5 sec. to force kill.
		});
	};
	
	//-----------------------------------------------------------------------
	aaWebDrive.connect = async function () {
		return new Promise(async (resolve, reject) => {
			try {
				this.ws = new WebSocket(this.url);
				
				this.ws.on('open', async () => {
					console.log('🔗 Connected to WebDriver BiDi');
					this.connected = true;
					this.reconnectAttempts = 0;
					await this.createSession();
					await this.subscribe([
						"browsingContext.navigationStarted",
						"browsingContext.domContentLoaded",
						"browsingContext.fragmentNavigated",
						"browsingContext.navigationCommitted",
						"browsingContext.historyUpdated",
						"browsingContext.load",
						"browsingContext.contextDestroyed",
						"browsingContext.userPromptOpened",
						//"browsingContext.downloadWillBegin",
						//"browsingContext.downloadEnd",
					]);
					this.on("browsingContext.contextDestroyed",(message)=>{
						const context=message.context;
						this.pageMap.delete(context);
					});
					this.emit('connected');
					resolve();
				});
				
				this.ws.on('message', this.handleMessage);
				this.ws.on('close', this.handleClose);
				this.ws.on('error', this.handleError);
				
				// 连接超时
				setTimeout(() => {
					if (!this.connected) {
						reject(new Error('Connection timeout'));
					}
				}, this.options.timeout);
				
			} catch (error) {
				reject(error);
			}
		});
	};

	//---------------------------------------------------------------------------
	aaWebDrive.handleMessage = async function (data) {
		try {
			const message = JSON.parse(data.toString());
			//console.log(`Got WebDriver message: `,message);
			
			if (message.type === 'success' || message.type === 'error'|| message.type === 'exception') {
				// 处理命令响应
				await this.handleCommandResponse(message);
			} else if (message.type === 'event') {
				// 处理事件通知
				await this.handleEvent(message);
			} else {
				console.warn('Unknown message type:', message);
			}
		} catch (error) {
			console.error('Error parsing message:', error);
		}
	};

	//---------------------------------------------------------------------------
	aaWebDrive.handleCommandResponse = async function (message) {
		const pending = this.pendingCommands.get(message.id);
		if (pending) {
			clearTimeout(pending.timeout);
			this.pendingCommands.delete(message.id);
			
			if (message.type === 'success') {
				pending.resolve(message.result);
			} else {
				const error = new Error(`${message.error}: ${message.message}`);
				error.code = message.error;
				error.stacktrace = message.stacktrace;
				pending.reject(error);
			}
		}
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
	aaWebDrive.handleClose = async function (code, reason) {
		console.log(`🔌 Connection closed: ${code} - ${reason}`);
		this.connected = false;
		this.emit('disconnected', { code, reason });
		
		// 清理待处理的命令
		this.pendingCommands.forEach(({ reject, timeout }) => {
			clearTimeout(timeout);
			reject(new Error('Connection closed'));
		});
		this.pendingCommands.clear();
		
		// 尝试重连
		if (this.reconnectAttempts < this.options.maxReconnectAttempts) {
			this.attemptReconnect().then(() => {});
		}
	};

	//---------------------------------------------------------------------------
	aaWebDrive.handleError = function (error) {
		console.error('❌ WebSocket error:', error);
		this.emit('error', error);
	};

	//---------------------------------------------------------------------------
	aaWebDrive.attemptReconnect = async function () {
		this.reconnectAttempts++;
		console.log(`🔄 Attempting to reconnect (${this.reconnectAttempts}/${this.options.maxReconnectAttempts})...`);
		
		setTimeout(async () => {
			try {
				await this.connect();
				
				// 重新创建会话和订阅事件
				if (this.sessionId) {
					await this.createSession();
					if (this.subscribedEvents.size > 0) {
						await this.subscribe([...this.subscribedEvents]);
					}
				}
			} catch (error) {
				console.error('Reconnection failed:', error);
			}
		}, this.options.reconnectInterval);
	};

	//---------------------------------------------------------------------------
	aaWebDrive.sendCommand = async function (method, params = {},timeout=0) {
		if (!this.connected) {
			throw new Error('Not connected to WebDriver BiDi');
		}
		
		const id = ++this.messageId;
		
		return new Promise((resolve, reject) => {
			let timer;
			// 设置超时
			if(timeout>0) {
				timer = setTimeout(() => {
					this.pendingCommands.delete(id);
					reject(new Error(`Command timeout: ${method}`));
				}, timeout||this.options.timeout);
			}
			
			this.pendingCommands.set(id, { resolve, reject, timeout:timer });
			
			const message = JSON.stringify({ id, method, params });
			this.ws.send(message);
			
			// 调试日志
			if (this.options.debug) {
				console.log('📤 Sent:', { id, method, params });
			}
		});
	};
}

//***************************************************************************
// ===== 会话管理 =====
//***************************************************************************
{
	//----------------------------------------------------------------------
	aaWebDrive.createSession = async function (capabilities = {}) {
		const result = await this.sendCommand('session.new', {
			capabilities: {
				alwaysMatch: { browserName: 'firefox', ...capabilities }
			}
		});
		
		this.sessionId = result.sessionId;
		console.log('📱 Session created:', this.sessionId);
		return result;
	};
	
	//----------------------------------------------------------------------
	aaWebDrive.getStatus=async function(){
		return this.sendCommand('session.status');
	};
	
	//----------------------------------------------------------------------
	aaWebDrive.endSession=async function(){
		if (this.sessionId) {
			await this.sendCommand('session.end');
			this.sessionId = null;
		}
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
}

export default AaWebDrive;
export {AaWebDrive};