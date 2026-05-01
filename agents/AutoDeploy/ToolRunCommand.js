//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IUIO756A0MoreImports*/
import axios from 'axios';
import { buildFixPrompt } from "./ClaudeBridge.mjs";
/*}#1IUIO756A0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"command":{
			"name":"command","type":"auto",
			"required":true,
			"defaultValue":"",
			"desc":"A bash command",
		},
		"repo":{
			"name":"repo","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1IUIO756A0ArgsView*/
	/*}#1IUIO756A0ArgsView*/
};

/*#{1IUIO756A0StartDoc*/
async function fetchLinks(customQuery, maxResults = 5) {
		const options = {
				method: "POST",
				headers: {
						Authorization: "Bearer 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",
						"Content-Type": "application/json"
				},
				body: JSON.stringify({
						query: customQuery,
						max_results: maxResults,
						topic: "general",
						search_depth: "basic",
						include_answer: false,
						include_raw_content: false
				})
		};

		const response = await fetch("https://api.tavily.com/search", options);
		const { results = [] } = await response.json();

		return results
				.filter(r => r.url)
				.map(r => r.url);
}


async function extractArticle(url) {
		try {
				const resp = await fetch("http://8.140.204.249:8000/extract_from_url", {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ url })
				});

				const data = await resp.json();

				if (data.success) {
						// 提取成功
						return `文章链接：${url}\n文章内容：${data.text}`;
				} else {
						// 提取失败
						return `文章链接：${url}\n文章内容：提取失败`;
				}
		} catch (err) {
				console.error("提取请求出错：", err);
				return `文章链接：${url}\n文章内容：请求失败`;
		}
}


async function fetchLinksAndArticles(customQuery, maxResults = 5) {
		const links = await fetchLinks(customQuery, maxResults);

		// 并发提取正文
		const articleStrings = await Promise.all(
				links.map(link => extractArticle(link))
		);

		// 如需一个大字符串，可返回 articleStrings.join("\n---\n");
		return articleStrings.join("\n---\n");
}

async function getSolution(query) {
	const url = "http://ec2-43-199-143-95.ap-east-1.compute.amazonaws.com:222/qa/retrieve";
	let solution = "";

	try {
		const response = await fetch(url, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify({
			error_desc: query,
			tags: []
		})
	});

	let result;

	if (response.status === 404) {
		result = [];
	} else if (response.status === 200) {
		result = await response.json();
	} else {
		result = [];
		console.log(`Error: ${response.status} - ${await response.text()}`);
	}

	// Use result here
	if(result !== [] && result.data) {
		for (let item in result.data) {
			let data = result.data[item];
			let metadata = data.metadata;
			let content = data.page_content;
			if (metadata.dense_score > 0.6) {
				solution += '==============================================\n';
				solution += 'Issue: ' + content + '\n';
				solution += 'Solution: ' + metadata.solution + '\n';
			}
		}
	}
		return solution;

	} catch (error) {
		console.error('Request failed:', error);
		return "";
	}
}

async function sendRequest(error_desc, error_solution) {
	const url = "http://ec2-43-199-143-95.ap-east-1.compute.amazonaws.com:222/qa/index";

	try {
		const response = await axios.post(url, {
			error_desc: error_desc,
			error_solution: error_solution
	});

	if (response.status === 201) {
		return response.data;
	} else {
		return {
			error: "Failed to fetch data",
			status_code: response.status,
			response: response.data
			};
		}
	} catch (error) {
		console.error('Request failed:', error);
		return {
			error: "Request failed",
			message: error.message
		};
	}
}

function countTokens(text) {
let chineseChars = 0;

// Count Chinese characters (Unicode range: \u4e00 to \u9fff)
for (let i = 0; i < text.length; i++) {
const char = text[i];
if (char >= '\u4e00' && char <= '\u9fff') {
chineseChars++;
}
}

// Calculate the number of other characters
const otherChars = text.length - chineseChars;

// Return the token count based on the given formula
return Math.floor(chineseChars / 1.5 + otherChars / 4);
}

/*}#1IUIO756A0StartDoc*/
//----------------------------------------------------------------------------
let ToolRunCommand=async function(session){
	let command,repo;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,Run,UpdateSolution,Check,Fail,ClaudeFix,Check2,Success;
	/*#{1IUIO756A0LocalVals*/
	let current_output, output, current_path, issue, search_result, bug, current_files, latest_path, all_files, cnt=0;
	let history_summary="";
	/*}#1IUIO756A0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			command=input.command;
			repo=input.repo;
		}else{
			command=undefined;
			repo=undefined;
		}
		/*#{1IUIO756A0ParseArgs*/
		/*}#1IUIO756A0ParseArgs*/
	}
	
	/*#{1IUIO756A0PreContext*/
	function extract(session, sep = '\n<<<###>>>\n') {
		const lines = session.split(/\r?\n/);
		const outputs = [];
		let i = 0;
	
		if (i < lines.length && !/__AGENT_SHELL__>/.test(lines[i])) {
			i++;
			const chunk = [];
			while (i < lines.length && !/__AGENT_SHELL__>/.test(lines[i])) {
			chunk.push(lines[i]);
			i++;
			}
			outputs.push(chunk.join('\n').trim());
		}
		while (i < lines.length) {
			const m = lines[i].match(/__AGENT_SHELL__>\s*(\S.*)$/);
			if (m) {
			i++;
			const chunk = [];
			while (i < lines.length && !/__AGENT_SHELL__>/.test(lines[i])) {
				chunk.push(lines[i]);
				i++;
			}
			outputs.push(chunk.join('\n').trim());
			} else {
			i++;
			}
		}
		return outputs
			.map(o => (o === '' ? ' ' : o))
			.join(sep);
	}
	/*}#1IUIO756A0PreContext*/
	context={};
	/*#{1IUIO756A0PostContext*/
	/*}#1IUIO756A0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IUIO65O30
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(command===undefined || command==="") missing=true;
		if(repo===undefined || repo==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:Run,result:(result),preSeg:"1IUIO65O30",outlet:"1IUIO756A1"};
	};
	FixArgs.jaxId="1IUIO65O30"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Run"]=Run=async function(input){//:1IUIOB71S0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=command;
		args['options']="";
		/*#{1IUIOB71S0PreCodes*/
		/*}#1IUIOB71S0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IUIOB71S0PostCodes*/
		current_output=result;
		output=result;
		issue=result;
		/*}#1IUIOB71S0PostCodes*/
		return {seg:Check,result:(result),preSeg:"1IUIOB71S0",outlet:"1IUIOC3B40"};
	};
	Run.jaxId="1IUIOB71S0"
	Run.url="Run@"+agentURL
	
	segs["UpdateSolution"]=UpdateSolution=async function(input){//:1J3IG34AB0
		let result=input
		try{
			/*#{1J3IG34AB0Code*/
			try{
				await sendRequest(bug,input.summary);
			} catch(error){
				console.log("Update Error");
			}
			
			/*}#1J3IG34AB0Code*/
		}catch(error){
			/*#{1J3IG34AB0ErrorCode*/
			/*}#1J3IG34AB0ErrorCode*/
		}
		return {result:result};
	};
	UpdateSolution.jaxId="1J3IG34AB0"
	UpdateSolution.url="UpdateSolution@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1JNEG598A0
		let result=input;
		/*#{1JNEG598A0Start*/
		const lines = result.trim().split('\n');
		const lastTwoLines = lines.slice(-2).join('\n');
		/*}#1JNEG598A0Start*/
		if(!lastTwoLines.includes('Successful')){
			return {seg:ClaudeFix,result:(input),preSeg:"1JNEG598A0",outlet:"1JNEG60TB0"};
		}
		/*#{1JNEG598A0Post*/
		/*}#1JNEG598A0Post*/
		return {seg:Success,result:(result),preSeg:"1JNEG598A0",outlet:"1JNEG60TB1"};
	};
	Check.jaxId="1JNEG598A0"
	Check.url="Check@"+agentURL
	
	segs["Fail"]=Fail=async function(input){//:1JNEG6TA30
		let result=input
		try{
			/*#{1JNEG6TA30Code*/
			result={result:"Failed"};
			/*}#1JNEG6TA30Code*/
		}catch(error){
			/*#{1JNEG6TA30ErrorCode*/
			/*}#1JNEG6TA30ErrorCode*/
		}
		return {result:result};
	};
	Fail.jaxId="1JNEG6TA30"
	Fail.url="Fail@"+agentURL
	
	segs["ClaudeFix"]=ClaudeFix=async function(input){//:1JNEG8N1P0
		let result=input
		try{
			/*#{1JNEG8N1P0Code*/
			const cc = globalContext.claudeSession;
			const fixPrompt = buildFixPrompt({
				failedCommand: command,
				errorOutput: input,
				platform: process.platform,
				model: "",
				completedSteps: [],
			});
			
			const fixResult = await cc.send(fixPrompt);
			const output = fixResult.output || "";
			result=output;
			/*}#1JNEG8N1P0Code*/
		}catch(error){
			/*#{1JNEG8N1P0ErrorCode*/
			/*}#1JNEG8N1P0ErrorCode*/
		}
		return {seg:Check2,result:(result),preSeg:"1JNEG8N1P0",outlet:"1JNEG8RBJ0"};
	};
	ClaudeFix.jaxId="1JNEG8N1P0"
	ClaudeFix.url="ClaudeFix@"+agentURL
	
	segs["Check2"]=Check2=async function(input){//:1JNEGSF1V0
		let result=input;
		if(input.includes("UNFIXABLE")){
			return {seg:Fail,result:(input),preSeg:"1JNEGSF1V0",outlet:"1JNEGSQM70"};
		}
		return {seg:Success,result:(result),preSeg:"1JNEGSF1V0",outlet:"1JNEGSQM71"};
	};
	Check2.jaxId="1JNEGSF1V0"
	Check2.url="Check2@"+agentURL
	
	segs["Success"]=Success=async function(input){//:1JNEGT3I60
		let result=input
		try{
			/*#{1JNEGT3I60Code*/
			result={result:"Finish"};
			/*}#1JNEGT3I60Code*/
		}catch(error){
			/*#{1JNEGT3I60ErrorCode*/
			/*}#1JNEGT3I60ErrorCode*/
		}
		return {result:result};
	};
	Success.jaxId="1JNEGT3I60"
	Success.url="Success@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ToolRunCommand",
		url:agentURL,
		autoStart:true,
		jaxId:"1IUIO756A0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{command,repo}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IUIO756A0PreEntry*/
			/*}#1IUIO756A0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IUIO756A0PostEntry*/
			/*}#1IUIO756A0PostEntry*/
			return result;
		},
		/*#{1IUIO756A0MoreAgentAttrs*/
		/*}#1IUIO756A0MoreAgentAttrs*/
	};
	/*#{1IUIO756A0PostAgent*/
	/*}#1IUIO756A0PostAgent*/
	return agent;
};
/*#{1IUIO756A0ExCodes*/
/*}#1IUIO756A0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "ToolRunCommand",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				command:{type:"auto",description:"A bash command"},
				repo:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true
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
		name:"ToolRunCommand",showName:"ToolRunCommand",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"command":{name:"command",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"repo":{name:"repo",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","command","repo","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolRunCommand"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['command']=");this.genAttrStatement(seg.getAttr("command"));coder.packText(";");coder.newLine();
			coder.packText("args['repo']=");this.genAttrStatement(seg.getAttr("repo"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AutoDeploy_dev/ai/ToolRunCommand.js",args,false);`);coder.newLine();
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
/*#{1IUIO756A0PostDoc*/
/*}#1IUIO756A0PostDoc*/


export default ToolRunCommand;
export{ToolRunCommand,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IUIO756A0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IUIO756B0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1IUIO5V5O0",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IUIO756B1",
//			"attrs": {
//				"command": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IUIO756B2",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "A bash command",
//						"required": "true"
//					}
//				},
//				"repo": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J08OD2VG0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IUIO756B3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IUIO756B4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IUIO756B5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IUIO65O30",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "200",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1IUIO756A1",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIOB71S0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IUIOB71S0",
//					"attrs": {
//						"id": "Run",
//						"viewName": "",
//						"label": "",
//						"x": "465",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IUIOC3B60",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IUIOC3B61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#command",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IUIOC3B40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JNEG598A0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J3IG34AB0",
//					"attrs": {
//						"id": "UpdateSolution",
//						"viewName": "",
//						"label": "",
//						"x": "3595",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3IG4GEQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3IG4GEQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J3IG3KCB0",
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
//					"def": "brunch",
//					"jaxId": "1JNEG598A0",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "705",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JNEG6PUQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JNEG6PUQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JNEG60TB1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JNEGT3I60"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JNEG60TB0",
//									"attrs": {
//										"id": "Fail",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JNEG6PUQ2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JNEG6PUQ3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!lastTwoLines.includes('Successful')"
//									},
//									"linkedSeg": "1JNEG8N1P0"
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
//					"jaxId": "1JNEG6TA30",
//					"attrs": {
//						"id": "Fail",
//						"viewName": "",
//						"label": "",
//						"x": "1410",
//						"y": "-30",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JNEG6V2A0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JNEG6V2A1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JNEG6V240",
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
//					"def": "code",
//					"jaxId": "1JNEG8N1P0",
//					"attrs": {
//						"id": "ClaudeFix",
//						"viewName": "",
//						"label": "",
//						"x": "905",
//						"y": "-15",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JNEGABON0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JNEGABON1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JNEG8RBJ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JNEGSF1V0"
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
//					"jaxId": "1JNEGSF1V0",
//					"attrs": {
//						"id": "Check2",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "-15",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JNEGSQMA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JNEGSQMA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JNEGSQM71",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JNEGT3I60"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JNEGSQM70",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JNEGSQMA2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JNEGSQMA3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.includes(\"UNFIXABLE\")"
//									},
//									"linkedSeg": "1JNEG6TA30"
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
//					"jaxId": "1JNEGT3I60",
//					"attrs": {
//						"id": "Success",
//						"viewName": "",
//						"label": "",
//						"x": "1410",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JNEGTFVT0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JNEGTFVT1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JNEGTFVJ0",
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
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}