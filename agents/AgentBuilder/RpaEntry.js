//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1HDBOSUN90MoreImports*/
/*}#1HDBOSUN90MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"search":{
			"name":"search","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"",
		},
		"searchNum":{
			"name":"searchNum","type":"integer",
			"defaultValue":5,
			"desc":"",
		},
		"opts":{
			"name":"opts","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"platforms":{
			"name":"platforms","type":"auto",
			"defaultValue":[],
			"desc":"",
		}
	},
	/*#{1HDBOSUN90ArgsView*/
	/*}#1HDBOSUN90ArgsView*/
};

/*#{1HDBOSUN90StartDoc*/
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let RpaEntry=async function(session){
	let search,searchNum,opts,platforms;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let CheckSearch,fixagrs,SelectPlatform,PlatformBranch,LoopEnd,RedNoteLoginAgent,TwitterLoginAgent,BaiduSearchAgent,TwitterReadAgent,RedNoteSearchAgent,StartRpa,OpenBrowser,TwitterSearchAgent,GoogleSearchAgent,RedNoteAgent,LoopUrl,ReadAgent,MergedRes,RedditSearchAgent;
	/*#{1HDBOSUN90LocalVals*/
	//console.log(globalContext);
	/*}#1HDBOSUN90LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			search=input.search;
			searchNum=input.searchNum;
			opts=input.opts;
			platforms=input.platforms;
		}else{
			search=undefined;
			searchNum=undefined;
			opts=undefined;
			platforms=undefined;
		}
		/*#{1HDBOSUN90ParseArgs*/
		/*}#1HDBOSUN90ParseArgs*/
	}
	
	/*#{1HDBOSUN90PreContext*/
	/*}#1HDBOSUN90PreContext*/
	context={
		websites: "",
		articleList: [],
		channel: "",
		/*#{1HDBOSUNA3ExCtxAttrs*/
		/*}#1HDBOSUNA3ExCtxAttrs*/
	};
	/*#{1HDBOSUN90PostContext*/
	/*}#1HDBOSUN90PostContext*/
	let $agent,agent,segs={};
	segs["CheckSearch"]=CheckSearch=async function(input){//:1JASGK77L0
		let result=input;
		/*#{1JASGK77L0Start*/
		if(platforms&&platforms.length){
			input = platforms;
		};
		/*}#1JASGK77L0Start*/
		if(!search){
			return {seg:SelectPlatform,result:(input),preSeg:"1JASGK77L0",outlet:"1JASGM4E70"};
		}
		if(platforms&&platforms.length){
			return {seg:LoopUrl,result:(input),preSeg:"1JASGK77L0",outlet:"1JD9M8N9A0"};
		}
		/*#{1JASGK77L0Post*/
		/*}#1JASGK77L0Post*/
		return {seg:SelectPlatform,result:(result),preSeg:"1JASGK77L0",outlet:"1JASGM4E71"};
	};
	CheckSearch.jaxId="1JASGK77L0"
	CheckSearch.url="CheckSearch@"+agentURL
	
	segs["fixagrs"]=fixagrs=async function(input){//:1JASGNI3U0
		let result=input;
		let missing=false;
		let smartAsk=false;
		/*#{1JASGNI3U0PreCodes*/
		/*}#1JASGNI3U0PreCodes*/
		if(search===undefined || search==="") missing=true;
		if(searchNum===undefined || searchNum==="") missing=true;
		if(opts===undefined || opts==="") missing=true;
		if(platforms===undefined || platforms==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		/*#{1JASGNI3U0PostCodes*/
		/*}#1JASGNI3U0PostCodes*/
		return {seg:StartRpa,result:(result),preSeg:"1JASGNI3U0",outlet:"1JASGOAEQ0"};
	};
	fixagrs.jaxId="1JASGNI3U0"
	fixagrs.url="fixagrs@"+agentURL
	
	segs["SelectPlatform"]=SelectPlatform=async function(input){//:1JAI4NAPN0
		let prompt=((($ln==="CN")?("请选择"):("Please select the web platforms")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{text:(($ln==="CN")?("小红书"):("RedNote")),code:0},
			{text:(($ln==="CN")?("推特"):("Twitter")),code:1},
			{text:(($ln==="CN")?("百度"):("Baidu")),code:2},
			{text:(($ln==="CN")?("谷歌"):("Google")),code:3},
			{text:"Reddit",code:4},
		];
		let result="";
		let item=null;
		
		/*#{1JAI4NAPN0PreCodes*/
		/*}#1JAI4NAPN0PreCodes*/
		if(silent){
			result="";
			return {seg:LoopUrl,result:(result),preSeg:"1JAI4NAPN0",outlet:"1JAI4NAP40"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:true,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		/*#{1JAI4NAPN0PostCodes*/
		const resultArray = result.split(", ").map(item => item.trim());
		context.websites = resultArray;
		//console.log(resultArray,'resultArray');
		result = resultArray;
		/*}#1JAI4NAPN0PostCodes*/
		/*#{1JAI4NAPN0FinCodes*/
		/*}#1JAI4NAPN0FinCodes*/
		return {seg:LoopUrl,result:(result),preSeg:"1JAI4NAPN0",outlet:"1JAI4QSIV0"};
	};
	SelectPlatform.jaxId="1JAI4NAPN0"
	SelectPlatform.url="SelectPlatform@"+agentURL
	
	segs["PlatformBranch"]=PlatformBranch=async function(input){//:1JAI4HS2T0
		let result=input;
		/*#{1JAI4HS2T0Start*/
		input = {
			platform:input,
			search,
			searchNum,
		};
		//console.log(input,"input test====")
		/*}#1JAI4HS2T0Start*/
		if((input.platform === "小红书" || input.platform === "RedNote")){
			return {seg:RedNoteLoginAgent,result:(input),preSeg:"1JAI4HS2T0",outlet:"1JAI4MAIF0"};
		}
		if((input.platform === "百度" || input.platform === "Baidu")){
			return {seg:BaiduSearchAgent,result:(input),preSeg:"1JAI4HS2T0",outlet:"1JAI4JSEU0"};
		}
		if((input.platform === "Twitter" || input.platform === "推特")){
			return {seg:TwitterLoginAgent,result:(input),preSeg:"1JAI4HS2T0",outlet:"1JAIQNSGB0"};
		}
		if((input.platform === "谷歌" || input.platform === "Google")){
			return {seg:GoogleSearchAgent,result:(input),preSeg:"1JAI4HS2T0",outlet:"1JAIQME990"};
		}
		if(input.platform === "Reddit"){
			return {seg:RedditSearchAgent,result:(input),preSeg:"1JAI4HS2T0",outlet:"1JC5LD0AJ0"};
		}
		/*#{1JAI4HS2T0Post*/
		/*}#1JAI4HS2T0Post*/
		return {result:result};
	};
	PlatformBranch.jaxId="1JAI4HS2T0"
	PlatformBranch.url="PlatformBranch@"+agentURL
	
	segs["LoopEnd"]=LoopEnd=async function(input){//:1JAI6PK160
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("任务已结束。"):("The task has ended."));
		/*#{1JAI6PK160PreCodes*/
		/*}#1JAI6PK160PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JAI6PK160PostCodes*/
		//console.log(context.articleList,'LoopEnd');
		//result = context.articleList;
		result = [...context.articleList]
		/*}#1JAI6PK160PostCodes*/
		return {result:result};
	};
	LoopEnd.jaxId="1JAI6PK160"
	LoopEnd.url="LoopEnd@"+agentURL
	
	segs["RedNoteLoginAgent"]=RedNoteLoginAgent=async function(input){//:1JAQDPQI70
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/rednoteLogin.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JAQDPQI70Input*/
		/*}#1JAQDPQI70Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1JAQDPQI70Output*/
		result = input;
		/*}#1JAQDPQI70Output*/
		return {seg:RedNoteSearchAgent,result:(result),preSeg:"1JAQDPQI70",outlet:"1JAQDQEJP0"};
	};
	RedNoteLoginAgent.jaxId="1JAQDPQI70"
	RedNoteLoginAgent.url="RedNoteLoginAgent@"+agentURL
	
	segs["TwitterLoginAgent"]=TwitterLoginAgent=async function(input){//:1JAQG6HDA0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/twitterLogin.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JAQG6HDA0Input*/
		/*}#1JAQG6HDA0Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1JAQG6HDA0Output*/
		result = input;
		/*}#1JAQG6HDA0Output*/
		return {seg:TwitterSearchAgent,result:(result),preSeg:"1JAQG6HDA0",outlet:"1JAQG6UGG0"};
	};
	TwitterLoginAgent.jaxId="1JAQG6HDA0"
	TwitterLoginAgent.url="TwitterLoginAgent@"+agentURL
	
	segs["BaiduSearchAgent"]=BaiduSearchAgent=async function(input){//:1JASSKBN60
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/baiduSearch.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JASSKBN60Input*/
		/*}#1JASSKBN60Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1JASSKBN60Output*/
		/*}#1JASSKBN60Output*/
		return {seg:ReadAgent,result:(result),preSeg:"1JASSKBN60",outlet:"1JASSLBCJ0"};
	};
	BaiduSearchAgent.jaxId="1JASSKBN60"
	BaiduSearchAgent.url="BaiduSearchAgent@"+agentURL
	
	segs["TwitterReadAgent"]=TwitterReadAgent=async function(input){//:1JBC9T6BC0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/twitterArticleRead.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JBC9T6BC0Input*/
		/*}#1JBC9T6BC0Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1JBC9T6BC0Output*/
		/*}#1JBC9T6BC0Output*/
		return {seg:MergedRes,result:(result),preSeg:"1JBC9T6BC0",outlet:"1JBC9UQ8D0"};
	};
	TwitterReadAgent.jaxId="1JBC9T6BC0"
	TwitterReadAgent.url="TwitterReadAgent@"+agentURL
	
	segs["RedNoteSearchAgent"]=RedNoteSearchAgent=async function(input){//:1JAV9EAPP0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/rednoteSearch.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:RedNoteAgent,result:(result),preSeg:"1JAV9EAPP0",outlet:"1JAV9FH7H0"};
	};
	RedNoteSearchAgent.jaxId="1JAV9EAPP0"
	RedNoteSearchAgent.url="RedNoteSearchAgent@"+agentURL
	
	segs["StartRpa"]=StartRpa=async function(input){//:1JAVCP71K0
		let result=true;
		let aiQuery=true;
		let $alias="RPAHOME";
		let $url="";
		let $ref=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let $webRpa=null;
		/*#{1JAVCP71K0PreCodes*/
		context.channel = input;
		//context.search = input;
		//console.log(context.search,'StartRpa');
		/*}#1JAVCP71K0PreCodes*/
		try{
			if($ref){
				let $page,$browser;
				let $pageVal="aaPage";
				$page=WebRpa.getPageByRef($ref);
				context.rpaBrowser=$browser=$page.webDrive;
				context.webRpa=$webRpa=$browser.aaWebRpa;
				Object.defineProperty(context, $pageVal, {enumerable:true,get(){return $webRpa.currentPage},set(v){$webRpa.setCurrentPage(v)}});
				context[$pageVal]=$page;
			}else{
				let $pageVal="aaPage";
				context.webRpa=$webRpa=session.webRpa || new WebRpa(session);
				session.webRpa=$webRpa;
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JAVCP71K0"));
				if($alias){
					let $headless=false;
					let $devtools=false;
					let options={$headless:false,$devtools:false,autoDataDir:false};
					let $browser=null;
					/*#{1JAVCP71K0PreBrowser*/
					/*}#1JAVCP71K0PreBrowser*/
					context.rpaBrowser=$browser=await context.webRpa.openBrowser($alias,options);
					context.rpaHostPage=$browser.hostPage;
					Object.defineProperty(context, $pageVal, {enumerable:true,get(){return $webRpa.currentPage},set(v){$webRpa.setCurrentPage(v)}});
					/*#{1JAVCP71K0PostBrowser*/
					/*}#1JAVCP71K0PostBrowser*/
					if($url){
						let $page=null;
						let $opts={};
						/*#{1JAVCP71K0PrePage*/
						/*}#1JAVCP71K0PrePage*/
						context[$pageVal]=$page=await $browser.newPage();
						await $page.goto($url,{});
						/*#{1JAVCP71K0PostPage*/
						/*}#1JAVCP71K0PostPage*/
					}
				}
			}
			$waitAfter && (await sleep($waitAfter));
		}catch(error){
			throw error;
		}
		/*#{1JAVCP71K0PostCodes*/
		/*}#1JAVCP71K0PostCodes*/
		return {seg:OpenBrowser,result:(result),preSeg:"1JAVCP71K0",outlet:"1JAVCPI690"};
	};
	StartRpa.jaxId="1JAVCP71K0"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["OpenBrowser"]=OpenBrowser=async function(input){//:1JAVCP8750
		let result=true;
		let browser=null;
		let headless=false;
		let devtools=false;
		let dataDir=false;
		let alias="RPAHOME";
		let options={headless,devtools,autoDataDir:dataDir};
		/*#{1JAVCP8750PreCodes*/
		/*}#1JAVCP8750PreCodes*/
		try{
			context.rpaBrowser=browser=await context.webRpa.openBrowser(alias,options);
			context.rpaHostPage=browser.hostPage;
		
		}catch(error){
			/*#{1JAVCP8750ErrorCode*/
			/*}#1JAVCP8750ErrorCode*/
		}
		/*#{1JAVCP8750PostCodes*/
		globalContext.rpaBrowser = context.rpaBrowser;
		globalContext.webRpa = context.webRpa;
		globalContext.rpaHostPage = browser.rpaHostPage;
		//console.log(globalContext,'globalContext','OpenBrowser');
		/*}#1JAVCP8750PostCodes*/
		return {seg:CheckSearch,result:(result),preSeg:"1JAVCP8750",outlet:"1JAVCPI691"};
	};
	OpenBrowser.jaxId="1JAVCP8750"
	OpenBrowser.url="OpenBrowser@"+agentURL
	
	segs["TwitterSearchAgent"]=TwitterSearchAgent=async function(input){//:1JB44HO2M0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/twitterSearch.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:TwitterReadAgent,result:(result),preSeg:"1JB44HO2M0",outlet:"1JB44J12F0"};
	};
	TwitterSearchAgent.jaxId="1JB44HO2M0"
	TwitterSearchAgent.url="TwitterSearchAgent@"+agentURL
	
	segs["GoogleSearchAgent"]=GoogleSearchAgent=async function(input){//:1JBC6FCM90
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/googleSearch.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:ReadAgent,result:(result),preSeg:"1JBC6FCM90",outlet:"1JBC6GO3A0"};
	};
	GoogleSearchAgent.jaxId="1JBC6FCM90"
	GoogleSearchAgent.url="GoogleSearchAgent@"+agentURL
	
	segs["RedNoteAgent"]=RedNoteAgent=async function(input){//:1JBF53M1S0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/rednoteRead.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:MergedRes,result:(result),preSeg:"1JBF53M1S0",outlet:"1JBF54KBP0"};
	};
	RedNoteAgent.jaxId="1JBF53M1S0"
	RedNoteAgent.url="RedNoteAgent@"+agentURL
	
	segs["LoopUrl"]=LoopUrl=async function(input){//:1JBHJ07RR0
		let result=input;
		let list=input;
		let i,n,item,loopR;
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			loopR=await session.runAISeg(agent,PlatformBranch,item,"1JBHJ07RR0","1JBHJ0L712")
			if(loopR==="break"){
				break;
			}
		}
		return {seg:LoopEnd,result:(result),preSeg:"1JBHJ07RR0",outlet:"1JBHJ0L6P0"};
	};
	LoopUrl.jaxId="1JBHJ07RR0"
	LoopUrl.url="LoopUrl@"+agentURL
	
	segs["ReadAgent"]=ReadAgent=async function(input){//:1JBOLQGCO0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/articleRead.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JBOLQGCO0Input*/
		/*}#1JBOLQGCO0Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1JBOLQGCO0Output*/
		//context.articleList = context.articleList.concat(result);
		/*}#1JBOLQGCO0Output*/
		return {seg:MergedRes,result:(result),preSeg:"1JBOLQGCO0",outlet:"1JBOLQGCP2"};
	};
	ReadAgent.jaxId="1JBOLQGCO0"
	ReadAgent.url="ReadAgent@"+agentURL
	
	segs["MergedRes"]=MergedRes=async function(input){//:1JBP3I5AJ0
		let result=input
		try{
			/*#{1JBP3I5AJ0Code*/
			context.articleList = context.articleList.concat(input);
			/*}#1JBP3I5AJ0Code*/
		}catch(error){
			/*#{1JBP3I5AJ0ErrorCode*/
			/*}#1JBP3I5AJ0ErrorCode*/
		}
		return {result:result};
	};
	MergedRes.jaxId="1JBP3I5AJ0"
	MergedRes.url="MergedRes@"+agentURL
	
	segs["RedditSearchAgent"]=RedditSearchAgent=async function(input){//:1JC5M4IKG0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/redditSearch.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JC5M4IKG0Input*/
		/*}#1JC5M4IKG0Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1JC5M4IKG0Output*/
		/*}#1JC5M4IKG0Output*/
		return {seg:ReadAgent,result:(result),preSeg:"1JC5M4IKG0",outlet:"1JC5M590H0"};
	};
	RedditSearchAgent.jaxId="1JC5M4IKG0"
	RedditSearchAgent.url="RedditSearchAgent@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"RpaEntry",
		url:agentURL,
		autoStart:true,
		jaxId:"1HDBOSUN90",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{search,searchNum,opts,platforms}*/){
			let result;
			parseAgentArgs(input);
			/*#{1HDBOSUN90PreEntry*/
			/*}#1HDBOSUN90PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1HDBOSUN90PostEntry*/
			/*}#1HDBOSUN90PostEntry*/
			return result;
		},
		/*#{1HDBOSUN90MoreAgentAttrs*/
		/*}#1HDBOSUN90MoreAgentAttrs*/
	};
	/*#{1HDBOSUN90PostAgent*/
	/*}#1HDBOSUN90PostAgent*/
	return agent;
};
/*#{1HDBOSUN90ExCodes*/
/*}#1HDBOSUN90ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "RpaEntry",
		description: "这是一个AI代理。",
		parameters:{
			type: "object",
			properties:{
				search:{type:"string",description:""},
				searchNum:{type:"integer",description:""},
				opts:{type:"auto",description:""},
				platforms:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true
}];
//#CodyExport<<<
/*#{1HDBOSUN90PostDoc*/
/*}#1HDBOSUN90PostDoc*/


export default RpaEntry;
export{RpaEntry,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1HDBOSUN90",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1HDBOSUNA0",
//			"attrs": {
//				"agent": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1HDBOSUNA4",
//					"attrs": {
//						"constructArgs": {
//							"jaxId": "1HDBOSUNB0",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1HDBOSUNB1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1HDBOSUNB2",
//							"attrs": {}
//						},
//						"mockupOnly": "false",
//						"nullMockup": "false",
//						"exportType": "UI Data Template",
//						"exportClass": "false",
//						"superClass": ""
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1HDBOSUNA1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "StartRpa",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IH2869AD0",
//			"attrs": {
//				"search": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JASGSQBD0",
//					"attrs": {
//						"type": "String",
//						"required": "true",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"searchNum": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JASGSQBD1",
//					"attrs": {
//						"type": "Integer",
//						"mockup": "5",
//						"desc": ""
//					}
//				},
//				"opts": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JASGSQBD2",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"platforms": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JD7MOIA10",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1HDBOSUNA2",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1HDBOSUNA3",
//			"attrs": {
//				"websites": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JASH1S150",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"articleList": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JBP321510",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				},
//				"channel": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JC5JE5RH0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1HDIJB7SK6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JASGK77L0",
//					"attrs": {
//						"id": "CheckSearch",
//						"viewName": "",
//						"label": "",
//						"x": "-740",
//						"y": "380",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JASGM4EC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JASGM4EC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JASGM4E71",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JAI4NAPN0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JASGM4E70",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JASGM4EC2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JASGM4EC3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!search"
//									},
//									"linkedSeg": "1JAI4NAPN0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JD9M8N9A0",
//									"attrs": {
//										"id": "Platforms",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JD9MB3R20",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JD9MB3R21",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#platforms&&platforms.length"
//									},
//									"linkedSeg": "1JD9MF24Q0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1JASGNI3U0",
//					"attrs": {
//						"id": "fixagrs",
//						"viewName": "",
//						"label": "",
//						"x": "-1345",
//						"y": "395",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1JASGOAEQ0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAVCP71K0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1JAI4NAPN0",
//					"attrs": {
//						"id": "SelectPlatform",
//						"viewName": "",
//						"label": "",
//						"x": "25",
//						"y": "365",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Please select the web platforms",
//							"localize": {
//								"EN": "Please select the web platforms",
//								"CN": "请选择"
//							},
//							"localizable": true
//						},
//						"multi": "true",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1JAI4QSIV0",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							},
//							"linkedSeg": "1JBHJ07RR0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JAI4NAP40",
//									"attrs": {
//										"id": "RedNote",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "RedNote",
//											"localize": {
//												"EN": "RedNote",
//												"CN": "小红书"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JAI4QSJD0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JAI4QSJD1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JBHJ07RR0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JAIQNSGM0",
//									"attrs": {
//										"id": "Twitter",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Twitter",
//											"localize": {
//												"EN": "Twitter",
//												"CN": "推特"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JAIQNSGM1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JAIQNSGM2",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JBHJ07RR0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JBOLI8QI0",
//									"attrs": {
//										"id": "Baidu",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Baidu",
//											"localize": {
//												"EN": "Baidu",
//												"CN": "百度"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JBOLI8QI1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JBOLI8QI2",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JBHJ07RR0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JBOLGU2S0",
//									"attrs": {
//										"id": "Google",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Google",
//											"localize": {
//												"EN": "Google",
//												"CN": "谷歌"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JBOLI8QI11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JBOLI8QI12",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JBHJ07RR0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JC5L4LAP0",
//									"attrs": {
//										"id": "Reddit",
//										"desc": "输出节点。",
//										"text": "Reddit",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JC5L4LAP1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JC5L4LAP2",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JBHJ07RR0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JAI4HS2T0",
//					"attrs": {
//						"id": "PlatformBranch",
//						"viewName": "",
//						"label": "",
//						"x": "585",
//						"y": "350",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAI4MAII0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAI4MAII1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JAI4MAIG0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JAI4MAIF0",
//									"attrs": {
//										"id": "RedNote",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JAI4MAII2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JAI4MAII3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#(input.platform === \"小红书\" || input.platform === \"RedNote\")"
//									},
//									"linkedSeg": "1JAQDPQI70"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JAI4JSEU0",
//									"attrs": {
//										"id": "Baidu",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JAI4MAII4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JAI4MAII5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#(input.platform === \"百度\" || input.platform === \"Baidu\")"
//									},
//									"linkedSeg": "1JASSKBN60"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JAIQNSGB0",
//									"attrs": {
//										"id": "Twitter",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JAIQNSGN0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JAIQNSGN1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#(input.platform === \"Twitter\" || input.platform === \"推特\")"
//									},
//									"linkedSeg": "1JAQG6HDA0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JAIQME990",
//									"attrs": {
//										"id": "Google",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JAIQNSGN2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JAIQNSGN3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#(input.platform === \"谷歌\" || input.platform === \"Google\")"
//									},
//									"linkedSeg": "1JBC6FCM90"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JC5LD0AJ0",
//									"attrs": {
//										"id": "Reddit",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JC5LD0AT0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JC5LD0AT1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.platform === \"Reddit\""
//									},
//									"linkedSeg": "1JC5M4IKG0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JAI6PK160",
//					"attrs": {
//						"id": "LoopEnd",
//						"viewName": "",
//						"label": "",
//						"x": "595",
//						"y": "550",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAI6QBIS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAI6QBIS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "The task has ended.",
//							"localize": {
//								"EN": "The task has ended.",
//								"CN": "任务已结束。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JAI6QBIO0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JAQDPQI70",
//					"attrs": {
//						"id": "RedNoteLoginAgent",
//						"viewName": "",
//						"label": "",
//						"x": "905",
//						"y": "235",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQDQEK10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQDQEK11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/rednoteLogin.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JAQDQEJP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAV9EAPP0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JAQG6HDA0",
//					"attrs": {
//						"id": "TwitterLoginAgent",
//						"viewName": "",
//						"label": "",
//						"x": "905",
//						"y": "345",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQG6UGL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQG6UGL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/twitterLogin.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JAQG6UGG0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB44HO2M0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JASSKBN60",
//					"attrs": {
//						"id": "BaiduSearchAgent",
//						"viewName": "",
//						"label": "",
//						"x": "905",
//						"y": "290",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JASSLBCN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JASSLBCN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/baiduSearch.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JASSLBCJ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBCH8NT70"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JBC9T6BC0",
//					"attrs": {
//						"id": "TwitterReadAgent",
//						"viewName": "",
//						"label": "",
//						"x": "1415",
//						"y": "345",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBC9UQ8G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBC9UQ8G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/twitterArticleRead.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JBC9UQ8D0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBP3I5AJ0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JAV9EAPP0",
//					"attrs": {
//						"id": "RedNoteSearchAgent",
//						"viewName": "",
//						"label": "",
//						"x": "1260",
//						"y": "235",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAV9FH7O0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAV9FH7O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/rednoteSearch.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JAV9FH7H0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBF53M1S0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JAVCP71K0",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "-1155",
//						"y": "395",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAVCPI6I0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAVCPI6I1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"browser": "RPAHOME",
//						"headless": "false",
//						"devtools": "false",
//						"url": "",
//						"valName": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JAVCPI690",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAVCP8750"
//						},
//						"catchlet": {
//							"jaxId": "1JAVCPI6I2",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JAVCPI6I3",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JAVCPI6I4",
//									"attrs": {
//										"cast": ""
//									}
//								}
//							}
//						},
//						"aiQuery": "true",
//						"autoCurrentPage": "true"
//					},
//					"icon": "start.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenBrowser",
//					"jaxId": "1JAVCP8750",
//					"attrs": {
//						"id": "OpenBrowser",
//						"viewName": "",
//						"label": "",
//						"x": "-960",
//						"y": "380",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAVCPI6I5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAVCPI6I6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"alias": "RPAHOME",
//						"headless": "false",
//						"devtools": "false",
//						"dataDir": "false",
//						"outlet": {
//							"jaxId": "1JAVCPI691",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JASGK77L0"
//						},
//						"run": "",
//						"errorSeg": ""
//					},
//					"icon": "web.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JB44HO2M0",
//					"attrs": {
//						"id": "TwitterSearchAgent",
//						"viewName": "",
//						"label": "",
//						"x": "1160",
//						"y": "345",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB44J12O0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB44J12O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/twitterSearch.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JB44J12F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBC9T6BC0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JBC6FCM90",
//					"attrs": {
//						"id": "GoogleSearchAgent",
//						"viewName": "",
//						"label": "",
//						"x": "905",
//						"y": "400",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBC6GO3E0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBC6GO3E1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/googleSearch.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JBC6GO3A0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBET2QT80"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JBCH8NT70",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1570",
//						"y": "290",
//						"outlet": {
//							"jaxId": "1JBCH92MB1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBOLQGCO0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JBET2QT80",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1500",
//						"y": "400",
//						"outlet": {
//							"jaxId": "1JBET328N0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBOLQGCO0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JBF53M1S0",
//					"attrs": {
//						"id": "RedNoteAgent",
//						"viewName": "",
//						"label": "",
//						"x": "1585",
//						"y": "235",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBF54KBV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBF54KBV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/rednoteRead.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JBF54KBP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBP3I5AJ0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1JBHJ07RR0",
//					"attrs": {
//						"id": "LoopUrl",
//						"viewName": "",
//						"label": "",
//						"x": "345",
//						"y": "365",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBHJ0L710",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBHJ0L711",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1JBHJ0L712",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAI4HS2T0"
//						},
//						"catchlet": {
//							"jaxId": "1JBHJ0L6P0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAI6PK160"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JBOLQGCO0",
//					"attrs": {
//						"id": "ReadAgent",
//						"viewName": "",
//						"label": "",
//						"x": "1715",
//						"y": "400",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBOLQGCP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBOLQGCP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/articleRead.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JBOLQGCP2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBP3I5AJ0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JBP3I5AJ0",
//					"attrs": {
//						"id": "MergedRes",
//						"viewName": "",
//						"label": "",
//						"x": "2095",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBP3JLD90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBP3JLD91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JBP3JLD00",
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
//					"def": "aiBot",
//					"jaxId": "1JC5M4IKG0",
//					"attrs": {
//						"id": "RedditSearchAgent",
//						"viewName": "",
//						"label": "",
//						"x": "905",
//						"y": "460",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC5M590P0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC5M590P1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/redditSearch.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JC5M590H0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC60HKA40"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JC60HKA40",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1585",
//						"y": "460",
//						"outlet": {
//							"jaxId": "1JC60HQRS0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBOLQGCO0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JD9MELHU0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "180",
//						"y": "570",
//						"outlet": {
//							"jaxId": "1JD9MFU6F0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBHJ07RR0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JD9MF24Q0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "-465",
//						"y": "570",
//						"outlet": {
//							"jaxId": "1JD9MFU6F1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JD9MELHU0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI代理。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}