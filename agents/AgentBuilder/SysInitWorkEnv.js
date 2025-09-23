//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IG32J23V0MoreImports*/
import {execSync,exec} from "child_process";
import os from "os";
import gpuInfo from "gpu-info";
import diskUsage from "diskusage";
/*}#1IG32J23V0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
/*#{1IG32J23V0StartDoc*/
function getCondaEnvName() {
	return new Promise((resolve, reject) => {
		exec('conda info --envs', (error, stdout, stderr) => {
			if (error || stderr) {
				reject(`Error: ${error || stderr}`);
				return;
			}

			const lines = stdout.split('\n');
			const activeEnv = lines.find(line => line.includes('*'));
			if (activeEnv) {
				const envName = activeEnv.split(' ')[0].trim();
				resolve(envName);
			} else {
				reject('No active Conda environment found');
			}
		});
	});
}
/*}#1IG32J23V0StartDoc*/
//----------------------------------------------------------------------------
let SysInitWorkEnv=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let InitEnv,ReadConifg,InitBash,ShowEnv;
	let env=null;
	
	/*#{1IG32J23V0LocalVals*/
	async function addLog(log,notify){
		let logs=globalContext.agentBuilderLogs;
		if(!logs){
			logs=globalContext.agentBuilderLogs=[];
		}
		logs.push(log);
		if(notify){
			session.addChatText("log",JSON.stringify(log));
		}
	}
	/*}#1IG32J23V0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IG32J23V0ParseArgs*/
		/*}#1IG32J23V0ParseArgs*/
	}
	
	/*#{1IG32J23V0PreContext*/
	/*}#1IG32J23V0PreContext*/
	context={};
	/*#{1IG32J23V0PostContext*/
	/*}#1IG32J23V0PostContext*/
	let $agent,agent,segs={};
	segs["InitEnv"]=InitEnv=async function(input){//:1IG32J8B00
		let result=input
		/*#{1IG32J8B00Code*/
		env=globalContext.env;
		if(!env){
			env=globalContext.env={};
		}
		//系统基本信息:
		env.platform=process.platform;
		env.arch=process.arch;
		env.totalMemory=os.totalmem();
		env.freeMemory=os.freemem();
		env.os={
			type:os.type(),
			version:os.release()
		};
		
		//GPU 信息
		try {
			let gpus = await gpuInfo();
			env.gpu = gpus;
		}catch(err){
			if(env.platform==="darwin"){
				env.gpu={
					memory:env.totalMemory
				};
			}else{
				env.gpu=null;
			}
			
		}
		
		//磁盘信息:
		try {
			const path = process.platform === 'win32' ? 'C:' : '/';
			const { available, total } = diskUsage.checkSync(path);
			env.freeDiskSpace=`${(available / 1024 / 1024 / 1024).toFixed(2)} GB`;
			env.totalDiskSpace=`${(total / 1024 / 1024 / 1024).toFixed(2)} GB`;
		} catch (error) {
			console.error('Failed to check disk space:', error);
		}		
		//Node信息:		
		env.node={
			execPath:process.execPath,
			version:process.version
		};
		
		//Conda信息:
		try {
			const condaName=await getCondaEnvName();
			const condaVersion = execSync('conda --version').toString().trim();
			const versionNumber = condaVersion.split(' ')[1];
			console.log('Conda Version:', versionNumber);
			env.conda={
				default:condaName||null,
				version: versionNumber
			};
		}catch (error){
			console.error('Conda is not installed or not in PATH');
			env.conda=null;
		}		
		
		//Docker信息:
		try {
			const dockerVersion = execSync('docker --version').toString().trim();
			console.log('Docker is installed:', dockerVersion);
			env.docker={
				version:dockerVersion
			};
		} catch (error) {
			console.error('Docker is not installed or not in PATH');
			env.docker=null;
		}
		/*}#1IG32J8B00Code*/
		return {seg:ReadConifg,result:(result),preSeg:"1IG32J8B00",outlet:"1IG32JGK90"};
	};
	InitEnv.jaxId="1IG32J8B00"
	InitEnv.url="InitEnv@"+agentURL
	
	segs["ReadConifg"]=ReadConifg=async function(input){//:1IG32KVO90
		let result=input
		/*#{1IG32KVO90Code*/
		let config=session.agentNode.nodeJSON;
		env.rootPath=config.rootPath||"";
		if(env.rootPath[0]!=="/"){
			env.rootPath=pathLib.join(session.agentNode.path,env.rootPath);
			if(env.conda && config.conda){
				env.conda.default=config.conda;
			}
		}
		/*}#1IG32KVO90Code*/
		return {seg:InitBash,result:(result),preSeg:"1IG32KVO90",outlet:"1IG32OB9D0"};
	};
	ReadConifg.jaxId="1IG32KVO90"
	ReadConifg.url="ReadConifg@"+agentURL
	
	segs["InitBash"]=InitBash=async function(input){//:1IG3G17U20
		let result,args={};
		args['bashId']="";
		args['action']="Create";
		args['commands']="";
		args['options']={client:true};
		/*#{1IG3G17U20PreCodes*/
		/*}#1IG3G17U20PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IG3G17U20PostCodes*/
		globalContext.bash=result;
		/*}#1IG3G17U20PostCodes*/
		return {seg:ShowEnv,result:(result),preSeg:"1IG3G17U20",outlet:"1IG3G2LGG0"};
	};
	InitBash.jaxId="1IG3G17U20"
	InitBash.url="InitBash@"+agentURL
	
	segs["ShowEnv"]=ShowEnv=async function(input){//:1IG3GT0LF0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=`
Environment:
\`\`\`javascript
${JSON.stringify(env,null,"\t")}
\`\`\`
`;
		/*#{1IG3GT0LF0PreCodes*/
		/*}#1IG3GT0LF0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IG3GT0LF0PostCodes*/
		result = content;
		/*}#1IG3GT0LF0PostCodes*/
		return {result:result};
	};
	ShowEnv.jaxId="1IG3GT0LF0"
	ShowEnv.url="ShowEnv@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"SysInitWorkEnv",
		url:agentURL,
		autoStart:true,
		jaxId:"1IG32J23V0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IG32J23V0PreEntry*/
			/*}#1IG32J23V0PreEntry*/
			result={seg:InitEnv,"input":input};
			/*#{1IG32J23V0PostEntry*/
			/*}#1IG32J23V0PostEntry*/
			return result;
		},
		/*#{1IG32J23V0MoreAgentAttrs*/
		/*}#1IG32J23V0MoreAgentAttrs*/
	};
	/*#{1IG32J23V0PostAgent*/
	/*}#1IG32J23V0PostAgent*/
	return agent;
};
/*#{1IG32J23V0ExCodes*/
/*}#1IG32J23V0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "SysInitWorkEnv",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	isChatApi: true
}];
//#CodyExport<<<
/*#{1IG32J23V0PostDoc*/
/*}#1IG32J23V0PostDoc*/


export default SysInitWorkEnv;
export{SysInitWorkEnv,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IG32J23V0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IG32J23V1",
//			"attrs": {
//				"SysInitWorkEnv": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IG32J2400",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IG32J2401",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IG32J2402",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IG32J2403",
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
//			"jaxId": "1IG32J23V2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IG32J23V3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IG32J23V4",
//			"attrs": {
//				"env": {
//					"type": "auto",
//					"valText": "null"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IG32J23V5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IG32J23V6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IG32J8B00",
//					"attrs": {
//						"id": "InitEnv",
//						"viewName": "",
//						"label": "",
//						"x": "115",
//						"y": "110",
//						"desc": "初始化默认的工作环境。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG32JGKA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG32JGKA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG32JGK90",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG32KVO90"
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
//					"jaxId": "1IG32KVO90",
//					"attrs": {
//						"id": "ReadConifg",
//						"viewName": "",
//						"label": "",
//						"x": "380",
//						"y": "110",
//						"desc": "读取config.json",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG32OB9F0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG32OB9F1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG32OB9D0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG3G17U20"
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
//					"def": "Bash",
//					"jaxId": "1IG3G17U20",
//					"attrs": {
//						"id": "InitBash",
//						"viewName": "",
//						"label": "",
//						"x": "615",
//						"y": "110",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG3G2LGM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG3G2LGM1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "\"\"",
//						"action": "Create",
//						"commands": "\"\"",
//						"options": "#{client:true}",
//						"outlet": {
//							"jaxId": "1IG3G2LGG0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG3GT0LF0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IG3GT0LF0",
//					"attrs": {
//						"id": "ShowEnv",
//						"viewName": "",
//						"label": "",
//						"x": "875",
//						"y": "110",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG3GUT1J0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG3GUT1J1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#`\nEnvironment:\n\\`\\`\\`javascript\n${JSON.stringify(env,null,\"\\t\")}\n\\`\\`\\`\n`",
//						"outlet": {
//							"jaxId": "1IG3GUT1G0",
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
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}