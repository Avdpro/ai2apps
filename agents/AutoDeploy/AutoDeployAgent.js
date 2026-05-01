//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1JN92DRGT0MoreImports*/
import { runClaudeWithSession } from './ClaudeBridge.mjs';
import { buildFullPipelinePrompt } from './AutoDeployPrompt.js';
import fsp from 'fs/promises';
/*}#1JN92DRGT0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"model":{
			"name":"model","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JN92DRGT0ArgsView*/
	/*}#1JN92DRGT0ArgsView*/
};

/*#{1JN92DRGT0StartDoc*/
/*}#1JN92DRGT0StartDoc*/
//----------------------------------------------------------------------------
let AutoDeployAgent=async function(session){
	let model;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let AutoDeploy,Read,UpdateDeploy,UpdateUsage,UpdateDelete,UpdateSize,GetUrl;
	/*#{1JN92DRGT0LocalVals*/
	let deployGuideMD, usageGuideMD, url;
	const API_URL = process.env.MODELHUNT_TEST_API_URL;
	const KEY = process.env.MODELHUNT_PUBLIC_KEY;
	/*}#1JN92DRGT0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
		}else{
			model=undefined;
		}
		/*#{1JN92DRGT0ParseArgs*/
		/*}#1JN92DRGT0ParseArgs*/
	}
	
	/*#{1JN92DRGT0PreContext*/
	/*}#1JN92DRGT0PreContext*/
	context={};
	/*#{1JN92DRGT0PostContext*/
	/*}#1JN92DRGT0PostContext*/
	let $agent,agent,segs={};
	segs["AutoDeploy"]=AutoDeploy=async function(input){//:1JN92GB540
		let result=input
		try{
			/*#{1JN92GB540Code*/
			let $channel = 'Chat';
			let opts = { txtHeader: 'AutoDeploy', channel: $channel };
			let role = 'assistant';
			// Build the full pipeline prompt
			const prompt = buildFullPipelinePrompt({
				model,
				repoUrl: url,
				deployGuideMD,
				usageGuideMD,
			});
			
			session.addChatText(role, ($ln === 'CN'
									? '🚀 启动全自动部署流程...\n'
									: '🚀 Starting full deployment pipeline...\n'), opts);
			
			session.addChatText(role, ($ln === 'CN'
									? '📋 Phase 1: 分析仓库 → Phase 2: 生成 deploy.json → Phase 3: 执行部署 & 修复\n'
									+ '📄 Phase 4: 生成 usage.yaml'
									: '📋 Phase 1: Analyze repo → Phase 2: Generate deploy.json → Phase 3: Deploy & Fix\n'
									+ '📄 Phase 4: Generate usage.yaml'), opts);
			
			// Run Claude Code for the full pipeline
			const deployResult = await runClaudeWithSession({
				session,
				prompt,
				cwd: process.env.HOME || '/tmp',
				timeout: 60 * 60 * 1000, // 1 hour
				onProgress: (text) => {
					if (text && text.trim()) {
						session.addChatText('assistant', text.trim(), { ...opts, channel: 'Log' });
					}
				},
			});
			
			if (deployResult.success) {
				session.addChatText(role, ($ln === 'CN'
										? '✅ 全流程完成！\n\n文件已生成:\n'
										+ '  • ~/.modelhunt/deploy/{id}.json\n'
										+ '  • ~/.modelhunt/usage/{id}.yaml'
										: '✅ Pipeline complete!\n\nFiles generated:\n'
										+ '  • ~/.modelhunt/deploy/{id}.json\n'
										+ '  • ~/.modelhunt/usage/{id}.yaml'), opts);
				result = { result: 'Finish', output: deployResult.output };
			} else {
				session.addChatText(role, ($ln === 'CN'
										? '❌ 流程失败: ' + (deployResult.error || '未知错误')
										: '❌ Pipeline failed: ' + (deployResult.error || 'unknown error')), opts);
				result = { result: 'Failed', error: deployResult.error, output: deployResult.output };
			}
			/*}#1JN92GB540Code*/
		}catch(error){
			/*#{1JN92GB540ErrorCode*/
			result=error;
			/*}#1JN92GB540ErrorCode*/
		}
		return {seg:UpdateDeploy,result:(result),preSeg:"1JN92GB540",outlet:"1JN92GJ540"};
	};
	AutoDeploy.jaxId="1JN92GB540"
	AutoDeploy.url="AutoDeploy@"+agentURL
	
	segs["Read"]=Read=async function(input){//:1JN92VKAH0
		let result=input
		try{
			/*#{1JN92VKAH0Code*/
			const deployPath = pathLib.join(basePath, './Deploy/guide.md');
			const usagePath = pathLib.join(basePath, './Usage/guide.md');
			deployGuideMD = await fsp.readFile(deployPath, 'utf-8');
			usageGuideMD = await fsp.readFile(usagePath, 'utf-8');
			/*}#1JN92VKAH0Code*/
		}catch(error){
			/*#{1JN92VKAH0ErrorCode*/
			/*}#1JN92VKAH0ErrorCode*/
		}
		return {seg:AutoDeploy,result:(result),preSeg:"1JN92VKAH0",outlet:"1JN92VRVI0"};
	};
	Read.jaxId="1JN92VKAH0"
	Read.url="Read@"+agentURL
	
	segs["UpdateDeploy"]=UpdateDeploy=async function(input){//:1JNE5FQ6D0
		let result=input
		try{
			/*#{1JNE5FQ6D0Code*/
			let opts = { txtHeader: 'AutoDeploy', channel: 'Chat' };
			
			session.addChatText('assistant', ($ln === 'CN'
				? `🔄 开始同步模型 [${model}] 的平台部署数据...`
				: `🔄 Syncing platform deployment data for model [${model}]...`), opts);
			
			// 1. 读取前序步骤生成的 deploy.json 文件
			const deployPath = pathLib.join(process.env.HOME || '/tmp', '.modelhunt/deploy', `${model}.json`);
			let deployData;
			try {
				const fileContent = await fsp.readFile(deployPath, 'utf-8');
				deployData = JSON.parse(fileContent);
			} catch (err) {
				throw new Error(`读取 deploy.json 失败: ${err.message}`);
			}
			
			// 2. 提取需要发送的 platform 字段
			const requestBody = deployData.platforms;
			if (!requestBody) {
				throw new Error(`在 deploy.json 中未找到 'platforms' 字段!`);
			}
			
			// 3. 构建目标 URL (将写死的 spark_tts 替换为动态传入的 model 变量)
			const targetUrl = `${API_URL.replace(/\/$/, '')}/api/public/v1/models/${model}`;
			
			// 4. 发送 API 请求
			const response = await fetch(targetUrl, {
				method: 'PUT', // 建议和后端沟通使用 PATCH/POST/PUT
				headers: {
					'accept': 'application/json',
					'Content-Type': 'application/json',
					'Authorization': `Bearer ${KEY}`
				},
				body: JSON.stringify(requestBody)
			});
			
			if (!response.ok) {
				const errorText = await response.text();
				throw new Error(`API 同步失败! HTTP 状态码: ${response.status}, 详情: ${errorText}`);
			}
			
			const responseJson = await response.json();
			
			session.addChatText('assistant', ($ln === 'CN'
				? `✅ 平台数据同步完成！API 已成功接收。`
				: `✅ Platform data sync complete! API successfully received the payload.`), opts);
			/*}#1JNE5FQ6D0Code*/
		}catch(error){
			/*#{1JNE5FQ6D0ErrorCode*/
			/*}#1JNE5FQ6D0ErrorCode*/
		}
		return {seg:UpdateUsage,result:(result),preSeg:"1JNE5FQ6D0",outlet:"1JNE5G43S0"};
	};
	UpdateDeploy.jaxId="1JNE5FQ6D0"
	UpdateDeploy.url="UpdateDeploy@"+agentURL
	
	segs["UpdateUsage"]=UpdateUsage=async function(input){//:1JNE6AVC40
		let result=input
		try{
			/*#{1JNE6AVC40Code*/
			let opts = { txtHeader: 'AutoDeploy', channel: 'Chat' };
			
			session.addChatText('assistant', ($ln === 'CN'
				? `🔄 开始同步模型 [${model}] 的 Usage 配置...`
				: `🔄 Syncing usage config for model [${model}]...`), opts);
			
			// 1. 读取前序步骤生成的 usage.yaml 文件作为纯字符串
			const usagePath = pathLib.join(process.env.HOME || '/tmp', '.modelhunt/usage', `${model}.yaml`);
			let yamlContent;
			try {
				yamlContent = await fsp.readFile(usagePath, 'utf-8');
			} catch (err) {
				throw new Error(`读取 usage.yaml 失败: ${err.message}`);
			}
			
			// 2. 组装符合 curl 请求规范的 Body
			const requestBody = {
				usage_config: yamlContent
			};
			
			// 3. 构建目标 URL (替换 spark_ttss 为动态变量 model)
			const targetUrl = `${API_URL.replace(/\/$/, '')}/api/public/v1/models/${model}/usage`;
			
			// 4. 发送 PUT 请求
			const response = await fetch(targetUrl, {
				method: 'PUT',
				headers: {
					'accept': 'application/json',
					'Content-Type': 'application/json',
					'Authorization': `Bearer ${KEY}`
				},
				body: JSON.stringify(requestBody)
			});
			
			if (!response.ok) {
				const errorText = await response.text();
				throw new Error(`Usage API 同步失败! HTTP 状态码: ${response.status}, 详情: ${errorText}`);
			}
			
			const responseJson = await response.json();
			
			session.addChatText('assistant', ($ln === 'CN'
				? `✅ Usage 配置同步完成！API 已成功更新。`
				: `✅ Usage config sync complete! API successfully updated.`), opts);
			/*}#1JNE6AVC40Code*/
		}catch(error){
			/*#{1JNE6AVC40ErrorCode*/
			/*}#1JNE6AVC40ErrorCode*/
		}
		return {seg:UpdateDelete,result:(result),preSeg:"1JNE6AVC40",outlet:"1JNE6B3P50"};
	};
	UpdateUsage.jaxId="1JNE6AVC40"
	UpdateUsage.url="UpdateUsage@"+agentURL
	
	segs["UpdateDelete"]=UpdateDelete=async function(input){//:1JNE6H5DA0
		let result=input
		try{
			/*#{1JNE6H5DA0Code*/
			/*}#1JNE6H5DA0Code*/
		}catch(error){
			/*#{1JNE6H5DA0ErrorCode*/
			/*}#1JNE6H5DA0ErrorCode*/
		}
		return {seg:UpdateSize,result:(result),preSeg:"1JNE6H5DA0",outlet:"1JNE6OD720"};
	};
	UpdateDelete.jaxId="1JNE6H5DA0"
	UpdateDelete.url="UpdateDelete@"+agentURL
	
	segs["UpdateSize"]=UpdateSize=async function(input){//:1JNE8Q00C0
		let result=input
		try{
			/*#{1JNE8Q00C0Code*/
			
					let opts = { txtHeader: 'AutoDeploy', channel: 'Chat' };
			
					session.addChatText('assistant', ($ln === 'CN'
						? `🔄 开始同步模型 [${model}] 的体积大小数据...`
						: `🔄 Syncing space data for model [${model}]...`), opts);
			
					// 1. 读取体积配置文件 (推断文件名为: 模型名_size.json)
					// 注意：如果你是在当前目录的 deploy 文件夹下运行，请将路径改为 pathLib.join(basePath, 'deploy', `${model}_size.json`)
					const sizePath = pathLib.join(process.env.HOME || '/tmp', '.modelhunt/deploy', `${model}_size.json`);
					let sizeData;
					try {
						const fileContent = await fsp.readFile(sizePath, 'utf-8');
						sizeData = JSON.parse(fileContent);
					} catch (err) {
						throw new Error(`读取 ${model}_size.json 失败: ${err.message}`);
					}
			
					// 2. 提取并转换 size.total 为浮点数 (例如: "~2.4 GB" -> 2.4)
					let spaceValue = 0.0;
					if (sizeData && sizeData.size && sizeData.size.total) {
						// 使用正则提取字符串中的数字和小数点部分
						const match = sizeData.size.total.match(/[\d.]+/);
						if (match) {
							spaceValue = parseFloat(match[0]);
						} else {
							throw new Error(`无法从 size.total (${sizeData.size.total}) 中解析出有效数字!`);
						}
					} else {
						throw new Error(`在 ${model}_size.json 中未找到 'size.total' 字段!`);
					}
			
					// 3. 组装符合 curl 请求规范的 Body
					const requestBody = {
						space: spaceValue
					};
			
					// 4. 构建目标 URL (将 spark_tts 替换为动态变量 model)
					const targetUrl = `${API_URL.replace(/\/$/, '')}/api/public/v1/models/${model}`;
			
					// 5. 发送 PATCH 请求
					const response = await fetch(targetUrl, {
						method: 'PATCH',
						headers: {
							'accept': 'application/json',
							'Content-Type': 'application/json',
							'Authorization': `Bearer ${KEY}`
						},
						body: JSON.stringify(requestBody)
					});
			
					if (!response.ok) {
						const errorText = await response.text();
						throw new Error(`Size API 同步失败! HTTP 状态码: ${response.status}, 详情: ${errorText}`);
					}
			
					const responseJson = await response.json();
			
					session.addChatText('assistant', ($ln === 'CN'
						? `✅ 体积数据同步完成！API 已更新占用空间为: ${spaceValue} GB。`
						: `✅ Space data sync complete! API updated space to: ${spaceValue} GB.`), opts);
						/*}#1JNE8Q00C0Code*/
		}catch(error){
			/*#{1JNE8Q00C0ErrorCode*/
			/*}#1JNE8Q00C0ErrorCode*/
		}
		return {result:result};
	};
	UpdateSize.jaxId="1JNE8Q00C0"
	UpdateSize.url="UpdateSize@"+agentURL
	
	segs["GetUrl"]=GetUrl=async function(input){//:1JNE94TEK0
		let result=API_URL
		try{
			/*#{1JNE94TEK0Code*/
			let opts = { txtHeader: 'AutoDeploy', channel: 'Chat' };
			const targetUrl = `${API_URL.replace(/\/$/, '')}/api/public/v1/models/${model}`;
			const response = await fetch(targetUrl, {
				method: 'GET',
				headers: {
					'accept': 'application/json',
					'Authorization': `Bearer ${KEY}`
				}
			});
			if (!response.ok) {
				const errorText = await response.text();
				throw new Error(`获取模型详情失败! HTTP 状态码: ${response.status}, 详情: ${errorText}`);
			}
			const responseJson = await response.json();
			result=response;
			if (!responseJson.urlGitHub) {
				throw new Error(`API 响应中未找到 'urlGithub' 字段! 可能是该模型未配置仓库地址。`);
			}
			url = responseJson.urlGitHub;
															/*}#1JNE94TEK0Code*/
		}catch(error){
			/*#{1JNE94TEK0ErrorCode*/
			/*}#1JNE94TEK0ErrorCode*/
		}
		return {seg:Read,result:(result),preSeg:"1JNE94TEK0",outlet:"1JNE954100"};
	};
	GetUrl.jaxId="1JNE94TEK0"
	GetUrl.url="GetUrl@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"AutoDeployAgent",
		url:agentURL,
		autoStart:true,
		jaxId:"1JN92DRGT0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JN92DRGT0PreEntry*/
			/*}#1JN92DRGT0PreEntry*/
			result={seg:GetUrl,"input":input};
			/*#{1JN92DRGT0PostEntry*/
			/*}#1JN92DRGT0PostEntry*/
			return result;
		},
		/*#{1JN92DRGT0MoreAgentAttrs*/
		/*}#1JN92DRGT0MoreAgentAttrs*/
	};
	/*#{1JN92DRGT0PostAgent*/
	/*}#1JN92DRGT0PostAgent*/
	return agent;
};
/*#{1JN92DRGT0ExCodes*/
/*}#1JN92DRGT0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1JN92DRGT0PostDoc*/
/*}#1JN92DRGT0PostDoc*/


export default AutoDeployAgent;
export{AutoDeployAgent};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JN92DRGT0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JN92DTUD0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1JN92DTUD1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "GetUrl",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JN92DTUD2",
//			"attrs": {
//				"model": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JN9HEB1N0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JN92DTUD3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JN92DTUD4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JN92DTUD5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JN92GB540",
//					"attrs": {
//						"id": "AutoDeploy",
//						"viewName": "",
//						"label": "",
//						"x": "200",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JN92HD580",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JN92HD581",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JN92GJ540",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JNE5FQ6D0"
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
//					"jaxId": "1JN92VKAH0",
//					"attrs": {
//						"id": "Read",
//						"viewName": "",
//						"label": "",
//						"x": "-100",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JN9303CP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JN9303CP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JN92VRVI0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JN92GB540"
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
//					"jaxId": "1JNE5FQ6D0",
//					"attrs": {
//						"id": "UpdateDeploy",
//						"viewName": "",
//						"label": "",
//						"x": "550",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JNE5VM3T0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JNE5VM3T1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JNE5G43S0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JNE6AVC40"
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
//					"jaxId": "1JNE6AVC40",
//					"attrs": {
//						"id": "UpdateUsage",
//						"viewName": "",
//						"label": "",
//						"x": "840",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JNE6B3P70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JNE6B3P71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JNE6B3P50",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JNE6H5DA0"
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
//					"jaxId": "1JNE6H5DA0",
//					"attrs": {
//						"id": "UpdateDelete",
//						"viewName": "",
//						"label": "",
//						"x": "1155",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JNE6Q23R0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JNE6Q23R1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JNE6OD720",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JNE8Q00C0"
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
//					"jaxId": "1JNE8Q00C0",
//					"attrs": {
//						"id": "UpdateSize",
//						"viewName": "",
//						"label": "",
//						"x": "1430",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JNE8Q4CF0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JNE8Q4CF1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JNE8Q4CB0",
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
//					"jaxId": "1JNE94TEK0",
//					"attrs": {
//						"id": "GetUrl",
//						"viewName": "",
//						"label": "",
//						"x": "-430",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JNE95D840",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JNE95D841",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JNE954100",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JN92VKAH0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#API_URL",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}