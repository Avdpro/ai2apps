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
let TwitterLogin=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Start,OpenBrowser,OpenPage,Notify,FindTwitterLoginBtn,ActivePage,FlagLogin,TwitterLoginConfirm,BackToApp,NeedLoginNotice,CheckAgain,ActivePage_1,FindTwitterLoginBtn_1;
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
		try{
			context.rpaBrowser=browser=await context.webRpa.openBrowser(alias,options);
			context.rpaHostPage=browser.hostPage;
		
		}catch(error){
			/*#{1IH28HPRB0ErrorCode*/
			/*}#1IH28HPRB0ErrorCode*/
		}
		return {result:result};
	};
	OpenBrowser.jaxId="1IH28HPRB0"
	OpenBrowser.url="OpenBrowser@"+agentURL
	
	segs["OpenPage"]=OpenPage=async function(input){//:1IH28P38Q0
		let pageVal="aaPage";
		let $url="https://x.com/";
		let $waitBefore=0;
		let $waitAfter=1000;
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
		context.comments = input.comments;
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
		let content=(($ln==="CN")?("推特页面已打开，AI 正在执行联网搜索任务......"):("Twitter page has been opened, AI is performing a web search task......"));
		session.addChatText(role,content,opts);
		return {seg:FindTwitterLoginBtn,result:(result),preSeg:"1IH28Q6DB0",outlet:"1IH28R1BB0"};
	};
	Notify.jaxId="1IH28Q6DB0"
	Notify.url="Notify@"+agentURL
	
	segs["FindTwitterLoginBtn"]=FindTwitterLoginBtn=async function(input){//:1JAQFTV110
		let result=true;
		let pageVal="aaPage";
		let $node=undefined;
		let $query="(//button[@data-testid='SideNav_AccountSwitcher_Button'])";
		let $multi=false;
		let $options=undefined;
		let $waitBefore=1000;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		try{
			if($multi){
				result=await context.webRpa.queryNodes(page,$node,$query,$options);
			}else{
				result=await context.webRpa.queryNode(page,$node,$query,$options);
			}
			if((!result)||($multi && !result.length)){
				throw "Querry not found";
			}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JAQFTV110ErrorCode*/
			/*}#1JAQFTV110ErrorCode*/
			return {seg:ActivePage,result:error,preSeg:"1JAQFTV110",outlet:"1JAQFTV0C0"};
		}
		return {result:result};
	};
	FindTwitterLoginBtn.jaxId="1JAQFTV110"
	FindTwitterLoginBtn.url="FindTwitterLoginBtn@"+agentURL
	
	segs["ActivePage"]=ActivePage=async function(input){//:1JAQFV8EG0
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
			/*#{1JAQFV8EG0ErrorCode*/
			/*}#1JAQFV8EG0ErrorCode*/
		}
		return {seg:FlagLogin,result:(result),preSeg:"1JAQFV8EG0",outlet:"1JAQFVN1H0"};
	};
	ActivePage.jaxId="1JAQFV8EG0"
	ActivePage.url="ActivePage@"+agentURL
	
	segs["FlagLogin"]=FlagLogin=async function(input){//:1JAQG03H10
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $query="(//button[@data-testid='SideNav_AccountSwitcher_Button'])";
		let $queryHint="";
		let $waitBefore=0;
		let $waitAfter=500;
		let $options={};
		let $timeout=undefined;
		let page=context[pageVal];
		let $args=[];
		
		if($timeout){$options.timeout=$timeout;}
		$waitBefore && (await sleep($waitBefore));
		$query=$queryHint?(await page.confirmQuery($query,$queryHint,"1JAQG03H10")):$query;
		if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
		context[$flag]=context.webRpa.waitQuery(page,$query,$options);
		$waitAfter && (await sleep($waitAfter))
		return {seg:TwitterLoginConfirm,result:(result),preSeg:"1JAQG03H10",outlet:"1JAQG0NQJ0"};
	};
	FlagLogin.jaxId="1JAQG03H10"
	FlagLogin.url="FlagLogin@"+agentURL
	
	segs["TwitterLoginConfirm"]=TwitterLoginConfirm=async function(input){//:1JAQG0UME0
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
			return {seg:ActivePage_1,result:(result),preSeg:"1JAQG0UME0",outlet:"1JAQG0ULV0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			return {seg:ActivePage_1,result:(result),preSeg:"1JAQG0UME0",outlet:"1JAQG0ULV0"};
		}
		result=("")||result;
		return {seg:NeedLoginNotice,result:(result),preSeg:"1JAQG0UME0",outlet:"1JAQG0ULV1"};
	
	};
	TwitterLoginConfirm.jaxId="1JAQG0UME0"
	TwitterLoginConfirm.url="TwitterLoginConfirm@"+agentURL
	
	segs["BackToApp"]=BackToApp=async function(input){//:1JAQG3M440
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
			/*#{1JAQG3M440ErrorCode*/
			/*}#1JAQG3M440ErrorCode*/
		}
		return {seg:CheckAgain,result:(result),preSeg:"1JAQG3M440",outlet:"1JAQG5EHK0"};
	};
	BackToApp.jaxId="1JAQG3M440"
	BackToApp.url="BackToApp@"+agentURL
	
	segs["NeedLoginNotice"]=NeedLoginNotice=async function(input){//:1JAQG4KNP0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("检测到您尚未登录，请先登录。"):("You are not logged in yet. Please log in first."));
		session.addChatText(role,content,opts);
		return {seg:CheckAgain,result:(result),preSeg:"1JAQG4KNP0",outlet:"1JAQG5EHK1"};
	};
	NeedLoginNotice.jaxId="1JAQG4KNP0"
	NeedLoginNotice.url="NeedLoginNotice@"+agentURL
	
	segs["CheckAgain"]=CheckAgain=async function(input){//:1JAQG5NQT0
		let result=input;
		return {seg:FindTwitterLoginBtn,result:result,preSeg:"1JAQFTV110",outlet:"1JAQG66O00"};
	
	};
	CheckAgain.jaxId="1JAQFTV110"
	CheckAgain.url="CheckAgain@"+agentURL
	
	segs["ActivePage_1"]=ActivePage_1=async function(input){//:1JASG0CSQ0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=500;
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
			/*#{1JASG0CSQ0ErrorCode*/
			/*}#1JASG0CSQ0ErrorCode*/
		}
		return {seg:BackToApp,result:(result),preSeg:"1JASG0CSQ0",outlet:"1JASG0CSQ3"};
	};
	ActivePage_1.jaxId="1JASG0CSQ0"
	ActivePage_1.url="ActivePage_1@"+agentURL
	
	segs["FindTwitterLoginBtn_1"]=FindTwitterLoginBtn_1=async function(input){//:1JGM7BIBL1
		let result=true;
		let pageVal="aaPage";
		let $node=undefined;
		let $query="(//a[@data-testid='loginButton'])";
		let $multi=false;
		let $options=undefined;
		let $waitBefore=1000;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		try{
			if($multi){
				result=await context.webRpa.queryNodes(page,$node,$query,$options);
			}else{
				result=await context.webRpa.queryNode(page,$node,$query,$options);
			}
			if((!result)||($multi && !result.length)){
				throw "Querry not found";
			}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JGM7BIBL1ErrorCode*/
			/*}#1JGM7BIBL1ErrorCode*/
		}
		return {result:result};
	};
	FindTwitterLoginBtn_1.jaxId="1JGM7BIBL1"
	FindTwitterLoginBtn_1.url="FindTwitterLoginBtn_1@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"TwitterLogin",
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


export default TwitterLogin;
export{TwitterLogin};
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
//						"x": "-190",
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
//						"x": "15",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
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
//						"x": "255",
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
//						"url": "https://x.com/",
//						"vpWidth": "1200",
//						"vpHeight": "900",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "1000",
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
//						"x": "475",
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
//							"valText": "Twitter page has been opened, AI is performing a web search task......",
//							"localize": {
//								"EN": "Twitter page has been opened, AI is performing a web search task......",
//								"CN": "推特页面已打开，AI 正在执行联网搜索任务......"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IH28R1BB0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAQFTV110"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1JAQFTV110",
//					"attrs": {
//						"id": "FindTwitterLoginBtn",
//						"viewName": "",
//						"label": "",
//						"x": "670",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQFUJCP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQFUJCP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"node": "",
//						"query": "(//button[@data-testid='SideNav_AccountSwitcher_Button'])",
//						"queryHint": "",
//						"multi": "false",
//						"options": "",
//						"errorSeg": "",
//						"waitBefore": "1000",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JAQFUJCO0",
//							"attrs": {
//								"id": "Found",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1JAQFTV0C0",
//									"attrs": {
//										"id": "Missing",
//										"desc": "输出节点。"
//									},
//									"linkedSeg": "1JAQFV8EG0"
//								}
//							]
//						}
//					},
//					"icon": "/@aae/assets/wait_find.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaActivePage",
//					"jaxId": "1JAQFV8EG0",
//					"attrs": {
//						"id": "ActivePage",
//						"viewName": "",
//						"label": "",
//						"x": "970",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQFVN1I0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQFVN1I1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true}",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JAQFVN1H0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAQG03H10"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaFlagWait",
//					"jaxId": "1JAQG03H10",
//					"attrs": {
//						"id": "FlagLogin",
//						"viewName": "",
//						"label": "",
//						"x": "1205",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQG0NQK0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQG0NQK1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Query",
//						"flag": "$WaitFlag",
//						"query": "(//button[@data-testid='SideNav_AccountSwitcher_Button'])",
//						"queryHint": "",
//						"waitBefore": "0",
//						"waitAfter": "500",
//						"outlet": {
//							"jaxId": "1JAQG0NQJ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAQG0UME0"
//						}
//					},
//					"icon": "/@aae/assets/wait_flag.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askConfirm",
//					"jaxId": "1JAQG0UME0",
//					"attrs": {
//						"id": "TwitterLoginConfirm",
//						"viewName": "",
//						"label": "",
//						"x": "1415",
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
//									"jaxId": "1JAQG0ULV0",
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
//											"jaxId": "1JAQG1MNA0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JAQG1MNA1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JASG0CSQ0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JAQG0ULV1",
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
//											"jaxId": "1JAQG1MNA2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JAQG1MNA3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JAQG4KNP0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JAQG3M440",
//					"attrs": {
//						"id": "BackToApp",
//						"viewName": "",
//						"label": "",
//						"x": "1910",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQG5EHL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQG5EHL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JAQG5EHK0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAQG5NQT0"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JAQG4KNP0",
//					"attrs": {
//						"id": "NeedLoginNotice",
//						"viewName": "",
//						"label": "",
//						"x": "1680",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAQG5EHL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAQG5EHL3",
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
//							"jaxId": "1JAQG5EHK1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAQG5NQT0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JAQG5NQT0",
//					"attrs": {
//						"id": "CheckAgain",
//						"viewName": "",
//						"label": "",
//						"x": "2135",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JAQFTV110",
//						"outlet": {
//							"jaxId": "1JAQG66O00",
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
//					"def": "WebRpaActivePage",
//					"jaxId": "1JASG0CSQ0",
//					"attrs": {
//						"id": "ActivePage_1",
//						"viewName": "",
//						"label": "",
//						"x": "1685",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JASG0CSQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JASG0CSQ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true}",
//						"waitBefore": "500",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JASG0CSQ3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAQG3M440"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1JGM7BIBL1",
//					"attrs": {
//						"id": "FindTwitterLoginBtn_1",
//						"viewName": "",
//						"label": "",
//						"x": "675",
//						"y": "65",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGM7BIBM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGM7BIBM1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"node": "",
//						"query": "(//a[@data-testid='loginButton'])",
//						"queryHint": "",
//						"multi": "false",
//						"options": "",
//						"errorSeg": "",
//						"waitBefore": "1000",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JGM7BIBM2",
//							"attrs": {
//								"id": "Found",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1JGM7BIBM3",
//									"attrs": {
//										"id": "Missing",
//										"desc": "输出节点。"
//									}
//								}
//							]
//						}
//					},
//					"icon": "/@aae/assets/wait_find.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI代理。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}