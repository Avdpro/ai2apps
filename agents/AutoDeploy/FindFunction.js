//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1J1V02CK70MoreImports*/
import fsp from 'fs/promises';
/*}#1J1V02CK70MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"dir":{
			"name":"dir","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"conda":{
			"name":"conda","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1J1V02CK70ArgsView*/
	/*}#1J1V02CK70ArgsView*/
};

/*#{1J1V02CK70StartDoc*/
/*}#1J1V02CK70StartDoc*/
//----------------------------------------------------------------------------
let FindFunction=async function(session){
	let dir,conda;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FindReferences,InitBash,GetPath,ListFiles,ReadFiles,ExtractUsage,Summary,output;
	/*#{1J1V02CK70LocalVals*/
	let all_files,input_type,output_type, output_suffix;
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
	/*}#1J1V02CK70LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			dir=input.dir;
			conda=input.conda;
		}else{
			dir=undefined;
			conda=undefined;
		}
		/*#{1J1V02CK70ParseArgs*/
		/*}#1J1V02CK70ParseArgs*/
	}
	
	/*#{1J1V02CK70PreContext*/
	/*}#1J1V02CK70PreContext*/
	context={};
	/*#{1J1V02CK70PostContext*/
	/*}#1J1V02CK70PostContext*/
	let $agent,agent,segs={};
	segs["FindReferences"]=FindReferences=async function(input){//:1J1V0UE3H0
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1-mini",
			maxToken:32768,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=FindReferences.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`用户输入了find "$(pwd)" -type f命令的得到了输出，请根据输出的结果给出所有可能帮助安装和部署项目的文件完整绝对路径，以json格式给出。

## 需要查找的文件类型包括：

**安装相关文件:**
- README.md, readme.md, README.txt, README.rst, README
- INSTALL.md, install.md, INSTALL.txt, INSTALL.rst, INSTALL
- SETUP.md, setup.md, SETUP.txt, SETUP.rst, SETUP
- GETTING_STARTED.md, getting_started.md, GettingStarted.md
- QUICKSTART.md, quickstart.md, QuickStart.md

**文档相关文件:**
- DOCS.md, docs.md, DOCUMENTATION.md, documentation.md
- API.md, api.md, USAGE.md, usage.md
- EXAMPLES.md, examples.md, TUTORIAL.md, tutorial.md

## 输出格式：

如果找到相关文件：
{
  "exists": true,
  "files": [
    {
      "type": "readme",
      "path": "/Users/xxx/project/README.md"
    },
    {
      "type": "install",
      "path": "/Users/xxx/project/INSTALL.md"
    },
      "type": "docs",
      "path": "/Users/xxx/project/DOCS.md"
    },
    {
      "type": "usage",
      "path": "/Users/xxx/project/Usage.md"
    }
  ],
  "total_count": 4
}

如果没有找到任何相关文件：
{
  "exists": false,
  "installation_files": [],
  "total_count": 0
}

## 文件类型分类：
- \`readme\`: README相关文件
- \`install\`: 安装说明文件
- \`docs\`: 文档相关文件
- \`usage\`: 使用相关文件

请根据find命令的输出结果，识别并返回所有可能帮助项目使用的文件路径。`},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("FindReferences@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:ReadFiles,result:(result),preSeg:"1J1V0UE3H0",outlet:"1J1V1413E0"};
	};
	FindReferences.jaxId="1J1V0UE3H0"
	FindReferences.url="FindReferences@"+agentURL
	
	segs["InitBash"]=InitBash=async function(input){//:1J1V15IB00
		let result,args={};
		args['bashId']="";
		args['action']="Create";
		args['commands']="";
		args['options']={client:true};
		/*#{1J1V15IB00PreCodes*/
		/*}#1J1V15IB00PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1J1V15IB00PostCodes*/
		globalContext.bash=result;
		/*}#1J1V15IB00PostCodes*/
		return {seg:GetPath,result:(result),preSeg:"1J1V15IB00",outlet:"1J1V16HKF0"};
	};
	InitBash.jaxId="1J1V15IB00"
	InitBash.url="InitBash@"+agentURL
	
	segs["GetPath"]=GetPath=async function(input){//:1J1V17EDS0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=`cd "${dir}"`;
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:ListFiles,result:(result),preSeg:"1J1V17EDS0",outlet:"1J1V185HV0"};
	};
	GetPath.jaxId="1J1V17EDS0"
	GetPath.url="GetPath@"+agentURL
	
	segs["ListFiles"]=ListFiles=async function(input){//:1J1V18T7O0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']='find "$(pwd)" -type f -not -path "*/.git/*" -not -path "*/__pycache__/*" -not -path "*/.pytest_cache/*" -not -path "*/.tox/*" -not -path "*/venv/*" -not -path "*/.venv/*" -not -path "*/env/*" -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" -not -path "*/*.egg-info/*" -not -path "*/.mypy_cache/*" -not -path "*/.coverage/*"';
		args['options']="";
		/*#{1J1V18T7O0PreCodes*/
		/*}#1J1V18T7O0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1J1V18T7O0PostCodes*/
		all_files=extract(result);
		/*}#1J1V18T7O0PostCodes*/
		return {seg:FindReferences,result:(result),preSeg:"1J1V18T7O0",outlet:"1J1V19LQ20"};
	};
	ListFiles.jaxId="1J1V18T7O0"
	ListFiles.url="ListFiles@"+agentURL
	
	segs["ReadFiles"]=ReadFiles=async function(input){//:1J1V21LS30
		let result=input
		/*#{1J1V21LS30Code*/
		let combinedContent = `# Comprehensive Guide
				
				This guide combines information from multiple project documentation files.
				
				---
				
				`;
				
				// Group files by type for better organization
				const filesByType = {
					readme: [],
					install: [],
					usage: [],
					docs: []
				};
				
				// Categorize files
				for (const file of input.files) {
					if (filesByType[file.type]) {
						filesByType[file.type].push(file);
					}
				}
				
				// Define the order of sections
				const sectionOrder = [
					{ type: 'readme', title: '📖 Project Overview' },
					{ type: 'install', title: '🚀 Installation Instructions' },
					{ type: 'usage', title: '🚀 Usage Guide' },
					{ type: 'docs', title: '📚 Additional Documentation' }
				];
				
				// Process each section
				for (const section of sectionOrder) {
					const filesInSection = filesByType[section.type];
					if (filesInSection && filesInSection.length > 0) {
						combinedContent += `## ${section.title}\n\n`;
						
						for (const file of filesInSection) {
							try {
								// Read file content
								const content = await fsp.readFile(file.path, "utf-8");
								const fileName = pathLib.basename(file.path);
								
								combinedContent += `### From ${fileName}\n\n`;
								combinedContent += `*Source: \`${file.path}\`*\n\n`;
								
								// Clean up the content (remove title if it duplicates our section)
								let cleanContent = content;
								
								// Remove common markdown titles that might conflict
								cleanContent = cleanContent.replace(/^#\s+.*$/gm, (match) => {
									// Convert top-level headers to lower level
									return match.replace(/^#\s+/, '#### ');
								});
								
								combinedContent += cleanContent;
								combinedContent += '\n\n---\n\n';
								
							} catch (error) {
								console.warn(`Failed to read file ${file.path}:`, error.message);
								combinedContent += `### ${pathLib.basename(file.path)} (Failed to read)\n\n`;
								combinedContent += `*Error reading file: \`${file.path}\`*\n\n`;
								combinedContent += '---\n\n';
							}
						}
					}
				}
				result=combinedContent;
				/*}#1J1V21LS30Code*/
		return {seg:ExtractUsage,result:(result),preSeg:"1J1V21LS30",outlet:"1J1V22CKI0"};
	};
	ReadFiles.jaxId="1J1V21LS30"
	ReadFiles.url="ReadFiles@"+agentURL
	
	segs["ExtractUsage"]=ExtractUsage=async function(input){//:1J1V27C0J0
		let prompt;
		let result=null;
		/*#{1J1V27C0J0Input*/
		/*}#1J1V27C0J0Input*/
		
		let opts={
			platform:"Claude",
			mode:"claude-3-7-sonnet-latest",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=ExtractUsage.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"请你作为用户助手，根据已部署的项目文档中 **Quick Start**、**Usage**、**Examples**、**Command Line Tools** 等使用说明部分，面向普通用户提取并整理以下信息：\n\n1. 基本使用示例\n2. 命令行使用方式\n3. 主要功能列表\n\n重点关注项目提供的1个核心功能（如 OCR、TTS 等），并对该功能尝试识别：\n**功能名称**\n**功能描述**\n**使用方法**（命令行示例）\n\n注意你所选择的功能在命令行使用中必须存在输入参数，且参数必须为text或filePath，其余参数均应该有默认且可以直接使用的参数，不需要用户自己填写或修改，即在命令行示例中只能有输入文本/输入文件路径/输出文件路径，其余参数均应选择最合适的值，并和功能描述相对应。\n如果输出的filePath是一个文件夹/目录的路径，请在output_description中指明需要压缩为zip文件，输出的格式是zip的路径，内容是A zip file containing ...。\n请严格按照以下 JSON 格式输出：\n\n{\n  \"features\": [\n    {\n      \"name\": \"功能名称（简洁明了）\",\n      \"description\": \"功能详细描述（说明具体作用和适用场景）\",\n      \"input_type\": \"text/filePath\",\n      \"input_description\": \"输入参数的具体描述\",\n      \"output_type\": \"text/filePath\",\n      \"output_is_directory_path\": true/false,\n      \"need_zip\": true/false,\n      \"output_suffix\":\"输出结果的文件后缀名，如zip, png, md, txt 等等\"\n      \"output_description\": \"输出结果的详细描述（文件格式、内容说明）\",\n      \"command\": \"完整的命令行执行示例（可以直接复制粘贴运行）\",\n    }\n  ]\n}\n\n"},
		];
		/*#{1J1V27C0J0PrePrompt*/
		/*}#1J1V27C0J0PrePrompt*/
		prompt=`项目内包含的文件有：
${all_files}
参考资料：
${input}`;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1J1V27C0J0FilterMessage*/
			/*}#1J1V27C0J0FilterMessage*/
			messages.push(msg);
		}
		/*#{1J1V27C0J0PreCall*/
		/*}#1J1V27C0J0PreCall*/
		result=(result===null)?(await session.callSegLLM("ExtractUsage@"+agentURL,opts,messages,true)):result;
		/*#{1J1V27C0J0PostCall*/
		let tmp = trimJSON(result);
		tmp = tmp.features[0];
		input_type = tmp.input_type;
		output_type = tmp.output_type;
		output_suffix = tmp.output_suffix;
		/*}#1J1V27C0J0PostCall*/
		return {seg:Summary,result:(result),preSeg:"1J1V27C0J0",outlet:"1J1V28QVC0"};
	};
	ExtractUsage.jaxId="1J1V27C0J0"
	ExtractUsage.url="ExtractUsage@"+agentURL
	
	segs["Summary"]=Summary=async function(input){//:1J30DLNHV0
		let prompt;
		let result;
		
		let opts={
			platform:"Claude",
			mode:"claude-3-7-sonnet-latest",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=Summary.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`请把输入总结成使用指南，严格按照输入给出的input_type和output_type，输出markdown格式的文本。在指南中加上这句话：已经在本机的 conda 环境 ${conda} 安装相关依赖，运行相关 cli 需要先激活虚拟环境。`},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("Summary@"+agentURL,opts,messages,true);
		return {seg:output,result:(result),preSeg:"1J30DLNHV0",outlet:"1J30DLTFQ0"};
	};
	Summary.jaxId="1J30DLNHV0"
	Summary.url="Summary@"+agentURL
	
	segs["output"]=output=async function(input){//:1J4293O9E0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=input;
		/*#{1J4293O9E0PreCodes*/
		/*}#1J4293O9E0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1J4293O9E0PostCodes*/
		result = {guide:input,input_type:input_type,output_type:output_type,output_suffix:output_suffix};
		/*}#1J4293O9E0PostCodes*/
		return {result:result};
	};
	output.jaxId="1J4293O9E0"
	output.url="output@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"FindFunction",
		url:agentURL,
		autoStart:true,
		jaxId:"1J1V02CK70",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{dir,conda}*/){
			let result;
			parseAgentArgs(input);
			/*#{1J1V02CK70PreEntry*/
			/*}#1J1V02CK70PreEntry*/
			result={seg:InitBash,"input":input};
			/*#{1J1V02CK70PostEntry*/
			/*}#1J1V02CK70PostEntry*/
			return result;
		},
		/*#{1J1V02CK70MoreAgentAttrs*/
		/*}#1J1V02CK70MoreAgentAttrs*/
	};
	/*#{1J1V02CK70PostAgent*/
	/*}#1J1V02CK70PostAgent*/
	return agent;
};
/*#{1J1V02CK70ExCodes*/
/*}#1J1V02CK70ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1J1V02CK70PostDoc*/
/*}#1J1V02CK70PostDoc*/


export default FindFunction;
export{FindFunction};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1J1V02CK70",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1J1V02CK90",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1J1V02CK91",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "InitBash",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1J1V02CK92",
//			"attrs": {
//				"dir": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J1V02CK93",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"conda": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J3NPLTP00",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1J1V02CK94",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1J1V02CK95",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1J1V02CK96",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1J1V0UE3H0",
//					"attrs": {
//						"id": "FindReferences",
//						"viewName": "",
//						"label": "",
//						"x": "470",
//						"y": "200",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1V1413G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1V1413G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1-mini",
//						"system": "#`用户输入了find \"$(pwd)\" -type f命令的得到了输出，请根据输出的结果给出所有可能帮助安装和部署项目的文件完整绝对路径，以json格式给出。\n\n## 需要查找的文件类型包括：\n\n**安装相关文件:**\n- README.md, readme.md, README.txt, README.rst, README\n- INSTALL.md, install.md, INSTALL.txt, INSTALL.rst, INSTALL\n- SETUP.md, setup.md, SETUP.txt, SETUP.rst, SETUP\n- GETTING_STARTED.md, getting_started.md, GettingStarted.md\n- QUICKSTART.md, quickstart.md, QuickStart.md\n\n**文档相关文件:**\n- DOCS.md, docs.md, DOCUMENTATION.md, documentation.md\n- API.md, api.md, USAGE.md, usage.md\n- EXAMPLES.md, examples.md, TUTORIAL.md, tutorial.md\n\n## 输出格式：\n\n如果找到相关文件：\n{\n  \"exists\": true,\n  \"files\": [\n    {\n      \"type\": \"readme\",\n      \"path\": \"/Users/xxx/project/README.md\"\n    },\n    {\n      \"type\": \"install\",\n      \"path\": \"/Users/xxx/project/INSTALL.md\"\n    },\n      \"type\": \"docs\",\n      \"path\": \"/Users/xxx/project/DOCS.md\"\n    },\n    {\n      \"type\": \"usage\",\n      \"path\": \"/Users/xxx/project/Usage.md\"\n    }\n  ],\n  \"total_count\": 4\n}\n\n如果没有找到任何相关文件：\n{\n  \"exists\": false,\n  \"installation_files\": [],\n  \"total_count\": 0\n}\n\n## 文件类型分类：\n- \\`readme\\`: README相关文件\n- \\`install\\`: 安装说明文件\n- \\`docs\\`: 文档相关文件\n- \\`usage\\`: 使用相关文件\n\n请根据find命令的输出结果，识别并返回所有可能帮助项目使用的文件路径。`",
//						"temperature": "0",
//						"maxToken": "32768",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#input",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1J1V1413E0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1V21LS30"
//						},
//						"stream": "true",
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
//					"jaxId": "1J1V15IB00",
//					"attrs": {
//						"id": "InitBash",
//						"viewName": "",
//						"label": "",
//						"x": "-185",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1V16HKH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1V16HKH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "\"\"",
//						"action": "Create",
//						"commands": "\"\"",
//						"options": "#{client:true}",
//						"outlet": {
//							"jaxId": "1J1V16HKF0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1V17EDS0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1J1V17EDS0",
//					"attrs": {
//						"id": "GetPath",
//						"viewName": "",
//						"label": "",
//						"x": "35",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1V1895U0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1V1895U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#`cd \"${dir}\"`",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J1V185HV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1V18T7O0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1J1V18T7O0",
//					"attrs": {
//						"id": "ListFiles",
//						"viewName": "",
//						"label": "",
//						"x": "240",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1V19LQ70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1V19LQ71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#'find \"$(pwd)\" -type f -not -path \"*/.git/*\" -not -path \"*/__pycache__/*\" -not -path \"*/.pytest_cache/*\" -not -path \"*/.tox/*\" -not -path \"*/venv/*\" -not -path \"*/.venv/*\" -not -path \"*/env/*\" -not -path \"*/node_modules/*\" -not -path \"*/dist/*\" -not -path \"*/build/*\" -not -path \"*/*.egg-info/*\" -not -path \"*/.mypy_cache/*\" -not -path \"*/.coverage/*\"'",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J1V19LQ20",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1V0UE3H0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J1V21LS30",
//					"attrs": {
//						"id": "ReadFiles",
//						"viewName": "",
//						"label": "",
//						"x": "725",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1V2411S0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1V2411S1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J1V22CKI0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1V27C0J0"
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
//					"def": "callLLM",
//					"jaxId": "1J1V27C0J0",
//					"attrs": {
//						"id": "ExtractUsage",
//						"viewName": "",
//						"label": "",
//						"x": "955",
//						"y": "200",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1V28QVH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1V28QVH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "Claude",
//						"mode": "claude-3-7-sonnet-latest",
//						"system": "请你作为用户助手，根据已部署的项目文档中 **Quick Start**、**Usage**、**Examples**、**Command Line Tools** 等使用说明部分，面向普通用户提取并整理以下信息：\n\n1. 基本使用示例\n2. 命令行使用方式\n3. 主要功能列表\n\n重点关注项目提供的1个核心功能（如 OCR、TTS 等），并对该功能尝试识别：\n**功能名称**\n**功能描述**\n**使用方法**（命令行示例）\n\n注意你所选择的功能在命令行使用中必须存在输入参数，且参数必须为text或filePath，其余参数均应该有默认且可以直接使用的参数，不需要用户自己填写或修改，即在命令行示例中只能有输入文本/输入文件路径/输出文件路径，其余参数均应选择最合适的值，并和功能描述相对应。\n如果输出的filePath是一个文件夹/目录的路径，请在output_description中指明需要压缩为zip文件，输出的格式是zip的路径，内容是A zip file containing ...。\n请严格按照以下 JSON 格式输出：\n\n{\n  \"features\": [\n    {\n      \"name\": \"功能名称（简洁明了）\",\n      \"description\": \"功能详细描述（说明具体作用和适用场景）\",\n      \"input_type\": \"text/filePath\",\n      \"input_description\": \"输入参数的具体描述\",\n      \"output_type\": \"text/filePath\",\n      \"output_is_directory_path\": true/false,\n      \"need_zip\": true/false,\n      \"output_suffix\":\"输出结果的文件后缀名，如zip, png, md, txt 等等\"\n      \"output_description\": \"输出结果的详细描述（文件格式、内容说明）\",\n      \"command\": \"完整的命令行执行示例（可以直接复制粘贴运行）\",\n    }\n  ]\n}\n\n",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#`项目内包含的文件有：\n${all_files}\n参考资料：\n${input}`",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1J1V28QVC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J30DLNHV0"
//						},
//						"stream": "true",
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
//						"responseFormat": "text",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1J30DLNHV0",
//					"attrs": {
//						"id": "Summary",
//						"viewName": "",
//						"label": "",
//						"x": "1235",
//						"y": "200",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J30DLTFT0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J30DLTFT1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "Claude",
//						"mode": "claude-3-7-sonnet-latest",
//						"system": "#`请把输入总结成使用指南，严格按照输入给出的input_type和output_type，输出markdown格式的文本。在指南中加上这句话：已经在本机的 conda 环境 ${conda} 安装相关依赖，运行相关 cli 需要先激活虚拟环境。`",
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
//							"jaxId": "1J30DLTFQ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4293O9E0"
//						},
//						"stream": "true",
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
//						"responseFormat": "text",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J4293O9E0",
//					"attrs": {
//						"id": "output",
//						"viewName": "",
//						"label": "",
//						"x": "1455",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4293RG30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4293RG31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1J4293RG10",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}