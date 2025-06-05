//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHHLMCC50MoreImports*/
import fsp from 'fs/promises';
import os from 'os';
/*}#1IHHLMCC50MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"filePath":{
			"name":"filePath","type":"auto",
			"defaultValue":"",
			"desc":"要读取的文件路径列表，请提供完整的绝对路径，示例：['/home/1.pdf','/home/2.docx']",
		}
	},
	/*#{1IHHLMCC50ArgsView*/
	/*}#1IHHLMCC50ArgsView*/
};

/*#{1IHHLMCC50StartDoc*/
import pdfParse from 'pdf-parse/lib/pdf-parse.js';


async function readPdf(pdfUrl) {
	const dataBuffer = await fsp.readFile(pdfUrl);

	try {
		const data = await pdfParse(dataBuffer);
		console.log("提取的文本：\n", data.text);
		console.log("页数：", data.numpages);
		return data.text.slice(0,10000);
	} catch (err) {
		console.error("解析失败:", err);
		return err;
	}
}

import mammoth from 'mammoth';

async function readDocx(filePath) {
try {
const buffer = await fsp.readFile(filePath);
const { value: text } = await mammoth.extractRawText({ buffer });
return text.slice(0,10000);
} catch (err) {
console.error('读取 DOCX 失败:', err);
return null;
}
}


function getFileExtension(filename) {

return pathLib.extname(filename).slice(1).toLowerCase();
}

function expandTilde(filePath) {
if (filePath.startsWith('~')) {
		console.log(os.homedir());
return pathLib.join(os.homedir(), filePath.slice(1));
}
return filePath;
}

/*}#1IHHLMCC50StartDoc*/
//----------------------------------------------------------------------------
let ToolReadFile=async function(session){
	let filePath;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,ReadFile,Check,ReadPDF,ReadDoc,Loop,exit;
	/*#{1IHHLMCC50LocalVals*/
	let all_content = [];
	/*}#1IHHLMCC50LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			filePath=input.filePath;
		}else{
			filePath=undefined;
		}
		/*#{1IHHLMCC50ParseArgs*/
		/*}#1IHHLMCC50ParseArgs*/
	}
	
	/*#{1IHHLMCC50PreContext*/
	/*}#1IHHLMCC50PreContext*/
	context={};
	/*#{1IHHLMCC50PostContext*/
	/*}#1IHHLMCC50PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IHHLN9J60
		let result=input;
		let missing=false;
		let smartAsk=false;
		/*#{1IHHLN9J60PreCodes*/
		/*}#1IHHLN9J60PreCodes*/
		if(filePath===undefined || filePath==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		/*#{1IHHLN9J60PostCodes*/
		/*}#1IHHLN9J60PostCodes*/
		return {seg:Loop,result:(result),preSeg:"1IHHLN9J60",outlet:"1IHHLO8ID0"};
	};
	FixArgs.jaxId="1IHHLN9J60"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["ReadFile"]=ReadFile=async function(input){//:1IHHLO2SF0
		let result=input
		/*#{1IHHLO2SF0Code*/
		try{
			let content;
			content=await fsp.readFile(input,"utf8");
			all_content.push({filePath:input,content:content.slice(0,10000)});
			result={result:"Finish",content:content};
		}catch(err){
			if(filePath[0]!="/"){
				result={result:"Fail",content:`文件路径错误，需要"/"开头的完整路径，而不是相对路径。`};
			}else{
				result={result:"Fail",content:`读取文件内容失败: ${""+err}`};
			}
		}
		/*}#1IHHLO2SF0Code*/
		return {result:result};
	};
	ReadFile.jaxId="1IHHLO2SF0"
	ReadFile.url="ReadFile@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1INQITAF80
		let result=input;
		if(getFileExtension(input) === "pdf"){
			return {seg:ReadPDF,result:(input),preSeg:"1INQITAF80",outlet:"1INQITIV40"};
		}
		if(getFileExtension(input) === "doc" || getFileExtension(input) === "docx"){
			return {seg:ReadDoc,result:(input),preSeg:"1INQITAF80",outlet:"1INQM7AM70"};
		}
		return {seg:ReadFile,result:(result),preSeg:"1INQITAF80",outlet:"1INQITIV50"};
	};
	Check.jaxId="1INQITAF80"
	Check.url="Check@"+agentURL
	
	segs["ReadPDF"]=ReadPDF=async function(input){//:1INQJ4EML0
		let result=input
		/*#{1INQJ4EML0Code*/
		result = await readPdf(input);
		all_content.push({filePath:input,content:result});
		/*}#1INQJ4EML0Code*/
		return {result:result};
	};
	ReadPDF.jaxId="1INQJ4EML0"
	ReadPDF.url="ReadPDF@"+agentURL
	
	segs["ReadDoc"]=ReadDoc=async function(input){//:1INQM8KL10
		let result=input
		/*#{1INQM8KL10Code*/
		result = await readDocx(input);
		all_content.push({filePath:input,content:result});
		/*}#1INQM8KL10Code*/
		return {result:result};
	};
	ReadDoc.jaxId="1INQM8KL10"
	ReadDoc.url="ReadDoc@"+agentURL
	
	segs["Loop"]=Loop=async function(input){//:1INTDVOS90
		let result=input;
		let list=filePath;
		let i,n,item,loopR;
		/*#{1INTDVOS90PreLoop*/
		/*}#1INTDVOS90PreLoop*/
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			/*#{1INTDVOS90InLoopPre*/
			if(item){
				if(item.startsWith("hub")){
					item = await session.getHubPath(item);
				}
			}
			if(item){
				item=expandTilde(item);
			}
			/*}#1INTDVOS90InLoopPre*/
			loopR=await session.runAISeg(agent,Check,item,"1INTDVOS90","1INTE0VFF0")
			if(loopR==="break"){
				break;
			}
			/*#{1INTDVOS90InLoopPost*/
			/*}#1INTDVOS90InLoopPost*/
		}
		/*#{1INTDVOS90PostCodes*/
		/*}#1INTDVOS90PostCodes*/
		return {seg:exit,result:(result),preSeg:"1INTDVOS90",outlet:"1INTE0VFG0"};
	};
	Loop.jaxId="1INTDVOS90"
	Loop.url="Loop@"+agentURL
	
	segs["exit"]=exit=async function(input){//:1INTE3E6E0
		let result=input
		/*#{1INTE3E6E0Code*/
		result=JSON.stringify(all_content);
		/*}#1INTE3E6E0Code*/
		return {result:result};
	};
	exit.jaxId="1INTE3E6E0"
	exit.url="exit@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ToolReadFile",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHHLMCC50",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{filePath}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHHLMCC50PreEntry*/
			/*}#1IHHLMCC50PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IHHLMCC50PostEntry*/
			/*}#1IHHLMCC50PostEntry*/
			return result;
		},
		/*#{1IHHLMCC50MoreAgentAttrs*/
		/*}#1IHHLMCC50MoreAgentAttrs*/
	};
	/*#{1IHHLMCC50PostAgent*/
	/*}#1IHHLMCC50PostAgent*/
	return agent;
};
/*#{1IHHLMCC50ExCodes*/
/*}#1IHHLMCC50ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "ToolReadFile",
		description: "这是读取文件内容的工具。如果需要读取文件的文本内容，请调用本工具。\n请提供要读取的文件的完整路径，不要提供相对路径。",
		parameters:{
			type: "object",
			properties:{
				filePath:{type:"auto",description:"要读取的文件路径列表，请提供完整的绝对路径，示例：['/home/1.pdf','/home/2.docx']"}
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
		name:"ToolReadFile",showName:"ToolReadFile",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"filePath":{name:"filePath",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","filePath","codes","desc"],
		desc:"这是读取文件内容的工具。如果需要读取文件的文本内容，请调用本工具。\n请提供要读取的文件的完整路径，不要提供相对路径。"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolReadFile"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['filePath']=");this.genAttrStatement(seg.getAttr("filePath"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/builder_new/ai/ToolReadFile.js",args,false);`);coder.newLine();
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
/*#{1IHHLMCC50PostDoc*/
/*}#1IHHLMCC50PostDoc*/


export default ToolReadFile;
export{ToolReadFile,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHHLMCC50",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHHLMCC51",
//			"attrs": {
//				"ToolReadFile": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHHLMCC57",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHHLMCC60",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHHLMCC61",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHHLMCC62",
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
//			"jaxId": "1IHHLMCC52",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "FixArgs",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHHLMCC53",
//			"attrs": {
//				"filePath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHHLN1VR0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "要读取的文件路径列表，请提供完整的绝对路径，示例：['/home/1.pdf','/home/2.docx']"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHHLMCC54",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IHHLMCC55",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHHLMCC56",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHHLN9J60",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "-190",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1IHHLO8ID0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INTDVOS90"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHHLO2SF0",
//					"attrs": {
//						"id": "ReadFile",
//						"viewName": "",
//						"label": "",
//						"x": "525",
//						"y": "390",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IHHLOHQ70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHLOHQ71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHHLO8IE0",
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
//					"def": "brunch",
//					"jaxId": "1INQITAF80",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "325",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INQJ4HM80",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INQJ4HM81",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INQITIV50",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IHHLO2SF0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INQITIV40",
//									"attrs": {
//										"id": "pdf",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INQJ4HM82",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INQJ4HM83",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#getFileExtension(input) === \"pdf\""
//									},
//									"linkedSeg": "1INQJ4EML0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INQM7AM70",
//									"attrs": {
//										"id": "doc",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INQM7V6J0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INQM7V6J1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#getFileExtension(input) === \"doc\" || getFileExtension(input) === \"docx\""
//									},
//									"linkedSeg": "1INQM8KL10"
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
//					"jaxId": "1INQJ4EML0",
//					"attrs": {
//						"id": "ReadPDF",
//						"viewName": "",
//						"label": "",
//						"x": "525",
//						"y": "165",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INQJ4HM84",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INQJ4HM85",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INQJ4HM30",
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
//					"jaxId": "1INQM8KL10",
//					"attrs": {
//						"id": "ReadDoc",
//						"viewName": "",
//						"label": "",
//						"x": "525",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INQM8VP90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INQM8VP91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INQM8VP50",
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
//					"def": "loopArray",
//					"jaxId": "1INTDVOS90",
//					"attrs": {
//						"id": "Loop",
//						"viewName": "",
//						"label": "",
//						"x": "40",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INTE34TJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INTE34TJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#filePath",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1INTE0VFF0",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INQITAF80"
//						},
//						"catchlet": {
//							"jaxId": "1INTE0VFG0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INTE3E6E0"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1INTE3E6E0",
//					"attrs": {
//						"id": "exit",
//						"viewName": "",
//						"label": "",
//						"x": "235",
//						"y": "450",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INTE3QT50",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INTE3QT51",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INTE3QSS0",
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
//				}
//			]
//		},
//		"desc": "这是读取文件内容的工具。如果需要读取文件的文本内容，请调用本工具。\n请提供要读取的文件的完整路径，不要提供相对路径。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}