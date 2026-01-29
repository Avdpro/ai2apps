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
let articleRead=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let ShowProcess,ReadUrl,OpenPage,ReadPage,ClosePage,ShowReadRes,LoopReadLinks,ShowRes;
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
		/*#{1JBC9KUBF5ExCtxAttrs*/
		/*}#1JBC9KUBF5ExCtxAttrs*/
	};
	/*#{1JBC9KUBF0PostContext*/
	/*}#1JBC9KUBF0PostContext*/
	let $agent,agent,segs={};
	segs["ShowProcess"]=ShowProcess=async function(input){//:1JBCBBN5G0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("正在读取内容，请稍等..."):("Loading content, please wait..."));
		/*#{1JBCBBN5G0PreCodes*/
		/*}#1JBCBBN5G0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JBCBBN5G0PostCodes*/
		result = input.finds;
		/*}#1JBCBBN5G0PostCodes*/
		return {result:result};
	};
	ShowProcess.jaxId="1JBCBBN5G0"
	ShowProcess.url="ShowProcess@"+agentURL
	
	segs["ReadUrl"]=ReadUrl=async function(input){//:1JBCAFG9K0
		let result=input;
		let list=input;
		let i,n,item,loopR;
		/*#{1JBCAFG9K0PreLoop*/
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
		return {seg:ShowReadRes,result:(result),preSeg:"1JBCAFG9K0",outlet:"1JBCAFR330"};
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
		return {seg:ReadPage,result:(true),preSeg:"1JBCAGK3A0",outlet:"1JBCAHRKC0"};
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
		return {result:result};
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
	
	segs["ShowReadRes"]=ShowReadRes=async function(input){//:1JBCCN4QK0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content="";
		/*#{1JBCCN4QK0PreCodes*/
		const arr1 = input;
		const arr2 = context.pageArticles;
		const out = arr1.map((item, idx) => {
			const raw = arr2[idx] || '';
			return {
				key: item.url,
				content: raw,
				platform: item?.platform,
			}
		});
			content = `
		\`\`\`
			${JSON.stringify(out,null,"\t")}
		\`\`\`
		` ;
		/*}#1JBCCN4QK0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JBCCN4QK0PostCodes*/
		result = out;
		/*}#1JBCCN4QK0PostCodes*/
		return {result:result};
	};
	ShowReadRes.jaxId="1JBCCN4QK0"
	ShowReadRes.url="ShowReadRes@"+agentURL
	
	segs["LoopReadLinks"]=LoopReadLinks=async function(input){//:1JBP2AL4N0
		let result=input
		try{
			/*#{1JBP2AL4N0Code*/
			context.rpaBrowser = globalContext.rpaBrowser;
			context.webRpa = globalContext.webRpa;
			const CONCURRENCY = 10;
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
								const platform = item.platform;
			await page.goto(key, { waitUntil: 'domcontentloaded', timeout: 15000 });
								const content = await context.webRpa.readArticle(page, null, {
									removeHidden: false,
									timeout: 8000
								});
								return {
									key,    
									title: item.title,
									content,               
									platform,
								};
							} catch (e) {
								return { result: "Fail", key: item.url, platform:item.platform, error: e.message };
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
			const arr = await fetchArticles(input?.finds);
			console.log("!!!!! arr",arr);
			result = arr;
			/*}#1JBP2AL4N0Code*/
		}catch(error){
			/*#{1JBP2AL4N0ErrorCode*/
			/*}#1JBP2AL4N0ErrorCode*/
		}
		return {result:result};
	};
	LoopReadLinks.jaxId="1JBP2AL4N0"
	LoopReadLinks.url="LoopReadLinks@"+agentURL
	
	segs["ShowRes"]=ShowRes=async function(input){//:1JBP2B0PT0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=`
  \`\`\`
        ${JSON.stringify(input,null,"\t")}
   \`\`\`
` ;
		/*#{1JBP2B0PT0PreCodes*/
		/*}#1JBP2B0PT0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JBP2B0PT0PostCodes*/
		/*}#1JBP2B0PT0PostCodes*/
		return {result:result};
	};
	ShowRes.jaxId="1JBP2B0PT0"
	ShowRes.url="ShowRes@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"articleRead",
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
			result={seg:LoopReadLinks,"input":input};
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


export default articleRead;
export{articleRead};
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
//		"entry": "LoopReadLinks",
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
//					"def": "output",
//					"jaxId": "1JBCBBN5G0",
//					"attrs": {
//						"id": "ShowProcess",
//						"viewName": "",
//						"label": "",
//						"x": "20",
//						"y": "430",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBCBC0FD0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBCBC0FD1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Loading content, please wait...",
//							"localize": {
//								"EN": "Loading content, please wait...",
//								"CN": "正在读取内容，请稍等..."
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JBCBC0F80",
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
//					"def": "loopArray",
//					"jaxId": "1JBCAFG9K0",
//					"attrs": {
//						"id": "ReadUrl",
//						"viewName": "",
//						"label": "",
//						"x": "265",
//						"y": "250",
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
//						"loopArray": "#input",
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
//							"linkedSeg": "1JBCCN4QK0"
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
//						"x": "510",
//						"y": "235",
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
//							"linkedSeg": "1JBCBK3D70"
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
//						"x": "725",
//						"y": "235",
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
//							}
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
//						"x": "935",
//						"y": "235",
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
//					"def": "output",
//					"jaxId": "1JBCCN4QK0",
//					"attrs": {
//						"id": "ShowReadRes",
//						"viewName": "",
//						"label": "",
//						"x": "510",
//						"y": "295",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBCCO3S70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBCCO3S71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "",
//						"outlet": {
//							"jaxId": "1JBCCO3S30",
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
//					"def": "code",
//					"jaxId": "1JBP2AL4N0",
//					"attrs": {
//						"id": "LoopReadLinks",
//						"viewName": "",
//						"label": "",
//						"x": "240",
//						"y": "430",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBP2BJQR0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBP2BJQR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JBP2BJQO0",
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
//					"def": "output",
//					"jaxId": "1JBP2B0PT0",
//					"attrs": {
//						"id": "ShowRes",
//						"viewName": "",
//						"label": "",
//						"x": "495",
//						"y": "430",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBP2BJQR2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBP2BJQR3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#`\n  \\`\\`\\`\n        ${JSON.stringify(input,null,\"\\t\")}\n   \\`\\`\\`\n` ",
//						"outlet": {
//							"jaxId": "1JBP2BJQP0",
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