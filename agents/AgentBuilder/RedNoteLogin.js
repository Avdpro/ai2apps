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
/*#{1HDBOSUN90StartDoc*/
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let RedNoteLogin=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Start,OpenBrowser,OpenPage,Notify,FindLoginBtn,ActivePage,FlagLogin,AskLogin,AwaitLogin,BackToApp,CheckAgain,AbortBack,AbortPage,AbortLogin,RedNoteLoginConfirm,ActivePage_1,BackToApp_1,NeedLoginNotice,CheckAgain_1;
	/*#{1HDBOSUN90LocalVals*/
	/*}#1HDBOSUN90LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1HDBOSUN90ParseArgs*/
		/*}#1HDBOSUN90ParseArgs*/
	}
	
	/*#{1HDBOSUN90PreContext*/
	/*}#1HDBOSUN90PreContext*/
	context={};
	/*#{1HDBOSUN90PostContext*/
	/*}#1HDBOSUN90PostContext*/
	let $agent,agent,segs={};
	segs["Start"]=Start=async function(input){//:1IH28H5RP0
		let result=true;
		let aiQuery=true;
		let $alias="RPAHOME";
		let $url="";
		let $ref=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let $webRpa=null;
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1IH28H5RP0"));
				if($alias){
					let $headless=false;
					let $devtools=false;
					let options={$headless:false,$devtools:false,autoDataDir:false};
					let $browser=null;
					context.rpaBrowser=$browser=await context.webRpa.openBrowser($alias,options);
					context.rpaHostPage=$browser.hostPage;
					Object.defineProperty(context, $pageVal, {enumerable:true,get(){return $webRpa.currentPage},set(v){$webRpa.setCurrentPage(v)}});
					if($url){
						let $page=null;
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
		return {seg:OpenBrowser,result:(result),preSeg:"1IH28H5RP0",outlet:"1IH28I25B0"};
	};
	Start.jaxId="1IH28H5RP0"
	Start.url="Start@"+agentURL
	
	segs["OpenBrowser"]=OpenBrowser=async function(input){//:1IH28HPRB0
		let result=true;
		let browser=null;
		let headless=false;
		let devtools=false;
		let dataDir=false;
		let alias="RPAHOME";
		let options={headless,devtools,autoDataDir:dataDir};
		/*#{1IH28HPRB0PreCodes*/
		/*}#1IH28HPRB0PreCodes*/
		try{
			context.rpaBrowser=browser=await context.webRpa.openBrowser(alias,options);
			context.rpaHostPage=browser.hostPage;
		
		}catch(error){
			/*#{1IH28HPRB0ErrorCode*/
			/*}#1IH28HPRB0ErrorCode*/
		}
		/*#{1IH28HPRB0PostCodes*/
		/*}#1IH28HPRB0PostCodes*/
		return {result:result};
	};
	OpenBrowser.jaxId="1IH28HPRB0"
	OpenBrowser.url="OpenBrowser@"+agentURL
	
	segs["OpenPage"]=OpenPage=async function(input){//:1IH28P38Q0
		let pageVal="aaPage";
		let $url="https://www.xiaohongshu.com";
		let $waitBefore=0;
		let $waitAfter=0;
		let $width=1200;
		let $height=900;
		let $userAgent="";
		let $timeout=(undefined)||0;
		let page=null;
		let $openOpts={timeout:$timeout};
		$waitBefore && (await sleep($waitBefore));
		/*#{1IH28P38Q0PreCodes*/
		context.rpaBrowser = globalContext.rpaBrowser;
		context.webRpa = globalContext.webRpa;
		/*}#1IH28P38Q0PreCodes*/
		try{
			context[pageVal]=page=await context.rpaBrowser.newPage();
			($width && $height) && (await page.setViewport({width:$width,height:$height}));
			$userAgent && (await page.setUserAgent($userAgent));
			await page.goto($url,$openOpts);
			$waitAfter && (await sleep($waitAfter));
		}catch(error){
			/*#{1IH28P38Q0ErrorCode*/
			/*}#1IH28P38Q0ErrorCode*/
		}
		/*#{1IH28P38Q0PostCodes*/
		globalContext.aaPage = context[pageVal];
		context.search = input.search;
		context.searchNum = input.searchNum;
		/*}#1IH28P38Q0PostCodes*/
		return {seg:Notify,result:(true),preSeg:"1IH28P38Q0",outlet:"1IH28P9TV0"};
	};
	OpenPage.jaxId="1IH28P38Q0"
	OpenPage.url="OpenPage@"+agentURL
	
	segs["Notify"]=Notify=async function(input){//:1IH28Q6DB0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("小红书已打开。"):("RedNote has been opened."));
		session.addChatText(role,content,opts);
		return {seg:FindLoginBtn,result:(result),preSeg:"1IH28Q6DB0",outlet:"1IH28R1BB0"};
	};
	Notify.jaxId="1IH28Q6DB0"
	Notify.url="Notify@"+agentURL
	
	segs["FindLoginBtn"]=FindLoginBtn=async function(input){//:1JAQDDK940
		let result=true;
		let pageVal="aaPage";
		let $node=undefined;
		let $query="(//li[@class=\"user side-bar-component\"])";
		let $multi=false;
		let $options=undefined;
		let $waitBefore=500;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		/*#{1JAQDDK940PreCodes*/
		if($multi){
			result=await globalContext.webRpa.queryNodes(page,$node,$query,$options);
		}else{
			result=await globalContext.webRpa.queryNode(page,$node,$query,$options);
		}
		/*}#1JAQDDK940PreCodes*/
		try{
			if($multi){
				result=await context.webRpa.queryNodes(page,$node,$query,$options);
			}else{
				result=await context.webRpa.queryNode(page,$node,$query,$options);
			}
			if((!result)||($multi && !result.length)){
				throw "Querry not found";
			}
			/*#{1JAQDDK940CheckItem*/
			/*}#1JAQDDK940CheckItem*/
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JAQDDK940ErrorCode*/
			/*}#1JAQDDK940ErrorCode*/
			return {seg:ActivePage,result:error,preSeg:"1JAQDDK940",outlet:"1JAQDDK8J0"};
		}
		/*#{1JAQDDK940PostCodes*/
		//globalContext.rednotePage = context.aaPage;
		//globalContext.rednoteBrowser = context.rpaBrowser;
		//globalContext.rednoteWebRpa = context.webRpa
		/*}#1JAQDDK940PostCodes*/
		return {result:result};
	};
	FindLoginBtn.jaxId="1JAQDDK940"
	FindLoginBtn.url="FindLoginBtn@"+agentURL
	
	segs["ActivePage"]=ActivePage=async function(input){//:1JAQDFJII0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let $options={"focusBrowser":true};
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		try{
			await page.bringToFront($options);
			waitAfter && (await sleep(waitAfter))
			if($options.focusBrowser && $options.switchBack){
				let $browser=context.rpaBrowser;
				if($browser){
					await $browser.backToApp();
				}
			}
		}catch(error){
			/*#{1JAQDFJII0ErrorCode*/
			/*}#1JAQDFJII0ErrorCode*/
		}
		return {seg:FlagLogin,result:(result),preSeg:"1JAQDFJII0",outlet:"1JAQDH9MB1"};
	};
	ActivePage.jaxId="1JAQDFJII0"
	ActivePage.url="ActivePage@"+agentURL
	
	segs["FlagLogin"]=FlagLogin=async function(input){//:1JAQDGC4G0
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $query="(//li[@class=\"user side-bar-component\"])";
		let $queryHint="";
		let $waitBefore=0;
		let $waitAfter=0;
		let $options={};
		let $timeout=undefined;
		let page=context[pageVal];
		let $args=[];
		
		if($timeout){$options.timeout=$timeout;}
		$waitBefore && (await sleep($waitBefore));
		/*#{1JAQDGC4G0PreCodes*/
		/*}#1JAQDGC4G0PreCodes*/
		$query=$queryHint?(await page.confirmQuery($query,$queryHint,"1JAQDGC4G0")):$query;
		if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
		context[$flag]=context.webRpa.waitQuery(page,$query,$options);
		$waitAfter && (await sleep($waitAfter))
		/*#{1JAQDGC4G0PostCodes*/
		context[$flag]=globalContext.webRpa.waitQuery(page,$query,$options);
		/*}#1JAQDGC4G0PostCodes*/
		return {seg:RedNoteLoginConfirm,result:(result),preSeg:"1JAQDGC4G0",outlet:"1JAQDH9MB2"};
	};
	FlagLogin.jaxId="1JAQDGC4G0"
	FlagLogin.url="FlagLogin@"+agentURL
	
	segs["AskLogin"]=AskLogin=async function(input){//:1JAQDHJ0S0
		let result=input;
		/*#{1JAQDHJ0S0Start*/
		let page=context["aaPage"];
		result=await page.callFunction(function($ln){
			return window.confirm((($ln==="CN")?("AI2Apps: 搜索小红书需要先登录，登录后会自动返回AI2Apps继续。"):/*EN*/("AI2Apps: Searching RedNote requires login first, and will automatically return to AI2Apps after logging in.")));
		},[$ln]);
		/*}#1JAQDHJ0S0Start*/
		if(!!result){
			return {seg:AwaitLogin,result:(input),preSeg:"1JAQDHJ0S0",outlet:"1JAQDLCK50"};
		}
		/*#{1JAQDHJ0S0Post*/
		/*}#1JAQDHJ0S0Post*/
		return {seg:AbortBack,result:(result),preSeg:"1JAQDHJ0S0",outlet:"1JAQDI88I0"};
	};
	AskLogin.jaxId="1JAQDHJ0S0"
	AskLogin.url="AskLogin@"+agentURL
	
	segs["AwaitLogin"]=AwaitLogin=async function(input){//:1JAQDJLQT0
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		try{
			result=$flag?(await context[$flag]):input;
		}catch(error){
			return {result:error};
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:BackToApp,result:(result),preSeg:"1JAQDJLQT0",outlet:"1JAQDLCK52"};
	};
	AwaitLogin.jaxId="1JAQDJLQT0"
	AwaitLogin.url="AwaitLogin@"+agentURL
	
	segs["BackToApp"]=BackToApp=async function(input){//:1JAQDKOJ30
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JAQDKOJ30ErrorCode*/
			/*}#1JAQDKOJ30ErrorCode*/
		}
		return {seg:CheckAgain,result:(result),preSeg:"1JAQDKOJ30",outlet:"1JAQDLCK53"};
	};
	BackToApp.jaxId="1JAQDKOJ30"
	BackToApp.url="BackToApp@"+agentURL
	
	segs["CheckAgain"]=CheckAgain=async function(input){//:1JAQDMR3T0
		let result=input;
		return {seg:FindLoginBtn,result:result,preSeg:"1JAQDDK940",outlet:"1JAQDPCLQ0"};
	
	};
	CheckAgain.jaxId="1JAQDDK940"
	CheckAgain.url="CheckAgain@"+agentURL
	
	segs["AbortBack"]=AbortBack=async function(input){//:1JAQDNSL10
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		/*#{1JAQDNSL10PreCodes*/
		browser = globalContext.rpaBrowser;
		/*}#1JAQDNSL10PreCodes*/
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JAQDNSL10ErrorCode*/
			/*}#1JAQDNSL10ErrorCode*/
		}
		/*#{1JAQDNSL10PostCodes*/
		/*}#1JAQDNSL10PostCodes*/
		return {seg:AbortPage,result:(result),preSeg:"1JAQDNSL10",outlet:"1JAQDPCLQ1"};
	};
	AbortBack.jaxId="1JAQDNSL10"
	AbortBack.url="AbortBack@"+agentURL
	
	segs["AbortPage"]=AbortPage=async function(input){//:1JAQDO7VO0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		/*#{1JAQDO7VO0PreCodes*/
		/*}#1JAQDO7VO0PreCodes*/
		try{
			await page.close();
			context[pageVal]=null;
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JAQDO7VO0ErrorCode*/
			/*}#1JAQDO7VO0ErrorCode*/
		}
		/*#{1JAQDO7VO0PostCodes*/
		/*}#1JAQDO7VO0PostCodes*/
		return {seg:AbortLogin,result:(result),preSeg:"1JAQDO7VO0",outlet:"1JAQDPCLR0"};
	};
	AbortPage.jaxId="1JAQDO7VO0"
	AbortPage.url="AbortPage@"+agentURL
	
	segs["AbortLogin"]=AbortLogin=async function(input){//:1JAQDOTHU0
		let result=input
		try{
			/*#{1JAQDOTHU0Code*/
			/*}#1JAQDOTHU0Code*/
		}catch(error){
			/*#{1JAQDOTHU0ErrorCode*/
			/*}#1JAQDOTHU0ErrorCode*/
		}
		return {result:result};
	};
	AbortLogin.jaxId="1JAQDOTHU0"
	AbortLogin.url="AbortLogin@"+agentURL
	
	segs["RedNoteLoginConfirm"]=RedNoteLoginConfirm=async function(input){//:1JGJRRPBP0
		let prompt=((($ln==="CN")?("是否登录？"):("Login?")))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=((($ln==="CN")?("已登录"):("Logged in")))||"OK";
		let button2=((($ln==="CN")?("未登录"):("Not logged in")))||"Cancel";
		let button3="";
		let result="";
		let value=0;
		if(silent){
			result="";
			return {seg:ActivePage_1,result:(result),preSeg:"1JGJRRPBP0",outlet:"1JGJRRPB80"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			return {seg:ActivePage_1,result:(result),preSeg:"1JGJRRPBP0",outlet:"1JGJRRPB80"};
		}
		result=("")||result;
		return {seg:NeedLoginNotice,result:(result),preSeg:"1JGJRRPBP0",outlet:"1JGJRRPB81"};
	
	};
	RedNoteLoginConfirm.jaxId="1JGJRRPBP0"
	RedNoteLoginConfirm.url="RedNoteLoginConfirm@"+agentURL
	
	segs["ActivePage_1"]=ActivePage_1=async function(input){//:1JGJRU92E0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let $options={"focusBrowser":true};
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		try{
			await page.bringToFront($options);
			waitAfter && (await sleep(waitAfter))
			if($options.focusBrowser && $options.switchBack){
				let $browser=context.rpaBrowser;
				if($browser){
					await $browser.backToApp();
				}
			}
		}catch(error){
			/*#{1JGJRU92E0ErrorCode*/
			/*}#1JGJRU92E0ErrorCode*/
		}
		return {seg:BackToApp_1,result:(result),preSeg:"1JGJRU92E0",outlet:"1JGJRU92E3"};
	};
	ActivePage_1.jaxId="1JGJRU92E0"
	ActivePage_1.url="ActivePage_1@"+agentURL
	
	segs["BackToApp_1"]=BackToApp_1=async function(input){//:1JGJRUH630
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JGJRUH630ErrorCode*/
			/*}#1JGJRUH630ErrorCode*/
		}
		return {seg:CheckAgain_1,result:(result),preSeg:"1JGJRUH630",outlet:"1JGJRUH633"};
	};
	BackToApp_1.jaxId="1JGJRUH630"
	BackToApp_1.url="BackToApp_1@"+agentURL
	
	segs["NeedLoginNotice"]=NeedLoginNotice=async function(input){//:1JGJRUPFB0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("检测到您尚未登录，请先登录。"):("You are not logged in yet. Please log in first."));
		session.addChatText(role,content,opts);
		return {seg:CheckAgain_1,result:(result),preSeg:"1JGJRUPFB0",outlet:"1JGJS0D110"};
	};
	NeedLoginNotice.jaxId="1JGJRUPFB0"
	NeedLoginNotice.url="NeedLoginNotice@"+agentURL
	
	segs["CheckAgain_1"]=CheckAgain_1=async function(input){//:1JGJRVTDC0
		let result=input;
		return {seg:FindLoginBtn,result:result,preSeg:"1JAQDDK940",outlet:"1JGJRVTDC1"};
	
	};
	CheckAgain_1.jaxId="1JAQDDK940"
	CheckAgain_1.url="CheckAgain_1@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"RedNoteLogin",
		url:agentURL,
		autoStart:true,
		jaxId:"1HDBOSUN90",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1HDBOSUN90PreEntry*/
			/*}#1HDBOSUN90PreEntry*/
			result={seg:OpenPage,"input":input};
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
//#CodyExport<<<
/*#{1HDBOSUN90PostDoc*/
/*}#1HDBOSUN90PostDoc*/


export default RedNoteLogin;
export{RedNoteLogin};
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
//		"entry": "OpenPage",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IH2869AD0",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1HDBOSUNA2",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1HDBOSUNA3",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1HDIJB7SK6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1IH28H5RP0",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "95",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH28I25C0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH28I25C1",
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
//							"jaxId": "1IH28I25B0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH28HPRB0"
//						},
//						"catchlet": {
//							"jaxId": "1IH28I25C2",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1IH28I25C3",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1IH28I25C4",
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
//					"jaxId": "1IH28HPRB0",
//					"attrs": {
//						"id": "OpenBrowser",
//						"viewName": "",
//						"label": "",
//						"x": "300",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH28I25C5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH28I25C6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"alias": "RPAHOME",
//						"headless": "false",
//						"devtools": "false",
//						"dataDir": "false",
//						"outlet": {
//							"jaxId": "1IH28I25B1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"run": "",
//						"errorSeg": ""
//					},
//					"icon": "web.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1IH28P38Q0",
//					"attrs": {
//						"id": "OpenPage",
//						"viewName": "",
//						"label": "",
//						"x": "535",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH28P9U10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH28P9U11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "https://www.xiaohongshu.com",
//						"vpWidth": "1200",
//						"vpHeight": "900",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1IH28P9TV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH28Q6DB0"
//						},
//						"run": "",
//						"errorSeg": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IH28Q6DB0",
//					"attrs": {
//						"id": "Notify",
//						"viewName": "",
//						"label": "",
//						"x": "760",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH28R1BC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH28R1BC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "RedNote has been opened.",
//							"localize": {
//								"EN": "RedNote has been opened.",
//								"CN": "小红书已打开。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IH28R1BB0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAQDDK940"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1JAQDDK940",
//					"attrs": {
//						"id": "FindLoginBtn",
//						"viewName": "",
//						"label": "",
//						"x": "975",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQDH9ME0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQDH9ME1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"node": "",
//						"query": "(//li[@class=\"user side-bar-component\"])",
//						"queryHint": "",
//						"multi": "false",
//						"options": "",
//						"errorSeg": "",
//						"waitBefore": "500",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JAQDH9MB0",
//							"attrs": {
//								"id": "Find",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1JAQDDK8J0",
//									"attrs": {
//										"id": "Missing",
//										"desc": "输出节点。"
//									},
//									"linkedSeg": "1JAQDFJII0"
//								}
//							]
//						}
//					},
//					"icon": "/@aae/assets/wait_find.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaActivePage",
//					"jaxId": "1JAQDFJII0",
//					"attrs": {
//						"id": "ActivePage",
//						"viewName": "",
//						"label": "",
//						"x": "1220",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQDH9ME2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQDH9ME3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true}",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JAQDH9MB1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAQDGC4G0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaFlagWait",
//					"jaxId": "1JAQDGC4G0",
//					"attrs": {
//						"id": "FlagLogin",
//						"viewName": "",
//						"label": "",
//						"x": "1435",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQDH9ME4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQDH9ME5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Query",
//						"flag": "$WaitFlag",
//						"query": "(//li[@class=\"user side-bar-component\"])",
//						"queryHint": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JAQDH9MB2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJRRPBP0"
//						}
//					},
//					"icon": "/@aae/assets/wait_flag.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JAQDHJ0S0",
//					"attrs": {
//						"id": "AskLogin",
//						"viewName": "",
//						"label": "",
//						"x": "1620",
//						"y": "840",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQDJ9A70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQDJ9A71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JAQDI88I0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JAQDNSL10"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JAQDLCK50",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JAQDLCK90",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JAQDLCK91",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!result"
//									},
//									"linkedSeg": "1JAQDJLQT0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JAQDJLQT0",
//					"attrs": {
//						"id": "AwaitLogin",
//						"viewName": "",
//						"label": "",
//						"x": "1860",
//						"y": "785",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQDLCK92",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQDLCK93",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JAQDLCK52",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAQDKOJ30"
//						},
//						"catchlet": {
//							"jaxId": "1JAQDLCK51",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "/@aae/assets/wait_await.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JAQDKOJ30",
//					"attrs": {
//						"id": "BackToApp",
//						"viewName": "",
//						"label": "",
//						"x": "2080",
//						"y": "770",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQDLCK94",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQDLCK95",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JAQDLCK53",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAQDMR3T0"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JAQDMR3T0",
//					"attrs": {
//						"id": "CheckAgain",
//						"viewName": "",
//						"label": "",
//						"x": "2320",
//						"y": "770",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JAQDDK940",
//						"outlet": {
//							"jaxId": "1JAQDPCLQ0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "arrowupright.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JAQDNSL10",
//					"attrs": {
//						"id": "AbortBack",
//						"viewName": "",
//						"label": "",
//						"x": "1860",
//						"y": "880",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQDPCLV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQDPCLV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JAQDPCLQ1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAQDO7VO0"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaClosePage",
//					"jaxId": "1JAQDO7VO0",
//					"attrs": {
//						"id": "AbortPage",
//						"viewName": "",
//						"label": "",
//						"x": "2095",
//						"y": "880",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQDPCLV2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQDPCLV3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JAQDPCLR0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAQDOTHU0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JAQDOTHU0",
//					"attrs": {
//						"id": "AbortLogin",
//						"viewName": "",
//						"label": "",
//						"x": "2330",
//						"y": "880",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQDPCM00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQDPCM01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JAQDPCLR1",
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
//					"def": "askConfirm",
//					"jaxId": "1JGJRRPBP0",
//					"attrs": {
//						"id": "RedNoteLoginConfirm",
//						"viewName": "",
//						"label": "",
//						"x": "1660",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Login?",
//							"localize": {
//								"EN": "Login?",
//								"CN": "是否登录？"
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JGJRRPB80",
//									"attrs": {
//										"id": "Ok",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Logged in",
//											"localize": {
//												"EN": "Logged in",
//												"CN": "已登录"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGJRTQN50",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGJRTQN51",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JGJRU92E0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JGJRRPB81",
//									"attrs": {
//										"id": "Cancel",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Not logged in",
//											"localize": {
//												"EN": "Not logged in",
//												"CN": "未登录"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGJRTQN52",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGJRTQN53",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JGJRUPFB0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaActivePage",
//					"jaxId": "1JGJRU92E0",
//					"attrs": {
//						"id": "ActivePage_1",
//						"viewName": "",
//						"label": "",
//						"x": "1940",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGJRU92E1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGJRU92E2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true}",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JGJRU92E3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJRUH630"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JGJRUH630",
//					"attrs": {
//						"id": "BackToApp_1",
//						"viewName": "",
//						"label": "",
//						"x": "2180",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGJRUH631",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGJRUH632",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JGJRUH633",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJRVTDC0"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JGJRUPFB0",
//					"attrs": {
//						"id": "NeedLoginNotice",
//						"viewName": "",
//						"label": "",
//						"x": "2045",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGJS0D140",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGJS0D141",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "You are not logged in yet. Please log in first.",
//							"localize": {
//								"EN": "You are not logged in yet. Please log in first.",
//								"CN": "检测到您尚未登录，请先登录。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JGJS0D110",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJRVTDC0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JGJRVTDC0",
//					"attrs": {
//						"id": "CheckAgain_1",
//						"viewName": "",
//						"label": "",
//						"x": "2480",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JAQDDK940",
//						"outlet": {
//							"jaxId": "1JGJRVTDC1",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "arrowupright.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI代理。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}