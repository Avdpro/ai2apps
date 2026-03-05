//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1JIBT8AQO0MoreImports*/
/*}#1JIBT8AQO0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"model":{
			"name":"model","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JIBT8AQO0ArgsView*/
	/*}#1JIBT8AQO0ArgsView*/
};

/*#{1JIBT8AQO0StartDoc*/
/*}#1JIBT8AQO0StartDoc*/
//----------------------------------------------------------------------------
let DeleteModel=async function(session){
	let model;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,GetInfo,CheckType,Init,Start,Remove,Tip,RemoveConda,RemoveCode,RemoveModel,Finish,Extra;
	/*#{1JIBT8AQO0LocalVals*/
	let model_type, conda_env, model_path, project_path, extra_command;
	/*}#1JIBT8AQO0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
		}else{
			model=undefined;
		}
		/*#{1JIBT8AQO0ParseArgs*/
		/*}#1JIBT8AQO0ParseArgs*/
	}
	
	/*#{1JIBT8AQO0PreContext*/
	/*}#1JIBT8AQO0PreContext*/
	context={};
	/*#{1JIBT8AQO0PostContext*/
	/*}#1JIBT8AQO0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1JIBT8O9O0
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(model===undefined || model==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:GetInfo,result:(result),preSeg:"1JIBT8O9O0",outlet:"1JIBT8STF0"};
	};
	FixArgs.jaxId="1JIBT8O9O0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["GetInfo"]=GetInfo=async function(input){//:1JIBU5U7N0
		let result=input
		try{
			/*#{1JIBU5U7N0Code*/
			const apiUrl = process.env.MODELHUNT_API_URL;
			const basicUrl = `${apiUrl.replace(/\/$/, '')}/api/v1/models/${model}`;
			const response = await fetch(basicUrl)
			if (!response.ok) {
				throw new Error(`Failed to fetch basic information: ${response.status} ${response.statusText}`);
			}
			const Config = await response.json();
			model_type = Config.model_type;
			conda_env = Config.conda_env;
			project_path = Config.project_path;
			model_path = Config.model_path;
			extra_command = Config.uninstall_command;
			/*}#1JIBU5U7N0Code*/
		}catch(error){
			/*#{1JIBU5U7N0ErrorCode*/
			/*}#1JIBU5U7N0ErrorCode*/
		}
		return {seg:Init,result:(result),preSeg:"1JIBU5U7N0",outlet:"1JIBU662V0"};
	};
	GetInfo.jaxId="1JIBU5U7N0"
	GetInfo.url="GetInfo@"+agentURL
	
	segs["CheckType"]=CheckType=async function(input){//:1JIBUA8NV0
		let result=input;
		if(model_type==="github"){
			return {seg:RemoveConda,result:(input),preSeg:"1JIBUA8NV0",outlet:"1JIBUDJPM0"};
		}
		if(model_type==="ollama"){
			return {seg:Start,result:(input),preSeg:"1JIBUA8NV0",outlet:"1JIBUAEHH0"};
		}
		return {seg:Finish,result:(result),preSeg:"1JIBUA8NV0",outlet:"1JIBUDJPM1"};
	};
	CheckType.jaxId="1JIBUA8NV0"
	CheckType.url="CheckType@"+agentURL
	
	segs["Init"]=Init=async function(input){//:1JIBUCJSL0
		let result,args={};
		args['bashId']="";
		args['action']="Create";
		args['commands']="";
		args['options']={client:true};
		/*#{1JIBUCJSL0PreCodes*/
		/*}#1JIBUCJSL0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1JIBUCJSL0PostCodes*/
		globalContext.bash=result;
		/*}#1JIBUCJSL0PostCodes*/
		return {seg:Tip,result:(result),preSeg:"1JIBUCJSL0",outlet:"1JIBUDJPM2"};
	};
	Init.jaxId="1JIBUCJSL0"
	Init.url="Init@"+agentURL
	
	segs["Start"]=Start=async function(input){//:1JIBUK3OA0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="ollama list || (brew services start ollama && sleep 3)";
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:Remove,result:(result),preSeg:"1JIBUK3OA0",outlet:"1JIBUU23B0"};
	};
	Start.jaxId="1JIBUK3OA0"
	Start.url="Start@"+agentURL
	
	segs["Remove"]=Remove=async function(input){//:1JIBV00HH0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=`ollama rm ${model}`;
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:Finish,result:(result),preSeg:"1JIBV00HH0",outlet:"1JIBV11JG0"};
	};
	Remove.jaxId="1JIBV00HH0"
	Remove.url="Remove@"+agentURL
	
	segs["Tip"]=Tip=async function(input){//:1JIBV3ENF0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("正在删除模型，请稍等"):("Deleting model, please wait"));
		session.addChatText(role,content,opts);
		return {seg:CheckType,result:(result),preSeg:"1JIBV3ENF0",outlet:"1JIBV57D40"};
	};
	Tip.jaxId="1JIBV3ENF0"
	Tip.url="Tip@"+agentURL
	
	segs["RemoveConda"]=RemoveConda=async function(input){//:1JIBV94JM0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=`conda env remove -n ${conda_env} -y`;
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:RemoveModel,result:(result),preSeg:"1JIBV94JM0",outlet:"1JIC0EE160"};
	};
	RemoveConda.jaxId="1JIBV94JM0"
	RemoveConda.url="RemoveConda@"+agentURL
	
	segs["RemoveCode"]=RemoveCode=async function(input){//:1JIC0GST30
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="";
		args['options']="";
		/*#{1JIC0GST30PreCodes*/
		let command = "";
		if(project_path) command = `rm -rvf "${project_path}"`;
		args['commands'] = command;
		/*}#1JIC0GST30PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1JIC0GST30PostCodes*/
		/*}#1JIC0GST30PostCodes*/
		return {seg:Extra,result:(result),preSeg:"1JIC0GST30",outlet:"1JIC0M4F60"};
	};
	RemoveCode.jaxId="1JIC0GST30"
	RemoveCode.url="RemoveCode@"+agentURL
	
	segs["RemoveModel"]=RemoveModel=async function(input){//:1JIEDBS6J0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="";
		args['options']="";
		/*#{1JIEDBS6J0PreCodes*/
		let command = "";
		if(model_path) command = `rm -rvf "${model_path}"`;
		args['commands'] = command;
		/*}#1JIEDBS6J0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1JIEDBS6J0PostCodes*/
		/*}#1JIEDBS6J0PostCodes*/
		return {seg:RemoveCode,result:(result),preSeg:"1JIEDBS6J0",outlet:"1JIEDC8960"};
	};
	RemoveModel.jaxId="1JIEDBS6J0"
	RemoveModel.url="RemoveModel@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1JIEESAT30
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("该模型及其相关代码已成功删除。"):("The model and its associated code have been successfully deleted."));
		session.addChatText(role,content,opts);
		return {result:result};
	};
	Finish.jaxId="1JIEESAT30"
	Finish.url="Finish@"+agentURL
	
	segs["Extra"]=Extra=async function(input){//:1JIEG1N380
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=extra_command;
		args['options']="";
		/*#{1JIEG1N380PreCodes*/
		if(!extra_command) return {seg:Finish,result:(result),preSeg:"1JIEG1N380",outlet:"1JIEG2AE40"};
		/*}#1JIEG1N380PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1JIEG1N380PostCodes*/
		/*}#1JIEG1N380PostCodes*/
		return {seg:Finish,result:(result),preSeg:"1JIEG1N380",outlet:"1JIEG2AE40"};
	};
	Extra.jaxId="1JIEG1N380"
	Extra.url="Extra@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"DeleteModel",
		url:agentURL,
		autoStart:true,
		jaxId:"1JIBT8AQO0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JIBT8AQO0PreEntry*/
			/*}#1JIBT8AQO0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1JIBT8AQO0PostEntry*/
			/*}#1JIBT8AQO0PostEntry*/
			return result;
		},
		/*#{1JIBT8AQO0MoreAgentAttrs*/
		/*}#1JIBT8AQO0MoreAgentAttrs*/
	};
	/*#{1JIBT8AQO0PostAgent*/
	/*}#1JIBT8AQO0PostAgent*/
	return agent;
};
/*#{1JIBT8AQO0ExCodes*/
/*}#1JIBT8AQO0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1JIBT8AQO0PostDoc*/
/*}#1JIBT8AQO0PostDoc*/


export default DeleteModel;
export{DeleteModel};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JIBT8AQO0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JIBT8AQQ0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1JIBT8AQQ1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JIBT8AQQ2",
//			"attrs": {
//				"model": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JIBT8STG0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JIBT8AQQ3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JIBT8AQQ4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JIBT8AQQ5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1JIBT8O9O0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "-205",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1JIBT8STF0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIBU5U7N0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JIBU5U7N0",
//					"attrs": {
//						"id": "GetInfo",
//						"viewName": "",
//						"label": "",
//						"x": "5",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIBU66310",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIBU66311",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JIBU662V0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIBUCJSL0"
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
//					"jaxId": "1JIBUA8NV0",
//					"attrs": {
//						"id": "CheckType",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIBUDJPS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIBUDJPS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JIBUDJPM1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JIEER8VG0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JIBUDJPM0",
//									"attrs": {
//										"id": "github",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JIBUDJPS2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JIBUDJPS3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#model_type===\"github\""
//									},
//									"linkedSeg": "1JIBV94JM0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JIBUAEHH0",
//									"attrs": {
//										"id": "ollama",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JIBUDJPS4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JIBUDJPS5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#model_type===\"ollama\""
//									},
//									"linkedSeg": "1JIBUK3OA0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JIBUCJSL0",
//					"attrs": {
//						"id": "Init",
//						"viewName": "",
//						"label": "",
//						"x": "215",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIBUDJPS6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIBUDJPS7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "\"\"",
//						"action": "Create",
//						"commands": "\"\"",
//						"options": "#{client:true}",
//						"outlet": {
//							"jaxId": "1JIBUDJPM2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIBV3ENF0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JIBUK3OA0",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "850",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIBUU23L0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIBUU23L1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "ollama list || (brew services start ollama && sleep 3)",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JIBUU23B0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIBV00HH0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JIBV00HH0",
//					"attrs": {
//						"id": "Remove",
//						"viewName": "",
//						"label": "",
//						"x": "1085",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIBV11JL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIBV11JL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#`ollama rm ${model}`",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JIBV11JG0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIEESAT30"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JIBV3ENF0",
//					"attrs": {
//						"id": "Tip",
//						"viewName": "",
//						"label": "",
//						"x": "415",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIBV57D80",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIBV57D81",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Deleting model, please wait",
//							"localize": {
//								"EN": "Deleting model, please wait",
//								"CN": "正在删除模型，请稍等"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JIBV57D40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIBUA8NV0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JIBV94JM0",
//					"attrs": {
//						"id": "RemoveConda",
//						"viewName": "",
//						"label": "",
//						"x": "850",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIC0G9660",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIC0G9661",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#`conda env remove -n ${conda_env} -y`",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JIC0EE160",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIEDBS6J0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JIC0GST30",
//					"attrs": {
//						"id": "RemoveCode",
//						"viewName": "",
//						"label": "",
//						"x": "1325",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIC0M4FF0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIC0M4FF1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "\"\"",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JIC0M4F60",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIEG1N380"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JIEDBS6J0",
//					"attrs": {
//						"id": "RemoveModel",
//						"viewName": "",
//						"label": "",
//						"x": "1085",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIEDD7T50",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIEDD7T51",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "\"\"",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JIEDC8960",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIC0GST30"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JIEER8VG0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "850",
//						"y": "520",
//						"outlet": {
//							"jaxId": "1JIEESOTT0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIEEREH30"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JIEEREH30",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1435",
//						"y": "520",
//						"outlet": {
//							"jaxId": "1JIEESOTT1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIEESAT30"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JIEESAT30",
//					"attrs": {
//						"id": "Finish",
//						"viewName": "",
//						"label": "",
//						"x": "1595",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIEESOTT2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIEESOTT3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "The model and its associated code have been successfully deleted.",
//							"localize": {
//								"EN": "The model and its associated code have been successfully deleted.",
//								"CN": "该模型及其相关代码已成功删除。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JIEESOTO0",
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
//					"def": "Bash",
//					"jaxId": "1JIEG1N380",
//					"attrs": {
//						"id": "Extra",
//						"viewName": "",
//						"label": "",
//						"x": "1600",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIEG2AEC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIEG2AEC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#extra_command",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JIEG2AE40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIEESAT30"
//						}
//					},
//					"icon": "terminal.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}