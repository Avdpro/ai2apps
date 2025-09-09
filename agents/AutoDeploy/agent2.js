//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1HDBOSUN90MoreImports*/
import fsp from 'fs/promises';
/*}#1HDBOSUN90MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.pathToFileURL(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"url":{
			"name":"url","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"用户需要部署的github项目的链接，如https://github.com/Avdpro/ai2apps",
		}
	},
	/*#{1HDBOSUN90ArgsView*/
	/*}#1HDBOSUN90ArgsView*/
};

/*#{1HDBOSUN90StartDoc*/
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let agent2=async function(session){
	let url;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let InitBash,Get,Clone,GetPath,FindReadme,CheckReadme,NoReadme,WriteSetupGuide,SetupProject,FixArgs,Guide;
	/*#{1HDBOSUN90LocalVals*/
	let repo, folder, current_path;
	
	/*}#1HDBOSUN90LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			url=input.url;
		}else{
			url=undefined;
		}
		/*#{1HDBOSUN90ParseArgs*/
		/*}#1HDBOSUN90ParseArgs*/
	}
	
	/*#{1HDBOSUN90PreContext*/
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
	/*}#1HDBOSUN90PreContext*/
	context={};
	/*#{1HDBOSUN90PostContext*/
	/*}#1HDBOSUN90PostContext*/
	let $agent,agent,segs={};
	segs["InitBash"]=InitBash=async function(input){//:1IVIQJIRE0
		let result,args={};
		args['bashId']="";
		args['action']="Create";
		args['commands']="";
		args['options']={client:true};
		/*#{1IVIQJIRE0PreCodes*/
		/*}#1IVIQJIRE0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IVIQJIRE0PostCodes*/
		globalContext.bash=result;
		/*}#1IVIQJIRE0PostCodes*/
		return {seg:Get,result:(result),preSeg:"1IVIQJIRE0",outlet:"1IVIQK39F0"};
	};
	InitBash.jaxId="1IVIQJIRE0"
	InitBash.url="InitBash@"+agentURL
	
	segs["Get"]=Get=async function(input){//:1IVIQNTGJ0
		let prompt;
		let result=null;
		/*#{1IVIQNTGJ0Input*/
		/*}#1IVIQNTGJ0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1-mini",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=Get.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"用户有一个github项目的链接，请给出使用git clone需要的url, repo和git clone之后在当前目录生成的文件夹名称，以json格式给出，如 {url:\"https://github.com/Avdpro/ai2apps.git\",repo:\"Avdpro/ai2apps\",dir:\"ai2apps\"}"},
		];
		/*#{1IVIQNTGJ0PrePrompt*/
		/*}#1IVIQNTGJ0PrePrompt*/
		prompt=url;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IVIQNTGJ0FilterMessage*/
			/*}#1IVIQNTGJ0FilterMessage*/
			messages.push(msg);
		}
		/*#{1IVIQNTGJ0PreCall*/
		/*}#1IVIQNTGJ0PreCall*/
		result=(result===null)?(await session.callSegLLM("Get@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1IVIQNTGJ0PostCall*/
		folder=result.dir;
		repo=result.repo;
		/*}#1IVIQNTGJ0PostCall*/
		return {seg:Clone,result:(result),preSeg:"1IVIQNTGJ0",outlet:"1IVIQUBK60"};
	};
	Get.jaxId="1IVIQNTGJ0"
	Get.url="Get@"+agentURL
	
	segs["Clone"]=Clone=async function(input){//:1IVIR0M3A0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=[`cd "${decodeURIComponent(basePath)}"`,`mkdir -p projects`,`cd projects`,`git clone ${input.url}`, `cd ${input.dir}`];
		args['options']="";
		/*#{1IVIR0M3A0PreCodes*/
		/*}#1IVIR0M3A0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IVIR0M3A0PostCodes*/
		/*}#1IVIR0M3A0PostCodes*/
		return {seg:GetPath,result:(result),preSeg:"1IVIR0M3A0",outlet:"1IVIR283T0"};
	};
	Clone.jaxId="1IVIR0M3A0"
	Clone.url="Clone@"+agentURL
	
	segs["GetPath"]=GetPath=async function(input){//:1IVIR603S0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=["pwd"];
		args['options']="";
		/*#{1IVIR603S0PreCodes*/
		/*}#1IVIR603S0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IVIR603S0PostCodes*/
		current_path=extract(result);
		/*}#1IVIR603S0PostCodes*/
		return {seg:Guide,result:(result),preSeg:"1IVIR603S0",outlet:"1IVIRB74M1"};
	};
	GetPath.jaxId="1IVIR603S0"
	GetPath.url="GetPath@"+agentURL
	
	segs["FindReadme"]=FindReadme=async function(input){//:1IVIRJAV80
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1-mini",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=FindReadme.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"用户输入了pwd和ls命令的得到了输出，请根据输出的结果给出readme的完整路径，以json格式给出，如{exists:true,path:\"/Users/xxx/ai2apps/readme.md\"}，如果不存在readme，请输出 {exists:false}"},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("FindReadme@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {result:result};
	};
	FindReadme.jaxId="1IVIRJAV80"
	FindReadme.url="FindReadme@"+agentURL
	
	segs["CheckReadme"]=CheckReadme=async function(input){//:1IVIRNBT70
		let result=input;
		if(input.exists){
			return {result:input};
		}
		return {result:result};
	};
	CheckReadme.jaxId="1IVIRNBT70"
	CheckReadme.url="CheckReadme@"+agentURL
	
	segs["NoReadme"]=NoReadme=async function(input){//:1IVIRNSHQ0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="Readme not found";
		session.addChatText(role,content,opts);
		return {result:result};
	};
	NoReadme.jaxId="1IVIRNSHQ0"
	NoReadme.url="NoReadme@"+agentURL
	
	segs["WriteSetupGuide"]=WriteSetupGuide=async function(input){//:1IVIRP9RP0
		let result=input
		/*#{1IVIRP9RP0Code*/
		let content = input;
		const filePath = pathLib.join(decodeURIComponent(basePath), 'setup_guide.md');
		await fsp.writeFile(filePath, content);
		/*}#1IVIRP9RP0Code*/
		return {seg:SetupProject,result:(result),preSeg:"1IVIRP9RP0",outlet:"1IVIRQEDP0"};
	};
	WriteSetupGuide.jaxId="1IVIRP9RP0"
	WriteSetupGuide.url="WriteSetupGuide@"+agentURL
	
	segs["SetupProject"]=SetupProject=async function(input){//:1IVIS07O60
		let result;
		let arg={"prjPath":basePath,"folder":folder,"repo":repo};
		let agentNode=("")||null;
		let sourcePath=pathLib.join(basePath,"../AutoDeploy/PrjSetupBySteps.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	SetupProject.jaxId="1IVIS07O60"
	SetupProject.url="SetupProject@"+agentURL
	
	segs["FixArgs"]=FixArgs=async function(input){//:1J0997VD40
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(url===undefined || url==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:InitBash,result:(result),preSeg:"1J0997VD40",outlet:"1J0997VD41"};
	};
	FixArgs.jaxId="1J0997VD40"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Guide"]=Guide=async function(input){//:1J0QVE4SV0
		let result;
		let arg={"repo_dir":current_path};
		let agentNode=("EnrichReadme")||null;
		let sourcePath="agent.py";
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:WriteSetupGuide,result:(result),preSeg:"1J0QVE4SV0",outlet:"1J0QVEFCK0"};
	};
	Guide.jaxId="1J0QVE4SV0"
	Guide.url="Guide@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"agent2",
		url:agentURL,
		autoStart:true,
		jaxId:"1HDBOSUN90",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{url}*/){
			let result;
			parseAgentArgs(input);
			/*#{1HDBOSUN90PreEntry*/
			/*}#1HDBOSUN90PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1HDBOSUN90PostEntry*/
			/*}#1HDBOSUN90PostEntry*/
			return result;
		},
		/*#{1HDBOSUN90MoreAgentAttrs*/
		/*}#1HDBOSUN90MoreAgentAttrs*/
	};
	/*#{1HDBOSUN90PostAgent*/
	/*}#1HDBOSUN90PostAgent*/
	return agent;
};
/*#{1HDBOSUN90ExCodes*/
/*}#1HDBOSUN90ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "agent2",
		description: "这是一个帮助用户自动部署github项目的agent，需要给出github的链接如https://github.com/Avdpro/ai2apps或repo的名称如Avdpro/ai2apps。",
		parameters:{
			type: "object",
			properties:{
				url:{type:"string",description:"用户需要部署的github项目的链接，如https://github.com/Avdpro/ai2apps"}
			}
		}
	},
	agentNode: "AutoDeploy",
	agentName: "agent2.js"
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
		name:"agent2",showName:"agent2",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"url":{name:"url",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","url","codes","desc"],
		desc:"这是一个帮助用户自动部署github项目的agent，需要给出github的链接如https://github.com/Avdpro/ai2apps或repo的名称如Avdpro/ai2apps。"
	});
	
	DocAIAgentExporter.segTypeExporters["agent2"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['url']=");this.genAttrStatement(seg.getAttr("url"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AutoDeploy/ai/agent2.js",args,false);`);coder.newLine();
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
/*#{1HDBOSUN90PostDoc*/
/*}#1HDBOSUN90PostDoc*/


export default agent2;
export{agent2,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1HDBOSUN90",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1HDBOSUNA0",
//			"attrs": {
//				"agent": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1HDBOSUNA4",
//					"attrs": {
//						"constructArgs": {
//							"jaxId": "1HDBOSUNB0",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1HDBOSUNB1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1HDBOSUNB2",
//							"attrs": {}
//						},
//						"mockupOnly": "false",
//						"nullMockup": "false",
//						"exportType": "UI Data Template",
//						"exportClass": "false"
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1HDBOSUNA1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "FixArgs",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IVIQH5MC0",
//			"attrs": {
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J0997VD60",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "用户需要部署的github项目的链接，如https://github.com/Avdpro/ai2apps",
//						"required": "true"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1HDBOSUNA2",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1HDBOSUNA3",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1HDIJB7SK6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IVIQJIRE0",
//					"attrs": {
//						"id": "InitBash",
//						"viewName": "",
//						"label": "",
//						"x": "345",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIQK39H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIQK39H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "\"\"",
//						"action": "Create",
//						"commands": "\"\"",
//						"options": "#{client:true}",
//						"outlet": {
//							"jaxId": "1IVIQK39F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVIQNTGJ0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IVIQNTGJ0",
//					"attrs": {
//						"id": "Get",
//						"viewName": "",
//						"label": "",
//						"x": "565",
//						"y": "135",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIQUBKH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIQUBKH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1-mini",
//						"system": "用户有一个github项目的链接，请给出使用git clone需要的url, repo和git clone之后在当前目录生成的文件夹名称，以json格式给出，如 {url:\"https://github.com/Avdpro/ai2apps.git\",repo:\"Avdpro/ai2apps\",dir:\"ai2apps\"}",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#url",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IVIQUBK60",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVIR0M3A0"
//						},
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "No",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "json_object",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IVIR0M3A0",
//					"attrs": {
//						"id": "Clone",
//						"viewName": "",
//						"label": "",
//						"x": "775",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIR28410",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIR28411",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#[`cd \"${decodeURIComponent(basePath)}\"`,`mkdir -p projects`,`cd projects`,`git clone ${input.url}`, `cd ${input.dir}`]",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IVIR283T0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVIR603S0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IVIR603S0",
//					"attrs": {
//						"id": "GetPath",
//						"viewName": "",
//						"label": "",
//						"x": "1000",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIRB7554",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIRB7555",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "[\"pwd\"]",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IVIRB74M1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0QVE4SV0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IVIRJAV80",
//					"attrs": {
//						"id": "FindReadme",
//						"viewName": "",
//						"label": "",
//						"x": "1165",
//						"y": "290",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIRMVE20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIRMVE21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "OpenAI",
//						"mode": "gpt-4.1-mini",
//						"system": "用户输入了pwd和ls命令的得到了输出，请根据输出的结果给出readme的完整路径，以json格式给出，如{exists:true,path:\"/Users/xxx/ai2apps/readme.md\"}，如果不存在readme，请输出 {exists:false}",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#input",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IVIRMVDS0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "No",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "json_object",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IVIRNBT70",
//					"attrs": {
//						"id": "CheckReadme",
//						"viewName": "",
//						"label": "",
//						"x": "1420",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIROKCJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIROKCJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IVIROKCD1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IVIROKCD0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IVIROKCJ2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IVIROKCJ3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.exists"
//									}
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
//					"jaxId": "1IVIRNSHQ0",
//					"attrs": {
//						"id": "NoReadme",
//						"viewName": "",
//						"label": "",
//						"x": "1680",
//						"y": "150",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIROKCJ4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIROKCJ5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "Readme not found",
//						"outlet": {
//							"jaxId": "1IVIROKCD2",
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
//					"jaxId": "1IVIRP9RP0",
//					"attrs": {
//						"id": "WriteSetupGuide",
//						"viewName": "",
//						"label": "",
//						"x": "1665",
//						"y": "35",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIS010L0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIS010L1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IVIRQEDP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVIS07O60"
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
//					"def": "aiBot",
//					"jaxId": "1IVIS07O60",
//					"attrs": {
//						"id": "SetupProject",
//						"viewName": "",
//						"label": "",
//						"x": "1960",
//						"y": "35",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIS0ONV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIS0ONV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AutoDeploy/PrjSetupBySteps.js",
//						"argument": "{\"prjPath\":\"#basePath\",\"folder\":\"#folder\",\"repo\":\"#repo\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IVIS0ONQ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"agentNode": ""
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1J0997VD40",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "120",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1J0997VD41",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVIQJIRE0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1J0QVE4SV0",
//					"attrs": {
//						"id": "Guide",
//						"viewName": "",
//						"label": "",
//						"x": "1210",
//						"y": "135",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J0QVF60R0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J0QVF60R1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "agent.py",
//						"argument": "{\"repo_dir\":\"#current_path\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1J0QVEFCK0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVIRP9RP0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"agentNode": "EnrichReadme"
//					},
//					"icon": "agent.svg"
//				}
//			]
//		},
//		"desc": "这是一个帮助用户自动部署github项目的agent，需要给出github的链接如https://github.com/Avdpro/ai2apps或repo的名称如Avdpro/ai2apps。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"AutoDeploy\",\"chatEntry\":false,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\"}"
//	}
//}