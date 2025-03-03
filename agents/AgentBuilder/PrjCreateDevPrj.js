//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IK2OCGG60MoreImports*/
import {tabNT,tabFS} from "/@tabos";
import {getCloudDiskInfo,checkOutDisk,getDiskChanges,commitDisk,updateDisk,checkInDisk,genSandBoxData,restoreSandbox} from "/@disk/utils.js";
import {installPkg,uninstallPkg,redirectPkgTag,installPkgOnDisk,setupDiskPkgs} from "/@pkg/pkgUtil.js";
import {filterJSONPath} from "../filterjson.js";
/*}#1IK2OCGG60MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"diskId":{
			"name":"diskId","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"diskName":{
			"name":"diskName","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"editCfg":{
			"name":"editCfg","type":"auto",
			"required":false,
			"defaultValue":"",
			"desc":"",
		},
		"prjMeta":{
			"name":"prjMeta","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1IK2OCGG60ArgsView*/
	/*}#1IK2OCGG60ArgsView*/
};

/*#{1IK2OCGG60StartDoc*/
/*}#1IK2OCGG60StartDoc*/
//----------------------------------------------------------------------------
let PrjCreateDevPrj=async function(session){
	let diskId,diskName,editCfg,prjMeta;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Start,CreateTTY,TipCheckOut,CheckOutDisk,TipFilterJSON,FilterJSON,CheckSetupScript,SetupScript,TipError,SaveEditCfg,AskOpenPrj,OpenIDE,Exit,IsBackend,HasBackend,TipNoBackend,TipEnd;
	let tty=null;
	
	/*#{1IK2OCGG60LocalVals*/
	/*}#1IK2OCGG60LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			diskId=input.diskId;
			diskName=input.diskName;
			editCfg=input.editCfg;
			prjMeta=input.prjMeta;
		}else{
			diskId=undefined;
			diskName=undefined;
			editCfg=undefined;
			prjMeta=undefined;
		}
		/*#{1IK2OCGG60ParseArgs*/
		/*}#1IK2OCGG60ParseArgs*/
	}
	
	/*#{1IK2OCGG60PreContext*/
	/*}#1IK2OCGG60PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IK2OCGG60PostContext*/
	/*}#1IK2OCGG60PostContext*/
	let agent,segs={};
	segs["Start"]=Start=async function(input){//:1IK2RV2SP0
		let result=input;
		/*#{1IK2RV2SP0Code*/
		false
		/*}#1IK2RV2SP0Code*/
		return {seg:IsBackend,result:(result),preSeg:"1IK2RV2SP0",outlet:"1IK2S287H0",catchSeg:TipError,catchlet:"1IK2S287H1"};
	};
	Start.jaxId="1IK2RV2SP0"
	Start.url="Start@"+agentURL
	
	segs["CreateTTY"]=CreateTTY=async function(input){//:1IK2RBN550
		let result=input
		/*#{1IK2RBN550Code*/
		tty=await session.WSCall_CreateTTY();
		/*}#1IK2RBN550Code*/
		return {seg:TipCheckOut,result:(result),preSeg:"1IK2RBN550",outlet:"1IK2RC6560"};
	};
	CreateTTY.jaxId="1IK2RBN550"
	CreateTTY.url="CreateTTY@"+agentURL
	
	segs["TipCheckOut"]=TipCheckOut=async function(input){//:1IK2RF0FP0
		let result=input;
		let opts={};
		let role="assistant";
		let content=(($ln==="CN")?("下载项目内容……"):("Downloading project content..."));
		session.addChatText(role,content,opts);
		return {seg:CheckOutDisk,result:(result),preSeg:"1IK2RF0FP0",outlet:"1IK2RJOOU1"};
	};
	TipCheckOut.jaxId="1IK2RF0FP0"
	TipCheckOut.url="TipCheckOut@"+agentURL
	
	segs["CheckOutDisk"]=CheckOutDisk=async function(input){//:1IK2RE3MV0
		let result=input
		/*#{1IK2RE3MV0Code*/
		await checkOutDisk(tty,diskId,null,diskName,false);
		await setupDiskPkgs(tty,diskName);
		/*}#1IK2RE3MV0Code*/
		return {seg:TipFilterJSON,result:(result),preSeg:"1IK2RE3MV0",outlet:"1IK2RJOOU0"};
	};
	CheckOutDisk.jaxId="1IK2RE3MV0"
	CheckOutDisk.url="CheckOutDisk@"+agentURL
	
	segs["TipFilterJSON"]=TipFilterJSON=async function(input){//:1IK2RFIAF0
		let result=input;
		let opts={};
		let role="assistant";
		let content=(($ln==="CN")?("更新配置文件……"):("Updating configuration file..."));
		session.addChatText(role,content,opts);
		return {seg:FilterJSON,result:(result),preSeg:"1IK2RFIAF0",outlet:"1IK2RJOOU2"};
	};
	TipFilterJSON.jaxId="1IK2RFIAF0"
	TipFilterJSON.url="TipFilterJSON@"+agentURL
	
	segs["FilterJSON"]=FilterJSON=async function(input){//:1IK2RHL740
		let result=input
		/*#{1IK2RHL740Code*/
		let path,vals,userVO;
		path="/"+diskName;
		vals={
			prj_path:path,
			prj_name:diskName
		};
		if(await tabNT.checkLogin(true)){
			userVO=tabNT.loginVO;
			vals.email=userVO.email;
			vals.user_id=vals.userId;
			vals.user_name=vals.name;
		}
		await filterJSONPath(path,vals);
		/*}#1IK2RHL740Code*/
		return {seg:CheckSetupScript,result:(result),preSeg:"1IK2RHL740",outlet:"1IK2RJOOU3"};
	};
	FilterJSON.jaxId="1IK2RHL740"
	FilterJSON.url="FilterJSON@"+agentURL
	
	segs["CheckSetupScript"]=CheckSetupScript=async function(input){//:1IK2RJ3LR0
		let result=input;
		/*#{1IK2RJ3LR0Start*/
		let setup;
		try{
			setup=(await import(`/~/${diskName}/setup.js`)).setupPrj;
		}catch(err){
			setup=null;
		}
		/*}#1IK2RJ3LR0Start*/
		if(!!setup){
			return {seg:SetupScript,result:(input),preSeg:"1IK2RJ3LR0",outlet:"1IK2RJOOU4"};
		}
		/*#{1IK2RJ3LR0Post*/
		/*}#1IK2RJ3LR0Post*/
		return {seg:SaveEditCfg,result:(result),preSeg:"1IK2RJ3LR0",outlet:"1IK2RJOOU5"};
	};
	CheckSetupScript.jaxId="1IK2RJ3LR0"
	CheckSetupScript.url="CheckSetupScript@"+agentURL
	
	segs["SetupScript"]=SetupScript=async function(input){//:1IK2RKCBN0
		let result;
		let sourcePath=pathLib.joinTabOSURL(basePath,"./PrjTabOSPrjSetup.js");
		let arg={"dirPath":"/"+diskName,"setupType":"setupPrj"};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:SaveEditCfg,result:(result),preSeg:"1IK2RKCBN0",outlet:"1IK2RUJD70"};
	};
	SetupScript.jaxId="1IK2RKCBN0"
	SetupScript.url="SetupScript@"+agentURL
	
	segs["TipError"]=TipError=async function(input){//:1IK2RVNMD0
		let result=input;
		let opts={};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {result:result};
	};
	TipError.jaxId="1IK2RVNMD0"
	TipError.url="TipError@"+agentURL
	
	segs["SaveEditCfg"]=SaveEditCfg=async function(input){//:1IKRDIMN40
		let result=input
		/*#{1IKRDIMN40Code*/
		//Pre-define active files when open the project in CCEdit:
		if(editCfg){
			await tabFS.writeFile(`/doc/tabstudio/_${diskName}.json`,JSON.stringify(editCfg,null,"\t"),"utf8");
		}
		/*}#1IKRDIMN40Code*/
		return {seg:AskOpenPrj,result:(result),preSeg:"1IKRDIMN40",outlet:"1IKRDKAK70"};
	};
	SaveEditCfg.jaxId="1IKRDIMN40"
	SaveEditCfg.url="SaveEditCfg@"+agentURL
	
	segs["AskOpenPrj"]=AskOpenPrj=async function(input){//:1IK2S4UGP0
		let prompt=((($ln==="CN")?("开发项目工程已创建，是否在IDE里打开工程？"):("Development project has been created, do you want to open it in the IDE?")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("在IDE中打开工程"):("Open project in IDE")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("退出，不打开工程"):("Exit without opening project")),code:1},
		];
		let result="";
		let item=null;
		
		/*#{1IK2S4UGP0PreCodes*/
		/*}#1IK2S4UGP0PreCodes*/
		if(silent){
			result="";
			return {seg:OpenIDE,result:(result),preSeg:"1IK2S4UGP0",outlet:"1IK2S4UGC0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		/*#{1IK2S4UGP0PostCodes*/
		/*}#1IK2S4UGP0PostCodes*/
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:OpenIDE,result:(result),preSeg:"1IK2S4UGP0",outlet:"1IK2S4UGC0"};
		}else if(item.code===1){
			return {seg:Exit,result:(result),preSeg:"1IK2S4UGP0",outlet:"1IK2S4UGC2"};
		}
		/*#{1IK2S4UGP0FinCodes*/
		/*}#1IK2S4UGP0FinCodes*/
		return {result:result};
	};
	AskOpenPrj.jaxId="1IK2S4UGP0"
	AskOpenPrj.url="AskOpenPrj@"+agentURL
	
	segs["OpenIDE"]=OpenIDE=async function(input){//:1IK2S9VEK0
		let result=input
		/*#{1IK2S9VEK0Code*/
		//Open it in IDE:
		let startURL=`${document.location.origin}/@tabedit?path=${encodeURIComponent(diskName)}`;
		if(window.openTabOSAppPage){
			window.openTabOSAppPage(startURL);
		}else{
			window.open(startURL);
		}
		result={result:"Finish",content:"Project created, and opened in an new IDE."};
		/*}#1IK2S9VEK0Code*/
		return {result:result};
	};
	OpenIDE.jaxId="1IK2S9VEK0"
	OpenIDE.url="OpenIDE@"+agentURL
	
	segs["Exit"]=Exit=async function(input){//:1IK2SAA710
		let result=input
		/*#{1IK2SAA710Code*/
		result={result:"Finish",content:"Project created."};
		/*}#1IK2SAA710Code*/
		return {result:result};
	};
	Exit.jaxId="1IK2SAA710"
	Exit.url="Exit@"+agentURL
	
	segs["IsBackend"]=IsBackend=async function(input){//:1ILCQGG880
		let result=input;
		if(prjMeta.backend){
			return {seg:HasBackend,result:(input),preSeg:"1ILCQGG880",outlet:"1ILCQSBT10"};
		}
		return {seg:CreateTTY,result:(result),preSeg:"1ILCQGG880",outlet:"1ILCQSBT11"};
	};
	IsBackend.jaxId="1ILCQGG880"
	IsBackend.url="IsBackend@"+agentURL
	
	segs["HasBackend"]=HasBackend=async function(input){//:1ILCQI90F0
		let result=input;
		/*#{1ILCQI90F0Start*/
		let hasBackend,res;
		hasBackend=false;
		res=await tabNT.makeCall("AhListAgentNodes",{});
		if(res && res.code===200){
			hasBackend=true;
		}
		/*}#1ILCQI90F0Start*/
		if(!hasBackend){
			return {seg:TipNoBackend,result:(input),preSeg:"1ILCQI90F0",outlet:"1ILCQSBT12"};
		}
		/*#{1ILCQI90F0Post*/
		/*}#1ILCQI90F0Post*/
		return {seg:CreateTTY,result:(result),preSeg:"1ILCQI90F0",outlet:"1ILCQSBT13"};
	};
	HasBackend.jaxId="1ILCQI90F0"
	HasBackend.url="HasBackend@"+agentURL
	
	segs["TipNoBackend"]=TipNoBackend=async function(input){//:1ILCQJ5HR0
		let prompt=((($ln==="CN")?("当前项目运行在后端，需要部署在本地的AI2Apps实例。当前AI2Apps环境不是本地部署的，或者后端没有正常运行。如果继续创建工程，你可以查看/编辑工程内容，但是无法运行。是否仍然创建项目？"):("This project is running on the backend and requires deployment on a local AI2Apps instance. The current AI2Apps environment is not deployed locally, or the backend is not running properly. If you continue to create the project, you can view/edit the project content but cannot run it. Do you still want to create the project?")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("放弃创建工程"):("Cancel creating project")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("仍然创建工程"):("Continue Creating Project")),code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:TipEnd,result:(result),preSeg:"1ILCQJ5HR0",outlet:"1ILCQJ5H80"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:TipEnd,result:(result),preSeg:"1ILCQJ5HR0",outlet:"1ILCQJ5H80"};
		}else if(item.code===1){
			return {seg:CreateTTY,result:(result),preSeg:"1ILCQJ5HR0",outlet:"1ILCQJ5H81"};
		}
		return {result:result};
	};
	TipNoBackend.jaxId="1ILCQJ5HR0"
	TipNoBackend.url="TipNoBackend@"+agentURL
	
	segs["TipEnd"]=TipEnd=async function(input){//:1ILCQR3M10
		let result=input
		/*#{1ILCQR3M10Code*/
		/*}#1ILCQR3M10Code*/
		return {result:result};
	};
	TipEnd.jaxId="1ILCQR3M10"
	TipEnd.url="TipEnd@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"PrjCreateDevPrj",
		url:agentURL,
		autoStart:true,
		jaxId:"1IK2OCGG60",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{diskId,diskName,editCfg,prjMeta}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IK2OCGG60PreEntry*/
			/*}#1IK2OCGG60PreEntry*/
			result={seg:Start,"input":input};
			/*#{1IK2OCGG60PostEntry*/
			/*}#1IK2OCGG60PostEntry*/
			return result;
		},
		/*#{1IK2OCGG60MoreAgentAttrs*/
		/*}#1IK2OCGG60MoreAgentAttrs*/
	};
	/*#{1IK2OCGG60PostAgent*/
	/*}#1IK2OCGG60PostAgent*/
	return agent;
};
/*#{1IK2OCGG60ExCodes*/
/*}#1IK2OCGG60ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IK2OCGG60PostDoc*/
/*}#1IK2OCGG60PostDoc*/


export default PrjCreateDevPrj;
export{PrjCreateDevPrj};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IK2OCGG60",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IK2OCGG61",
//			"attrs": {
//				"PrjCreateDevPrj": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IK2OCGG67",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IK2OCGG70",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IK2OCGG71",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IK2OCGG72",
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
//			"jaxId": "1IK2OCGG62",
//			"attrs": {}
//		},
//		"entry": "Start",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IK2OCGG63",
//			"attrs": {
//				"diskId": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IK2P0N7D0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"diskName": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IK2P0N7D1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"editCfg": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IKRDI1NG0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "false"
//					}
//				},
//				"prjMeta": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ILCPJFAR0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IK2OCGG64",
//			"attrs": {
//				"tty": {
//					"type": "auto",
//					"valText": "null"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IK2OCGG65",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IK2OCGG66",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1IK2RV2SP0",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "80",
//						"y": "360",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK2S287L0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK2S287L1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK2S287H0",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILCQGG880"
//						},
//						"catchlet": {
//							"jaxId": "1IK2S287H1",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK2RVNMD0"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IK2RBN550",
//					"attrs": {
//						"id": "CreateTTY",
//						"viewName": "",
//						"label": "",
//						"x": "545",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK2RCNNG0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK2RCNNG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK2RC6560",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK2RF0FP0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IK2RF0FP0",
//					"attrs": {
//						"id": "TipCheckOut",
//						"viewName": "",
//						"label": "",
//						"x": "775",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK2RJOP22",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK2RJOP23",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": {
//							"type": "string",
//							"valText": "Downloading project content...",
//							"localize": {
//								"EN": "Downloading project content...",
//								"CN": "下载项目内容……"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IK2RJOOU1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK2RE3MV0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IK2RE3MV0",
//					"attrs": {
//						"id": "CheckOutDisk",
//						"viewName": "",
//						"label": "",
//						"x": "1015",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK2RJOP20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK2RJOP21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK2RJOOU0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK2RFIAF0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IK2RFIAF0",
//					"attrs": {
//						"id": "TipFilterJSON",
//						"viewName": "",
//						"label": "",
//						"x": "1265",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK2RJOP24",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK2RJOP25",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": {
//							"type": "string",
//							"valText": "Updating configuration file...",
//							"localize": {
//								"EN": "Updating configuration file...",
//								"CN": "更新配置文件……"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IK2RJOOU2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK2RHL740"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IK2RHL740",
//					"attrs": {
//						"id": "FilterJSON",
//						"viewName": "",
//						"label": "",
//						"x": "1520",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK2RJOP26",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK2RJOP27",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK2RJOOU3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK2RJ3LR0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IK2RJ3LR0",
//					"attrs": {
//						"id": "CheckSetupScript",
//						"viewName": "",
//						"label": "",
//						"x": "1760",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK2RJOP28",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK2RJOP29",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK2RJOOU5",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IKRDIMN40"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IK2RJOOU4",
//									"attrs": {
//										"id": "FindScript",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IK2RJOP210",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IK2RJOP211",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!setup"
//									},
//									"linkedSeg": "1IK2RKCBN0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IK2RKCBN0",
//					"attrs": {
//						"id": "SetupScript",
//						"viewName": "",
//						"label": "",
//						"x": "2045",
//						"y": "270",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK2RUJDA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK2RUJDA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/PrjTabOSPrjSetup.js",
//						"argument": "{\"dirPath\":\"#\\\"/\\\"+diskName\",\"setupType\":\"setupPrj\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IK2RUJD70",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKRDIMN40"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IK2RVNMD0",
//					"attrs": {
//						"id": "TipError",
//						"viewName": "",
//						"label": "",
//						"x": "265",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IK2S287L2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK2S287L3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IK2S287H2",
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
//					"jaxId": "1IKRDIMN40",
//					"attrs": {
//						"id": "SaveEditCfg",
//						"viewName": "",
//						"label": "",
//						"x": "2290",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKRDKAKA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKRDKAKA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKRDKAK70",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK2S4UGP0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IK2S4UGP0",
//					"attrs": {
//						"id": "AskOpenPrj",
//						"viewName": "",
//						"label": "",
//						"x": "2545",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Development project has been created, do you want to open it in the IDE?",
//							"localize": {
//								"EN": "Development project has been created, do you want to open it in the IDE?",
//								"CN": "开发项目工程已创建，是否在IDE里打开工程？"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IK2S9NC90",
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
//									"jaxId": "1IK2S4UGC0",
//									"attrs": {
//										"id": "Open",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Open project in IDE",
//											"localize": {
//												"EN": "Open project in IDE",
//												"CN": "在IDE中打开工程"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IK2S9NCB0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IK2S9NCB1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IK2S9VEK0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IK2S4UGC2",
//									"attrs": {
//										"id": "Exit",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Exit without opening project",
//											"localize": {
//												"EN": "Exit without opening project",
//												"CN": "退出，不打开工程"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IK2S9NCB2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IK2S9NCB3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IK2SAA710"
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
//					"def": "code",
//					"jaxId": "1IK2S9VEK0",
//					"attrs": {
//						"id": "OpenIDE",
//						"viewName": "",
//						"label": "",
//						"x": "2815",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IK2SAUJI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK2SAUJI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK2SAUJE0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IK2SAA710",
//					"attrs": {
//						"id": "Exit",
//						"viewName": "",
//						"label": "",
//						"x": "2815",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IK2SAUJI2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK2SAUJI3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK2SAUJE1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILCQGG880",
//					"attrs": {
//						"id": "IsBackend",
//						"viewName": "",
//						"label": "",
//						"x": "270",
//						"y": "310",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILCQSBT90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILCQSBT91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILCQSBT11",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IK2RBN550"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILCQSBT10",
//									"attrs": {
//										"id": "Backend",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILCQSBT92",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILCQSBT93",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#prjMeta.backend"
//									},
//									"linkedSeg": "1ILCQI90F0"
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
//					"jaxId": "1ILCQI90F0",
//					"attrs": {
//						"id": "HasBackend",
//						"viewName": "",
//						"label": "",
//						"x": "530",
//						"y": "155",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILCQSBT94",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILCQSBT95",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILCQSBT13",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1ILCTBJ880"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILCQSBT12",
//									"attrs": {
//										"id": "NoBackend",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILCQSBT96",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILCQSBT97",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!hasBackend"
//									},
//									"linkedSeg": "1ILCQJ5HR0"
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
//					"jaxId": "1ILCQJ5HR0",
//					"attrs": {
//						"id": "TipNoBackend",
//						"viewName": "",
//						"label": "",
//						"x": "805",
//						"y": "140",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "This project is running on the backend and requires deployment on a local AI2Apps instance. The current AI2Apps environment is not deployed locally, or the backend is not running properly. If you continue to create the project, you can view/edit the project content but cannot run it. Do you still want to create the project?",
//							"localize": {
//								"EN": "This project is running on the backend and requires deployment on a local AI2Apps instance. The current AI2Apps environment is not deployed locally, or the backend is not running properly. If you continue to create the project, you can view/edit the project content but cannot run it. Do you still want to create the project?",
//								"CN": "当前项目运行在后端，需要部署在本地的AI2Apps实例。当前AI2Apps环境不是本地部署的，或者后端没有正常运行。如果继续创建工程，你可以查看/编辑工程内容，但是无法运行。是否仍然创建项目？"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1ILCQSBT14",
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
//									"jaxId": "1ILCQJ5H80",
//									"attrs": {
//										"id": "GiveUp",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Cancel creating project",
//											"localize": {
//												"EN": "Cancel creating project",
//												"CN": "放弃创建工程"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILCQSBT98",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILCQSBT99",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1ILCQR3M10"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1ILCQJ5H81",
//									"attrs": {
//										"id": "Create",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Continue Creating Project",
//											"localize": {
//												"EN": "Continue Creating Project",
//												"CN": "仍然创建工程"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILCQSBT910",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILCQSBT911",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1ILCQROTK0"
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
//					"def": "code",
//					"jaxId": "1ILCQR3M10",
//					"attrs": {
//						"id": "TipEnd",
//						"viewName": "",
//						"label": "",
//						"x": "1065",
//						"y": "110",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILCQSBT912",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILCQSBT913",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILCQSBT15",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1ILCQROTK0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "985",
//						"y": "240",
//						"outlet": {
//							"jaxId": "1ILCQSBT914",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILCTBJ880"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1ILCQRTHD0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "570",
//						"y": "240",
//						"outlet": {
//							"jaxId": "1ILCQSBT915",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK2RBN550"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1ILCTBJ880",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "715",
//						"y": "240",
//						"outlet": {
//							"jaxId": "1ILCTBQDR0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILCQRTHD0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}