//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHN60ESM0MoreImports*/
import fsp from 'fs/promises';
/*}#1IHN60ESM0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"path":{
			"name":"path","type":"string",
			"defaultValue":"",
			"desc":"要展示结构的目录路径",
		},
		"deep":{
			"name":"deep","type":"integer",
			"required":false,
			"defaultValue":"",
			"desc":"展示内容的最大深度。默认为3，如果为1，则只展示路径目录内一层的项目。",
		}
	},
	/*#{1IHN60ESM0ArgsView*/
	/*}#1IHN60ESM0ArgsView*/
};

/*#{1IHN60ESM0StartDoc*/
async function generateDirectoryTree(dirPath, maxDepth, currentDepth = 0) {
	if (currentDepth > maxDepth) {
		return '...\n';
	}

	let result = '';
	try {
		let fileNum=0;
		const entries = await fsp.readdir(dirPath, { withFileTypes: true });

		if (entries.length > 50) {
			result += `  `.repeat(currentDepth) + `- Too many files...\n`;
			return result;
		}

		for (const entry of entries) {
			const entryPath = pathLib.join(dirPath, entry.name);
			const isDirectory = entry.isDirectory();


			if (isDirectory) {
				result += `  `.repeat(currentDepth) + `- ${entry.name}${isDirectory ? '/' : ''}\n`;
				result += await generateDirectoryTree(entryPath, maxDepth, currentDepth + 1);
			}else{
				if(fileNum>50){
					fileNum+=1;
				}else{
					result += `  `.repeat(currentDepth) + `- ${entry.name}\n`;
					fileNum+=1;
				}
			}
		}
		if(fileNum>50){
			result += `  `.repeat(currentDepth) + `- ...more files...\n`;
		}
	} catch (err) {
		result += `  `.repeat(currentDepth) + `- [Error reading directory]\n`;
	}

	return result;
}
/*}#1IHN60ESM0StartDoc*/
//----------------------------------------------------------------------------
let ToolReadDir=async function(session){
	let path,deep;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,ShowDir;
	/*#{1IHN60ESM0LocalVals*/
	/*}#1IHN60ESM0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			path=input.path;
			deep=input.deep;
		}else{
			path=undefined;
			deep=undefined;
		}
		/*#{1IHN60ESM0ParseArgs*/
		/*}#1IHN60ESM0ParseArgs*/
	}
	
	/*#{1IHN60ESM0PreContext*/
	/*}#1IHN60ESM0PreContext*/
	context={};
	/*#{1IHN60ESM0PostContext*/
	/*}#1IHN60ESM0PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IHN61LMI0
		let result=input;
		let missing=false;
		if(path===undefined || path==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:ShowDir,result:(result),preSeg:"1IHN61LMI0",outlet:"1IHN689AR0"};
	};
	FixArgs.jaxId="1IHN61LMI0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["ShowDir"]=ShowDir=async function(input){//:1IHN68FC20
		let result=input
		/*#{1IHN68FC20Code*/
		if(!(deep>=0)){
			deep=3;
		}
		result=await generateDirectoryTree(path,deep);
		/*}#1IHN68FC20Code*/
		return {result:result};
	};
	ShowDir.jaxId="1IHN68FC20"
	ShowDir.url="ShowDir@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"ToolReadDir",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHN60ESM0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{path,deep}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHN60ESM0PreEntry*/
			/*}#1IHN60ESM0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IHN60ESM0PostEntry*/
			/*}#1IHN60ESM0PostEntry*/
			return result;
		},
		/*#{1IHN60ESM0MoreAgentAttrs*/
		/*}#1IHN60ESM0MoreAgentAttrs*/
	};
	/*#{1IHN60ESM0PostAgent*/
	/*}#1IHN60ESM0PostAgent*/
	return agent;
};
/*#{1IHN60ESM0ExCodes*/
/*}#1IHN60ESM0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "ToolReadDir",
		description: "这是获取一个目录里内容层级结构的工具/智能体，如果你想知道某个目录包含的内容，请调用这个工具。\n请提供要读取目录的完整路径，不要提供相对路径。",
		parameters:{
			type: "object",
			properties:{
				path:{type:"string",description:"要展示结构的目录路径"},
				deep:{type:"integer",description:"展示内容的最大深度。默认为3，如果为1，则只展示路径目录内一层的项目。"}
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
		name:"ToolReadDir",showName:"ToolReadDir",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"path":{name:"path",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"deep":{name:"deep",showName:undefined,type:"integer",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","path","deep","codes","desc"],
		desc:"这是获取一个目录里内容层级结构的工具/智能体，如果你想知道某个目录包含的内容，请调用这个工具。\n请提供要读取目录的完整路径，不要提供相对路径。"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolReadDir"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['path']=");this.genAttrStatement(seg.getAttr("path"));coder.packText(";");coder.newLine();
			coder.packText("args['deep']=");this.genAttrStatement(seg.getAttr("deep"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AgentBuilder/ai/ToolReadDir.js",args,false);`);coder.newLine();
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
/*#{1IHN60ESM0PostDoc*/
/*}#1IHN60ESM0PostDoc*/


export default ToolReadDir;
export{ToolReadDir,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHN60ESM0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHN60ESM1",
//			"attrs": {
//				"ToolReadDir": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHN60ESM7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHN60ESM8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHN60ESM9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHN60ESM10",
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
//			"jaxId": "1IHN60ESM2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHN60ESM3",
//			"attrs": {
//				"path": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHN689AR1",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要展示结构的目录路径"
//					}
//				},
//				"deep": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHN689AR2",
//					"attrs": {
//						"type": "Integer",
//						"mockup": "\"\"",
//						"desc": "展示内容的最大深度。默认为3，如果为1，则只展示路径目录内一层的项目。",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHN60ESM4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IHN60ESM5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHN60ESM6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHN61LMI0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "80",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IHN689AR0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHN68FC20"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHN68FC20",
//					"attrs": {
//						"id": "ShowDir",
//						"viewName": "",
//						"label": "",
//						"x": "280",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHN68RAA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHN68RAA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHN68RA90",
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
//		"desc": "这是获取一个目录里内容层级结构的工具/智能体，如果你想知道某个目录包含的内容，请调用这个工具。\n请提供要读取目录的完整路径，不要提供相对路径。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}