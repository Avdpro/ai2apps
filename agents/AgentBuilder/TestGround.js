//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IIF9SU5D0MoreImports*/
/*}#1IIF9SU5D0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
/*#{1IIF9SU5D0StartDoc*/
/*}#1IIF9SU5D0StartDoc*/
//----------------------------------------------------------------------------
let TestGround=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let InitBash,TestCommands,Bash,BashResult;
	let bash=null;
	
	/*#{1IIF9SU5D0LocalVals*/
	/*}#1IIF9SU5D0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IIF9SU5D0ParseArgs*/
		/*}#1IIF9SU5D0ParseArgs*/
	}
	
	/*#{1IIF9SU5D0PreContext*/
	/*}#1IIF9SU5D0PreContext*/
	context={};
	/*#{1IIF9SU5D0PostContext*/
	/*}#1IIF9SU5D0PostContext*/
	let agent,segs={};
	segs["InitBash"]=InitBash=async function(input){//:1IIF9U9B60
		let result;
		let sourcePath=pathLib.join(basePath,"./Bash.js");
		let arg={"bashId":"","action":"Create","commands":"","options":{client:true}};
		/*#{1IIF9U9B60Input*/
		/*}#1IIF9U9B60Input*/
		result= await session.pipeChat(sourcePath,arg,false);
		/*#{1IIF9U9B60Output*/
		bash=result;
		/*}#1IIF9U9B60Output*/
		return {seg:TestCommands,result:(result),preSeg:"1IIF9U9B60",outlet:"1IIF9V8KR0"};
	};
	InitBash.jaxId="1IIF9U9B60"
	InitBash.url="InitBash@"+agentURL
	
	segs["TestCommands"]=TestCommands=async function(input){//:1IIF9USHF0
		let result;
		let sourcePath=pathLib.join(basePath,"./Bash.js");
		let arg={"bashId":bash,"action":"Command","commands":"","options":{}};
		/*#{1IIF9USHF0Input*/
		arg.commands=[
			"ls",
			`read -p "是否继续操作？(y/n): " answer && [[ "$answer" == "y" || "$answer" == "Y" ]] && echo "继续操作..." || echo "操作已取消。"`,
			`read -p "请输入文件名以启动程序：" filename && echo "加载 $filename..." && sleep 2 && echo "文件格式不支持。"`
		];
		/*}#1IIF9USHF0Input*/
		result= await session.pipeChat(sourcePath,arg,false);
		/*#{1IIF9USHF0Output*/
		/*}#1IIF9USHF0Output*/
		return {seg:BashResult,result:(result),preSeg:"1IIF9USHF0",outlet:"1IIF9V8KR1"};
	};
	TestCommands.jaxId="1IIF9USHF0"
	TestCommands.url="TestCommands@"+agentURL
	
	segs["BashResult"]=BashResult=async function(input){//:1IIFAB1MF0
		let result=input;
		let role="assistant";
		let content=`
Bash result:  
\`\`\`
${input}
\`\`\`
`;
		session.addChatText(role,content);
		return {result:result};
	};
	BashResult.jaxId="1IIFAB1MF0"
	BashResult.url="BashResult@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"TestGround",
		url:agentURL,
		autoStart:true,
		jaxId:"1IIF9SU5D0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IIF9SU5D0PreEntry*/
			/*}#1IIF9SU5D0PreEntry*/
			result={seg:InitBash,"input":input};
			/*#{1IIF9SU5D0PostEntry*/
			/*}#1IIF9SU5D0PostEntry*/
			return result;
		},
		/*#{1IIF9SU5D0MoreAgentAttrs*/
		/*}#1IIF9SU5D0MoreAgentAttrs*/
	};
	/*#{1IIF9SU5D0PostAgent*/
	/*}#1IIF9SU5D0PostAgent*/
	return agent;
};
/*#{1IIF9SU5D0ExCodes*/
/*}#1IIF9SU5D0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IIF9SU5D0PostDoc*/
/*}#1IIF9SU5D0PostDoc*/


export default TestGround;
export{TestGround};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IIF9SU5D0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IIF9SU5D1",
//			"attrs": {
//				"TestGround": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IIF9SU5D7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IIF9SU5D8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IIF9SU5D9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IIF9SU5D10",
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
//			"jaxId": "1IIF9SU5D2",
//			"attrs": {}
//		},
//		"entry": "InitBash",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IIF9SU5D3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IIF9SU5D4",
//			"attrs": {
//				"bash": {
//					"type": "auto",
//					"valText": "null"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IIF9SU5D5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IIF9SU5D6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IIF9U9B60",
//					"attrs": {
//						"id": "InitBash",
//						"viewName": "",
//						"label": "",
//						"x": "135",
//						"y": "155",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIF9V8KS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIF9V8KS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/Bash.js",
//						"argument": "{\"bashId\":\"\",\"action\":\"Create\",\"commands\":\"\",\"options\":\"#{client:true}\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IIF9V8KR0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF9USHF0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IIF9USHF0",
//					"attrs": {
//						"id": "TestCommands",
//						"viewName": "",
//						"label": "",
//						"x": "345",
//						"y": "155",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIF9V8KS2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIF9V8KS3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/Bash.js",
//						"argument": "{\"bashId\":\"#bash\",\"action\":\"Command\",\"commands\":\"\",\"options\":\"#{}\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IIF9V8KR1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIFAB1MF0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "note",
//					"jaxId": "1IIF9V3320",
//					"attrs": {
//						"id": "Bash",
//						"label": "",
//						"x": "135",
//						"y": "100",
//						"from": "",
//						"desc": "这是一个注释。"
//					},
//					"icon": "memo.svg",
//					"isNote": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IIFAB1MF0",
//					"attrs": {
//						"id": "BashResult",
//						"viewName": "",
//						"label": "",
//						"x": "590",
//						"y": "155",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIFABA8U0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIFABA8U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`\nBash result:  \n\\`\\`\\`\n${input}\n\\`\\`\\`\n`",
//						"outlet": {
//							"jaxId": "1IIFABA8S0",
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