//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1INQRHVQR0MoreImports*/
import fsp from 'fs/promises';
import XLSX from "xlsx";
import os from "os";
/*}#1INQRHVQR0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"content":{
			"name":"content","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"filePath":{
			"name":"filePath","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"append":{
			"name":"append","type":"bool",
			"required":true,
			"defaultValue":"",
			"desc":"是否追加写入文件，true表示追加写入，false表示覆盖写入",
		}
	},
	/*#{1INQRHVQR0ArgsView*/
	/*}#1INQRHVQR0ArgsView*/
};

/*#{1INQRHVQR0StartDoc*/
function getFileExtension(filename) {

return pathLib.extname(filename).slice(1).toLowerCase();
	
}




function writeExcelFromCSV(csvData, filePath) {
try {
const rows = csvData.split('\n');
const data = rows.map(row => {
return row.split('^|^').map(field => field.trim());
});
const wb = XLSX.utils.book_new();
const ws = XLSX.utils.aoa_to_sheet(data);
XLSX.utils.book_append_sheet(wb, ws, "Sheet1");
XLSX.writeFile(wb, filePath);
return `Excel 文件已生成: ${filePath}`;
} catch (error) {
return `生成Excel文件时出错: ${error}`;
}
}


function expandTilde(filePath) {
if (filePath.startsWith('~')) {
		console.log(os.homedir());
return pathLib.join(os.homedir(), filePath.slice(1));
}
return filePath;
}

/*}#1INQRHVQR0StartDoc*/
//----------------------------------------------------------------------------
let ToolWriteFile=async function(session){
	let content,filePath,append;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,Check,Write,WriteExcel,Save,MkDir;
	/*#{1INQRHVQR0LocalVals*/
	/*}#1INQRHVQR0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			content=input.content;
			filePath=input.filePath;
			append=input.append;
		}else{
			content=undefined;
			filePath=undefined;
			append=undefined;
		}
		/*#{1INQRHVQR0ParseArgs*/
		if(filePath){
			filePath=expandTilde(filePath);
		}
		/*}#1INQRHVQR0ParseArgs*/
	}
	
	/*#{1INQRHVQR0PreContext*/
	
	/*}#1INQRHVQR0PreContext*/
	context={};
	/*#{1INQRHVQR0PostContext*/
	/*}#1INQRHVQR0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1INQR9RA40
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(content===undefined || content==="") missing=true;
		if(filePath===undefined || filePath==="") missing=true;
		if(append===undefined || append==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:MkDir,result:(result),preSeg:"1INQR9RA40",outlet:"1INQRHVQS0"};
	};
	FixArgs.jaxId="1INQR9RA40"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1INQRH7IC0
		let result=input;
		if(getFileExtension(filePath) === "xlsx" || getFileExtension(filePath) === "xls"){
			return {seg:WriteExcel,result:(input),preSeg:"1INQRH7IC0",outlet:"1INQRHVQS1"};
		}
		return {seg:Write,result:(result),preSeg:"1INQRH7IC0",outlet:"1INQRHVQU0"};
	};
	Check.jaxId="1INQRH7IC0"
	Check.url="Check@"+agentURL
	
	segs["Write"]=Write=async function(input){//:1INQRLQJG0
		let result=input
		/*#{1INQRLQJG0Code*/
		if(append){
			await fsp.appendFile(filePath, content, 'utf-8');
		}
		else{
			await fsp.writeFile(filePath, content, 'utf-8');
		}
		
		/*}#1INQRLQJG0Code*/
		return {seg:Save,result:(result),preSeg:"1INQRLQJG0",outlet:"1INQRLU7T0"};
	};
	Write.jaxId="1INQRLQJG0"
	Write.url="Write@"+agentURL
	
	segs["WriteExcel"]=WriteExcel=async function(input){//:1IOA7QSH90
		let result=input
		/*#{1IOA7QSH90Code*/
		result = writeExcelFromCSV(content, filePath);
		/*}#1IOA7QSH90Code*/
		return {seg:Save,result:(result),preSeg:"1IOA7QSH90",outlet:"1IOA7R19O0"};
	};
	WriteExcel.jaxId="1IOA7QSH90"
	WriteExcel.url="WriteExcel@"+agentURL
	
	segs["Save"]=Save=async function(input){//:1IOCBF0SJ0
		let result=input
		/*#{1IOCBF0SJ0Code*/
		result=await fsp.readFile(filePath);
		result=await session.saveHubFile(pathLib.basename(filePath), result);
		/*}#1IOCBF0SJ0Code*/
		return {result:result};
	};
	Save.jaxId="1IOCBF0SJ0"
	Save.url="Save@"+agentURL
	
	segs["MkDir"]=MkDir=async function(input){//:1IP1EDPSP0
		let result=input
		/*#{1IP1EDPSP0Code*/
		if(filePath){
			filePath=expandTilde(filePath);
		}
		result=await fsp.mkdir(pathLib.dirname(filePath), {recursive:true});
		/*}#1IP1EDPSP0Code*/
		return {seg:Check,result:(result),preSeg:"1IP1EDPSP0",outlet:"1IP1EI2MK0"};
	};
	MkDir.jaxId="1IP1EDPSP0"
	MkDir.url="MkDir@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ToolWriteFile",
		url:agentURL,
		autoStart:true,
		jaxId:"1INQRHVQR0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{content,filePath,append}*/){
			let result;
			parseAgentArgs(input);
			/*#{1INQRHVQR0PreEntry*/
			/*}#1INQRHVQR0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1INQRHVQR0PostEntry*/
			/*}#1INQRHVQR0PostEntry*/
			return result;
		},
		/*#{1INQRHVQR0MoreAgentAttrs*/
		/*}#1INQRHVQR0MoreAgentAttrs*/
	};
	/*#{1INQRHVQR0PostAgent*/
	/*}#1INQRHVQR0PostAgent*/
	return agent;
};
/*#{1INQRHVQR0ExCodes*/
/*}#1INQRHVQR0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "ToolWriteFile",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				content:{type:"auto",description:""},
				filePath:{type:"auto",description:""},
				append:{type:"bool",description:"是否追加写入文件，true表示追加写入，false表示覆盖写入"}
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
		name:"ToolWriteFile",showName:"ToolWriteFile",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"content":{name:"content",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"filePath":{name:"filePath",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"append":{name:"append",showName:undefined,type:"bool",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","content","filePath","append","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolWriteFile"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['content']=");this.genAttrStatement(seg.getAttr("content"));coder.packText(";");coder.newLine();
			coder.packText("args['filePath']=");this.genAttrStatement(seg.getAttr("filePath"));coder.packText(";");coder.newLine();
			coder.packText("args['append']=");this.genAttrStatement(seg.getAttr("append"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/builder_new/ai/ToolWriteFile.js",args,false);`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
			this.packUpdateContext(coder,seg);
			this.packUpdateGlobal(coder,seg);
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
/*#{1INQRHVQR0PostDoc*/
/*}#1INQRHVQR0PostDoc*/


export default ToolWriteFile;
export{ToolWriteFile,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1INQRHVQR0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1INQRHVR20",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1INQRA3240",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1INQRHVR21",
//			"attrs": {
//				"content": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1INQRHVR22",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"filePath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1INQRHVR23",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"append": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IPGFS09V0",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "\"\"",
//						"desc": "是否追加写入文件，true表示追加写入，false表示覆盖写入",
//						"enum": {
//							"type": "array",
//							"def": "Array",
//							"attrs": []
//						},
//						"required": "true"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1INQRHVR24",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1INQRHVR25",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1INQRHVR26",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1INQR9RA40",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "50",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1INQRHVQS0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IP1EDPSP0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1INQRH7IC0",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "415",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INQRHVR27",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INQRHVR28",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INQRHVQU0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1INQRLQJG0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INQRHVQS1",
//									"attrs": {
//										"id": "Excel",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INQRHVR29",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INQRHVR210",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#getFileExtension(filePath) === \"xlsx\" || getFileExtension(filePath) === \"xls\""
//									},
//									"linkedSeg": "1IOA7QSH90"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1INQRLQJG0",
//					"attrs": {
//						"id": "Write",
//						"viewName": "",
//						"label": "",
//						"x": "600",
//						"y": "185",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INQRNMV00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INQRNMV01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INQRLU7T0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOCBF0SJ0"
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
//					"def": "code",
//					"jaxId": "1IOA7QSH90",
//					"attrs": {
//						"id": "WriteExcel",
//						"viewName": "",
//						"label": "",
//						"x": "605",
//						"y": "85",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOA7R19U0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOA7R19U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOA7R19O0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOCBF0SJ0"
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
//					"def": "code",
//					"jaxId": "1IOCBF0SJ0",
//					"attrs": {
//						"id": "Save",
//						"viewName": "",
//						"label": "",
//						"x": "820",
//						"y": "85",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOCBFE9T0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOCBFE9T1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOCBFE9O0",
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
//					"def": "code",
//					"jaxId": "1IP1EDPSP0",
//					"attrs": {
//						"id": "MkDir",
//						"viewName": "",
//						"label": "",
//						"x": "245",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IP1EI2MT0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IP1EI2MT1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IP1EI2MK0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INQRH7IC0"
//						},
//						"outlets": {
//							"attrs": []
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