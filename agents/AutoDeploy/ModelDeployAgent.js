//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1JH032HA90MoreImports*/
import {tabOS,tabFS,tabNT} from "/@tabos";
/*}#1JH032HA90MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?decodeURI(baseURL):baseURL;
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"model":{
			"name":"model","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JH032HA90ArgsView*/
	/*}#1JH032HA90ArgsView*/
};

/*#{1JH032HA90StartDoc*/
/*}#1JH032HA90StartDoc*/
//----------------------------------------------------------------------------
let ModelDeployAgent=async function(session){
	let model;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Save,Deploy,Check,Ask,Run,Bye,Fail;
	/*#{1JH032HA90LocalVals*/
	/*}#1JH032HA90LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
		}else{
			model=undefined;
		}
		/*#{1JH032HA90ParseArgs*/
		/*}#1JH032HA90ParseArgs*/
	}
	
	/*#{1JH032HA90PreContext*/
	/*}#1JH032HA90PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1JH032HA90PostContext*/
	/*}#1JH032HA90PostContext*/
	let $agent,agent,segs={};
	segs["Save"]=Save=async function(input){//:1JH0351Q70
		let result=input
		try{
			/*#{1JH0351Q70Code*/
			let modelJSON=await tabFS.readFile(pathLib.join(basePath.slice(2),"model.json"),"utf8");
			modelJSON=JSON.parse(modelJSON);
			result=modelJSON;
			if (!modelJSON.deployable.includes(model)) {
				modelJSON.deployable.push(model);
				console.log(`模型 ${model} 已添加到列表。`);
			} else {
				console.log(`模型 ${model} 已存在，跳过添加。`);
			}
			await tabFS.writeFile(pathLib.join(basePath.slice(2),"model.json"),JSON.stringify(modelJSON,null,"\t"));
			/*}#1JH0351Q70Code*/
		}catch(error){
			/*#{1JH0351Q70ErrorCode*/
			result="111";
			/*}#1JH0351Q70ErrorCode*/
		}
		return {seg:Ask,result:(result),preSeg:"1JH0351Q70",outlet:"1JH0355IC0"};
	};
	Save.jaxId="1JH0351Q70"
	Save.url="Save@"+agentURL
	
	segs["Deploy"]=Deploy=async function(input){//:1JH0497RJ0
		let result,args={};
		args['nodeName']="AutoDeploy";
		args['callAgent']="ModelDeploy.js";
		args['callArg']={model:model};
		args['checkUpdate']=true;
		args['options']="";
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {seg:Check,result:(result),preSeg:"1JH0497RJ0",outlet:"1JH049CR80"};
	};
	Deploy.jaxId="1JH0497RJ0"
	Deploy.url="Deploy@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1JH04EDCO0
		let result=input;
		if(input.result==="Finish"){
			return {seg:Save,result:(input),preSeg:"1JH04EDCO0",outlet:"1JH04EUSP0"};
		}
		return {seg:Fail,result:(result),preSeg:"1JH04EDCO0",outlet:"1JH04EUSP1"};
	};
	Check.jaxId="1JH04EDCO0"
	Check.url="Check@"+agentURL
	
	segs["Ask"]=Ask=async function(input){//:1JH04FVFC0
		let prompt=((($ln==="CN")?("模型已就绪。现在就开始体验吗？"):("The model is ready. Want to try it out now?")))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=((($ln==="CN")?("立即体验"):("Let's go")))||"OK";
		let button2=((($ln==="CN")?("稍后再说"):("Maybe later")))||"Cancel";
		let button3="";
		let result="";
		let value=0;
		if(silent){
			result="";
			return {seg:Run,result:(result),preSeg:"1JH04FVFC0",outlet:"1JH04FVEN0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			return {seg:Run,result:(result),preSeg:"1JH04FVFC0",outlet:"1JH04FVEN0"};
		}
		result=("")||result;
		return {seg:Bye,result:(result),preSeg:"1JH04FVFC0",outlet:"1JH04FVEN1"};
	
	};
	Ask.jaxId="1JH04FVFC0"
	Ask.url="Ask@"+agentURL
	
	segs["Run"]=Run=async function(input){//:1JH05985V0
		let result,args={};
		args['nodeName']="AutoDeploy";
		args['callAgent']="ModelUse.js";
		args['callArg']={model:model};
		args['checkUpdate']=true;
		args['options']="";
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {result:result};
	};
	Run.jaxId="1JH05985V0"
	Run.url="Run@"+agentURL
	
	segs["Bye"]=Bye=async function(input){//:1JH05BJ6I0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("没问题！模型已经准备好了，想用的时候随时去 “模型列表” 找它就好。"):("No problem! It's ready whenever you are. You can find it in your Model List anytime."));
		session.addChatText(role,content,opts);
		return {result:result};
	};
	Bye.jaxId="1JH05BJ6I0"
	Bye.url="Bye@"+agentURL
	
	segs["Fail"]=Fail=async function(input){//:1JH06UJ270
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("部署未能完成。建议检查一下网络连接，之后重试看看。"):("Deployment couldn't be completed. Please check your connection and try again later."));
		session.addChatText(role,content,opts);
		return {result:result};
	};
	Fail.jaxId="1JH06UJ270"
	Fail.url="Fail@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ModelDeployAgent",
		url:agentURL,
		autoStart:true,
		jaxId:"1JH032HA90",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JH032HA90PreEntry*/
			/*}#1JH032HA90PreEntry*/
			result={seg:Deploy,"input":input};
			/*#{1JH032HA90PostEntry*/
			/*}#1JH032HA90PostEntry*/
			return result;
		},
		/*#{1JH032HA90MoreAgentAttrs*/
		/*}#1JH032HA90MoreAgentAttrs*/
	};
	/*#{1JH032HA90PostAgent*/
	/*}#1JH032HA90PostAgent*/
	return agent;
};
/*#{1JH032HA90ExCodes*/
/*}#1JH032HA90ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1JH032HA90PostDoc*/
/*}#1JH032HA90PostDoc*/


export default ModelDeployAgent;
export{ModelDeployAgent};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JH032HA90",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JH032HVD0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1JH032HVD1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "Deploy",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JH032HVD2",
//			"attrs": {
//				"model": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JH034QVU0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JH032HVD3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JH032HVD4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JH032HVD5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JH0351Q70",
//					"attrs": {
//						"id": "Save",
//						"viewName": "",
//						"label": "",
//						"x": "785",
//						"y": "290",
//						"desc": "This is an AISeg.",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH0355ID0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH0355ID1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JH0355IC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JH04FVFC0"
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
//					"def": "RemoteChat",
//					"jaxId": "1JH0497RJ0",
//					"attrs": {
//						"id": "Deploy",
//						"viewName": "",
//						"label": "",
//						"x": "340",
//						"y": "305",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH049CRC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH049CRC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AutoDeploy",
//						"callAgent": "ModelDeploy.js",
//						"callArg": "#{model:model}",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JH049CR80",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JH04EDCO0"
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JH04EDCO0",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "560",
//						"y": "305",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH04EUST0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH04EUST1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JH04EUSP1",
//							"attrs": {
//								"id": "Fail",
//								"desc": "Outlet.",
//								"output": ""
//							},
//							"linkedSeg": "1JH06UJ270"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JH04EUSP0",
//									"attrs": {
//										"id": "Success",
//										"desc": "Outlet.",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JH04EUST2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JH04EUST3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.result===\"Finish\""
//									},
//									"linkedSeg": "1JH0351Q70"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askConfirm",
//					"jaxId": "1JH04FVFC0",
//					"attrs": {
//						"id": "Ask",
//						"viewName": "",
//						"label": "",
//						"x": "1025",
//						"y": "290",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "The model is ready. Want to try it out now?",
//							"localize": {
//								"EN": "The model is ready. Want to try it out now?",
//								"CN": "模型已就绪。现在就开始体验吗？"
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JH04FVEN0",
//									"attrs": {
//										"id": "Start",
//										"desc": "Outlet.",
//										"text": {
//											"type": "string",
//											"valText": "Let's go",
//											"localize": {
//												"EN": "Let's go",
//												"CN": "立即体验"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JH04JV6C0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JH04JV6C1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JH05985V0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JH04FVEN1",
//									"attrs": {
//										"id": "Later",
//										"desc": "Outlet.",
//										"text": {
//											"type": "string",
//											"valText": "Maybe later",
//											"localize": {
//												"EN": "Maybe later",
//												"CN": "稍后再说"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JH04JV6C2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JH04JV6C3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JH05BJ6I0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1JH05985V0",
//					"attrs": {
//						"id": "Run",
//						"viewName": "",
//						"label": "",
//						"x": "1215",
//						"y": "185",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH059B5C0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH059B5C1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AutoDeploy",
//						"callAgent": "ModelUse.js",
//						"callArg": "#{model:model}",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JH059B590",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							}
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JH05BJ6I0",
//					"attrs": {
//						"id": "Bye",
//						"viewName": "",
//						"label": "",
//						"x": "1215",
//						"y": "305",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH05C4M10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH05C4M11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "No problem! It's ready whenever you are. You can find it in your Model List anytime.",
//							"localize": {
//								"EN": "No problem! It's ready whenever you are. You can find it in your Model List anytime.",
//								"CN": "没问题！模型已经准备好了，想用的时候随时去 “模型列表” 找它就好。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JH05C4LV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JH06UJ270",
//					"attrs": {
//						"id": "Fail",
//						"viewName": "",
//						"label": "",
//						"x": "785",
//						"y": "400",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH070SSR0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH070SSR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Deployment couldn't be completed. Please check your connection and try again later.",
//							"localize": {
//								"EN": "Deployment couldn't be completed. Please check your connection and try again later.",
//								"CN": "部署未能完成。建议检查一下网络连接，之后重试看看。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JH070SSO0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				}
//			]
//		},
//		"desc": "This is an AI agent.",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}