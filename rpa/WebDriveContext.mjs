import { EventEmitter } from 'events';
import fsp from "fs/promises";
import pathLib from "path";
import KeyCodes from "./KeyCodes.mjs";
import clipboardy from 'clipboardy'
import { ensureCodeLib } from './CodeLib.mjs'
import html2md from 'html-to-md';
import AhFileLib from "../agenthub/AhFileLib.mjs";

async function sleep(time){
	let func,pms;
	pms=new Promise((resolve,reject)=>{
		setTimeout(resolve,time);
	});
	return pms;
}

function wrapArgumentForBiDi(value) {
	if(value && value.type){
		return value;
	}
	if (value === null) return { type: 'null' };
	if (value === undefined) return { type: 'undefined' };
	if (typeof value === 'string') return { type: 'string', value };
	if (typeof value === 'number') return { type: 'number', value };
	if (typeof value === 'boolean') return { type: 'boolean', value };
	if (typeof value === 'bigint') return { type: 'bigint', value: value.toString() + 'n' };
	if (value instanceof Date) return { type: 'date', value: value.toISOString() };
	if (value instanceof RegExp) return { type: 'regexp', value: { pattern: value.source, flags: value.flags } };
	
	if (Array.isArray(value)) {
		return {
			type: 'array',
			value: value.map(wrapArgumentForBiDi)
		};
	}
	
	if (typeof value === 'object') {
		const obj = [];//{}
		for (const key of Object.keys(value)) {
			obj.push([key,wrapArgumentForBiDi(value[key])]);
			//obj[key] = wrapArgumentForBiDi(value[key]);
		}
		return { type: 'object', value: obj };
	}
	
	throw new Error(`Unsupported value type: ${typeof value}`);
}

function deserializeEvaluateResult(result) {
	if (!result || typeof result !== 'object') return result;
	
	if ('type' in result) {
		switch (result.type) {
			case 'null':
				return null;
			case 'undefined':
				return undefined;
			case 'string':
			case 'number':
			case 'boolean':
				return result.value;
			case 'bigint':
				return BigInt(result.value);
			case 'date':
				return new Date(result.value);
			case 'regexp':
				return new RegExp(result.value.pattern, result.value.flags);
			case 'array':
				return (result.value || []).map(deserializeEvaluateResult);
			case 'object': {
				let val
				const obj = {};
				for (val of result.value || []) {
					obj[val[0]] = deserializeEvaluateResult(val[1]);
				}
				return obj;
			}
			default:
				// For unhandled types like 'map', 'set', 'function', or 'node' handles etc.
				return result;
		}
	}
	
	// fallback: already raw value or unexpected format
	return result;
}

//***************************************************************************
//AaWebDriveMouse
//***************************************************************************
let AaWebDriveMouse,aaWebDriveMouse;
{
	AaWebDriveMouse=function(context){
		this.context=context;
	};
	aaWebDriveMouse=AaWebDriveMouse.prototype={};
	
	//----------------------------------------------------------------------
	aaWebDriveMouse.move=async function(x,y,opts){
		let smooth;
		smooth=opts?.smooth||(opts?.steps>1)||false;
		return this.context.moveMouse(x,y, { smooth });
	};

	//----------------------------------------------------------------------
	aaWebDriveMouse.click=async function(x,y,opts){
		let count,delay,smooth,i;
		let action=await this.context.startAction();
		count=opts?.count||1;
		delay=opts?.delay||30;
		smooth=opts?.smooth||(opts?.steps>1)||false;
		await this.move(x,y,{smooth});
		for(i=0;i<count;i++){
			await this.context.mouseClick({delay});
		}
		await this.context.endAction(action);
	};

	//----------------------------------------------------------------------
	aaWebDriveMouse.down=async function(opts){
		let button=opts?.button||0;
		return await this.context.mouseDown(button);
	};
	
	//----------------------------------------------------------------------
	aaWebDriveMouse.up=async function(opts){
		let button=opts?.button||0;
		return await this.context.mouseUp(button);
	};
	
	//----------------------------------------------------------------------
	aaWebDriveMouse.wheel=async function(opts){
		return await this.context.wheel(null,{x:this.context.pageMouseX,y:this.pageMouseY,deltaX:opts?.deltaX||0,deltaY:opts?.deltaY||0,smooth:opts?.smooth!==false,steps:opts?.steps||1});
	};
	
	//----------------------------------------------------------------------
	aaWebDriveMouse.dragAndDrop=async function(start,target,opts){
		let action=await this.context.startAction();
		await this.move(start.x,start.y,opts);
		await this.down();
		await this.move(target.x,target.y,opts);
		await this.up();
		await this.context.endAction(action);
	};
	
	//----------------------------------------------------------------------
	aaWebDriveMouse.reset=async function(opts){
		return this.move(5*Math.floor(Math.random()*10),5*Math.floor(Math.random()*10));
	};

	//----------------------------------------------------------------------
	aaWebDriveMouse.drag=async function(opts){/*TODO: Code this:*/};
	//----------------------------------------------------------------------
	aaWebDriveMouse.drop=async function(opts){/*TODO: Code this:*/};
	//----------------------------------------------------------------------
	aaWebDriveMouse.dragEnter=async function(target,data,opts){/*TODO: Code this:*/};
	//----------------------------------------------------------------------
	aaWebDriveMouse.dragOver=async function(target,data,opts){/*TODO: Code this:*/};
}

//***************************************************************************
//AaWebDriveKeyboard
//***************************************************************************
let AaWebDriveKeyboard,aaWebDriveKeyboard;
{
	AaWebDriveKeyboard=function(context){
		this.context=context;
	};
	aaWebDriveKeyboard=AaWebDriveKeyboard.prototype={};
	
	//----------------------------------------------------------------------
	aaWebDriveKeyboard.down=async function(key,opts){
		await this.context.keyDown(key);
	};
	
	//----------------------------------------------------------------------
	aaWebDriveKeyboard.up=async function(key,opts){
		await this.context.keyUp(key);
	};
	
	//----------------------------------------------------------------------
	aaWebDriveKeyboard.press=async function(key,opts){
		let count,delay,i;
		count=opts?.count||1;
		delay=opts?.delay||0;
		for(i=0;i<count;i++) {
			await this.context.keyDown(key);
			delay && (await sleep(delay));
			await this.context.keyUp(key);
		}
	};
	
	//----------------------------------------------------------------------
	aaWebDriveKeyboard.sendCharacter=async function(char,opts){
		return this.press(char,opts);
	};
	
	//----------------------------------------------------------------------
	aaWebDriveKeyboard.type=async function(text,opts){
		return await this.context.type(null,text,opts);
	};
}

//***************************************************************************
//AaWebDriveContext
//***************************************************************************
let AaWebDriveContext,aaWebDriveContext;
//---------------------------------------------------------------------------
AaWebDriveContext=function(webDrive,contextId){
	this.webDrive=webDrive;
	this.context=contextId;
	this.subscribes={};
	this.pageMouseX=Math.floor(Math.random()*30)+10;
	this.pageMouseY=Math.floor(Math.random()*30)+10;
	
	this.action=null;
	
	this.frameMap=new Map();
	
	//Inbuilt objects:
	this.mouse=new AaWebDriveMouse(this);
	this.keyboard=new AaWebDriveKeyboard(this);
};
aaWebDriveContext=AaWebDriveContext.prototype=Object.create(EventEmitter.prototype);
aaWebDriveContext.constructor = AaWebDriveContext;

//---------------------------------------------------------------------------
//cmd must be WebDrive-BiDi command!
aaWebDriveContext.sendCommand=async function(cmd,params,timeout){
	params.target={context:this.context};
	return await this.webDrive.sendCommand(cmd,params,timeout);
};//Tested

//***************************************************************************
// ======常用功能======
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDriveContext.goto=async function(url,opts){
		let wait,timeout;
		wait=opts?.wait||"complete";
		timeout=opts?.timeout||0;
		return await this.webDrive.goto(this.context, url, wait, timeout);
	};//Tested, seg applied
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.goBack=async function(opts){
		let wait;
		wait=opts?.wait||"complete";
		return await this.webDrive.goBack(this.context, wait);
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.goForward=async function(opts){
		let wait;
		wait=opts?.wait||"complete";
		return await this.webDrive.goForward(this.context, wait);
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.reload=async function(opts){
		let wait,ignoreCache;
		wait = opts?.wait || "complete";
		ignoreCache=opts?.ignoreCache||false;
		return await this.webDrive.reload(this.context, ignoreCache,wait);
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.title = async function () {
		return await this.sendCommand('script.evaluate', {
			expression: "document.title",
			awaitPromise: false,
			resultOwnership: "none"
		}).then(result => {
			return result.result.value;
		});
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.url = async function () {
		return await this.sendCommand('browsingContext.getTree', {
			root:this.context,
			maxDepth: 0
		}).then(result => {
			const context = result.contexts.find(ctx => ctx.context === this.context);
			return context ? context.url : null;
		});
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.content = async function () {
		return await this.sendCommand('script.evaluate', {
			expression: 'document.documentElement.outerHTML',
			awaitPromise: false,
			resultOwnership: 'root'
		}).then(result => {
			return result.result.value;
		});
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.setContent=async function(html,opts){
		//TODO: use sendCommand with WebDrive command
		let wait, url;
		wait = opts?.wait || "complete";
		url = opts?.url || "about:blank";
		
		// Use script.evaluate to set the document content
		await this.sendCommand('script.evaluate', {
			expression: `
				document.open();
				document.write(${JSON.stringify(html)});
				document.close();
			`,
			awaitPromise: false,
			resultOwnership: 'root'
		});
		
		// Wait for navigation to complete if specified
		if (wait === "complete") {
			await this.sendCommand('browsingContext.navigate', {
				url: 'data:text/html;charset=utf-8,' + encodeURIComponent(html),
				wait: wait
			});
		}
	};//TODO: Test this later
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.frames=async function(infoOnly=true){
		//TODO: use sendCommand with WebDrive command, return array of frame's webContext
		return await this.sendCommand('browsingContext.getTree', {
			root:this.context,
			maxDepth: 1
		}).then(result => {
			const context = result.contexts.find(ctx => ctx.context === this.context);
			if (context && context.children) {
				if(infoOnly){
					return context.children;
				}
				return context.children.map((child) => {
					let frame=this.frameMap.get(child.context);
					if(!frame) {
						frame = new AaWebDriveContext(this.webDrive, child.context);
						this.frameMap.set(child.context, frame);
					}
					return frame;
				});
			}
			return [];
		});
	};//Tested, but only tested return []

	//-----------------------------------------------------------------------
	aaWebDriveContext.close = async function (opts) {
		//TODO: use sendCommand with WebDrive command
		let promptBeforeUnload = opts?.promptBeforeUnload || false;
		
		return await this.webDrive.sendCommand('browsingContext.close', {
			context:this.context,
			promptBeforeUnload: promptBeforeUnload
		});
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.isClosed=async function(){
		//TODO: use sendCommand with WebDrive command
		try {
			const result=await this.sendCommand('browsingContext.getTree', {
				root:this.context,
				maxDepth: 0
			});
			const context = result.contexts.find(ctx => ctx.context === this.context);
			return !(!!context);
		} catch (error) {
			// If the command fails with a no such browsing context error, it's closed
			if (error.message && error.message.includes('no such ')) {
				return true;
			}
			// For other errors, re-throw them
			throw error;
		}
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.pdf=async function(opts){
		//TODO: use sendCommand with WebDrive command
		let options = opts || {};
		// Set default options
		let printOptions = {
			landscape: options.landscape || false,
			displayHeaderFooter: options.displayHeaderFooter || false,
			printBackground: options.printBackground || false,
			scale: options.scale || 1.0,
			paperWidth: options.width || 8.5,
			paperHeight: options.height || 11,
			marginTop: options.margin?.top || 0.4,
			marginBottom: options.margin?.bottom || 0.4,
			marginLeft: options.margin?.left || 0.4,
			marginRight: options.margin?.right || 0.4,
			pageRanges: options.pageRanges || '',
			headerTemplate: options.headerTemplate || '',
			footerTemplate: options.footerTemplate || '',
			preferCSSPageSize: options.preferCSSPageSize || false
		};
		
		// Handle format option (convert to width/height)
		if (options.format) {
			const formats = {
				'A0': { width: 33.1, height: 46.8 },
				'A1': { width: 23.4, height: 33.1 },
				'A2': { width: 16.54, height: 23.4 },
				'A3': { width: 11.7, height: 16.54 },
				'A4': { width: 8.27, height: 11.7 },
				'A5': { width: 5.83, height: 8.27 },
				'A6': { width: 4.13, height: 5.83 },
				'Letter': { width: 8.5, height: 11 },
				'Legal': { width: 8.5, height: 14 },
				'Tabloid': { width: 11, height: 17 },
				'Ledger': { width: 17, height: 11 }
			};
			
			if (formats[options.format]) {
				printOptions.paperWidth = formats[options.format].width;
				printOptions.paperHeight = formats[options.format].height;
			}
		}
		
		return await this.sendCommand('browsingContext.print', printOptions);
	};//TODO: Test this later
	
}

//***************************************************************************
// ======执行脚本/函数======
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDriveContext.evaluateFileOnNewDocument=async function(scriptId,filePath,...args){
		//TODO: Code this:
	};//TODO: Code this later:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.evaluateOnNewDocument=async function(scriptId,pageFunction,...args){
		//TODO: Code this:
	};//TODO: Code this later:
	
	aaWebDriveContext.removeScriptToEvaluateOnNewDocument=async function(scriptId){
		//TODO: Code this:
	};//TODO: Code this later:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.evaluateFile= async function(filePath, opts) {
		//TODO: ensure full-path, then read file content, then call this.evalaute:
		// Resolve the full path
		let fullPath;
		if (pathLib.isAbsolute(filePath)) {
			fullPath = filePath;
		} else {
			fullPath = pathLib.resolve(process.cwd(), filePath);
		}
		
		// Read the file content
		const fileContent = await fsp.readFile(fullPath, 'utf8');
		
		// Call evaluate with the file content
		return await this.evaluate(fileContent, opts);
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.evaluate= async function(expression, opts) {
		//TODO: use sendCommand with WebDrive command, opts should be like puppeteer API/s options
		let options = opts || {};
		if(options>0){
			options={timeout:options};
		}
		
		// Set default options based on WebDriver BiDi specification
		let evalOptions = {
			expression: expression,
			target: {
				context: this.context
			},
			awaitPromise: options.awaitPromise !== false, // Default to true
			resultOwnership: options.resultOwnership || 'none',
			serializationOptions: {
				maxDomDepth: options.maxDomDepth || 0,
				maxObjectDepth: options.maxObjectDepth || null,
				includeShadowTree: options.includeShadowTree || 'none'
			}
		};
		
		// Handle sandbox option if provided
		if (options.sandbox) {
			evalOptions.sandbox = options.sandbox;
		}else if (options.realm) {// Handle realm option if provided
			evalOptions.target.realm = options.realm;
		}
		
		try {
			let timeout=options?.timeout||0;
			const result = await this.sendCommand('script.evaluate', evalOptions,timeout);
			
			// Handle different result types
			if (result.type === 'success') {
				return result.result.value;
			} else if (result.type === 'exception') {
				throw new Error(result.exceptionDetails.text || 'Script evaluation failed');
			}
			return result;
		} catch (error) {
			// Re-throw with more context if needed
			throw error;
		}
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.evaluateHandle= async function(expression, opts) {
		//TODO: use sendCommand with WebDrive command, opts should be like puppeteer API/s options
		let options = opts || {};
		if(options>0){
			options={timeout:options};
		}
		
		// Set default options based on WebDriver BiDi specification
		let evalOptions = {
			expression: expression,
			target: {
				context: this.context
			},
			awaitPromise: options.awaitPromise !== false, // Default to true
			resultOwnership: options.resultOwnership || 'root',
			serializationOptions: {
				maxDomDepth: options.maxDomDepth || 0,
				maxObjectDepth: options.maxObjectDepth || null,
				includeShadowTree: options.includeShadowTree || 'none'
			}
		};
		
		// Handle sandbox option if provided
		if (options.sandbox) {
			evalOptions.sandbox = options.sandbox;
		}else if (options.realm) {// Handle realm option if provided
			evalOptions.target.realm = options.realm;
		}
		
		try {
			let timeout=options?.timeout||0;
			const result = await this.sendCommand('script.evaluate', evalOptions,timeout);
			
			// Handle different result types
			if (result.type === 'success') {
				return result.result;
			} else if (result.type === 'exception') {
				throw new Error(result.exceptionDetails.text || 'Script evaluation failed');
			}
			return result;
		} catch (error) {
			// Re-throw with more context if needed
			throw error;
		}
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.callFunctionFile= async function(filePath, arguments_, opts) {
		//TODO: ensure full-path, then read file content, then call this.callFunction:
		// Resolve the full path
		let fullPath;
		if (pathLib.isAbsolute(filePath)) {
			fullPath = filePath;
		} else {
			fullPath = pathLib.resolve(process.cwd(), filePath);
		}
		
		// Read the file content
		const fileContent = await fsp.readFile(fullPath, 'utf8');
		
		// Call evaluate with the file content
		return await this.callFunction(fileContent, arguments_,opts);
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.callFunction= async function(functionDeclaration, arguments_ = [], opts) {
		//TODO: use sendCommand with WebDrive command, opts should be like puppeteer API/s options
		let options = opts || {};
		if(options>0){
			options={timeout:options};
		}
		if(functionDeclaration instanceof Function){
			functionDeclaration=functionDeclaration.toString();
		}
		// Set default options based on WebDriver BiDi specification
		let callOptions = {
			functionDeclaration: functionDeclaration,
			target: {
				context: this.context
			},
			awaitPromise: options.awaitPromise !== false, // Default to true
			resultOwnership: options.resultOwnership || 'none',
			serializationOptions: {
				maxDomDepth: options.maxDomDepth || 0,
				maxObjectDepth: options.maxObjectDepth || null,
				includeShadowTree: options.includeShadowTree || 'none'
			}
		};
		
		// Add arguments if provided
		if (arguments_ && arguments_.length > 0) {
			arguments_=arguments_.map(value=>wrapArgumentForBiDi(value));
			callOptions.arguments = arguments_;
		}
		
		// Handle sandbox option if provided
		if (options.sandbox) {
			callOptions.target.sandbox = options.sandbox;
		}
		
		// Handle realm option if provided
		if (options.realm) {
			callOptions.target.realm = options.realm;
		}
		
		try {
			let timeout=options?.timeout||0;
			const result = await this.sendCommand('script.callFunction', callOptions,timeout);
			
			// Handle different result types
			if (result.type === 'success') {
				return deserializeEvaluateResult(result.result);
			} else if (result.type === 'exception') {
				throw new Error(result.exceptionDetails.text || 'Function call failed');
			}
			
			return result;
		} catch (error) {
			// Re-throw with more context if needed
			throw error;
		}
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.callFunctionHandle = async function(functionDeclaration, arguments_ = [], opts) {
		//TODO: use sendCommand with WebDrive command, opts should be like puppeteer API/s options
		let options = opts || {};
		if(options>0){
			options={timeout:options};
		}
		if(functionDeclaration instanceof Function){
			functionDeclaration=functionDeclaration.toString();
		}
		// Set default options based on WebDriver BiDi specification
		let callOptions = {
			functionDeclaration: functionDeclaration,
			target: {
				context: this.context
			},
			awaitPromise: options.awaitPromise !== false, // Default to true
			resultOwnership: options.resultOwnership || 'root',
			serializationOptions: {
				maxDomDepth: options.maxDomDepth || 0,
				maxObjectDepth: options.maxObjectDepth || null,
				includeShadowTree: options.includeShadowTree || 'none'
			}
		};
		
		// Add arguments if provided
		if (arguments_ && arguments_.length > 0) {
			arguments_=arguments_.map(value=>wrapArgumentForBiDi(value));
			callOptions.arguments = arguments_;
		}
		
		// Handle sandbox option if provided
		if (options.sandbox) {
			callOptions.target.sandbox = options.sandbox;
		}
		
		// Handle realm option if provided
		if (options.realm) {
			callOptions.target.realm = options.realm;
		}
		
		try {
			let timeout=options?.timeout||0;
			const result = await this.sendCommand('script.callFunction', callOptions,timeout);
			
			// Handle different result types
			if (result.type === 'success') {
				return result.result;
			} else if (result.type === 'exception') {
				throw new Error(result.exceptionDetails.text || 'Function call failed');
			}
			
			return result;
		} catch (error) {
			// Re-throw with more context if needed
			throw error;
		}
	};//Tested

	//-----------------------------------------------------------------------
	aaWebDriveContext.addScriptTag = async function(opts) {
		//TODO: use sendCommand with WebDrive command, opts should be like puppeteer API/s options
		let options = opts || {};
		let scriptElement;
		
		if (options.url) {
			// Add script tag with src attribute
			scriptElement = {
				tagName: 'script',
				attributes: {
					src: options.url
				}
			};
			
			// Add type attribute if specified
			if (options.type) {
				scriptElement.attributes.type = options.type;
			}
			
			// Add id attribute if specified
			if (options.id) {
				scriptElement.attributes.id = options.id;
			}
		} else if (options.content) {
			// Add script tag with inline content
			scriptElement = {
				tagName: 'script',
				innerHTML: options.content
			};
			
			// Add type attribute if specified
			if (options.type) {
				scriptElement.attributes = scriptElement.attributes || {};
				scriptElement.attributes.type = options.type;
			}
			
			// Add id attribute if specified
			if (options.id) {
				scriptElement.attributes = scriptElement.attributes || {};
				scriptElement.attributes.id = options.id;
			}
		} else if (options.path) {
			// For path option, we need to read the file content first
			// This would typically require fs module, but since we can't import here,
			// we'll throw an error indicating this needs to be handled at a higher level
			throw new Error('Path option not supported in WebDriver BiDi context. Use url or content instead.');
		} else {
			throw new Error('Either url, content, or path must be specified');
		}
		
		// Create the script element using script evaluation
		const createScriptExpression = `
			(function() {
				const script = document.createElement('script');
				${options.url ? `script.src = '${options.url}';` : ''}
				${options.content ? `script.textContent = ${JSON.stringify(options.content)};` : ''}
				${options.type ? `script.type = '${options.type}';` : ''}
				${options.id ? `script.id = '${options.id}';` : ''}
				
				return new Promise((resolve, reject) => {
					script.onload = () => resolve(script);
					script.onerror = (error) => reject(error);
					
					${options.url ? '' : 'resolve(script);'} // For inline scripts, resolve immediately
					
					document.head.appendChild(script);
				});
			})()
		`;
		
		try {
			const result = await this.sendCommand('script.evaluate', {
				expression: createScriptExpression,
				awaitPromise: true,
				resultOwnership: 'root'
			});
			
			return result.result;
		} catch (error) {
			throw new Error(`Failed to add script tag: ${error.message}`);
		}
	};//TODO: Test this later:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.addStyleTag = async function(opts) {
		//TODO: use sendCommand with WebDrive command, opts should be like puppeteer API/s options
		let options = opts || {};
		
		if (options.url) {
			// Add style tag with href attribute (external CSS)
			const createLinkExpression = `
				(function() {
					const link = document.createElement('link');
					link.rel = 'stylesheet';
					link.href = '${options.url}';
					${options.id ? `link.id = '${options.id}';` : ''}
					
					return new Promise((resolve, reject) => {
						link.onload = () => resolve(link);
						link.onerror = (error) => reject(error);
						
						document.head.appendChild(link);
					});
				})()
			`;
			
			try {
				const result = await this.sendCommand('script.evaluate', {
					expression: createLinkExpression,
					awaitPromise: true,
					resultOwnership: 'root'
				});
				
				return result.result;
			} catch (error) {
				throw new Error(`Failed to add style tag with URL: ${error.message}`);
			}
		} else if (options.content) {
			// Add style tag with inline content
			const createStyleExpression = `
				(function() {
					const style = document.createElement('style');
					style.textContent = ${JSON.stringify(options.content)};
					${options.id ? `style.id = '${options.id}';` : ''}
					
					document.head.appendChild(style);
					return style;
				})()
			`;
			
			try {
				const result = await this.sendCommand('script.evaluate', {
					expression: createStyleExpression,
					awaitPromise: false,
					resultOwnership: 'root'
				});
				
				return result.result;
			} catch (error) {
				throw new Error(`Failed to add style tag with content: ${error.message}`);
			}
		} else if (options.path) {
			// For path option, we need to read the file content first
			// This would typically require fs module, but since we can't import here,
			// we'll throw an error indicating this needs to be handled at a higher level
			throw new Error('Path option not supported in WebDriver BiDi context. Use url or content instead.');
		} else {
			throw new Error('Either url, content, or path must be specified');
		}
	};//TODO: Test this later:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.disown=async function(...handles){
		handles=handles.map(handle=>{return handle.handle||handle});
		return await this.sendCommand("script.disown",{
			"handles": handles
		});
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.exposeFunction=async function(name,func,sandbox){
		//TODO: Code this:
		
	};//TODO: Code this later:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.removeExposedFunction=async function(name,sandbox){
		//TODO: Code this:
	};//TODO: Code this later:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.ensureCodeLib=async function() {
		return await ensureCodeLib(this);
	};
}

//***************************************************************************
// ======控制页面======
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDriveContext.hideWindow=async function(){
		return this.webDrive.sendCommand('browsingContext.hideBrowserWindow', {context:this.context});
	};
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.unhideWindow=async function(){
		return this.webDrive.sendCommand('browsingContext.unhideBrowserWindow', {context:this.context});
	};
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.moveWindow=async function(x,y,width,height){
		return this.webDrive.sendCommand('browsingContext.moveBrowserWindow', {context:this.context,x,y,width,height});
	};

	//-----------------------------------------------------------------------
	aaWebDriveContext.getViewport=aaWebDriveContext.viewport=async function(){
		try {
			const result = await this.sendCommand('browsingContext.getTree', {
				maxDepth: 0
			});
			
			const context = result.contexts.find(ctx => ctx.context === this.context);
			if (!context) {
				return null;
			}
			
			// Get the current window size using script evaluation
			const viewportResult = await this.sendCommand('script.evaluate', {
				expression: `({
			width: window.innerWidth,
			height: window.innerHeight,
			deviceScaleFactor: window.devicePixelRatio || 1,
			isMobile: /Mobile|Android|iPhone|iPad/.test(navigator.userAgent),
			hasTouch: 'ontouchstart' in window || navigator.maxTouchPoints > 0,
			isLandscape: window.innerWidth > window.innerHeight
		})`,
				awaitPromise: false,
				resultOwnership: 'root'
			});
			
			return viewportResult.result.value;
		} catch (error) {
			throw new Error(`Failed to get viewport: ${error.message}`);
		}
	};//TODO: Test this:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.setViewport=async function(viewport,opts){
		//TODO: use sendCommand with WebDrive command, opts should be like puppeteer API/s options
		let options = opts || {};
		
		try {
			// First, we need to set the window size using browsingContext.setViewport if available
			// If not available, we just don't anything.
			let viewportParams = {
				viewport: {
					width: viewport.width,
					height: viewport.height
				}
			};
			
			// Try using browsingContext.setViewport command first
			try {
				await this.sendCommand('browsingContext.setViewport', viewportParams);
			} catch (error) {
				// If setViewport is not supported, we just ignore this.
			}
			// If mobile emulation is requested, set user agent
			if (viewport.isMobile && options.userAgent) {
				// Note: WebDriver BiDi doesn't have a direct way to set user agent
				// This would need to be handled at the browser session level
				console.warn('User agent setting not supported in WebDriver BiDi setViewport');
			}
			
			return true;
		} catch (error) {
			throw new Error(`Failed to set viewport: ${error.message}`);
		}
	};//TODO: Test this:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.bringToFront = async function(opts) {
		//Use sendCommand with WebDrive command
		try {
			// Use browsingContext.activate to bring the context to front
			await this.webDrive.sendCommand('browsingContext.activate', {context:this.context});
			if(opts?.focusBrowser){
				await this.webDrive.activate();
			}
			return true;
		} catch (error) {
			// If activate command is not supported, try alternative approach
			try {
				// Focus the window using script evaluation as fallback
				await this.sendCommand('script.evaluate', {
					expression: 'window.focus()',
					awaitPromise: false,
					resultOwnership: 'root'
				});
				return true;
			} catch (fallbackError) {
				throw new Error(`Failed to bring context to front: ${error.message}`);
			}
		}
	};//Tested, Seged.
	
	//-----------------------------------------------------------------------
	//Focus an HTML element by selector
	aaWebDriveContext.focus=async function(selector){
		//TODO: use sendCommand with WebDrive command
		try {
			if(typeof(selector)==="string") {
				// Use script.evaluate to focus the element by selector
				const result = await this.callFunction(
						function(selector) {
							// Try querySelector first, fallback to XPath if it fails or selector starts with "("
							let element;
							try {
								if (selector.startsWith('(')) {
									// Selector starts with "(", treat as XPath
									const xpathResult = document.evaluate(selector, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
									element = xpathResult.singleNodeValue;
								} else {
									// Try querySelector first
									try {
										element = document.querySelector(selector);
									} catch (error) {
										// querySelector failed, try XPath
										try {
											const xpathResult = document.evaluate(selector, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
											element = xpathResult.singleNodeValue;
										} catch (xpathError) {
											throw new Error('Invalid selector: ' + selector);
										}
									}
								}
							} catch (error) {
								element=null;
							}
							if (!element) {
								return false;
								//throw new Error('Element not found: ' + selector});
							}
							console.log("Selected element: ",element);
							element.focus();
							return true;
						},
					[selector]);
				return result;
			}else if(selector && selector.handle){
				await this.callFunction(`(element)=>{element.focus();}`,[selector]);
				return true;
			}else if(selector===null){
				await this.evaluate(`
					if (document.activeElement && typeof document.activeElement.blur === 'function') {
					  document.activeElement.blur();
					}
				`);
				return true;
			}else{
				return false;
			}
		} catch (error) {
			throw new Error(`Failed to focus element '${selector}': ${error.message}`);
		}
	};//Tested
	
	//-----------------------------------------------------------------------
	//Set HTML element value by selector
	aaWebDriveContext.select=async function(selector,...values){
		//TODO: use sendCommand with WebDrive command, if selector starts with "(" use document.evaluate select as XPath.
		try {
			if(typeof(selector)==="string") {
				// Use script.evaluate to select options in a <select> element
				const result = await this.callFunction(
					function (selector, ...values) {
						// Try querySelector first, fallback to XPath if it fails or selector starts with "("
						let element;
						try {
							if (selector.startsWith('(')) {
								// Selector starts with "(", treat as XPath
								const xpathResult = document.evaluate(selector, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
								element = xpathResult.singleNodeValue;
							} else {
								// Try querySelector first
								try {
									element = document.querySelector(selector);
								} catch (error) {
									// querySelector failed, try XPath
									try {
										const xpathResult = document.evaluate(selector, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
										element = xpathResult.singleNodeValue;
									} catch (xpathError) {
										throw new Error('Invalid selector: ' + selector);
									}
								}
							}
						} catch (error) {
							element = null;
						}
						
						if (!element) {
							throw new Error('Element not found: ' + selector);
						}
						
						if (element.tagName.toLowerCase() !== 'select') {
							throw new Error('Element is not a select element: ' + selector);
						}
						
						// Clear current selections
						for (let option of element.options) {
							option.selected = false;
						}
						
						// Select the specified values
						const selectedValues = [];
						for (let value of values) {
							let found = false;
							for (let option of element.options) {
								if (option.value === value || option.text === value) {
									option.selected = true;
									selectedValues.push(option.value);
									found = true;
									break;
								}
							}
							if (!found) {
								throw new Error('Option not found: ' + value);
							}
						}
						
						// Trigger change event
						element.dispatchEvent(new Event('change', { bubbles: true }));
						return selectedValues;
					},
					[selector, ...values]
				);
				return result;
			}else if(selector && selector.handle){
				const result = await this.callFunction(
					function (element, ...values) {
						// Try querySelector first, fallback to XPath if it fails or selector starts with "("
						if (!element) {
							throw new Error('Element not found');
						}
						if (element.tagName.toLowerCase() !== 'select') {
							throw new Error('Element is not a select element.');
						}
						// Clear current selections
						for (let option of element.options) {
							option.selected = false;
						}
						
						// Select the specified values
						const selectedValues = [];
						for (let value of values) {
							let found = false;
							for (let option of element.options) {
								if (option.value === value || option.text === value) {
									option.selected = true;
									selectedValues.push(option.value);
									found = true;
									break;
								}
							}
							if (!found) {
								throw new Error('Option not found: ' + value);
							}
						}
						
						// Trigger change event
						element.dispatchEvent(new Event('change', { bubbles: true }));
						return selectedValues;
					},
					[selector, ...values]
				);
				return result;
			}
		} catch (error) {
			throw new Error(`Failed to select options in element '${selector}': ${error.message}`);
		}
	};//TODO: Test this later
}

//***************************************************************************
// ======存取页面内容/Cookie======
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDriveContext.cookies = async function(urls) {
		//TODO: use sendCommand with WebDrive command
		try {
			let cookieParams = {};
			
			// If urls parameter is provided, use it to filter cookies
			if (urls) {
				if (typeof urls === 'string') {
					cookieParams.filter = { domain: new URL(urls).hostname };
				} else if (Array.isArray(urls)) {
					// For multiple URLs, we'll get cookies for all domains
					// WebDriver BiDi doesn't support multiple domain filters directly
					// so we'll get all cookies and filter client-side
					cookieParams = {};
				}
			}
			
			const result = await this.sendCommand('storage.getCookies', cookieParams);
			
			let cookies = result.cookies || [];
			
			// Client-side filtering if multiple URLs were provided
			if (urls && Array.isArray(urls)) {
				const domains = urls.map(url => new URL(url).hostname);
				cookies = cookies.filter(cookie =>
					domains.some(domain =>
						cookie.domain === domain ||
						cookie.domain === '.' + domain ||
						domain.endsWith(cookie.domain.replace(/^\./, ''))
					)
				);
			}
			
			// Transform WebDriver BiDi cookie format to Puppeteer-like format
			return cookies.map(cookie => ({
				name: cookie.name,
				value: cookie.value,
				domain: cookie.domain,
				path: cookie.path || '/',
				expires: cookie.expiry ? cookie.expiry : -1,
				size: (cookie.name + cookie.value).length,
				httpOnly: cookie.httpOnly || false,
				secure: cookie.secure || false,
				session: !cookie.expiry,
				sameSite: cookie.sameSite || 'Lax'
			}));
		} catch (error) {
			throw new Error(`Failed to get cookies: ${error.message}`);
		}
	};//TODO: Test this later:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.deleteCookie = async function(targets) {
		//TODO: use sendCommand with WebDrive command
		try {
			let cookieParams = {
				filter: {}
			};
			
			// Handle different target formats
			if (Array.isArray(targets)) {
				// Array of cookie objects with name and optionally url/domain
				for (let target of targets) {
					if (typeof target === 'string') {
						// String name - delete cookie by name
						cookieParams.filter.name = target;
					} else if (typeof target === 'object' && target.name) {
						// Object with name and optionally domain/url
						cookieParams.filter.name = target.name;
						
						if (target.url) {
							const urlObj = new URL(target.url);
							cookieParams.filter.domain = urlObj.hostname;
						} else if (target.domain) {
							cookieParams.filter.domain = target.domain;
						}
						
						if (target.path) {
							cookieParams.filter.path = target.path;
						}
					}
					
					// Delete each cookie individually
					await this.sendCommand('storage.deleteCookies', cookieParams);
				}
			} else if (typeof targets === 'string') {
				// Single cookie name
				cookieParams.filter.name = targets;
				await this.sendCommand('storage.deleteCookies', cookieParams);
			} else if (typeof targets === 'object' && targets.name) {
				// Single cookie object
				cookieParams.filter.name = targets.name;
				
				if (targets.url) {
					const urlObj = new URL(targets.url);
					cookieParams.filter.domain = urlObj.hostname;
				} else if (targets.domain) {
					cookieParams.filter.domain = targets.domain;
				}
				
				if (targets.path) {
					cookieParams.filter.path = targets.path;
				}
				
				await this.sendCommand('storage.deleteCookies', cookieParams);
			} else {
				throw new Error('Invalid targets parameter. Must be string, object with name property, or array of such values.');
			}
			
			return true;
		} catch (error) {
			throw new Error(`Failed to delete cookies: ${error.message}`);
		}
	};//TODO: Test this later:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.screencast=async function(opts){
		//TODO: Code this:
	};//TODO: Code this later:

	//-----------------------------------------------------------------------
	aaWebDriveContext.screenshot=async function(opts){
		//TODO: use sendCommand with WebDrive command, opts should be same as puppeteer's API
		let options = opts || {};

		// Set default options based on WebDriver BiDi specification
		let screenshotOptions = {
			context:this.context,
			origin: options.origin || 'viewport', // 'viewport' or 'document'
			format: {
				type: options.type || 'png' // 'png' or 'jpeg'
			},
			clip: null
		};

		// Handle quality option for JPEG
		if (options.type === 'jpeg' && options.quality !== undefined) {
			screenshotOptions.format.quality = Math.max(0, Math.min(1, options.quality));
		}

		// Handle clip option (specific area to capture)
		if (options.clip) {
			screenshotOptions.clip = {
				x: options.clip.x,
				y: options.clip.y,
				width: options.clip.width,
				height: options.clip.height
			};
		}

		// Handle fullPage option
		if (options.fullPage) {
			screenshotOptions.origin = 'document';
		}
		
		try {
			const result = await this.webDrive.sendCommand('browsingContext.captureScreenshot', screenshotOptions);
			
			// Return the base64 encoded image data
			if (options.encoding === 'base64') {
				return result.data;
			} else {
				// Convert base64 to buffer (default behavior)
				return Buffer.from(result.data, 'base64');
			}
		} catch (error) {
			throw new Error(`Failed to capture screenshot: ${error.message}`);
		}
	};//Tested, seg applied,
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.readArticle=async function(){
		let readPageArticle,article,html;
		readPageArticle=(await import("./CodeReadability.mjs")).default;
		article=await readPageArticle(this);
		if(!article || !article.content){
			let codeTag;
			let opts={mark:false,clean:true};
			codeTag=await ensureCodeLib(this);
			html= await this.callFunction((codeTag,node,opts) => {
				let codeLib = globalThis[codeTag];
				return codeLib.snapNodeHTML(node, opts);
			}, [codeTag,null,opts]);
		}else {
			html= `<div><a>${article.siteName}</a></div>\n<h1>${article.title}</h1>\n${article.content}`;
		}
		article=html2md(html);
		return article;
	};
}

//***************************************************************************
// ======页面元素访问======
//***************************************************************************
{
	//-----------------------------------------------------------------------
	//Return first HTML element handle find by selector. If selector starts with "(" it's indeed a XPath selector
	aaWebDriveContext.$ = async function(selector) {
		//TODO: use sendCommand with WebDrive command
		try {
			// Use script.evaluate to find the first element matching the selector
			const result = await this.sendCommand('script.evaluate', {
				expression: `
					(function() {
						let selector = ${JSON.stringify(selector)};
						let element;
						try {
							if (selector.startsWith('::-p-xpath')) {
								// XPath:
								selector=selector.substring('::-p-xpath'.length);
								const xpathResult = document.evaluate(selector, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
								element = xpathResult.singleNodeValue;
							}else if (selector.startsWith('(')) {
								// Selector starts with "(", treat as XPath
								const xpathResult = document.evaluate(selector, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
								element = xpathResult.singleNodeValue;
							} else {
								// Try querySelector first
								try {
									element = document.querySelector(selector);
								} catch (error) {
									// querySelector failed, try XPath
									try {
										const xpathResult = document.evaluate(selector, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
										element = xpathResult.singleNodeValue;
									} catch (xpathError) {
										throw new Error('Invalid selector: ' + selector);
									}
								}
							}
						} catch (error) {
							element = null;
						}
						
						return element;
					})()
				`,
				awaitPromise: false,
				resultOwnership: 'root'
			});
			
			// Return the element handle if found, otherwise null
			if (result.result && result.result.handle) {
				return result.result;
			}
			
			return null;
		} catch (error) {
			throw new Error(`Failed to find element '${selector}': ${error.message}`);
		}
	};//Tested

	//-----------------------------------------------------------------------
	//Return HTML element handle array find by selector. If selector starts with "(" it's indeed a XPath selector
	aaWebDriveContext.$$ = async function(selector) {
		//TODO: use sendCommand with WebDrive command
		try {
			// Use script.evaluate to find all elements matching the selector
			let result = await this.sendCommand('script.evaluate', {
				expression: `
			(function() {
				let selector = ${JSON.stringify(selector)};
				let elements = [];
				
				try {
					if (selector.startsWith('::-p-xpath')) {
						// XPath:
						selector=selector.substring('::-p-xpath'.length);
						const xpathResult = document.evaluate(selector, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
						for (let i = 0; i < xpathResult.snapshotLength; i++) {
							elements.push(xpathResult.snapshotItem(i));
						}
					}else if (selector.startsWith('(')) {
						// Selector starts with "(", treat as XPath
						const xpathResult = document.evaluate(selector, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
						for (let i = 0; i < xpathResult.snapshotLength; i++) {
							elements.push(xpathResult.snapshotItem(i));
						}
					} else {
						// Try querySelectorAll first
						try {
							elements = Array.from(document.querySelectorAll(selector));
						} catch (error) {
							// querySelectorAll failed, try XPath
							try {
								const xpathResult = document.evaluate(selector, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
								for (let i = 0; i < xpathResult.snapshotLength; i++) {
									elements.push(xpathResult.snapshotItem(i));
								}
							} catch (xpathError) {
								throw new Error('Invalid selector: ' + selector);
							}
						}
					}
				} catch (error) {
					elements = [];
				}
				return elements;
			})()
		`,
				awaitPromise: false,
				resultOwnership: 'root'
			});
			
			// Return the array of element handles
			if (result.result && result.result.value && Array.isArray(result.result.value)) {
				let list=[],i,n,elmt;
				n=result.result.value.length;
				for(i=0;i<n;i++){
					elmt=await this.sendCommand("script.callFunction",{
						"functionDeclaration": `function(arr){return arr[${i}];}`,
						"arguments": [
							result.result
						],
						"awaitPromise": true,
						"resultOwnership": "root"
					});
					list[i]=elmt.result;
				}
				await this.disown(result.result);
				return list;
			}
			return [];
		} catch (error) {
			throw new Error(`Failed to find elements '${selector}': ${error.message}`);
		}
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.$eval = async function(selector,pageFunction,...args) {
		//TODO: Code this:
	};//TODO: Code this later:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.$$eval = async function(selector) {
		//TODO: Code this:
	};//TODO: Code this later:
}

//***************************************************************************
// ======模拟用户操作======
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDriveContext.startAction=async function(){
		if(this.action && this.action.live){
			throw Error("Last action is not over");
		}
		this.action=await this.webDrive.startUserAction(this.context);
		return this.action;
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.endAction=async function(action){
		if(action!==this.action){
			return;
		}
		action.end();
		this.action=null;
	};
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.moveMouse=async function(x,y,opts){
		let smooth,action,actions;
		let orgX,orgY,objX,objY,offset;
		action=this.action;
		if(!action){
			await this.startAction();
		}
		
		orgX=this.pageMouseX;
		orgY=this.pageMouseY;
		objX = Math.floor(x);
		objY = Math.floor(y);
		
		smooth=opts?.smooth||false;
		if(smooth){
			let dx,dy,moveDis,moveTime,steps,i;
			const timeGap=20;
			actions=[];
			dx=objX-this.pageMouseX;
			dy=objY-this.pageMouseY;
			moveDis=Math.sqrt(dx*dx+dy*dy);
			moveTime=Math.floor(moveDis/1500*1000);
			steps=Math.floor(moveTime/timeGap);
			if(steps>0) {
				for (i = 0; i <= steps; i++) {
					const t = i / steps;
					const easeT = 0.5 * (1 - Math.cos(Math.PI * t));
					let x = orgX + (objX - orgX) * easeT;
					let y = orgY + (objY - orgY) * easeT;
					actions.push({
						type: "pointerMove",
						x: Math.round(x),
						y: Math.round(y),
						duration: Math.floor(timeGap * (Math.random() * 0.3 + 0.85))
					});
					if (Math.random() > 0.8) {
						actions.push({
							type: "pause",
							duration: Math.floor(timeGap * (Math.random() * 0.3 + 0.85) * 3)
						});
					}
				}
			}else{
				actions.push({ type: "pointerMove", x: objX, y: objY, duration: 0 });
			}
		}else{
			actions=[
				{ type: "pointerMove", x: objX, y: objY, duration: 0 },
			];
		}
		
		await this.webDrive.performActions(this.action,[
			{
				type: "pointer",
				id: "mouse1",
				parameters: { pointerType: "mouse" },
				actions: actions
			}
		]);
		
		this.pageMouseX=objX;
		this.pageMouseY=objY;
		
		if(!action){
			this.action.end();
			this.action=null;
		}
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.mouseDown=async function(button=0){
		let delay,action,actions;
		action=this.action;
		if(!action){
			await this.startAction();
		}
		actions = [
			{ type: "pointerDown", button },
		];
		
		await this.webDrive.performActions(this.action,[
			{
				type: "pointer",
				id: "mouse1",
				parameters: { pointerType: "mouse" },
				actions: actions
			}
		]);
		if(!action){
			this.action.end();
			this.action=null;
		}
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.mouseUp=async function(button=0){
		let delay,action,actions;
		action=this.action;
		if(!action){
			await this.startAction();
		}
		actions = [
			{ type: "pointerUp", button },
		];
		
		await this.webDrive.performActions(this.action,[
			{
				type: "pointer",
				id: "mouse1",
				parameters: { pointerType: "mouse" },
				actions: actions
			}
		]);
		if(!action){
			this.action.end();
			this.action=null;
		}
	};//Tested

	//-----------------------------------------------------------------------
	aaWebDriveContext.mouseClick=async function(opts){
		let delay,action,actions;
		action=this.action;
		if(!action){
			await this.startAction();
		}
		delay=opts?.delay;
		if(delay){
			actions = [
				{ type: "pointerDown", button: 0 },
				{ type: "pause",duration:delay},
				{ type: "pointerUp", button: 0 }
			];
		}else {
			actions = [
				{ type: "pointerDown", button: 0 },
				{ type: "pointerUp", button: 0 }
			];
		}
		
		await this.webDrive.performActions(this.action,[
			{
				type: "pointer",
				id: "mouse1",
				parameters: { pointerType: "mouse" },
				actions: actions
			}
		]);
		if(!action){
			this.action.end();
			this.action=null;
		}
	};//Tested

	//-----------------------------------------------------------------------
	aaWebDriveContext.click=async function(selector,opts){
		let handle,smooth,rect,action,actions;
		let orgX,orgY,objX,objY,offset;
		if(selector.handle){
			handle=selector;
		}else {
			handle = await this.$(selector);
		}
		if(!handle){
			return;
		}
		action=this.action;
		if(!action){
			await this.startAction();
		}
		rect=await this.callFunction(`(item)=>{
			const rect=item.getBoundingClientRect();
			if(!rect){
				return null;
			}
			return {
				x:rect.x, y:rect.y, width:rect.width, height: rect.height
			};
		}`,[handle]);
		
		await this.disown(handle);

		orgX=this.pageMouseX;
		orgY=this.pageMouseY;
		if(!rect){
			return;
		}
		offset=opts?.offset;
		if(offset){
			objX = Math.floor(rect.x + offset.x);
			objY = Math.floor(rect.y + offset.y);
		}else {
			objX = Math.floor(rect.x + rect.width * 0.5);
			objY = Math.floor(rect.y + rect.height * 0.5);
		}
		
		smooth=opts?.smooth||false;
		if(smooth){
			let dx,dy,moveDis,moveTime,steps,i;
			const timeGap=20;
			actions=[];
			dx=objX-this.pageMouseX;
			dy=objY-this.pageMouseY;
			moveDis=Math.sqrt(dx*dx+dy*dy);
			moveTime=Math.floor(moveDis/1500*1000);
			steps=Math.floor(moveTime/timeGap);
			if(steps>0) {
				for (i = 0; i <= steps; i++) {
					const t = i / steps;
					const easeT = 0.5 * (1 - Math.cos(Math.PI * t));
					let x = orgX + (objX - orgX) * easeT;
					let y = orgY + (objY - orgY) * easeT;
					actions.push({
						type: "pointerMove",
						x: Math.round(x),
						y: Math.round(y),
						duration: Math.floor(timeGap * (Math.random() * 0.3 + 0.85))
					});
					if (Math.random() > 0.8) {
						actions.push({
							type: "pause",
							duration: Math.floor(timeGap * (Math.random() * 0.3 + 0.85) * 3)
						});
					}
				}
			}else{
				actions.push({ type: "pointerMove", x: objX, y: objY, duration: 0 });
			}
			actions.push(...[
				{ type: "pointerDown", button: 0 },
				{
					type: "pause",
					duration: Math.floor(timeGap*(Math.random()*0.3+0.85)*3)
				},
				{ type: "pointerUp", button: 0 }
			]);
		}else{
			actions=[
				{ type: "pointerMove", x: objX, y: objY, duration: 0 },
				{ type: "pointerDown", button: 0 },
				{ type: "pointerUp", button: 0 }
			];
		}

		await this.webDrive.performActions(this.action,[
			{
				type: "pointer",
				id: "mouse1",
				parameters: { pointerType: "mouse" },
				actions: actions
			}
		]);
		
		this.pageMouseX=objX;
		this.pageMouseY=objY;

		if(!action){
			this.action.end();
			this.action=null;
		}
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.hover=async function(selector,opts){
		let handle,smooth,rect,action,actions;
		let orgX,orgY,objX,objY,offset;
		handle=await this.$(selector);
		if(!handle){
			return;
		}
		action=this.action;
		if(!action){
			await this.startAction();
		}
		rect=await this.callFunction(`(item)=>{
			const rect=item.getBoundingClientRect();
			if(!rect){
				return null;
			}
			return {
				x:rect.x, y:rect.y, width:rect.width, height: rect.height
			};
		}`,[handle]);
		
		orgX=this.pageMouseX;
		orgY=this.pageMouseY;
		if(!rect){
			return;
		}
		offset=opts?.offset;
		if(offset){
			objX = Math.floor(rect.x + offset.x);
			objY = Math.floor(rect.y + offset.y);
		}else {
			objX = Math.floor(rect.x + rect.width * 0.5);
			objY = Math.floor(rect.y + rect.height * 0.5);
		}
		
		smooth=opts?.smooth;
		if(smooth){
			let dx,dy,moveDis,moveTime,steps,i;
			const timeGap=20;
			actions=[];
			dx=objX-this.pageMouseX;
			dy=objY-this.pageMouseY;
			moveDis=Math.sqrt(dx*dx+dy*dy);
			moveTime=Math.floor(moveDis/1500*1000);
			steps=Math.floor(moveTime/timeGap);
			if(steps>0) {
				for (i = 0; i <= steps; i++) {
					const t = i / steps;
					const easeT = 0.5 * (1 - Math.cos(Math.PI * t));
					let x = orgX + (objX - orgX) * easeT;
					let y = orgY + (objY - orgY) * easeT;
					actions.push({
						type: "pointerMove",
						x: Math.round(x),
						y: Math.round(y),
						duration: Math.floor(timeGap * (Math.random() * 0.3 + 0.85))
					});
					if (Math.random() > 0.8) {
						actions.push({
							type: "pause",
							duration: Math.floor(timeGap * (Math.random() * 0.3 + 0.85) * 3)
						});
					}
				}
			}else{
				actions.push({ type: "pointerMove", x: objX, y: objY, duration: 0 });
			}
		}else{
			actions=[
				{ type: "pointerMove", x: objX, y: objY, duration: 0 },
			];
		}
		
		await this.webDrive.performActions(this.action,[
			{
				type: "pointer",
				id: "mouse1",
				parameters: { pointerType: "mouse" },
				actions: actions
			}
		]);
		
		this.pageMouseX=objX;
		this.pageMouseY=objY;
		
		if(!action && this.action){
			this.action.end();
			this.action=null;
		}
	};//TODO: Test this later
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.mouseWheel=async function(selector,opts){
		let delay,action,actions;
		let handle,x,y,deltaX,deltaY,steps;
		action=this.action;
		if(!action){
			await this.startAction();
		}
		x=opts?.x||0;
		y=opts?.y||0;
		deltaX=opts?.deltaX||0;
		deltaY=opts?.deltaY||100;
		if(selector){
			if(selector.handle){
				handle=selector;
			}else {
				handle = await this.$(selector);
			}
			
		}
		if(handle){
			const rect=await this.callFunction(function(item){
				const rect=item.getBoundingClientRect();
				if(!rect){
					return null;
				}
				return {
					x:rect.x, y:rect.y, width:rect.width, height: rect.height
				};
			},[handle]);
			x+=rect.x+rect.width*0.5;
			y+=rect.y+rect.height*0.5;
			await this.disown(handle);
		}else{
			const ss=await this.callFunction(function(){
				return {w:window.innerWidth,h:window.innerHeight}
			},[]);
			x+=ss.w*0.5;
			y+=ss.h*0.5;
		}
		x=Math.floor(x);
		y=Math.floor(y);
		await this.moveMouse(x,y,{smooth:opts?.smooth!==false});
		steps=opts?.steps;
		if(steps>1){
			let i;
			actions=[];
			for(i=0;i<steps;i++) {
				actions.push({
					type: "scroll",	x, y, deltaX:Math.floor(deltaX/steps), deltaY:Math.floor(deltaY/steps)
				},{ "type": "pause", "duration": 100 });
			}
		}else{
			actions = [
				{
					type: "scroll",
					x,y,deltaX,deltaY,duration:opts?.duration
				},
			];
		}
		await this.webDrive.performActions(this.action,[
			{
				type: "wheel",
				id: "wheel1",
				actions: actions
			}
		]);
		if(!action){
			this.action.end();
			this.action=null;
		}
	};//Tested

	//-----------------------------------------------------------------------
	aaWebDriveContext.tap=async function(selector,opts){
		//TODO: Code this:
	};//TODO: Code this later:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.type=async function(selector,text,opts){
		let handle,action,actions,delay,wrapEnter;
		delay=opts?.delay||0;
		wrapEnter=opts?.wrapEnter;
		if(selector){
			if(selector.handle){
				handle=selector.handle;
				await this.focus(handle);
			}else {
				handle = await this.$(selector);
				if(!handle){
					return;
				}
				await this.focus(handle);
				await this.disown(handle);
			}
		}
		action=this.action;
		if(!action){
			await this.startAction();
		}
		actions=[];
		for (let char of text) {
			if(wrapEnter && char==="\n"){
				actions.push({ type: "keyDown", value: KeyCodes.Shift });
				if(delay) {
					const pause = delay + (Math.random() - 0.5) * 0.2;
					actions.push({ type: "pause", duration: Math.max(10, Math.round(pause)) });
				}
				actions.push({ type: "keyDown", value: char });
				actions.push({ type: "keyUp", value: char });
				if(delay) {
					const pause = delay + (Math.random() - 0.5) * 0.2;
					actions.push({ type: "pause", duration: Math.max(10, Math.round(pause)) });
				}
				actions.push({ type: "keyUp", value: KeyCodes.Shift });
			}else {
				actions.push({ type: "keyDown", value: char });
				actions.push({ type: "keyUp", value: char });
			}
			
			// 随机插入 pause，模拟人类打字节奏
			if(delay) {
				const pause = delay + (Math.random() - 0.5) * 0.2;
				actions.push({ type: "pause", duration: Math.max(10, Math.round(pause)) });
			}
		}
		if(opts.postEnter){
			if(delay) {
				const pause = delay + (Math.random() - 0.5) * 0.2;
				actions.push({ type: "pause", duration: Math.max(10, Math.round(pause)) });
			}
			actions.push({ type: "keyDown", value: KeyCodes.Enter });
			actions.push({ type: "keyUp", value: KeyCodes.Enter });
		}
		await this.webDrive.performActions(this.action,[
			{
				type: "key",
				id: "keyboard1",
				actions: actions
			}
		]);
		if(!action && this.action){
			this.action.end();
			this.action=null;
		}
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.keyDown=async function(key,opts){
		let handle,action,actions,delay;
		key=KeyCodes[key]||key;
		action=this.action;
		if(!action){
			await this.startAction();
		}
		actions=[];
		actions.push({ type: "keyDown", value: key });
		await this.webDrive.performActions(this.action,[
			{
				type: "key",
				id: "keyboard1",
				actions: actions
			}
		]);
		if(!action && this.action){
			this.action.end();
			this.action=null;
		}
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.keyUp=async function(key,opts){
		let handle,action,actions,delay;
		key=KeyCodes[key]||key;
		action=this.action;
		if(!action){
			await this.startAction();
		}
		actions=[];
		actions.push({ type: "keyUp", value: key });
		await this.webDrive.performActions(this.action,[
			{
				type: "key",
				id: "keyboard1",
				actions: actions
			}
		]);
		if(!action && this.action){
			this.action.end();
			this.action=null;
		}
	};//Tested

	//-----------------------------------------------------------------------
	aaWebDriveContext.keySendChar=async function(key,opts){
		let action;
		action=this.action;
		if(!action){
			await this.startAction();
		}
		await this.type(null,key);
		if(!action && this.action){
			this.action.end();
			this.action=null;
		}
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.pressShortcut=async function(keys,opts){
		let key,i,n,action,actions;
		action=this.action;
		if(!action){
			await this.startAction();
		}
		
		if(typeof(keys)==="string"){
			keys=keys.split(">");
		}
		if(!Array.isArray(keys)){
			return false;
		}
		actions=[];
		n=keys.length;
		for(i=0;i<n;i++){
			key=keys[i];
			key=KeyCodes[key]||key;
			actions.push({ type: "keyDown", value: key });
			actions.push({ type: "pause", duration: Math.max(10, Math.round(30)) });
		}
		for(i=n-1;i>=0;i--){
			key=keys[i];
			key=KeyCodes[key]||key;
			actions.push({ type: "keyUp", value: key });
			actions.push({ type: "pause", duration: Math.max(10, Math.round(30)) });
		}
		await this.webDrive.performActions(this.action,[
			{
				type: "key",
				id: "keyboard1",
				actions: actions
			}
		]);
		if(!action && this.action){
			this.action.end();
			this.action=null;
		}
		return true;
	};
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.pasteText=async function(text,opts){
		let action,firstKey;
		action=this.action;
		if(!action){
			await this.startAction();
		}
		const isMac = process.platform === 'darwin';
		if(opts?.replace){
			await this.clearInputByKey();
		}
		firstKey=isMac?KeyCodes.Meta:KeyCodes.Control;
		await clipboardy.write(text);
		await this.keyDown(firstKey);
		await sleep(20);
		await this.keyDown("v");
		await sleep(10);
		await this.keyUp("v");
		await sleep(20);
		await this.keyUp(firstKey);
		if(!action && this.action){
			this.action.end();
			this.action=null;
		}
		await sleep(10);
	};//Tested.
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.clearInputByKey=async function(opts){
		let action,firstKey;
		action=this.action;
		if(!action){
			await this.startAction();
		}
		const isMac = process.platform === 'darwin';
		firstKey=isMac?KeyCodes.Meta:KeyCodes.Control;
		await this.keyDown(firstKey);
		await sleep(20);
		await this.keyDown("a");
		await sleep(10);
		await this.keyUp("a");
		await sleep(20);
		await this.keyUp(firstKey);
		await sleep(20);
		await this.keyDown(KeyCodes.Backspace);
		await sleep(10);
		await this.keyUp(KeyCodes.Backspace);
		if(!action && this.action){
			this.action.end();
			this.action=null;
		}
		await sleep(10);
	};//Tested.
}

//***************************************************************************
// ======订阅事件======
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDriveContext.subscribe=async function(events) {
		events.forEach((event) => {
			if(this.subscribes[event]>0){
				this.subscribes[event]+=1;
			}else{
				this.subscribes[event]=1;
			}
		});
		return this.sendCommand('session.subscribe', {
			events,
			contexts: [this.context]
		});
	};//TODO: Test this:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.unsubscribe=async function(events) {
		let evts=[];
		events.forEach((event) => {
			if(this.subscribes[event]>0){
				this.subscribes[event]-=1;
				if(this.subscribes[event]===0){
					evts.push(event);
				}
			}
		});
		if(evts.length>0) {
			return this.sendCommand('session.unsubscribe', {
				events,
				contexts: [this.context]
			});
		}
	};//TODO: Test this:
}

//***************************************************************************
// ======等待事件发生======
//***************************************************************************
{
	//-----------------------------------------------------------------------
	aaWebDriveContext.waitForSelector=async function(selector,opts){
		let pms,checker,timer,timeout,callback,callerror,call;
		
		timeout=opts?.timeout||0;
		
		pms=new Promise((resolve,reject)=>{
			callback=resolve;
			callerror=reject;
		});
		
		checker=setInterval(async ()=>{
			let result;
			result=await this.$(selector);
			if(result){
				call=callback;
				clearInterval(checker);
				if(timer){
					clearTimeout(timer);
				}
				if(call){
					callback=null;
					callerror=null;
					call(result);
				}else{
					await this.disown(result);
				}
			}
		},100);
		if(timeout>0){
			timer=setTimeout(()=>{
				let call;
				call=callback;
				clearInterval(checker);
				if(call){
					callback=null;
					callerror=null;
					call(null);
				}
			},timeout);
		}
		return pms;
	};//TODO: Test this:

	//-----------------------------------------------------------------------
	aaWebDriveContext.waitForNavigation=async function(opts){
		let pms,method,naviCallback,naviErrorCallback,historyCallback,timeout,callback,callerror,timer;
		pms=new Promise((resolve,reject)=>{
			callback=resolve;
			callerror=reject;
		});
		timeout=opts?.timeout||0;
		naviCallback=(event)=>{
			let call;
			if(event.context===this.context){
				this.webDrive.off(method,naviCallback);
				this.webDrive.off("browsingContext.NavigationFailed",naviErrorCallback);
				call=callback;
				if(call){
					if(timer){
						clearTimeout(timer);
					}
					callback=null;
					callerror=null;
					call(event.url);
				}
			}
		};
		naviErrorCallback=(event)=>{
			let call;
			if(event.context===this.context){
				this.webDrive.off(method,naviCallback);
				this.webDrive.off("browsingContext.navigationFailed",naviErrorCallback);
				call=callerror;
				if(call){
					if(timer){
						clearTimeout(timer);
					}
					callback=null;
					callerror=null;
					call(event.url);
				}
			}
		};
		historyCallback=async (event)=>{
			let call;
			if(event.context===this.context){
				this.webDrive.off("browsingContext.historyUpdated",naviErrorCallback);
				await sleep(300);
				this.webDrive.off(method,naviCallback);
				this.webDrive.off("browsingContext.navigationFailed",naviErrorCallback);
				call=callback;
				if(call){
					if(timer){
						clearTimeout(timer);
					}
					callback=null;
					callerror=null;
					call(event.url);
				}
			}
		}
		method="browsingContext."+(opts?.method||"load");
		this.webDrive.on(method,naviCallback);
		this.webDrive.on("browsingContext.navigationFailed",naviErrorCallback);
		this.webDrive.on("browsingContext.historyUpdated",historyCallback);
		
		if(timeout>0){
			timer=setTimeout(()=>{
				let call;
				call=callerror;
				if(call){
					this.webDrive.off(method,naviCallback);
					callback=null;
					callerror=null;
					call("Timeout");
				}
			},timeout);
		}
		return pms;
	};//Tested, seg applied
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.waitForNewPage=async function(opts){
		let webDrive,callback,callerror,timer,waitNavi,anyPage;
		let waitFunc=async (message)=>{
			let pages,context,call,page;
			context=message.context;
			if(anyPage || message.parent===this.context || message.originalOpener===this.context) {
				pages = await webDrive.getPages();
				page = pages.find((page) => {return page.context === context});
				if (page) {
					call = callback;
					if (call) {
						webDrive.off("browsingContext.contextCreated", waitFunc);
						callback = callerror = null;
						if(waitNavi) {
							await page.waitForNavigation();
						}
						call(page);
					}
				}
			}
		}
		anyPage=opts?.anyPage;
		waitNavi=opts?.waitNavi!==false;
		webDrive=this.webDrive;
		return new Promise((resolve,reject)=>{
			let timeout;
			callback=resolve;
			callerror=reject;
			timeout=opts?.timeout;
			webDrive.on("browsingContext.contextCreated",waitFunc);
			if(timeout>0){
				timer=setTimeout(()=>{
					let call;
					timer=null;
					call=callback;
					if(call){
						webDrive.off("browsingContext.contextCreated",waitFunc);
						callback=null;
						callerror=null;
						call(null);
					}
				})
			}
		});
	};//TODO: Code this:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.waitForNetworkIdle=async function(opts){
		let timeout,idleTime,concurrency,func;
		timeout=opts?.timeout||0;
		idleTime=opts?.idleTime||500;
		concurrency=opts?.concurrency||0;
		func=function (threshold = 500, maxInflight = 0,timeout) {
			return new Promise((resolve,reject) => {
				let lastActivity = Date.now();
				let orgTime=lastActivity;
				const interval = setInterval(() => {
					let now=Date.now();
					let entries = performance.getEntriesByType("resource");
					let inflight = entries.filter((e) => {
						return (!e.responseEnd);// || (now-(e.responseEnd+orgTime) < threshold);
					});
					if (inflight.length <= maxInflight && ((now - orgTime) > threshold)) {
						clearInterval(interval);
						resolve(true);
					} else if(timeout>0 && (now-orgTime>timeout)){
						reject(Error("Timeout"));
					}else{
						lastActivity = Date.now();
					}
				}, 100);
			});
		};
		await this.callFunction(func,[idleTime,concurrency,timeout]);
	};//Tested, seg applied
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.waitForDevicePrompt=async function(opts){
		//TODO: Code this:
		//WebDriveBidi not support for this.
	};//WebDriveBidi not support for this.
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.waitForDialog=async function(opts){
		let pms,waitFunc,callback,callerror,timer;
		waitFunc=(message)=>{
			let call;
			if(message.context!==this.context){
				return;
			}
			if(timer){
				clearTimeout(timer);
			}
			this.webDrive.off("browsingContext.userPromptOpened",waitFunc);
			call=callback;
			if(call){
				callback=null;
				callerror=null;
				call({
					type:message.type,
					message:message.message,
					accept:async (content)=>{
						await this.webDrive.sendCommand("browsingContext.handleUserPrompt",{
							context:this.context,
							accept:true,
							userText:content
						});
					},
					reject:async()=>{
						await this.webDrive.sendCommand("browsingContext.handleUserPrompt",{
							context:this.context,
							accept:false,
						});
					}
				});
			}
		}
		return new Promise((resolve,reject)=>{
			let timeout;
			callback=resolve;
			callerror=reject;
			timeout=opts?.timeout;
			this.webDrive.on("browsingContext.userPromptOpened",waitFunc);
			if(timeout>0){
				timer=setTimeout(()=>{
					let call;
					timer=null;
					call=callback;
					if(call){
						callback=null;
						callerror=null;
						call(null);
					}
				})
			}
		});
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.waitForFileChooser=async function(opts){
		let pms,fileChooser,timeout,callback,callerror,options;
		pms=new Promise((resolve,reject)=>{
			callback=resolve;
			callerror=reject;
		});
		timeout=opts?.timeout||0;
		if(timeout>0){
			options={timeout};
		}else{
			options={};
		}
		
		let codes=`(async() => {
		  let callback,callerror,input;
		  const originalClick = HTMLInputElement.prototype.click;
		  const pms=new Promise((resolve,reject)=>{
		    callback=resolve;
		    callerror=reject;
		  });
		  HTMLInputElement.prototype.click = function (...args) {
			if (this.type === "file") {
			  const info = {
				type: "file-input-clicked",
				id: this.id || null,
				outerHTML: this.outerHTML,
				timestamp: Date.now(),
			  };
			  callback(this);
			  return;
			}
			return originalClick.apply(this, args);
		  };
  		  input=await pms;
  		  HTMLInputElement.prototype.click=originalClick;
  		  return input;
		})();`
		this.evaluateHandle(codes,options).then((inputHandle)=> {
			let call;
			call=callback;
			if(call) {
				callback=null;
				callerror=null;
				if (inputHandle) {
					fileChooser = {
						type:"file",
						message:"",
						inputHandle: inputHandle,
						accept: async (files) => {
							let path,i,n,res;
							if(!Array.isArray(files)){
								files=[files];
							}
							n=files.length;
							for(i=0;i<n;i++){
								path=files[i];
								if(path.startsWith("hub://")){
									if(this.webDrive.agentNode){
										res=await this.webDrive.agentNode.callHub("AhFilePath",{fileName:path.substring(6)});
										if(res.code===200){
											files[i]=res.path;
										}
									}
								}
							}
							await this.webDrive.sendCommand("input.setFiles",{
								context:this.context,
								"element":inputHandle,
								"files":files
							});
							await this.disown(inputHandle);
						},
						reject: async () => {
							await this.disown(inputHandle);
						}
					};
					call(fileChooser);
				}else{
					call(null);
				}
			}
		});
		return await pms;
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.waitForDownloadBegin=async function(opts){
		let pms,waitFunc,callback,callerror,timer;
		waitFunc=(message)=>{
			let call;
			/*if(message.context!==this.context){
				return;
			}*/
			if(timer){
				clearTimeout(timer);
			}
			this.webDrive.off("downloads.downloadStarted",waitFunc);
			call=callback;
			if(call){
				callback=null;
				callerror=null;
				call({
					suggestedFilename:message.suggestedFilename,
					file:message.file,
					url:message.url,
				});
			}
		}
		return new Promise((resolve,reject)=>{
			let timeout;
			callback=resolve;
			callerror=reject;
			timeout=opts?.timeout;
			this.webDrive.on("downloads.downloadStarted",waitFunc);
			if(timeout>0){
				timer=setTimeout(()=>{
					let call;
					timer=null;
					call=callback;
					if(call){
						callback=null;
						callerror=null;
						call(null);
					}
				})
			}
		});
	};//TODO: Test this
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.waitForDownloadEnd=async function(opts){
		let pms,waitFunc,callback,callerror,timer;
		waitFunc=(message)=>{
			let call;
			/*if(message.context!==this.context){
				return;
			}*/
			if(timer){
				clearTimeout(timer);
			}
			
			this.webDrive.off("downloads.downloadFinished",waitFunc);
			//this.webDrive.off("browsingContext.downloadEnd",waitFunc);
			call=callback;
			if(call){
				callback=null;
				callerror=null;
				call({
					status:message.status,
					filepath:message.filepath,
					url:message.url,
				});
			}
		}
		return new Promise((resolve,reject)=>{
			let timeout;
			callback=resolve;
			callerror=reject;
			timeout=opts?.timeout;
			this.webDrive.on("downloads.downloadFinished",waitFunc);
			//this.webDrive.on("browsingContext.downloadEnd",waitFunc);
			if(timeout>0){
				timer=setTimeout(()=>{
					let call;
					timer=null;
					call=callback;
					if(call){
						callback=null;
						callerror=null;
						call(null);
					}
				})
			}
		});
	};//TODO: Test this
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.waitForFrame=async function(url,opts){
		let pms,checker,timer,timeout,callback,callerror,call;
		
		timeout=opts?.timeout||0;
		
		pms=new Promise((resolve,reject)=>{
			callback=resolve;
			callerror=reject;
		});

		checker=setInterval(async ()=>{
			let frames= await this.frames(true);
			for(let frame of frames){
				if(((url instanceof Function)&&url(frame.url))||url===frame.url){
					if(url(frame.url)){
						call=callback;
						clearInterval(checker);
						if(timer){
							clearTimeout(timer);
						}
						if(call){
							callback=null;
							callerror=null;
							call();
						}
					}
				}
			}
			
		},100);
		if(timeout>0){
			timer=setTimeout(()=>{
				let call;
				call=callerror;
				clearInterval(checker);
				if(call){
					callback=null;
					callerror=null;
					call("Timeout");
				}
			},timeout);
		}
		await pms;
	};//TODO: Test this:

	//-----------------------------------------------------------------------
	aaWebDriveContext.waitForFunction=async function(pageFunction,opts,...args){
		let pms,checker,timer,timeout,callback,callerror,call,interval;
		
		timeout=opts?.timeout||0;
		interval=opts?.interval||200;
		
		pms=new Promise((resolve,reject)=>{
			callback=resolve;
			callerror=reject;
		});
		
		checker=setInterval(async ()=>{
			let result;
			try {
				result = await this.callFunction(pageFunction, args);
				if (result) {
					call = callback;
					clearInterval(checker);
					if (timer) {
						clearTimeout(timer);
					}
					if (call) {
						callback = null;
						callerror = null;
						call(result);
					} else {
						if (result.handle) {
							try {
								await this.disown(result);
							} catch (err) {
							}
						}
					}
				}
			}catch(err){
				//Do thing, we just try keeping calling it
			}
		},interval);
		if(timeout>0){
			timer=setTimeout(()=>{
				let call;
				call=callerror;
				clearInterval(checker);
				if(call){
					callback=null;
					callerror=null;
					call("Timeout");
				}
			},timeout);
		}
		return await pms;
	};//Tested
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.waitForRequest=async function(url,opts){
	};//TODO: Code this later:
	
	//-----------------------------------------------------------------------
	aaWebDriveContext.waitForResponse=async function(url,opts){
	};//TODO: Code this later:
}

export default AaWebDriveContext;
export {AaWebDriveContext};

