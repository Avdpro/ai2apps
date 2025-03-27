//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1IHCKTECK0MoreImports*/
/*}#1IHCKTECK0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"url":{
			"name":"url","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"要读取的页面URL",
		},
		"query":{
			"name":"query","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"要从页面中获得的信息",
		},
		"format":{
			"name":"format","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"如果没有query，要提取内容的方式，可以选择: \"html\", \"markdown\"，默认提取html。",
		}
	},
	/*#{1IHCKTECK0ArgsView*/
	/*}#1IHCKTECK0ArgsView*/
};

/*#{1IHCKTECK0StartDoc*/
/*}#1IHCKTECK0StartDoc*/
//----------------------------------------------------------------------------
let RpaReadPage=async function(session){
	let url,query,format;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,StartRpa,RpaError,OpenBrowser,OpenPage,ReadContent,TryCatch,Error,CheckQuery,PlainResult,CallLlm,QueryResult,ClosePage,CloseBrowser;
	let pageContent="";
	
	/*#{1IHCKTECK0LocalVals*/
	/*}#1IHCKTECK0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			url=input.url;
			query=input.query;
			format=input.format;
		}else{
			url=undefined;
			query=undefined;
			format=undefined;
		}
		/*#{1IHCKTECK0ParseArgs*/
		/*}#1IHCKTECK0ParseArgs*/
	}
	
	/*#{1IHCKTECK0PreContext*/
	/*}#1IHCKTECK0PreContext*/
	context={};
	/*#{1IHCKTECK0PostContext*/
	/*}#1IHCKTECK0PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IHG4F0UN0
		let result=input;
		let missing=false;
		if(url===undefined || url==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:StartRpa,result:(result),preSeg:"1IHG4F0UN0",outlet:"1IHG4F0UN1"};
	};
	FixArgs.jaxId="1IHG4F0UN0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["StartRpa"]=StartRpa=async function(input){//:1ILSLB8D20
		let result=true;
		let aiQuery=true;
		try{
			context.webRpa=new WebRpa(session);
			aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1ILSLB8D20"));
		}catch(err){
			return {seg:RpaError,result:(err),preSeg:"1ILSLB8D20",outlet:"1ILSLGPJ90",catchSeg:RpaError,catchlet:"1ILSLGPJ90"};
		}
		return {seg:TryCatch,result:(result),preSeg:"1ILSLB8D20",outlet:"1ILSLGPJ91"};
	};
	StartRpa.jaxId="1ILSLB8D20"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["RpaError"]=RpaError=async function(input){//:1ILSLCH6O0
		let result=input
		/*#{1ILSLCH6O0Code*/
		result={result:"Failed",content:"Current AI2Apps evironment missing Web-RPA feature."};
		/*}#1ILSLCH6O0Code*/
		return {result:result};
	};
	RpaError.jaxId="1ILSLCH6O0"
	RpaError.url="RpaError@"+agentURL
	
	segs["OpenBrowser"]=OpenBrowser=async function(input){//:1ILSLD60H0
		let result=true;
		let browser=null;
		let headless=false;
		let devtools=false;
		let dataDir=true;
		let alias="RPAHOME";
		let options={headless,devtools,autoDataDir:dataDir};
		context.rpaBrowser=browser=await context.webRpa.openBrowser(alias,options);
		context.rpaHostPage=browser.hostPage;
		return {seg:OpenPage,result:(result),preSeg:"1ILSLD60H0",outlet:"1ILSLGPJ93"};
	};
	OpenBrowser.jaxId="1ILSLD60H0"
	OpenBrowser.url="OpenBrowser@"+agentURL
	
	segs["OpenPage"]=OpenPage=async function(input){//:1ILSLDR8V0
		let pageVal="aaPage";
		let $url=url;
		let $waitBefore=0;
		let $waitAfter=0;
		let $width=800;
		let $height=600;
		let $userAgent="";
		let page=null;
		$waitBefore && (await sleep($waitBefore));
		context[pageVal]=page=await context.rpaBrowser.newPage();
		($width && $height) && (await page.setViewport({width:$width,height:$height}));
		$userAgent && (await page.setUserAgent($userAgent));
		await page.goto($url);
		$waitAfter && (await sleep($waitAfter));
		return {seg:ReadContent,result:(page),preSeg:"1ILSLDR8V0",outlet:"1ILSLGPJ94"};
	};
	OpenPage.jaxId="1ILSLDR8V0"
	OpenPage.url="OpenPage@"+agentURL
	
	segs["ReadContent"]=ReadContent=async function(input){//:1ILSLEUOT0
		let result=null;
		let pageVal="aaPage";
		let $node=null;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $target=format==="markdown"?"article":"cleanHTML";
		$waitBefore && (await sleep($waitBefore));
		/*#{1ILSLEUOT0PreCodes*/
		/*}#1ILSLEUOT0PreCodes*/
		switch($target){
			case "cleanHTML":{
				result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:true,...$options});
				break;
			}
			case "html":{
				result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:false,...$options});
				break;
			}
			case "view":{
				result=await context.webRpa.readNodeView(page,$node,{removeHidden:false,...$options});
				break;
			}
			case "text":{
				result=await context.webRpa.readNodeText(page,$node,{removeHidden:false,...$options});
				break;
			}
			case "article":{
				result=await context.webRpa.readArticle(page,$node,{removeHidden:false,...$options});
				break;
			}
		}
		$waitAfter && (await sleep($waitAfter))
		/*#{1ILSLEUOT0PostCodes*/
		pageContent=result;
		/*}#1ILSLEUOT0PostCodes*/
		return {seg:ClosePage,result:(result),preSeg:"1ILSLEUOT0",outlet:"1ILSLGPJ95"};
	};
	ReadContent.jaxId="1ILSLEUOT0"
	ReadContent.url="ReadContent@"+agentURL
	
	segs["TryCatch"]=TryCatch=async function(input){//:1ILSLHPFN0
		let result=input;
		/*#{1ILSLHPFN0Code*/
		false
		/*}#1ILSLHPFN0Code*/
		return {seg:OpenBrowser,result:(result),preSeg:"1ILSLHPFN0",outlet:"1ILSM3Q480",catchSeg:Error,catchlet:"1ILSM3Q481"};
	};
	TryCatch.jaxId="1ILSLHPFN0"
	TryCatch.url="TryCatch@"+agentURL
	
	segs["Error"]=Error=async function(input){//:1ILSLIQ680
		let result=input
		/*#{1ILSLIQ680Code*/
		result={result:"Failed",content:`读取网页内容失败：${input}`};
		/*}#1ILSLIQ680Code*/
		return {result:result};
	};
	Error.jaxId="1ILSLIQ680"
	Error.url="Error@"+agentURL
	
	segs["CheckQuery"]=CheckQuery=async function(input){//:1ILSLJSP30
		let result=input;
		if(!!query){
			return {seg:CallLlm,result:(input),preSeg:"1ILSLJSP30",outlet:"1ILSM3Q483"};
		}
		return {seg:PlainResult,result:(result),preSeg:"1ILSLJSP30",outlet:"1ILSM3Q484"};
	};
	CheckQuery.jaxId="1ILSLJSP30"
	CheckQuery.url="CheckQuery@"+agentURL
	
	segs["PlainResult"]=PlainResult=async function(input){//:1ILSLKFP00
		let result=input
		/*#{1ILSLKFP00Code*/
		result={result:"Finish",content:pageContent};
		/*}#1ILSLKFP00Code*/
		return {result:result};
	};
	PlainResult.jaxId="1ILSLKFP00"
	PlainResult.url="PlainResult@"+agentURL
	
	segs["CallLlm"]=CallLlm=async function(input){//:1ILSLLRI70
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o-mini",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=CallLlm.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"`### 角色\n你是一个读取网页内容，回答用户问题的AI\n\n---\n### 网页网址：\n${url}\n\n---\n### 读取到的网页内容是：  \n${pageContent}\n\n---\n### 要从网页中提取的信息或回答的问题：\n${query}\n\n`"},
		];
		prompt="请分析网页内容做出回复";
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("CallLlm@"+agentURL,opts,messages,true);
		return {seg:QueryResult,result:(result),preSeg:"1ILSLLRI70",outlet:"1ILSM3Q486"};
	};
	CallLlm.jaxId="1ILSLLRI70"
	CallLlm.url="CallLlm@"+agentURL
	
	segs["QueryResult"]=QueryResult=async function(input){//:1ILSLMEMO0
		let result=input
		/*#{1ILSLMEMO0Code*/
		result={result:"Finish",content:input}
		/*}#1ILSLMEMO0Code*/
		return {result:result};
	};
	QueryResult.jaxId="1ILSLMEMO0"
	QueryResult.url="QueryResult@"+agentURL
	
	segs["ClosePage"]=ClosePage=async function(input){//:1IN5QV0PN0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		await page.close();
		context[pageVal]=null;
		waitAfter && (await sleep(waitAfter))
		return {seg:CloseBrowser,result:(result),preSeg:"1IN5QV0PN0",outlet:"1IN5QVQEL1"};
	};
	ClosePage.jaxId="1IN5QV0PN0"
	ClosePage.url="ClosePage@"+agentURL
	
	segs["CloseBrowser"]=CloseBrowser=async function(input){//:1IN5QTUK80
		let result=input;
		let browser=context.rpaBrowser;
		if(browser){
			await context.webRpa.closeBrowser(browser);
		}
		context.rpaBrowser=null;
		context.rpaHostPage=null;
		return {seg:CheckQuery,result:(result),preSeg:"1IN5QTUK80",outlet:"1IN5QVQEL0"};
	};
	CloseBrowser.jaxId="1IN5QTUK80"
	CloseBrowser.url="CloseBrowser@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"RpaReadPage",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHCKTECK0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{url,query,format}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHCKTECK0PreEntry*/
			/*}#1IHCKTECK0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IHCKTECK0PostEntry*/
			/*}#1IHCKTECK0PostEntry*/
			return result;
		},
		/*#{1IHCKTECK0MoreAgentAttrs*/
		/*}#1IHCKTECK0MoreAgentAttrs*/
	};
	/*#{1IHCKTECK0PostAgent*/
	/*}#1IHCKTECK0PostAgent*/
	return agent;
};
/*#{1IHCKTECK0ExCodes*/
/*}#1IHCKTECK0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "RpaReadPage",
		description: "这是一个读取Web页面内容的工具/AI智能体。给出一个页面URL和想要提取的信息（例如：获取页面的InnerHTML，页面文章详细内容，针对页面内容的问题等），本工具会读取页面内容并回答。\n仅用于读取互联网上页面内容，请不要使用本工具读取本地磁盘上的文件内容。",
		parameters:{
			type: "object",
			properties:{
				url:{type:"string",description:"要读取的页面URL"},
				query:{type:"string",description:"要从页面中获得的信息"},
				format:{type:"string",description:"如果没有query，要提取内容的方式，可以选择: \\\"html\\\", \\\"markdown\\\"，默认提取html。",enum:["html","markdown"]}
			}
		}
	}
}];

//:Export Edit-AddOn:
const DocAIAgentExporter=VFACT?VFACT.classRegs.DocAIAgentExporter:null;
if(DocAIAgentExporter){
	const EditAttr=VFACT.classRegs.EditAttr;
	const EditAISeg=VFACT.classRegs.EditAISeg;
	const EditAISegOutlet=VFACT.classRegs.EditAISegOutlet;
	const SegObjShellAttr=EditAISeg.SegObjShellAttr;
	const SegOutletDef=EditAISegOutlet.SegOutletDef;
	const docAIAgentExporter=DocAIAgentExporter.prototype;
	const packExtraCodes=docAIAgentExporter.packExtraCodes;
	const packResult=docAIAgentExporter.packResult;
	const varNameRegex = /^[a-zA-Z_$][a-zA-Z0-9_$]*$/;
	
	EditAISeg.regDef({
		name:"RpaReadPage",showName:"RpaReadPage",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"url":{name:"url",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"query":{name:"query",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"format":{name:"format",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","url","query","format","codes","desc"],
		desc:"这是一个读取Web页面内容的工具/AI智能体。给出一个页面URL和想要提取的信息（例如：获取页面的InnerHTML，页面文章详细内容，针对页面内容的问题等），本工具会读取页面内容并回答。\n仅用于读取互联网上页面内容，请不要使用本工具读取本地磁盘上的文件内容。"
	});
	
	DocAIAgentExporter.segTypeExporters["RpaReadPage"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['url']=");this.genAttrStatement(seg.getAttr("url"));coder.packText(";");coder.newLine();
			coder.packText("args['query']=");this.genAttrStatement(seg.getAttr("query"));coder.packText(";");coder.newLine();
			coder.packText("args['format']=");this.genAttrStatement(seg.getAttr("format"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AgentBuilder/ai/RpaReadPage.js",args,false);`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
			this.packUpdateContext(coder,seg);
			this.packUpdateGlobal(coder,seg);
			this.packResult(coder,seg,seg.outlet);
		}
		coder.indentLess();coder.maybeNewLine();
		coder.packText(`};`);coder.newLine();
		if(exportDebug){
			coder.packText(`${segName}.jaxId="${seg.jaxId}"`);coder.newLine();
		}
		coder.packText(`${segName}.url="${segName}@"+agentURL`);coder.newLine();
		coder.newLine();
	};
}
//#CodyExport<<<
/*#{1IHCKTECK0PostDoc*/
/*}#1IHCKTECK0PostDoc*/


export default RpaReadPage;
export{RpaReadPage,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHCKTECK0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHCKTECK1",
//			"attrs": {
//				"RpaReadPage": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHCKTECL2",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHCKTECL3",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHCKTECL4",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHCKTECL5",
//							"attrs": {}
//						},
//						"mockupOnly": "false",
//						"nullMockup": "false",
//						"exportClass": "false"
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1IHCKTECK2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHCKTECK3",
//			"attrs": {
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHG4ELHI0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要读取的页面URL",
//						"required": "true"
//					}
//				},
//				"query": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHG4ELHJ0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要从页面中获得的信息",
//						"required": "false"
//					}
//				},
//				"format": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ILSLAQ0P0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "如果没有query，要提取内容的方式，可以选择: \\\"html\\\", \\\"markdown\\\"，默认提取html。",
//						"required": "false",
//						"enum": {
//							"type": "array",
//							"def": "Array",
//							"attrs": [
//								{
//									"type": "auto",
//									"valText": "html"
//								},
//								{
//									"type": "auto",
//									"valText": "markdown"
//								}
//							]
//						}
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHCKTECK4",
//			"attrs": {
//				"pageContent": {
//					"type": "string",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IHCKTECL0",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHCKTECL1",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHG4F0UN0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "55",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IHG4F0UN1",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSLB8D20"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1ILSLB8D20",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "250",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSLGPJB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSLGPJB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSLGPJ91",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSLHPFN0"
//						},
//						"catchlet": {
//							"jaxId": "1ILSLGPJ90",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1ILSLGPJB2",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1ILSLGPJB3",
//									"attrs": {
//										"cast": ""
//									}
//								}
//							},
//							"linkedSeg": "1ILSLCH6O0"
//						},
//						"aiQuery": "true"
//					},
//					"icon": "start.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILSLCH6O0",
//					"attrs": {
//						"id": "RpaError",
//						"viewName": "",
//						"label": "",
//						"x": "475",
//						"y": "460",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1ILSLGPJB4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSLGPJB5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSLGPJ92",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenBrowser",
//					"jaxId": "1ILSLD60H0",
//					"attrs": {
//						"id": "OpenBrowser",
//						"viewName": "",
//						"label": "",
//						"x": "680",
//						"y": "305",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSLGPJB6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSLGPJB7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"alias": "RPAHOME",
//						"headless": "false",
//						"devtools": "false",
//						"dataDir": "true",
//						"outlet": {
//							"jaxId": "1ILSLGPJ93",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSLDR8V0"
//						},
//						"run": ""
//					},
//					"icon": "web.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1ILSLDR8V0",
//					"attrs": {
//						"id": "OpenPage",
//						"viewName": "",
//						"label": "",
//						"x": "920",
//						"y": "305",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSLGPJB8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSLGPJB9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "#url",
//						"vpWidth": "800",
//						"vpHeight": "600",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSLGPJ94",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSLEUOT0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1ILSLEUOT0",
//					"attrs": {
//						"id": "ReadContent",
//						"viewName": "",
//						"label": "",
//						"x": "1140",
//						"y": "305",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSLGPJB10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSLGPJB11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"target": "#format===\"markdown\"?\"article\":\"cleanHTML\"",
//						"node": "null",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSLGPJ95",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN5QV0PN0"
//						},
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1ILSLHPFN0",
//					"attrs": {
//						"id": "TryCatch",
//						"viewName": "",
//						"label": "",
//						"x": "475",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSM3Q4A0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSM3Q4A1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSM3Q480",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSLD60H0"
//						},
//						"catchlet": {
//							"jaxId": "1ILSM3Q481",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSLIQ680"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILSLIQ680",
//					"attrs": {
//						"id": "Error",
//						"viewName": "",
//						"label": "",
//						"x": "685",
//						"y": "415",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1ILSM3Q4A2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSM3Q4A3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSM3Q482",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILSLJSP30",
//					"attrs": {
//						"id": "CheckQuery",
//						"viewName": "",
//						"label": "",
//						"x": "1905",
//						"y": "305",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSM3Q4A4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSM3Q4A5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSM3Q484",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1ILSLKFP00"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSM3Q483",
//									"attrs": {
//										"id": "Query",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILSM3Q4A6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSM3Q4A7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!query"
//									},
//									"linkedSeg": "1ILSLLRI70"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILSLKFP00",
//					"attrs": {
//						"id": "PlainResult",
//						"viewName": "",
//						"label": "",
//						"x": "2135",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1ILSM3Q4A8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSM3Q4A9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSM3Q485",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1ILSLLRI70",
//					"attrs": {
//						"id": "CallLlm",
//						"viewName": "",
//						"label": "",
//						"x": "2135",
//						"y": "255",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSM3Q4A10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSM3Q4A11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o-mini",
//						"system": "`### 角色\n你是一个读取网页内容，回答用户问题的AI\n\n---\n### 网页网址：\n${url}\n\n---\n### 读取到的网页内容是：  \n${pageContent}\n\n---\n### 要从网页中提取的信息或回答的问题：\n${query}\n\n`",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "请分析网页内容做出回复",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1ILSM3Q486",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSLMEMO0"
//						},
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "No",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "text",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILSLMEMO0",
//					"attrs": {
//						"id": "QueryResult",
//						"viewName": "",
//						"label": "",
//						"x": "2340",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1ILSM3Q4A12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSM3Q4A13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSM3Q487",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaClosePage",
//					"jaxId": "1IN5QV0PN0",
//					"attrs": {
//						"id": "ClosePage",
//						"viewName": "",
//						"label": "",
//						"x": "1400",
//						"y": "305",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN5QVQER2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN5QVQER3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1IN5QVQEL1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN5QTUK80"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaCloseBrowser",
//					"jaxId": "1IN5QTUK80",
//					"attrs": {
//						"id": "CloseBrowser",
//						"viewName": "",
//						"label": "",
//						"x": "1640",
//						"y": "305",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN5QVQER0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN5QVQER1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IN5QVQEL0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSLJSP30"
//						}
//					},
//					"icon": "close.svg"
//				}
//			]
//		},
//		"desc": "这是一个读取Web页面内容的工具/AI智能体。给出一个页面URL和想要提取的信息（例如：获取页面的InnerHTML，页面文章详细内容，针对页面内容的问题等），本工具会读取页面内容并回答。\n仅用于读取互联网上页面内容，请不要使用本工具读取本地磁盘上的文件内容。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}