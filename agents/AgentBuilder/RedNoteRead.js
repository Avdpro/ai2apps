//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1JBC9KUBF0MoreImports*/
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*}#1JBC9KUBF0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
/*#{1JBC9KUBF0StartDoc*/
/*}#1JBC9KUBF0StartDoc*/
//----------------------------------------------------------------------------
let rednoteRead=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let ReadUrl,OpenPage,ReadPage,ClosePage,LoopReadLinks,CheckRefresh_1,AskVerify,CheckAgain,Wait,End,ShowPage,Tips,VerfiyAgain,ShowError;
	/*#{1JBC9KUBF0LocalVals*/
	/*}#1JBC9KUBF0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1JBC9KUBF0ParseArgs*/
		/*}#1JBC9KUBF0ParseArgs*/
	}
	
	/*#{1JBC9KUBF0PreContext*/
	/*}#1JBC9KUBF0PreContext*/
	context={
		pageArticles: [],
		links: [],
		/*#{1JBC9KUBF5ExCtxAttrs*/
		/*}#1JBC9KUBF5ExCtxAttrs*/
	};
	/*#{1JBC9KUBF0PostContext*/
	/*}#1JBC9KUBF0PostContext*/
	let $agent,agent,segs={};
	segs["ReadUrl"]=ReadUrl=async function(input){//:1JBCAFG9K0
		let result=input;
		let list=input.finds;
		let i,n,item,loopR;
		/*#{1JBCAFG9K0PreLoop*/
		//result = input.finds;
		context.links = input.finds;
		/*}#1JBCAFG9K0PreLoop*/
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			/*#{1JBCAFG9K0InLoopPre*/
			/*}#1JBCAFG9K0InLoopPre*/
			loopR=await session.runAISeg(agent,OpenPage,item,"1JBCAFG9K0","1JBCAFR382")
			if(loopR==="break"){
				break;
			}
			/*#{1JBCAFG9K0InLoopPost*/
			/*}#1JBCAFG9K0InLoopPost*/
		}
		/*#{1JBCAFG9K0PostCodes*/
		/*}#1JBCAFG9K0PostCodes*/
		return {seg:End,result:(result),preSeg:"1JBCAFG9K0",outlet:"1JBCAFR330"};
	};
	ReadUrl.jaxId="1JBCAFG9K0"
	ReadUrl.url="ReadUrl@"+agentURL
	
	segs["OpenPage"]=OpenPage=async function(input){//:1JBCAGK3A0
		let pageVal="aaPage";
		let $url=input.url;
		let $waitBefore=0;
		let $waitAfter=2500;
		let $width=1200;
		let $height=900;
		let $userAgent="";
		let $timeout=(undefined)||0;
		let page=null;
		let $openOpts={timeout:$timeout};
		$waitBefore && (await sleep($waitBefore));
		/*#{1JBCAGK3A0PreCodes*/
		context.rpaBrowser = globalContext.rpaBrowser;
		context.webRpa = globalContext.webRpa;
		/*}#1JBCAGK3A0PreCodes*/
		context[pageVal]=page=await context.rpaBrowser.newPage();
		($width && $height) && (await page.setViewport({width:$width,height:$height}));
		$userAgent && (await page.setUserAgent($userAgent));
		await page.goto($url,$openOpts);
		$waitAfter && (await sleep($waitAfter));
		/*#{1JBCAGK3A0PostCodes*/
		/*}#1JBCAGK3A0PostCodes*/
		return {seg:Wait,result:(true),preSeg:"1JBCAGK3A0",outlet:"1JBCAHRKC0"};
	};
	OpenPage.jaxId="1JBCAGK3A0"
	OpenPage.url="OpenPage@"+agentURL
	
	segs["ReadPage"]=ReadPage=async function(input){//:1JBCBK3D70
		let result=null;
		let pageVal="aaPage";
		let $node=null;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $target="article";
		$waitBefore && (await sleep($waitBefore));
		/*#{1JBCBK3D70PreCodes*/
		/*}#1JBCBK3D70PreCodes*/
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
		/*#{1JBCBK3D70PostCodes*/
		context.pageArticles.push(result);
		/*}#1JBCBK3D70PostCodes*/
		return {seg:ClosePage,result:(result),preSeg:"1JBCBK3D70",outlet:"1JBCBLIU80"};
	};
	ReadPage.jaxId="1JBCBK3D70"
	ReadPage.url="ReadPage@"+agentURL
	
	segs["ClosePage"]=ClosePage=async function(input){//:1JBCC5FKP0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=300;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		await page.close();
		context[pageVal]=null;
		waitAfter && (await sleep(waitAfter))
		return {result:result};
	};
	ClosePage.jaxId="1JBCC5FKP0"
	ClosePage.url="ClosePage@"+agentURL
	
	segs["LoopReadLinks"]=LoopReadLinks=async function(input){//:1JBORGRT10
		let result=input
		/*#{1JBORGRT10Code*/
		context.rpaBrowser = globalContext.rpaBrowser;
		context.webRpa = globalContext.webRpa;
		const CONCURRENCY = 5;
		async function fetchArticles(list) {
			const browser = context.rpaBrowser;
			const chunks = [];
			for (let i = 0; i < list.length; i += CONCURRENCY) {
				const slice = list.slice(i, i + CONCURRENCY);
				const batch = await Promise.all(
					slice.map(async (item) => {
						const page = await browser.newPage();
						try {
							const key = item.url;
							await page.goto(key, { waitUntil: 'domcontentloaded', timeout: 15000 });
							const content = await context.webRpa.readArticle(page, null, {
								removeHidden: false,
								timeout: 8000
							});
							return {
								key,                                    
								content,               
								platform: 'rednote',
								time: item.time,
								author: item.author,
								likes: item.likes,           
							};
						} catch (e) {
							return { result: "Fail", key: item.url, error: e.message };
						}finally {
							await page.close();
						}
					})
				);
				chunks.push(...batch);
			}
			console.log("!!!!! chunks",chunks);
			return chunks.filter(item => item.content && item.content.trim() !== '' && !item.error);
		}
		const arr = await fetchArticles(context.links);
		console.log("!!!!! arr",arr);
		result = arr;
		/*}#1JBORGRT10Code*/
		return {result:result};
	};
	LoopReadLinks.jaxId="1JBORGRT10"
	LoopReadLinks.url="LoopReadLinks@"+agentURL
	
	segs["CheckRefresh_1"]=CheckRefresh_1=async function(input){//:1JBP5UOES1
		let result=true;
		let pageVal="aaPage";
		let $node=undefined;
		let $query="(//div[@class=\"qrcode-container\"])";
		let $multi=false;
		let $options=null;
		let $waitBefore=300;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		if($multi){
			result=await context.webRpa.queryNodes(page,$node,$query,$options);
		}else{
			result=await context.webRpa.queryNode(page,$node,$query,$options);
		}
		if((!result)||($multi && !result.length)){
			$waitAfter && (await sleep($waitAfter))
			return {seg:ReadPage,result:(result),preSeg:"1JBP5UOES1",outlet:"1JBP5UOES5"};
		}else{
			$waitAfter && (await sleep($waitAfter))
			return {seg:ShowPage,result:(result),preSeg:"1JBP5UOES1",outlet:"1JBP5UOES4"};
		}
	};
	CheckRefresh_1.jaxId="1JBP5UOES1"
	CheckRefresh_1.url="CheckRefresh_1@"+agentURL
	
	segs["AskVerify"]=AskVerify=async function(input){//:1JBP61K950
		let prompt=((($ln==="CN")?("请扫码"):("Please scan the QR code")))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=((($ln==="CN")?("已扫码"):("Scanned")))||"OK";
		let button2=((($ln==="CN")?("未扫码"):("Not scanned")))||"Cancel";
		let button3="";
		let result="";
		let value=0;
		if(silent){
			result="";
			return {seg:CheckAgain,result:(result),preSeg:"1JBP61K950",outlet:"1JBP61K8J0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			return {seg:CheckAgain,result:(result),preSeg:"1JBP61K950",outlet:"1JBP61K8J0"};
		}
		result=("")||result;
		return {seg:Tips,result:(result),preSeg:"1JBP61K950",outlet:"1JBP61K8J1"};
	
	};
	AskVerify.jaxId="1JBP61K950"
	AskVerify.url="AskVerify@"+agentURL
	
	segs["CheckAgain"]=CheckAgain=async function(input){//:1JBP6BHP00
		let result=true;
		let pageVal="aaPage";
		let $node=undefined;
		let $query="(//div[@id=\"noteContainer\"])";
		let $multi=false;
		let $options=null;
		let $waitBefore=300;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		if($multi){
			result=await context.webRpa.queryNodes(page,$node,$query,$options);
		}else{
			result=await context.webRpa.queryNode(page,$node,$query,$options);
		}
		if((!result)||($multi && !result.length)){
			$waitAfter && (await sleep($waitAfter))
			return {seg:AskVerify,result:(result),preSeg:"1JBP6BHP00",outlet:"1JBP6BHOE0"};
		}else{
			$waitAfter && (await sleep($waitAfter))
			return {result:result};
		}
	};
	CheckAgain.jaxId="1JBP6BHP00"
	CheckAgain.url="CheckAgain@"+agentURL
	
	segs["Wait"]=Wait=async function(input){//:1JC330T4G0
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $waitBefore=0;
		let $waitAfter=100;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		try{
			result=await context[$flag];
		}catch(error){
			return {seg:ShowError,result:(error),preSeg:"1JC330T4G0",outlet:"1JC3311T90"};
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:CheckRefresh_1,result:(result),preSeg:"1JC330T4G0",outlet:"1JC3311T91"};
	};
	Wait.jaxId="1JC330T4G0"
	Wait.url="Wait@"+agentURL
	
	segs["End"]=End=async function(input){//:1JC33DU010
		let result=input
		/*#{1JC33DU010Code*/
		const arr1 = input.finds;
		const arr2 = context.pageArticles;
		const out = arr1.map((item, idx) => {
			const raw = arr2[idx] || '';
			//const content = raw.replace(/^\[小红书\]\(\)\n\n# .+? - 小红书\n\n/, '') .trim();
			return {
				key: item.url,
				content: raw,
				title: item.title,
				platform: 'rednote',
				time: item.time,
				author: item.author,
				likes: item.likes,
			}
		});
		result = out;
		/*}#1JC33DU010Code*/
		return {result:result};
	};
	End.jaxId="1JC33DU010"
	End.url="End@"+agentURL
	
	segs["ShowPage"]=ShowPage=async function(input){//:1JC33GGP00
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=100;
		let $options={"focusBrowser":true};
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		await page.bringToFront($options);
		waitAfter && (await sleep(waitAfter))
		return {seg:AskVerify,result:(result),preSeg:"1JC33GGP00",outlet:"1JC33IJN30"};
	};
	ShowPage.jaxId="1JC33GGP00"
	ShowPage.url="ShowPage@"+agentURL
	
	segs["Tips"]=Tips=async function(input){//:1JCO1R9C40
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("检测到您尚未扫码，请先扫码。"):("No scan detected. Please scan first."));
		session.addChatText(role,content,opts);
		return {seg:VerfiyAgain,result:(result),preSeg:"1JCO1R9C40",outlet:"1JCO1TSL50"};
	};
	Tips.jaxId="1JCO1R9C40"
	Tips.url="Tips@"+agentURL
	
	segs["VerfiyAgain"]=VerfiyAgain=async function(input){//:1JCO1UU4H0
		let result=input;
		return {seg:AskVerify,result:result,preSeg:"1JBP61K950",outlet:"1JCO1VL050"};
	
	};
	VerfiyAgain.jaxId="1JBP61K950"
	VerfiyAgain.url="VerfiyAgain@"+agentURL
	
	segs["ShowError"]=ShowError=async function(input){//:1JCQAE3U70
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("发生错误，请重试。"):("An error occurred, please try again."));
		session.addChatText(role,content,opts);
		return {result:result};
	};
	ShowError.jaxId="1JCQAE3U70"
	ShowError.url="ShowError@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"rednoteRead",
		url:agentURL,
		autoStart:true,
		jaxId:"1JBC9KUBF0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1JBC9KUBF0PreEntry*/
			/*}#1JBC9KUBF0PreEntry*/
			result={seg:ReadUrl,"input":input};
			/*#{1JBC9KUBF0PostEntry*/
			/*}#1JBC9KUBF0PostEntry*/
			return result;
		},
		/*#{1JBC9KUBF0MoreAgentAttrs*/
		/*}#1JBC9KUBF0MoreAgentAttrs*/
	};
	/*#{1JBC9KUBF0PostAgent*/
	/*}#1JBC9KUBF0PostAgent*/
	return agent;
};
/*#{1JBC9KUBF0ExCodes*/
/*}#1JBC9KUBF0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1JBC9KUBF0PostDoc*/
/*}#1JBC9KUBF0PostDoc*/


export default rednoteRead;
export{rednoteRead};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JBC9KUBF0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JBC9KUBF1",
//			"attrs": {
//				"baiduRead": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JBC9KUBF7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JBC9KUBF8",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JBC9KUBF9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JBC9KUBF10",
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
//			"jaxId": "1JBC9KUBF2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "ReadUrl",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JBC9KUBF3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1JBC9KUBF4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JBC9KUBF5",
//			"attrs": {
//				"pageArticles": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JBCCBN1U0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				},
//				"links": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JBP5NU0C0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1JBC9KUBF6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1JBCAFG9K0",
//					"attrs": {
//						"id": "ReadUrl",
//						"viewName": "",
//						"label": "",
//						"x": "195",
//						"y": "80",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBCAFR380",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBCAFR381",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input.finds",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1JBCAFR382",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBCAGK3A0"
//						},
//						"catchlet": {
//							"jaxId": "1JBCAFR330",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC33DU010"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1JBCAGK3A0",
//					"attrs": {
//						"id": "OpenPage",
//						"viewName": "",
//						"label": "",
//						"x": "400",
//						"y": "65",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBCAHRKG0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBCAHRKG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "#input.url",
//						"vpWidth": "1200",
//						"vpHeight": "900",
//						"userAgent": "",
//						"waitBefore": "",
//						"waitAfter": "2500",
//						"outlet": {
//							"jaxId": "1JBCAHRKC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC330T4G0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1JBCBK3D70",
//					"attrs": {
//						"id": "ReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "1035",
//						"y": "110",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBCBLIUB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBCBLIUB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"target": "Article",
//						"node": "null",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "",
//						"outlet": {
//							"jaxId": "1JBCBLIU80",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBCC5FKP0"
//						},
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaClosePage",
//					"jaxId": "1JBCC5FKP0",
//					"attrs": {
//						"id": "ClosePage",
//						"viewName": "",
//						"label": "",
//						"x": "1285",
//						"y": "110",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBCC5T9J0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBCC5T9J1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "300",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JBCC5T9F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JBORGRT10",
//					"attrs": {
//						"id": "LoopReadLinks",
//						"viewName": "",
//						"label": "",
//						"x": "210",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBORH9G80",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBORH9G81",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JBORH9G50",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1JBP5UOES1",
//					"attrs": {
//						"id": "CheckRefresh_1",
//						"viewName": "",
//						"label": "",
//						"x": "780",
//						"y": "50",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBP5UOES2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBP5UOES3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"node": "",
//						"query": "(//div[@class=\"qrcode-container\"])",
//						"queryHint": "",
//						"multi": "false",
//						"options": "null",
//						"waitBefore": "300",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JBP5UOES4",
//							"attrs": {
//								"id": "Found",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC33GGP00"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1JBP5UOES5",
//									"attrs": {
//										"id": "Missing",
//										"desc": "输出节点。"
//									},
//									"linkedSeg": "1JBCBK3D70"
//								}
//							]
//						}
//					},
//					"icon": "/@aae/assets/wait_find.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askConfirm",
//					"jaxId": "1JBP61K950",
//					"attrs": {
//						"id": "AskVerify",
//						"viewName": "",
//						"label": "",
//						"x": "1285",
//						"y": "35",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Please scan the QR code",
//							"localize": {
//								"EN": "Please scan the QR code",
//								"CN": "请扫码"
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JBP61K8J0",
//									"attrs": {
//										"id": "Verfiy",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Scanned",
//											"localize": {
//												"EN": "Scanned",
//												"CN": "已扫码"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JBP641DL0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JBP641DL1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JBP6BHP00"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JBP61K8J1",
//									"attrs": {
//										"id": "Cancel",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Not scanned",
//											"localize": {
//												"EN": "Not scanned",
//												"CN": "未扫码"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JBP641DL2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JBP641DL3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JCO1R9C40"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1JBP6BHP00",
//					"attrs": {
//						"id": "CheckAgain",
//						"viewName": "",
//						"label": "",
//						"x": "1495",
//						"y": "20",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBP6D9KJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBP6D9KJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"node": "",
//						"query": "(//div[@id=\"noteContainer\"])",
//						"queryHint": "",
//						"multi": "false",
//						"options": "null",
//						"waitBefore": "300",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JBP6D9KC0",
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
//									"jaxId": "1JBP6BHOE0",
//									"attrs": {
//										"id": "Missing",
//										"desc": "输出节点。"
//									},
//									"linkedSeg": "1JBP6ERG00"
//								}
//							]
//						}
//					},
//					"icon": "/@aae/assets/wait_find.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JBP6ERG00",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1655",
//						"y": "-65",
//						"outlet": {
//							"jaxId": "1JBP6H8ET0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBP6F68V0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JBP6F68V0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1310",
//						"y": "-65",
//						"outlet": {
//							"jaxId": "1JBP6H8ET1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBP61K950"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JC330T4G0",
//					"attrs": {
//						"id": "Wait",
//						"viewName": "",
//						"label": "",
//						"x": "610",
//						"y": "65",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC3311TB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC3311TB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "100",
//						"outlet": {
//							"jaxId": "1JC3311T91",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBP5UOES1"
//						},
//						"catchlet": {
//							"jaxId": "1JC3311T90",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JCQAE3U70"
//						}
//					},
//					"icon": "/@aae/assets/wait_await.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JC33DU010",
//					"attrs": {
//						"id": "End",
//						"viewName": "",
//						"label": "",
//						"x": "400",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC33FCS00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC33FCS01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JC33EAGB0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaActivePage",
//					"jaxId": "1JC33GGP00",
//					"attrs": {
//						"id": "ShowPage",
//						"viewName": "",
//						"label": "",
//						"x": "1030",
//						"y": "35",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC33IJN90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC33IJN91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true}",
//						"waitBefore": "0",
//						"waitAfter": "100",
//						"outlet": {
//							"jaxId": "1JC33IJN30",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBP61K950"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JCO1R9C40",
//					"attrs": {
//						"id": "Tips",
//						"viewName": "",
//						"label": "",
//						"x": "1525",
//						"y": "110",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCO1TSLA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCO1TSLA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "No scan detected. Please scan first.",
//							"localize": {
//								"EN": "No scan detected. Please scan first.",
//								"CN": "检测到您尚未扫码，请先扫码。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JCO1TSL50",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JCO1UU4H0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JCO1UU4H0",
//					"attrs": {
//						"id": "VerfiyAgain",
//						"viewName": "",
//						"label": "",
//						"x": "1710",
//						"y": "110",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JBP61K950",
//						"outlet": {
//							"jaxId": "1JCO1VL050",
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
//					"def": "output",
//					"jaxId": "1JCQAE3U70",
//					"attrs": {
//						"id": "ShowError",
//						"viewName": "",
//						"label": "",
//						"x": "815",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCQAFHDL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCQAFHDL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "An error occurred, please try again.",
//							"localize": {
//								"EN": "An error occurred, please try again.",
//								"CN": "发生错误，请重试。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JCQAFHDG0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}