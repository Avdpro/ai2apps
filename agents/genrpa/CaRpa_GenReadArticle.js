//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JE5HC48A0MoreImports*/
/*}#1JE5HC48A0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"pageRef":{
			"name":"pageRef","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"url":{
			"name":"url","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"profile":{
			"name":"profile","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"read":{
			"name":"read","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JE5HC48A0ArgsView*/
	/*}#1JE5HC48A0ArgsView*/
};

/*#{1JE5HC48A0StartDoc*/
/*}#1JE5HC48A0StartDoc*/
//----------------------------------------------------------------------------
let CaRpa_GenReadArticle=async function(session){
	let pageRef,url,profile,read;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,Blocker,FastRead,CheckArticle,ReadHTML,AIRead,FinDone,FinFail,NeedInfo,GenInfo;
	/*#{1JE5HC48A0LocalVals*/
	/*}#1JE5HC48A0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			url=input.url;
			profile=input.profile;
			read=input.read;
		}else{
			pageRef=undefined;
			url=undefined;
			profile=undefined;
			read=undefined;
		}
		/*#{1JE5HC48A0ParseArgs*/
		/*}#1JE5HC48A0ParseArgs*/
	}
	
	/*#{1JE5HC48A0PreContext*/
	/*}#1JE5HC48A0PreContext*/
	context={
		url: "",
		title: "",
		html: "",
		article: "",
		/*#{1JE5HC48A5ExCtxAttrs*/
		/*}#1JE5HC48A5ExCtxAttrs*/
	};
	/*#{1JE5HC48A0PostContext*/
	/*}#1JE5HC48A0PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JES7AT6E0
		let result=true;
		let aiQuery=true;
		let $alias=profile;
		let $url=url;
		let $ref=pageRef;
		let $waitBefore=0;
		let $waitAfter=0;
		try{
			if($ref){
				let $page,$browser;
				let $pageVal="aaPage";
				$page=WebRpa.getPageByRef($ref);
				context.rpaBrowser=$browser=$page.webDrive;
				context[$pageVal]=$page;
				context.webRpa=$browser.aaWebRpa;
			}else{
				context.webRpa=session.webRpa || new WebRpa(session);
				session.webRpa=context.webRpa;
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JES7AT6E0"));
				if($alias){
					let $headless=false;
					let $devtools=false;
					let options={$headless:false,$devtools:false,autoDataDir:false};
					let $browser=null;
					context.rpaBrowser=$browser=await context.webRpa.openBrowser($alias,options);
					context.rpaHostPage=$browser.hostPage;
					if($url){
						let $page=null;
						let $pageVal="aaPage";
						let $opts={};
						context[$pageVal]=$page=await $browser.newPage();
						await $page.goto($url,{});
					}
				}
			}
			$waitAfter && (await sleep($waitAfter));
		}catch(error){
			throw error;
		}
		return {seg:Blocker,result:(result),preSeg:"1JES7AT6E0",outlet:"1JES7AT6F0"};
	};
	StartRpa.jaxId="1JES7AT6E0"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["Blocker"]=Blocker=async function(input){//:1JES7BJ6A0
		let result;
		let arg={"pageRef":pageRef,"blocker":{remove:true},"waitAfter":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenBlockers.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:ReadHTML,result:(result),preSeg:"1JES7BJ6A0",outlet:"1JES7D0V10"};
	};
	Blocker.jaxId="1JES7BJ6A0"
	Blocker.url="Blocker@"+agentURL
	
	segs["FastRead"]=FastRead=async function(input){//:1JES7DO0M0
		let result=null;
		let pageVal="aaPage";
		let $node=null;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $target="article";
		$waitBefore && (await sleep($waitBefore));
		try{
			switch($target){
				case "cleanHTML":{
					result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:true,...$options});
					break;
				}
				case "html":{
					result=await context.webRpa.getInnerHTML(page,$node);
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
		}catch(error){
			/*#{1JES7DO0M0ErrorCode*/
			/*}#1JES7DO0M0ErrorCode*/
			return {seg:AIRead,result:error,preSeg:"1JES7DO0M0",outlet:null};
		}
		context["article"]=result;
		return {seg:CheckArticle,result:(result),preSeg:"1JES7DO0M0",outlet:"1JES7FVV50"};
	};
	FastRead.jaxId="1JES7DO0M0"
	FastRead.url="FastRead@"+agentURL
	
	segs["CheckArticle"]=CheckArticle=async function(input){//:1JES7EEEF0
		let result=input;
		if(context.article && context.article.length>300){
			return {seg:NeedInfo,result:(input),preSeg:"1JES7EEEF0",outlet:"1JES7FVV51"};
		}
		return {seg:AIRead,result:(result),preSeg:"1JES7EEEF0",outlet:"1JES7FVV52"};
	};
	CheckArticle.jaxId="1JES7EEEF0"
	CheckArticle.url="CheckArticle@"+agentURL
	
	segs["ReadHTML"]=ReadHTML=async function(input){//:1JES7FG730
		let result=null;
		let pageVal="aaPage";
		let $node=null;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $target="cleanHTML";
		$waitBefore && (await sleep($waitBefore));
		/*#{1JES7FG730PreCodes*/
		context.url=await page.url();
		context.title=await page.title();
		/*}#1JES7FG730PreCodes*/
		try{
			switch($target){
				case "cleanHTML":{
					result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:true,...$options});
					break;
				}
				case "html":{
					result=await context.webRpa.getInnerHTML(page,$node);
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
		}catch(error){
			/*#{1JES7FG730ErrorCode*/
			/*}#1JES7FG730ErrorCode*/
			return {seg:FinFail,result:error,preSeg:"1JES7FG730",outlet:null};
		}
		/*#{1JES7FG730PostCodes*/
		/*}#1JES7FG730PostCodes*/
		context["html"]=result;
		return {seg:FastRead,result:(result),preSeg:"1JES7FG730",outlet:"1JES7FVV53"};
	};
	ReadHTML.jaxId="1JES7FG730"
	ReadHTML.url="ReadHTML@"+agentURL
	
	segs["AIRead"]=AIRead=async function(input){//:1JES7G6JA0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-5-mini";
		let $agent;
		let result;
		
		let opts={
			platform:$platform,
			mode:$model,
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=AIRead.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"【角色】\n你是一个从HTML页面中提取文章内容的AI\n【输入】\n对话输入包含经过清洗后的网页HTML代码。\n【分析】\n你分析HTML代码，确认这个网页是否包含可以提取的文章内容。\n- 如果包含文章内容，提取并以Markdown格式返回完整的文章。\n- 如果当前页面并不包含有意义的文章，比如当前为404页面，当前为文章列表页面等，返回提取文章失败的原因\n【输出】\n你必须用JSON格式返回，不要包含JSON以外的内容。\n【成功提取到文章的JSON属性】\n{\n\ttitle: string 文章标题文本\n\tauthor?: string 文章作者\n\tpublishTime?: Date-string 文章发布时间\n\tarticle: text in markdown Markdown格式的完整的文章内容。\n    summary: 不超过300字的总结文本\n    keywords: array<string> 文章内容的关键字\n}\n【未能成功提取文章的JSON属性】\n{\n\tarticle: null\n    reason: string 未能提取文章内容的原因\n}"},
		];
		prompt=context.pageHtml;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		if($agent){
			result=await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat});
		}else{
			result=await session.callSegLLM("AIRead@"+agentURL,opts,messages,true);
		}
		result=trimJSON(result);
		if(input==="Article"){
			return {seg:FinDone,result:(input),preSeg:"1JES7G6JA0",outlet:"1JES7MABG0"};
		}
		if(input==="NoArticle"){
			return {seg:FinFail,result:(input),preSeg:"1JES7G6JA0",outlet:"1JES7GOND0"};
		}
		return {result:result};
	};
	AIRead.jaxId="1JES7G6JA0"
	AIRead.url="AIRead@"+agentURL
	
	segs["FinDone"]=FinDone=async function(input){//:1JES7L9KV0
		let result=input
		try{
			/*#{1JES7L9KV0Code*/
			result={
				status:"Done",result:"Finish",
				url:context.url,
				title:input.title||context.title,
				author:input.author,
				publishTime:input.publishTime,
				html:context.html,
				article:context.article||input.article,
				summary:input.summary,
				keywords:input.keywords
			};
			/*}#1JES7L9KV0Code*/
		}catch(error){
			/*#{1JES7L9KV0ErrorCode*/
			/*}#1JES7L9KV0ErrorCode*/
		}
		return {result:result};
	};
	FinDone.jaxId="1JES7L9KV0"
	FinDone.url="FinDone@"+agentURL
	
	segs["FinFail"]=FinFail=async function(input){//:1JES7LTNG0
		let result=input
		try{
			/*#{1JES7LTNG0Code*/
			result={status:"Failed",result:"Failed",reason:input.reason||"提取文章内容失败"};
			/*}#1JES7LTNG0Code*/
		}catch(error){
			/*#{1JES7LTNG0ErrorCode*/
			/*}#1JES7LTNG0ErrorCode*/
		}
		return {result:result};
	};
	FinFail.jaxId="1JES7LTNG0"
	FinFail.url="FinFail@"+agentURL
	
	segs["NeedInfo"]=NeedInfo=async function(input){//:1JES8TMNJ0
		let result=input;
		if(read && read.detail){
			return {seg:GenInfo,result:(input),preSeg:"1JES8TMNJ0",outlet:"1JES90S2B0"};
		}
		return {seg:FinDone,result:(result),preSeg:"1JES8TMNJ0",outlet:"1JES90S2B1"};
	};
	NeedInfo.jaxId="1JES8TMNJ0"
	NeedInfo.url="NeedInfo@"+agentURL
	
	segs["GenInfo"]=GenInfo=async function(input){//:1JES8V2Q50
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-5-mini";
		let $agent;
		let result;
		
		let opts={
			platform:$platform,
			mode:$model,
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=GenInfo.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"【角色】\n你是一个从Markdown文章中文章细节内容的AI\n【输入】\n对话输入是文章的Markdown文档。\n【分析】\n你分析文章内容，提取标题、作者、发布时间、总结等文章相关细节内容。\n【输出】\n你必须用JSON格式返回，不要包含JSON以外的内容。\n【成功提取到文章的JSON属性】\n{\n\ttitle: string 文章标题文本\n\tauthor?: string 文章作者\n\tpublishTime?: Date-string 文章发布时间\n    summary: 不超过300字的总结文本\n    keywords: array<string> 文章内容的关键字\n}\n【未能成功识别文章的内容的JSON属性】\n{\n\ttitle: null\n\tsummary: null\n\tkeywords: null\n    reason: string 未能提取文章内容的原因\n}\n"},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=GenInfo.cheats[prompt]||GenInfo.cheats[input]||(chatMem && GenInfo.cheats[""+chatMem.length])||GenInfo.cheats[""];
		if(!result){
			if($agent){
				result=await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat});
			}else{
				result=await session.callSegLLM("GenInfo@"+agentURL,opts,messages,true);
			}
		}
		result=trimJSON(result);
		return {seg:FinDone,result:(result),preSeg:"1JES8V2Q50",outlet:"1JES90S2B2"};
	};
	GenInfo.jaxId="1JES8V2Q50"
	GenInfo.url="GenInfo@"+agentURL
	GenInfo.cheats={
		"":"{ \"title\": \"Omega’s Speedmaster Moonwatch Does a Reverse Panda\", \"summary\": \"Omega推出Speedmaster Moonwatch“reverse panda”新款，提供不锈钢与18K Moonshine黄金两种材质。特色为黑色双层漆面表盘透出白色计时小盘、黑色陶瓷测速圈（dot over 90）、经典42mm表壳及手动上链Cal.3861（Co‑Axial、硅游丝、Master Chronometer）机芯。整体更为精致且技术升级，钢款性价比高，黄金款价格昂贵（约US$10,400与US$49,300）。\", \"keywords\": [ \"Omega\", \"Speedmaster\", \"Moonwatch\", \"Reverse Panda\", \"Moonshine gold\", \"Stainless steel\", \"Black lacquer dial\", \"Layered dial\", \"Ceramic bezel\", \"Tachymeter\", \"Dot over 90\", \"Cal. 3861\", \"Master Co‑Axial\", \"Manual-wind\", \"42 mm\", \"50 m\", \"Price\" ] }"
	};
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CaRpa_GenReadArticle",
		url:agentURL,
		autoStart:true,
		jaxId:"1JE5HC48A0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,url,profile,read}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JE5HC48A0PreEntry*/
			/*}#1JE5HC48A0PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JE5HC48A0PostEntry*/
			/*}#1JE5HC48A0PostEntry*/
			return result;
		},
		/*#{1JE5HC48A0MoreAgentAttrs*/
		/*}#1JE5HC48A0MoreAgentAttrs*/
	};
	/*#{1JE5HC48A0PostAgent*/
	/*}#1JE5HC48A0PostAgent*/
	return agent;
};
/*#{1JE5HC48A0ExCodes*/
/*}#1JE5HC48A0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "CaRpa_GenReadArticle",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				url:{type:"auto",description:""},
				profile:{type:"auto",description:""},
				read:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true
}];
//#CodyExport<<<
/*#{1JE5HC48A0PostDoc*/
/*}#1JE5HC48A0PostDoc*/


export default CaRpa_GenReadArticle;
export{CaRpa_GenReadArticle,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JE5HC48A0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JE5HC48A1",
//			"attrs": {
//				"CaRpa_GenReadArticle": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JE5HC48A7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JE5HC48A8",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JE5HC48A9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JE5HC48A10",
//							"attrs": {}
//						},
//						"mockupOnly": "false",
//						"nullMockup": "false",
//						"exportClass": "false",
//						"superClass": ""
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1JE5HC48A2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JE5HC48A3",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JES9B0VR0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JES9B0VR1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"profile": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JES9B0VR2",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"read": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JES9B0VR3",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JE5HC48A4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JE5HC48A5",
//			"attrs": {
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JESBP1E20",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"title": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JESBP1E21",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"html": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JES9CL8J0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"article": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JES9CL8J1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1JE5HC48A6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JES7AT6E0",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "130",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JES7AT6E1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JES7AT6E2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"browser": "#profile",
//						"headless": "false",
//						"devtools": "false",
//						"url": "#url",
//						"valName": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JES7AT6F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JES7BJ6A0"
//						},
//						"catchlet": {
//							"jaxId": "1JES7AT6F1",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JES7AT6F2",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JES7AT6F3",
//									"attrs": {
//										"cast": ""
//									}
//								}
//							}
//						},
//						"aiQuery": "true",
//						"ref": "#pageRef"
//					},
//					"icon": "start.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JES7BJ6A0",
//					"attrs": {
//						"id": "Blocker",
//						"viewName": "",
//						"label": "",
//						"x": "370",
//						"y": "210",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JES7D0V20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JES7D0V21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenBlockers.js",
//						"argument": "{\"pageRef\":\"#pageRef\",\"blocker\":\"#{remove:true}\",\"waitAfter\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JES7D0V10",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JES7FG730"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1JES7DO0M0",
//					"attrs": {
//						"id": "FastRead",
//						"viewName": "",
//						"label": "",
//						"x": "875",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JES7FVV60",
//							"attrs": {
//								"cast": "{\"url\":\"\",\"title\":\"\",\"html\":\"\",\"article\":\"result\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1JES7FVV61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"target": "Article",
//						"node": "null",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JES7FVV50",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JES7EEEF0"
//						},
//						"errorSeg": "1JES7G6JA0",
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JES7EEEF0",
//					"attrs": {
//						"id": "CheckArticle",
//						"viewName": "",
//						"label": "",
//						"x": "1115",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JES7FVV62",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JES7FVV63",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JES7FVV52",
//							"attrs": {
//								"id": "GotoAI",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JES7G6JA0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JES7FVV51",
//									"attrs": {
//										"id": "Article",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JES7FVV64",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JES7FVV65",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#context.article && context.article.length>300"
//									},
//									"linkedSeg": "1JES8TMNJ0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1JES7FG730",
//					"attrs": {
//						"id": "ReadHTML",
//						"viewName": "",
//						"label": "",
//						"x": "615",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JES7FVV66",
//							"attrs": {
//								"cast": "{\"url\":\"\",\"title\":\"\",\"html\":\"result\",\"article\":\"\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1JES7FVV67",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"target": "CleanHTML",
//						"node": "null",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JES7FVV53",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JES7DO0M0"
//						},
//						"errorSeg": "1JES7LTNG0",
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JES7G6JA0",
//					"attrs": {
//						"id": "AIRead",
//						"viewName": "",
//						"label": "",
//						"x": "1370",
//						"y": "280",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JES7MABJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JES7MABJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-5-mini",
//						"system": "【角色】\n你是一个从HTML页面中提取文章内容的AI\n【输入】\n对话输入包含经过清洗后的网页HTML代码。\n【分析】\n你分析HTML代码，确认这个网页是否包含可以提取的文章内容。\n- 如果包含文章内容，提取并以Markdown格式返回完整的文章。\n- 如果当前页面并不包含有意义的文章，比如当前为404页面，当前为文章列表页面等，返回提取文章失败的原因\n【输出】\n你必须用JSON格式返回，不要包含JSON以外的内容。\n【成功提取到文章的JSON属性】\n{\n\ttitle: string 文章标题文本\n\tauthor?: string 文章作者\n\tpublishTime?: Date-string 文章发布时间\n\tarticle: text in markdown Markdown格式的完整的文章内容。\n    summary: 不超过300字的总结文本\n    keywords: array<string> 文章内容的关键字\n}\n【未能成功提取文章的JSON属性】\n{\n\tarticle: null\n    reason: string 未能提取文章内容的原因\n}",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#context.pageHtml",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1JES7MABG1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"stream": "true",
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
//						"responseFormat": "json_object",
//						"formatDef": "\"\"",
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JES7MABG0",
//									"attrs": {
//										"id": "Article",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JES7MABJ2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JES7MABJ3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JES8VTU60"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JES7GOND0",
//									"attrs": {
//										"id": "NoArticle",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JES7MABJ4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JES7MABJ5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JES7LTNG0"
//								}
//							]
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JES7L9KV0",
//					"attrs": {
//						"id": "FinDone",
//						"viewName": "",
//						"label": "",
//						"x": "1955",
//						"y": "185",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JES7MABJ6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JES7MABJ7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JES7MABG2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JES7LTNG0",
//					"attrs": {
//						"id": "FinFail",
//						"viewName": "",
//						"label": "",
//						"x": "1615",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JES7MABJ8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JES7MABJ9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JES7MABG3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JES8TMNJ0",
//					"attrs": {
//						"id": "NeedInfo",
//						"viewName": "",
//						"label": "",
//						"x": "1370",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JES90S2D0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JES90S2D1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JES90S2B1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JES906PU0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JES90S2B0",
//									"attrs": {
//										"id": "Info",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JES90S2D2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JES90S2D3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#read && read.detail"
//									},
//									"linkedSeg": "1JES8V2Q50"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JES8V2Q50",
//					"attrs": {
//						"id": "GenInfo",
//						"viewName": "",
//						"label": "",
//						"x": "1615",
//						"y": "60",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JES90S2D4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JES90S2D5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-5-mini",
//						"system": "【角色】\n你是一个从Markdown文章中文章细节内容的AI\n【输入】\n对话输入是文章的Markdown文档。\n【分析】\n你分析文章内容，提取标题、作者、发布时间、总结等文章相关细节内容。\n【输出】\n你必须用JSON格式返回，不要包含JSON以外的内容。\n【成功提取到文章的JSON属性】\n{\n\ttitle: string 文章标题文本\n\tauthor?: string 文章作者\n\tpublishTime?: Date-string 文章发布时间\n    summary: 不超过300字的总结文本\n    keywords: array<string> 文章内容的关键字\n}\n【未能成功识别文章的内容的JSON属性】\n{\n\ttitle: null\n\tsummary: null\n\tkeywords: null\n    reason: string 未能提取文章内容的原因\n}\n",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#input",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1JES90S2B2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JES906PU0"
//						},
//						"stream": "true",
//						"secret": "false",
//						"allowCheat": "true",
//						"GPTCheats": {
//							"attrs": [
//								{
//									"type": "object",
//									"def": "GPTCheat",
//									"jaxId": "1JESEK0VD0",
//									"attrs": {
//										"prompt": "",
//										"reply": "{ \"title\": \"Omega’s Speedmaster Moonwatch Does a Reverse Panda\", \"summary\": \"Omega推出Speedmaster Moonwatch“reverse panda”新款，提供不锈钢与18K Moonshine黄金两种材质。特色为黑色双层漆面表盘透出白色计时小盘、黑色陶瓷测速圈（dot over 90）、经典42mm表壳及手动上链Cal.3861（Co‑Axial、硅游丝、Master Chronometer）机芯。整体更为精致且技术升级，钢款性价比高，黄金款价格昂贵（约US$10,400与US$49,300）。\", \"keywords\": [ \"Omega\", \"Speedmaster\", \"Moonwatch\", \"Reverse Panda\", \"Moonshine gold\", \"Stainless steel\", \"Black lacquer dial\", \"Layered dial\", \"Ceramic bezel\", \"Tachymeter\", \"Dot over 90\", \"Cal. 3861\", \"Master Co‑Axial\", \"Manual-wind\", \"42 mm\", \"50 m\", \"Price\" ] }"
//									}
//								}
//							]
//						},
//						"shareChatName": "",
//						"keepChat": "No",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "json_object",
//						"formatDef": "\"\"",
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JES8VTU60",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1600",
//						"y": "185",
//						"outlet": {
//							"jaxId": "1JES90S2D6",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JES7L9KV0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JES906PU0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1830",
//						"y": "130",
//						"outlet": {
//							"jaxId": "1JES90S2D7",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JES7L9KV0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}