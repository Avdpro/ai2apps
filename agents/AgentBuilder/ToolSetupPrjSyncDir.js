//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IJRPS73O0MoreImports*/
import {tabOS,tabFS,tabNT} from "/@tabos";
/*}#1IJRPS73O0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"dirPath":{
			"name":"dirPath","type":"string",
			"defaultValue":"",
			"desc":"项目路径",
		}
	},
	/*#{1IJRPS73O0ArgsView*/
	/*}#1IJRPS73O0ArgsView*/
};

/*#{1IJRPS73O0StartDoc*/
/*}#1IJRPS73O0StartDoc*/
//----------------------------------------------------------------------------
let ToolSetupPrjSyncDir=async function(session){
	let dirPath;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let CheckSyncInfo,TestDirName,AskOverwrite,AskNewName,CheckName,TipBadName,SaveInfo,SyncDir;
	let agentDir="";
	let diskJSON=null;
	let prjSyncVO=null;
	
	/*#{1IJRPS73O0LocalVals*/
	/*}#1IJRPS73O0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			dirPath=input.dirPath;
		}else{
			dirPath=undefined;
		}
		/*#{1IJRPS73O0ParseArgs*/
		/*}#1IJRPS73O0ParseArgs*/
	}
	
	/*#{1IJRPS73O0PreContext*/
	/*}#1IJRPS73O0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IJRPS73O0PostContext*/
	/*}#1IJRPS73O0PostContext*/
	let agent,segs={};
	segs["CheckSyncInfo"]=CheckSyncInfo=async function(input){//:1IJRQQU470
		let result=input;
		/*#{1IJRQQU470Start*/
		let syncDir;
		diskJSON=await tabFS.readFile(pathLib.join(dirPath,"disk.json"),"utf8");
		diskJSON=JSON.parse(diskJSON);
		syncDir=diskJSON.syncDir;
		if(!syncDir){
			diskJSON.syncDir=syncDir={"name":"","dirs":[]};
		}
		FindDir:{
			for(let dirVO of syncDir.dirs){
				if(dirVO.dir==="ai"){
					prjSyncVO=dirVO;
					break FindDir;
				}
			}
			prjSyncVO={"dir":"ai","target":null,"ignore":["prj",".idea"]};
			syncDir.dirs.push(prjSyncVO);
		}
		agentDir=prjSyncVO.target;
		/*}#1IJRQQU470Start*/
		if(!agentDir){
			/*#{1IJRQS6VG0Codes*/
			agentDir="AGENTS/"+pathLib.basename(dirPath);
			/*}#1IJRQS6VG0Codes*/
			return {seg:TestDirName,result:(input),preSeg:"1IJRQQU470",outlet:"1IJRQS6VG0"};
		}
		/*#{1IJRQQU470Post*/
		result=agentDir;
		/*}#1IJRQQU470Post*/
		return {seg:SyncDir,result:(result),preSeg:"1IJRQQU470",outlet:"1IJRQS6VG1"};
	};
	CheckSyncInfo.jaxId="1IJRQQU470"
	CheckSyncInfo.url="CheckSyncInfo@"+agentURL
	
	segs["TestDirName"]=TestDirName=async function(input){//:1IJRQ7UT10
		let result=input;
		/*#{1IJRQ7UT10Start*/
		let res,used;
		res=await tabNT.makeCall("fileGetEntries",{dir:agentDir});
		if(res && res.code===200){
			if(res.entries){
				used=true;
			}
		}else{
			throw Error((res && res.info)?`Get Agent node dir info error: ${res.info}.`:`Get Agent node dir info error ${res?res.code:"unkown"}.`);
		}
		/*}#1IJRQ7UT10Start*/
		if(used){
			return {seg:AskOverwrite,result:(input),preSeg:"1IJRQ7UT10",outlet:"1IJRQDP5T0"};
		}
		/*#{1IJRQ7UT10Post*/
		/*}#1IJRQ7UT10Post*/
		return {seg:SaveInfo,result:(result),preSeg:"1IJRQ7UT10",outlet:"1IJRQDP5T1"};
	};
	TestDirName.jaxId="1IJRQ7UT10"
	TestDirName.url="TestDirName@"+agentURL
	
	segs["AskOverwrite"]=AskOverwrite=async function(input){//:1IJRQ8DT60
		let prompt=((($ln==="CN")?(`智能体目录 ${agentDir} 不为空，您要将其用于新智能体吗？`):/*EN*/(`Agent dir ${agentDir} is not empty, do you want to use it for the new agent?`)))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("选择一个新的智能体目录名称"):("Choose a new agent dir name")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("覆盖智能体目录"):("Overwrite agent dir")),code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:AskNewName,result:(result),preSeg:"1IJRQ8DT60",outlet:"1IJRQ8DSK1"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:AskNewName,result:(result),preSeg:"1IJRQ8DT60",outlet:"1IJRQ8DSK1"};
		}else if(item.code===1){
			return {seg:SaveInfo,result:(result),preSeg:"1IJRQ8DT60",outlet:"1IJRQ8DSK0"};
		}
		return {result:result};
	};
	AskOverwrite.jaxId="1IJRQ8DT60"
	AskOverwrite.url="AskOverwrite@"+agentURL
	
	segs["AskNewName"]=AskNewName=async function(input){//:1IJRQG1P70
		let tip=((($ln==="CN")?("请输入一个新的AI智能体目录名称"):("Please input a new agent dir name")));
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let text=("");
		let result="";
		/*#{1IJRQG1P70PreCodes*/
		/*}#1IJRQG1P70PreCodes*/
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile});
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		/*#{1IJRQG1P70PostCodes*/
		agentDir=result;
		/*}#1IJRQG1P70PostCodes*/
		return {seg:CheckName,result:(result),preSeg:"1IJRQG1P70",outlet:"1IJRQHDDD0"};
	};
	AskNewName.jaxId="1IJRQG1P70"
	AskNewName.url="AskNewName@"+agentURL
	
	segs["CheckName"]=CheckName=async function(input){//:1IJRS4PU50
		let result=input;
		/*#{1IJRS4PU50Start*/
		let nameOK;
		const regex = /^(?!\.)[A-Za-z0-9 _-]+$/;
		nameOK=regex.test(agentDir);
		/*}#1IJRS4PU50Start*/
		if(!nameOK){
			/*#{1IJRSA77G0Codes*/
			/*}#1IJRSA77G0Codes*/
			return {seg:TipBadName,result:(input),preSeg:"1IJRS4PU50",outlet:"1IJRSA77G0"};
		}
		/*#{1IJRS4PU50Post*/
		agentDir="AGENTS/"+agentDir;
		/*}#1IJRS4PU50Post*/
		return {seg:TestDirName,result:(result),preSeg:"1IJRS4PU50",outlet:"1IJRSA77G1"};
	};
	CheckName.jaxId="1IJRS4PU50"
	CheckName.url="CheckName@"+agentURL
	
	segs["TipBadName"]=TipBadName=async function(input){//:1IJRS5A360
		let result=input;
		let opts={};
		let role="assistant";
		let content=(($ln==="CN")?("智能体目录名不合法，智能体目录名只能包含大、小写字母，数字，\"_\"，\"-\"和空格。"):("The agent directory name is invalid. The agent directory name can only contain uppercase and lowercase letters, numbers, '_', '-', and spaces."));
		session.addChatText(role,content,opts);
		return {seg:AskOverwrite,result:(result),preSeg:"1IJRS5A360",outlet:"1IJRSA77G2"};
	};
	TipBadName.jaxId="1IJRS5A360"
	TipBadName.url="TipBadName@"+agentURL
	
	segs["SaveInfo"]=SaveInfo=async function(input){//:1IJRT096M0
		let result=input
		/*#{1IJRT096M0Code*/
		prjSyncVO.target=agentDir;
		await tabFS.writeFile(pathLib.join(dirPath,"disk.json"),JSON.stringify(diskJSON,null,"\t"));
		/*}#1IJRT096M0Code*/
		return {seg:SyncDir,result:(result),preSeg:"1IJRT096M0",outlet:"1IJRT1EI80"};
	};
	SaveInfo.jaxId="1IJRT096M0"
	SaveInfo.url="SaveInfo@"+agentURL
	
	segs["SyncDir"]=SyncDir=async function(input){//:1IJRQ9C5J0
		let result=input
		/*#{1IJRQ9C5J0Code*/
		let synced;
		synced=await VFACT.app.modalDlg("/@StdUI/ui/DlgSyncDir.js",{path:dirPath,run:true});
		if(synced){
			session.addChatText("assistant",(($ln==="CN")?("智能体工程已和服务器同步完毕."):/*EN*/("Agent project synced with server.")));
		}
		result={result:"Finish",content:"Project synced.",agentDir:agentDir};
		/*}#1IJRQ9C5J0Code*/
		return {result:result};
	};
	SyncDir.jaxId="1IJRQ9C5J0"
	SyncDir.url="SyncDir@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"ToolSetupPrjSyncDir",
		url:agentURL,
		autoStart:true,
		jaxId:"1IJRPS73O0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{dirPath}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IJRPS73O0PreEntry*/
			/*}#1IJRPS73O0PreEntry*/
			result={seg:CheckSyncInfo,"input":input};
			/*#{1IJRPS73O0PostEntry*/
			/*}#1IJRPS73O0PostEntry*/
			return result;
		},
		/*#{1IJRPS73O0MoreAgentAttrs*/
		/*}#1IJRPS73O0MoreAgentAttrs*/
	};
	/*#{1IJRPS73O0PostAgent*/
	/*}#1IJRPS73O0PostAgent*/
	return agent;
};
/*#{1IJRPS73O0ExCodes*/
/*}#1IJRPS73O0ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "ToolSetupPrjSyncDir",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				dirPath:{type:"string",description:"项目路径"}
			}
		}
	},
	agent: ToolSetupPrjSyncDir
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
		name:"ToolSetupPrjSyncDir",showName:"ToolSetupPrjSyncDir",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"dirPath":{name:"dirPath",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","dirPath","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolSetupPrjSyncDir"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['dirPath']=");this.genAttrStatement(seg.getAttr("dirPath"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AgentBuilder/ai/ToolSetupPrjSyncDir.js",args,false);`);coder.newLine();
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
/*#{1IJRPS73O0PostDoc*/
/*}#1IJRPS73O0PostDoc*/


export default ToolSetupPrjSyncDir;
export{ToolSetupPrjSyncDir};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IJRPS73O0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IJRPS73O1",
//			"attrs": {
//				"ToolSetupPrjSyncDir": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IJRPS73O7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IJRPS73O8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IJRPS73O9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IJRPS73O10",
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
//			"jaxId": "1IJRPS73O2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IJRPS73O3",
//			"attrs": {
//				"dirPath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJRPU5RP0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "项目路径"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IJRPS73O4",
//			"attrs": {
//				"agentDir": {
//					"type": "string",
//					"valText": "",
//					"comment": "Agent dir name"
//				},
//				"diskJSON": {
//					"type": "auto",
//					"valText": "null",
//					"comment": "当前项目的diskJSON对象"
//				},
//				"prjSyncVO": {
//					"type": "auto",
//					"valText": "null"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IJRPS73O5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IJRPS73O6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJRQQU470",
//					"attrs": {
//						"id": "CheckSyncInfo",
//						"viewName": "",
//						"label": "",
//						"x": "95",
//						"y": "310",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJRQS6VN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJRQS6VN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJRQS6VG1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJRQRM6J0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJRQS6VG0",
//									"attrs": {
//										"id": "NoInfo",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IJRQS6VN2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJRQS6VN3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!agentDir"
//									},
//									"linkedSeg": "1IJRQ7UT10"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJRQ7UT10",
//					"attrs": {
//						"id": "TestDirName",
//						"viewName": "",
//						"label": "",
//						"x": "395",
//						"y": "295",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJRQDP5U0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJRQDP5U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJRQDP5T1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJRT096M0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJRQDP5T0",
//									"attrs": {
//										"id": "Used",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJRQDP5U2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJRQDP5U3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#used"
//									},
//									"linkedSeg": "1IJRQ8DT60"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IJRQ8DT60",
//					"attrs": {
//						"id": "AskOverwrite",
//						"viewName": "",
//						"label": "",
//						"x": "640",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "#(($ln===\"CN\")?(`智能体目录 ${agentDir} 不为空，您要将其用于新智能体吗？`):/*EN*/(`Agent dir ${agentDir} is not empty, do you want to use it for the new agent?`))",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IJRQDP5T2",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJRQ8DSK1",
//									"attrs": {
//										"id": "NewName",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Choose a new agent dir name",
//											"localize": {
//												"EN": "Choose a new agent dir name",
//												"CN": "选择一个新的智能体目录名称"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJRQDP5U6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJRQDP5U7",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJRQG1P70"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJRQ8DSK0",
//									"attrs": {
//										"id": "Overwrite",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Overwrite agent dir",
//											"localize": {
//												"EN": "Overwrite agent dir",
//												"CN": "覆盖智能体目录"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJRQDP5U4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJRQDP5U5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJRT096M0"
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
//					"def": "askChat",
//					"jaxId": "1IJRQG1P70",
//					"attrs": {
//						"id": "AskNewName",
//						"viewName": "",
//						"label": "",
//						"x": "910",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJRQHDDE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJRQHDDE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": {
//							"type": "string",
//							"valText": "Please input a new agent dir name",
//							"localize": {
//								"EN": "Please input a new agent dir name",
//								"CN": "请输入一个新的AI智能体目录名称"
//							},
//							"localizable": true
//						},
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IJRQHDDD0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJRS4PU50"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IJRQHFS00",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1315",
//						"y": "20",
//						"outlet": {
//							"jaxId": "1IJRQHQAJ0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJRQHLRI0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IJRQHLRI0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "425",
//						"y": "20",
//						"outlet": {
//							"jaxId": "1IJRQHQAJ1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJRQ7UT10"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IJRQRM6J0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "350",
//						"y": "430",
//						"outlet": {
//							"jaxId": "1IJRQS6VN4",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJRQRVOB0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IJRQRVOB0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1030",
//						"y": "430",
//						"outlet": {
//							"jaxId": "1IJRQS6VN5",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJRQ9C5J0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJRS4PU50",
//					"attrs": {
//						"id": "CheckName",
//						"viewName": "",
//						"label": "",
//						"x": "1145",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJRSA77K0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJRSA77K1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJRSA77G1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJRQHFS00"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJRSA77G0",
//									"attrs": {
//										"id": "BadName",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IJRSA77K2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJRSA77K3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!nameOK"
//									},
//									"linkedSeg": "1IJRS5A360"
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
//					"jaxId": "1IJRS5A360",
//					"attrs": {
//						"id": "TipBadName",
//						"viewName": "",
//						"label": "",
//						"x": "1405",
//						"y": "165",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJRSA77K4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJRSA77K5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": {
//							"type": "string",
//							"valText": "The agent directory name is invalid. The agent directory name can only contain uppercase and lowercase letters, numbers, '_', '-', and spaces.",
//							"localize": {
//								"EN": "The agent directory name is invalid. The agent directory name can only contain uppercase and lowercase letters, numbers, '_', '-', and spaces.",
//								"CN": "智能体目录名不合法，智能体目录名只能包含大、小写字母，数字，\"_\"，\"-\"和空格。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IJRSA77G2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJRS5KSA0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IJRS5KSA0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1565",
//						"y": "85",
//						"outlet": {
//							"jaxId": "1IJRSA77K6",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJRS5SBV0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IJRS5SBV0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "665",
//						"y": "85",
//						"outlet": {
//							"jaxId": "1IJRSA77K7",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJRQ8DT60"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJRT096M0",
//					"attrs": {
//						"id": "SaveInfo",
//						"viewName": "",
//						"label": "",
//						"x": "910",
//						"y": "310",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJRT1EIE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJRT1EIE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJRT1EI80",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJRQ9C5J0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJRQ9C5J0",
//					"attrs": {
//						"id": "SyncDir",
//						"viewName": "",
//						"label": "",
//						"x": "1145",
//						"y": "310",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJRQDP5V2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJRQDP5V3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJRQDP5T3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}