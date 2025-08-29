import { URL } from 'url'
import pathLib from 'path'
import { promises as fs, promises as fsp } from 'fs'
import { spawn } from 'child_process'
import { EventEmitter } from 'events'
import AaWebDrive from './WebDrive.mjs'
import WebSocket from 'ws'

let WebDriveSys,WebDriveApp;

const codeURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const codeDirURL=pathLib.dirname(codeURL);
const codeDirPath=codeDirURL.startsWith("file://")?pathLib.fileURLToPath(codeDirURL):codeDirURL;

const WebRpa_DataDirRoot=process.env.WEBRPA_DATADIR||process.env.AAF_DATADIR;

const aliasPattern = /^[a-zA-Z_][a-zA-Z0-9_]*$/;
const WebRpa_Version='0.0.1';

const browserAliasMap=new Map();
const browserMap=new Map();
let nextBrowserId=0;
let nextTempBrowserId=0;
let nextBrowserPort=9222;

async function sleep(time){
	let func,pms;
	pms=new Promise((resolve,reject)=>{
		setTimeout(resolve,time);
	});
	return pms;
}

async function deleteFile(filePath) {
	try {
		await fsp.unlink(filePath);
	} catch (err) {
	}
}

function getBrowserId(browser){
	let keys,key;
	keys=Array.from(browserMap.keys());
	for(key of keys){
		if(browserMap.get(key)===browser){
			return key;
		}
	}
	return null;
}

let WebDriveRpaStarted=false;
/**
 * 清理指定目录中以指定前缀开头的所有子目录
 * @param {string} prefix - 前缀（如 'firefox-profile-'）
 * @param {string} [baseDir='/tmp'] - 扫描的根目录，默认 /tmp
 */
async function cleanTmpDirs(prefix, baseDir = '/tmp') {
	try {
		const entries = await fs.readdir(baseDir, { withFileTypes: true });
		
		const targets = entries.filter(entry =>
			entry.isDirectory() && entry.name.startsWith(prefix)
		);
		
		for (const dir of targets) {
			const fullPath = pathLib.join(baseDir, dir.name);
			try {
				await fs.rm(fullPath, { recursive: true, force: true });
				console.log(`✅ 已删除: ${fullPath}`);
			} catch (err) {
				console.warn(`⚠️ 删除失败: ${fullPath}`, err.message);
			}
		}
		
		console.log(`共尝试清理 ${targets.length} 个目录`);
	} catch (err) {
		console.error('读取目录失败：', err.message);
	}
}

//***************************************************************************
//WebDriveApp
//***************************************************************************
{
	let webDriveApp;
	WebDriveApp=function(browserId){
		this.browserId=browserId;
		
		this.options={
			timeout:30000
		};

		this.firefox=null;
		this.port=9222;
		this.url=null;
		this.waitStart=null;
		this.alias="";
		this.hookedNodes=new Set();
		this.refCount=0;
		
		this.ws=null;
		this.messageId = 0;
		this.pendingCommands = new Map();
		
		this.sessionId = null;
		this.connected = false;
		
		this.reconnectTimer=null;
		this.reconnectAttempts = 0;
		this.subscribedEvents = new Set();
		
		// 绑定方法以保持this上下文
		this.handleMessage = this.handleMessage.bind(this);
		this.handleClose = this.handleClose.bind(this);
		this.handleError = this.handleError.bind(this);
		
	};
	webDriveApp=WebDriveApp.prototype=Object.create(EventEmitter.prototype);
	webDriveApp.constructor = WebDriveApp;
	
	//-----------------------------------------------------------------------
	webDriveApp.hookAgentNode=function(agentNode){
		this.hookedNodes.add(agentNode);
	};
	
	//-----------------------------------------------------------------------
	webDriveApp.sendToHooked=async function(msg,msgVO){
		let nodes,node;
		nodes = this.hookedNodes.values();
		for (node of nodes) {
			if(node.nodeWS) {
				node.send(msg, msgVO);
			}else{
				this.hookedNodes.delete(node);
			}
		}
	};

	//***********************************************************************
	// ===== 启停，网络连接 =====
	//***********************************************************************
	{
		//-----------------------------------------------------------------------
		webDriveApp.start = async function (pathToFireFox, pathToData, port = 9222, alias = null) {
			let firefox, args, waitApp, pms;
			if (this.waitStart) {
				return await this.waitStart;
			}
			if (!pathToFireFox) {
				pathToFireFox = process.env.WEBDRIVE_APP;
			}
			if (!pathToFireFox) {
				throw Error("Missing Firefox app path.");
			}
			if (pathToFireFox[0] === ".") {
				pathToFireFox = pathLib.join(codeDirPath, pathToFireFox);
			}
			this.port = port;
			pms = this.waitStart = new Promise((resolve, reject) => {
				this.startCallback = resolve;
				this.startCallerror = reject;
			});
			this.waitToStart = pms;
			this.url = `ws://localhost:${port}/session`;
			
			waitApp = true;
			if (pathToData) {
				args = ['-no-remote', `--remote-debugging-port=${port}`, `--profile`, pathToData, `about:blank`];//TODO: Code this;
			} else {
				args = [`--remote-debugging-port=${port}`, `about:blank`];
			}
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
					let callback;
					console.log('✅ Firefox WebDriver BiDi 已启动');
					waitApp=false;
					this.connect().then(()=>{
						waitApp = false;
						callback = this.startCallback;
						if (callback) {
							this.startCallback = null;
							this.startCallerror = null;
						}
						callback(this.port);
					});
				}
			});
			
			firefox.on('exit', async (code) => {
				console.log(`Firefox exited with code ${code}`);
				this.emit("browser.exit");
				await this.sendToHooked("WebDriveBrowserClosed", { alias: this.alias });
			});
			//Alias for AAEE-Driver
			this.alias = alias;
			this.aaeeAlias = alias;
			return await pms;
		};
		
		//-----------------------------------------------------------------------
		webDriveApp.close = async function () {
			let timer;
			return new Promise((resolve, reject) => {
				this.emit("browser.willExit");
				if (!this.firefox) {
					reject(new Error("Browser is not alive."));
				}
				this.firefox.on('exit', () => {
					this.firefox = null;
					if (timer) {
						clearTimeout(timer);
					}
					resolve();
				});
				this.firefox.kill('SIGTERM');
				timer = setTimeout(() => {
					if (this.firefox) {
						this.firefox.kill('SIGKILL');
					}
				}, 5000);//Wait 5 sec. to force kill.
			});
		};
		
		//-----------------------------------------------------------------------
		webDriveApp.connect = async function () {
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
		webDriveApp.handleMessage = async function (data) {
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
		webDriveApp.handleCommandResponse = async function (message) {
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
		webDriveApp.handleEvent = async function (message) {
			let nodes,node;
			const { method, params } = message;
			console.log(`Got WebDriver event: `,message);
			// 发出具体的事件
			this.emit(method, params);
			// 发出通用事件
			this.emit('event', { method, params });
			// 根据事件类型进行分类处理
			const [category] = method.split('.');
			this.emit(`${category}.*`, { method, params });
			
			await this.sendToHooked("WebDriveEvent", {alias:this.alias, event:message});
		};
		
		//---------------------------------------------------------------------------
		webDriveApp.handleClose = async function (code, reason) {
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
			}else{
				this.emit("browser.exit");
			}
		};
		
		//---------------------------------------------------------------------------
		webDriveApp.handleError = function (error) {
			console.error('❌ WebSocket error:', error);
			this.emit('error', error);
		};
		
		//---------------------------------------------------------------------------
		webDriveApp.attemptReconnect = async function () {
			this.reconnectAttempts++;
			console.log(`🔄 Attempting to reconnect (${this.reconnectAttempts}/${this.options.maxReconnectAttempts})...`);
			
			this.reconnectTimer=setTimeout(async () => {
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
		webDriveApp.sendCommand = async function (method, params = {},timeout=0) {
			if (!this.connected) {
				throw new Error('Not connected to WebDriver BiDi');
			}
			
			const id = ++this.messageId;
			
			return new Promise(async (resolve, reject) => {
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
				await this.ws.send(message);
				
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
		webDriveApp.createSession = async function (capabilities = {}) {
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
		webDriveApp.getStatus=async function(){
			return this.sendCommand('session.status');
		};
		
		//----------------------------------------------------------------------
		webDriveApp.endSession=async function(){
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
		webDriveApp.subscribe=async function(events) {
			events.forEach(event => this.subscribedEvents.add(event));
			return this.sendCommand('session.subscribe', { events });
		};
		
		//-----------------------------------------------------------------------
		webDriveApp.unsubscribe=async function(events) {
			events.forEach(event => this.subscribedEvents.delete(event));
			return this.sendCommand('session.unsubscribe', { events });
		};
	}
}

//---------------------------------------------------------------------------
async function openBrowser(alias,opts,agentNode){
	let browserId, browser, dirPath, port;
	if(!WebDriveRpaStarted){
		await cleanTmpDirs("AaWebDrive-");
		WebDriveRpaStarted=true;
	}
	
	if(alias){
		if((!aliasPattern.test(alias)) || alias.startsWith("TMP_")){
			throw Error("Browser alias is invalid.");
		}
		browserId=browserAliasMap.get(alias);
		if(browserId){
			browser=browserMap.get(browserId);
			if(browser){
				browser.hookAgentNode(agentNode);
				return browser;
			}
		}
	}
	dirPath=null;
	//Check auto data dir
	if(alias && WebRpa_DataDirRoot){
		dirPath = WebRpa_DataDirRoot;
		if (dirPath[0] !== "/") {
			throw Error("");
			//TODO: make it full path
		}
		dirPath = pathLib.join(dirPath, alias);
		try{
			await fs.access(dirPath);
			opts.userDataDir = dirPath;
		}catch(err){
			try {
				await fs.mkdir(dirPath, { recursive: true });
				opts.userDataDir = dirPath;
			}catch(err){
				//Do not use data-dir.
			}
		}
	}else{
		if(!alias) {
			alias = "TMP_" + (nextTempBrowserId++);
		}
		dirPath = await fsp.mkdtemp(pathLib.join("/tmp/", "AaWebDrive-"));
	}
	
	browserId = "" + (nextBrowserId++);
	browser = new WebDriveApp(browserId);
	browserMap.set(browserId, browser);
	if(opts.userDataDir){
		let zonePath=pathLib.join(opts.userDataDir,"AAEZone");
		try{
			await fs.access(zonePath);
			browser.aaeZonePath=zonePath;
		}catch(err){
			try {
				await fs.mkdir(zonePath, { recursive: true });
				browser.aaeZonePath=zonePath;
			}catch(err){
				//Do not use data-dir.
			}
		}
	}
	
	if(alias){
		browserAliasMap.set(alias,browserId);
		browser.aaeeAlias=alias;
	}else{
		alias="TMP_"+(nextTempBrowserId++);
		browserAliasMap.set(alias,browserId);
		browser.aaeeAlias=alias;
	}
	browser.hookAgentNode(agentNode);
	browser.on("browser.exit",()=>{
		browserAliasMap.delete(alias);
		browserMap.delete(browserId);
	});
	browser.on("browser.willExit",()=>{
		browserAliasMap.delete(alias);
		browserMap.delete(browserId);
	});
	port=nextBrowserPort++;
	await browser.start(null,dirPath,port,alias)
	return browser;
}

//***************************************************************************
//WebDriveSys
//***************************************************************************
WebDriveSys = {
	init:(handlerMap) => {
		//-------------------------------------------------------------------
		handlerMap.set("WebDriveOpenBrowser", async function (msg,msgVO,agentNode,session) {
			let alias = msgVO.alias;
			let opts=msgVO.options||msgVO.opts;
			let browser= await openBrowser(alias,opts,agentNode);
			if(browser){
				browser.refCount=browser.refCount>0?(browser.refCount+1):1;
				return browser.browserId;
			}
			return null;
		});

		//-------------------------------------------------------------------
		handlerMap.set("WebDriveCloseBrowser",async function (msg,msgVO,agentNode,session) {
			let browserId,browser;
			browserId= msgVO.browserId||msgVO.browser;
			if(browserId){
				browser=browserMap.get(browserId);
				if(browser){
					if(browser.refCount>0){
						browser.refCount--;
						if(browser.refCount===0){
							browser.close();
						}
					}
				}
			}
		});
		
		//-------------------------------------------------------------------
			handlerMap.set("WebDriveCommand",async function (msg,msgVO,agentNode,session) {
			let browserId,browser,method,params,timeout;
			browserId= msgVO.browserId||msgVO.browser;
			method=msgVO.method;
			params=msgVO.params;
			timeout=msgVO.timeout;
			if(browserId && method && params){
				browser=browserMap.get(browserId);
				if(browser){
					return await browser.sendCommand(method,params,timeout);
				}
			}
		});
	}
};

export default WebDriveSys;
export {WebDriveSys};