//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IH8EUS4Q1MoreImports*/
/*}#1IH8EUS4Q1MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"commands":{
			"name":"commands","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1IH8EUS4Q1ArgsView*/
	/*}#1IH8EUS4Q1ArgsView*/
};

/*#{1IH8EUS4Q1StartDoc*/
/*}#1IH8EUS4Q1StartDoc*/
//----------------------------------------------------------------------------
let ToolBashCommand=async function(session){
	let commands;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let CmdMenu,RunStep,KeepBash,WaitManun,ReadBash,TipSkiped,AskAbort,UserAbort,Chat;
	let env=globalContext.env;
	let project=globalContext.project;
	let bashContent=undefined;
	let task=globalContext.curTask;
	
	/*#{1IH8EUS4Q1LocalVals*/
	/*}#1IH8EUS4Q1LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			commands=input.commands;
		}else{
			commands=undefined;
		}
		/*#{1IH8EUS4Q1ParseArgs*/
		/*}#1IH8EUS4Q1ParseArgs*/
	}
	
	/*#{1IH8EUS4Q1PreContext*/
	/*}#1IH8EUS4Q1PreContext*/
	context={};
	/*#{1IH8EUS4Q1PostContext*/
	/*}#1IH8EUS4Q1PostContext*/
	let agent,segs={};
	segs["CmdMenu"]=CmdMenu=async function(input){//:1IH8F36M93
		let prompt=((($ln==="CN")?(`确认执行命令：${commands.join("\n")}`):(`Confirm execute commands: ${commands.join("\n")}`)))||input;
		let countdown=false;
		let placeholder=(undefined)||null;
		let withChat=true;
		let silent=globalContext.autoBash;
		let items=[
			{icon:"/~/tabos/shared/assets/run.svg"||"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("执行"):("Execute")),code:0},
			{icon:"/~/tabos/shared/assets/mouse.svg"||"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("人工执行"):("Manually execute")),code:1},
			{icon:"/~/tabos/shared/assets/moveback.svg"||"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("跳过这个步骤"):("Skip this step")),code:2},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("终止执行"):("Abort execution")),code:3},
		];
		let result="";
		let item=null;
		
		if(silent){
			result=input;
			return {seg:RunStep,result:(result),preSeg:"1IH8F36M93",outlet:"1IH8F36MA1"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {seg:Chat,result:(result),preSeg:"1IH8F36M93",outlet:"1IH8F36MA0"};
		}else if(item.code===0){
			result=(input);
			return {seg:RunStep,result:(result),preSeg:"1IH8F36M93",outlet:"1IH8F36MA1"};
		}else if(item.code===1){
			result=(input);
			return {seg:KeepBash,result:(result),preSeg:"1IH8F36M93",outlet:"1IH8F36MA4"};
		}else if(item.code===2){
			return {seg:TipSkiped,result:(result),preSeg:"1IH8F36M93",outlet:"1IH8F36MA7"};
		}else if(item.code===3){
			result=("/~/tabos/shared/assets/close.svg");
			return {seg:AskAbort,result:(result),preSeg:"1IH8F36M93",outlet:"1IH8F36MA10"};
		}
		return {seg:Chat,result:(result),preSeg:"1IH8F36M93",outlet:"1IH8F36MA0"};
	};
	CmdMenu.jaxId="1IH8F36M93"
	CmdMenu.url="CmdMenu@"+agentURL
	
	segs["RunStep"]=RunStep=async function(input){//:1IH8F4U790
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=input.commands;
		args['options']="";
		/*#{1IH8F4U790PreCodes*/
		/*}#1IH8F4U790PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IH8F4U790PostCodes*/
		if(task){
			task.log(`bash commands:\n\n ${result}`,"bash");
		}
		result=`Bash命令执行完毕，结果：\n\`\`\`\n${result}\n\`\`\`\n`;
		/*}#1IH8F4U790PostCodes*/
		return {result:result};
	};
	RunStep.jaxId="1IH8F4U790"
	RunStep.url="RunStep@"+agentURL
	
	segs["KeepBash"]=KeepBash=async function(input){//:1IH8F5P9O0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Content";
		args['commands']="";
		args['options']="";
		/*#{1IH8F5P9O0PreCodes*/
		/*}#1IH8F5P9O0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IH8F5P9O0PostCodes*/
		bashContent=result;
		/*}#1IH8F5P9O0PostCodes*/
		return {seg:WaitManun,result:(result),preSeg:"1IH8F5P9O0",outlet:"1IH8F5P9O3"};
	};
	KeepBash.jaxId="1IH8F5P9O0"
	KeepBash.url="KeepBash@"+agentURL
	
	segs["WaitManun"]=WaitManun=async function(input){//:1IH8F890K3
		let prompt=((($ln==="CN")?("人工执行完毕后请点击'继续'按钮。"):("Please click the 'Continue' button after manual execution.")))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=((($ln==="CN")?("继续"):("Continue")))||"OK";
		let button2=((($ln==="CN")?("取消"):("Cancel")))||"Cancel";
		let button3="";
		let result="";
		let value=0;
		/*#{1IH8F890K3PreCodes*/
		/*}#1IH8F890K3PreCodes*/
		if(silent){
			result="";
			/*#{1IH8F890L0Silent*/
			/*}#1IH8F890L0Silent*/
			return {seg:ReadBash,result:(result),preSeg:"1IH8F890K3",outlet:"1IH8F890L0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		/*#{1IH8F890K3PostCodes*/
		/*}#1IH8F890K3PostCodes*/
		if(value===1){
			result=("")||result;
			/*#{1IH8F890L0Btn1*/
			/*}#1IH8F890L0Btn1*/
			return {seg:ReadBash,result:(result),preSeg:"1IH8F890K3",outlet:"1IH8F890L0"};
		}
		result=("")||result;
		return {seg:CmdMenu,result:(result),preSeg:"1IH8F890K3",outlet:"1IH8F890L3"};
	
	};
	WaitManun.jaxId="1IH8F890K3"
	WaitManun.url="WaitManun@"+agentURL
	
	segs["ReadBash"]=ReadBash=async function(input){//:1IH8F98LL0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Content";
		args['commands']="";
		args['options']="";
		/*#{1IH8F98LL0PreCodes*/
		/*}#1IH8F98LL0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IH8F98LL0PostCodes*/
		result=result.substring(bashContent.length);
		if(task){
			task.log(`bash commands:\n\n ${result}`,"bash");
		}
		result=(($ln==="CN")?(`人工执行完毕，bash过程/结果：\n\`\`\`\n${result}\n\`\`\`\n`):/*EN*/(`Manual execution completed, bash process/result:\n\`\`\`\n${result}\n\`\`\`\n`));
		/*}#1IH8F98LL0PostCodes*/
		return {result:result};
	};
	ReadBash.jaxId="1IH8F98LL0"
	ReadBash.url="ReadBash@"+agentURL
	
	segs["TipSkiped"]=TipSkiped=async function(input){//:1IH8F9T460
		let result=input;
		let opts={};
		let role="assistant";
		let content=(($ln==="CN")?("已跳过此步骤"):("This step has been skipped"));
		/*#{1IH8F9T460PreCodes*/
		/*}#1IH8F9T460PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IH8F9T460PostCodes*/
		result=(($ln==="CN")?("用户选择跳过此步骤."):/*EN*/("User choosed to skip this step."));
		/*}#1IH8F9T460PostCodes*/
		return {result:result};
	};
	TipSkiped.jaxId="1IH8F9T460"
	TipSkiped.url="TipSkiped@"+agentURL
	
	segs["AskAbort"]=AskAbort=async function(input){//:1IH8FBOT63
		let prompt=((($ln==="CN")?("是否终止当前项目部署"):("Terminate the current project setup?")))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=("确定")||"OK";
		let button2=("取消")||"Cancel";
		let button3="";
		let result="";
		let value=0;
		if(silent){
			result="";
			return {seg:UserAbort,result:(result),preSeg:"1IH8FBOT63",outlet:"1IH8FBOT70"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			return {seg:UserAbort,result:(result),preSeg:"1IH8FBOT63",outlet:"1IH8FBOT70"};
		}
		result=(input)||result;
		return {seg:CmdMenu,result:(result),preSeg:"1IH8FBOT63",outlet:"1IH8FBOT73"};
	
	};
	AskAbort.jaxId="1IH8FBOT63"
	AskAbort.url="AskAbort@"+agentURL
	
	segs["UserAbort"]=UserAbort=async function(input){//:1IH8FCA340
		let result="没有执行命令。用户放弃：终止执行。"
		/*#{1IH8FCA340Code*/
		/*}#1IH8FCA340Code*/
		return {result:result};
	};
	UserAbort.jaxId="1IH8FCA340"
	UserAbort.url="UserAbort@"+agentURL
	
	segs["Chat"]=Chat=async function(input){//:1IH8FF1NJ0
		let result=`没有执行命令，用户意见：\n${input}`
		/*#{1IH8FF1NJ0Code*/
		//throw Error("测试 Catch Error 专用异常。");
		/*}#1IH8FF1NJ0Code*/
		return {result:result};
	};
	Chat.jaxId="1IH8FF1NJ0"
	Chat.url="Chat@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"ToolBashCommand",
		url:agentURL,
		autoStart:true,
		jaxId:"1IH8EUS4Q1",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{commands}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IH8EUS4Q1PreEntry*/
			/*}#1IH8EUS4Q1PreEntry*/
			result={seg:CmdMenu,"input":input};
			/*#{1IH8EUS4Q1PostEntry*/
			/*}#1IH8EUS4Q1PostEntry*/
			return result;
		},
		/*#{1IH8EUS4Q1MoreAgentAttrs*/
		/*}#1IH8EUS4Q1MoreAgentAttrs*/
	};
	/*#{1IH8EUS4Q1PostAgent*/
	/*}#1IH8EUS4Q1PostAgent*/
	return agent;
};
/*#{1IH8EUS4Q1ExCodes*/
/*}#1IH8EUS4Q1ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "ToolBashCommand",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				commands:{type:"auto",description:""}
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
		name:"ToolBashCommand",showName:"ToolBashCommand",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"commands":{name:"commands",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","commands","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolBashCommand"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['commands']=");this.genAttrStatement(seg.getAttr("commands"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AgentBuilder/ai/ToolBashCommand.js",args,false);`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
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
/*#{1IH8EUS4Q1PostDoc*/
/*}#1IH8EUS4Q1PostDoc*/


export default ToolBashCommand;
export{ToolBashCommand,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IH8EUS4Q1",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IH8EUS4Q1",
//			"attrs": {
//				"ToolBashCommand": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IH8EUS4Q7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IH8EUS4Q8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IH8EUS4Q9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IH8EUS4Q10",
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
//			"jaxId": "1IH8EUS4Q2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IH8EUS4Q3",
//			"attrs": {
//				"commands": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IH8EVK3K0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IH8EUS4Q4",
//			"attrs": {
//				"env": {
//					"type": "auto",
//					"valText": "#globalContext.env"
//				},
//				"project": {
//					"type": "auto",
//					"valText": "#globalContext.project"
//				},
//				"bashContent": {
//					"type": "auto",
//					"valText": ""
//				},
//				"task": {
//					"type": "auto",
//					"valText": "#globalContext.curTask"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IH8EUS4Q5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IH8EUS4Q6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IH8F36M93",
//					"attrs": {
//						"id": "CmdMenu",
//						"viewName": "",
//						"label": "",
//						"x": "225",
//						"y": "350",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "#`Confirm execute commands: ${commands.join(\"\\n\")}`",
//							"localize": {
//								"EN": "#`Confirm execute commands: ${commands.join(\"\\n\")}`",
//								"CN": "#`确认执行命令：${commands.join(\"\\n\")}`"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "true",
//						"outlet": {
//							"jaxId": "1IH8F36MA0",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							},
//							"linkedSeg": "1IH8FF1NJ0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IH8F36MA1",
//									"attrs": {
//										"id": "Exec",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Execute",
//											"localize": {
//												"EN": "Execute",
//												"CN": "执行"
//											},
//											"localizable": true
//										},
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH8F36MA2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8F36MA3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/tabos/shared/assets/run.svg"
//									},
//									"linkedSeg": "1IH8F4U790"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IH8F36MA4",
//									"attrs": {
//										"id": "Manun",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Manually execute",
//											"localize": {
//												"EN": "Manually execute",
//												"CN": "人工执行"
//											},
//											"localizable": true
//										},
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH8F36MA5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8F36MA6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/tabos/shared/assets/mouse.svg"
//									},
//									"linkedSeg": "1IH8F5P9O0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IH8F36MA7",
//									"attrs": {
//										"id": "Skip",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Skip this step",
//											"localize": {
//												"EN": "Skip this step",
//												"CN": "跳过这个步骤"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH8F36MA8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8F36MA9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/tabos/shared/assets/moveback.svg"
//									},
//									"linkedSeg": "1IH8F9T460"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IH8F36MA10",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Abort execution",
//											"localize": {
//												"EN": "Abort execution",
//												"CN": "终止执行"
//											},
//											"localizable": true
//										},
//										"result": "/~/tabos/shared/assets/close.svg",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH8F36MA11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8F36MA12",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IH8FBOT63"
//								}
//							]
//						},
//						"silent": "#globalContext.autoBash",
//						"countdown": "None",
//						"silentOutlet": "Exec"
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IH8F4U790",
//					"attrs": {
//						"id": "RunStep",
//						"viewName": "",
//						"label": "",
//						"x": "470",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IH8F4U7A0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8F4U7A1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#input.commands",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IH8F4U7A2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IH8F5P9O0",
//					"attrs": {
//						"id": "KeepBash",
//						"viewName": "",
//						"label": "",
//						"x": "470",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH8F5P9O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8F5P9O2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Content",
//						"commands": "\"\"",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IH8F5P9O3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8F890K3"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askConfirm",
//					"jaxId": "1IH8F890K3",
//					"attrs": {
//						"id": "WaitManun",
//						"viewName": "",
//						"label": "",
//						"x": "705",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Please click the 'Continue' button after manual execution.",
//							"localize": {
//								"EN": "Please click the 'Continue' button after manual execution.",
//								"CN": "人工执行完毕后请点击'继续'按钮。"
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IH8F890L0",
//									"attrs": {
//										"id": "Continue",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Continue",
//											"localize": {
//												"EN": "Continue",
//												"CN": "继续"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IH8F890L1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8F890L2",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IH8F98LL0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IH8F890L3",
//									"attrs": {
//										"id": "Cancel",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Cancel",
//											"localize": {
//												"EN": "Cancel",
//												"CN": "取消"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH8F890L4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8F890L5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IH8FIRAN0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IH8F98LL0",
//					"attrs": {
//						"id": "ReadBash",
//						"viewName": "",
//						"label": "",
//						"x": "965",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IH8F98LL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8F98LL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Content",
//						"commands": "\"\"",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IH8F98LL3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IH8F9T460",
//					"attrs": {
//						"id": "TipSkiped",
//						"viewName": "",
//						"label": "",
//						"x": "470",
//						"y": "350",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IH8F9T470",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8F9T471",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": {
//							"type": "string",
//							"valText": "This step has been skipped",
//							"localize": {
//								"EN": "This step has been skipped",
//								"CN": "已跳过此步骤"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IH8F9T472",
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
//					"def": "askConfirm",
//					"jaxId": "1IH8FBOT63",
//					"attrs": {
//						"id": "AskAbort",
//						"viewName": "",
//						"label": "",
//						"x": "470",
//						"y": "435",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Terminate the current project setup?",
//							"localize": {
//								"EN": "Terminate the current project setup?",
//								"CN": "是否终止当前项目部署"
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IH8FBOT70",
//									"attrs": {
//										"id": "Yes",
//										"desc": "输出节点。",
//										"text": "确定",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH8FBOT71",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8FBOT72",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IH8FCA340"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IH8FBOT73",
//									"attrs": {
//										"id": "Cancel",
//										"desc": "输出节点。",
//										"text": "取消",
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH8FBOT74",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8FBOT75",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IH8FI1HV0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH8FCA340",
//					"attrs": {
//						"id": "UserAbort",
//						"viewName": "",
//						"label": "",
//						"x": "705",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IH8FCA350",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8FCA351",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH8FCA352",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "没有执行命令。用户放弃：终止执行。"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH8FF1NJ0",
//					"attrs": {
//						"id": "Chat",
//						"viewName": "",
//						"label": "",
//						"x": "470",
//						"y": "535",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IH8FGT5A0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8FGT5A1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH8FG7270",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#`没有执行命令，用户意见：\\n${input}`"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IH8FI1HV0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "610",
//						"y": "645",
//						"outlet": {
//							"jaxId": "1IH8FJ7N50",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8FI71Q0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IH8FI71Q0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "265",
//						"y": "645",
//						"outlet": {
//							"jaxId": "1IH8FJ7N51",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8F36M93"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IH8FIRAN0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "865",
//						"y": "645",
//						"outlet": {
//							"jaxId": "1IH8FJ7N52",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8FI1HV0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}