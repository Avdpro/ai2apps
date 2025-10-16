import OpenAI,{toFile} from "openai";
import Anthropic from '@anthropic-ai/sdk';
import {GoogleGenAI} from '@google/genai';
import ollama from "ollama";

import followRedirects from "follow-redirects";
import {Readable} from "stream";

import ProxyCall from '../util/ProxyCall.js';
const { callProxy,proxyCall }=ProxyCall;
import ApiProxy from "../apiproxy/FetchProxy.mjs";
import invokeApi from '../util/InvokeApi.mjs'

const AIPlatforms={
	"OpenAI":{
		"gpt-5":{model:"gpt-5",label:"GPT-5"},
		"gpt-5-mini":{model:"gpt-5-mini",label:"GPT-5-Mini"},
		"gpt-5-nano":{model:"gpt-5-nano",label:"GPT-5-nano"},
		"gpt-5-codex":{model:"gpt-5-codex",label:"GPT-5-codex"},
		"gpt-4.1":{model:"gpt-4.1",label:"GPT-4.1"},
		"gpt-4o":{model:"gpt-4o",label:"GPT-4O"},
		"gpt-4.1-mini":{model:"gpt-4.1-mini",label:"GPT-4.1 Mini"},
		"gpt-4o-mini":{model:"gpt-4o-mini",label:"GPT-4O-mini"},
		"gpt-4.1-nano":{model:"gpt-4.1-nano",label:"GPT-4.1 Nano"},
		"gpt-3.5-turbo":{model:"gpt-3.5-turbo",label:"GPT-3.5"},
		"gpt-3.5-turbo-16k":{model:"gpt-3.5-turbo-16k",label:"GPT-3.5-16K"},
		"gpt-4":{model:"gpt-4",label:"GPT-4"},
		"gpt-4-turbo":{model:"gpt-4-turbo",label:"GPT-4 Turbo"},
	},
	"Google":{
		"gemini-2.5-pro":{model:"gemini-2.5-pro",label:"Gemini 2.5 Pro"},
		"gemini-2.5-flash":{model:"gemini-2.5-flash",label:"Gemini 2.5 flash"},
		"gemini-2.5-flash-lite":{model:"gemini-2.5-flash-lite",label:"Gemini 2.5 flash-lite"},
		"gemini-pro":{model:"gemini-pro",label:"Gemini Pro"}
	},
	"Claude":{
		"claude-3-7-sonnet-latest":{model:"claude-3-7-sonnet-latest",label:"Claude 3.7 Sonnet"},
		"claude-3-5-sonnet-latest":{model:"claude-3-5-sonnet-latest",label:"Claude 3.5 Sonnet"},
		"claude-3-5-sonnet-20240620":{model:"claude-3-5-sonnet-20240620",label:"Claude 3.5 Sonnet 240620"},
		"claude-3-sonnet-20240229":{model:"claude-3-sonnet-20240229",label:"Claude 3 Sonnet"},
		"claude-3-opus-20240229":{model:"claude-3-opus-20240229",label:"Claude 3 Opus"},
	},
	"Ollama":{
		"llama3":{model:"llama3",label:"LLAMA3 8b"},
		"llama3:70b":{model:"llama3:70b",label:"LLAMA3 70b"},
		"llama3-gradient":{model:"llama3-gradient",label:"LLAMA3 1024K 8b"},
		"llama3-gradient:70b":{model:"llama3-gradient:70b",label:"LLAMA3 1024K 70b"},
		"terrence/openbuddy":{model:"terrence/openbuddy",label:"LLAMA3 Chinese"},
		"phi3":{model:"phi3",label:"Phi3"},
		"moondream":{model:"moondream",label:"Moon Dream"},
	}
};

//---------------------------------------------------------------------------
//OpenAI:
const OPENAI_API_KEY=process.env.OPENAI_API_KEY;
let openAI;
if(OPENAI_API_KEY && OPENAI_API_KEY!=="[YOUR OPENAI KEY]") {
	openAI = new OpenAI({
		apiKey:OPENAI_API_KEY,
	});
}else{
	openAI=null;
}

//---------------------------------------------------------------------------
//Anthropic:
const CLAUDE_API_KEY=process.env.CLAUDE_API_KEY;
let anthropic=null;
if(CLAUDE_API_KEY) {
	anthropic = new Anthropic({
		apiKey: CLAUDE_API_KEY
	});
}

//---------------------------------------------------------------------------
//Google:
const GOOGLEAI_API_KEY=process.env.GOOGLEAI_API_KEY;
let googleAI=null;
if(GOOGLEAI_API_KEY) {
	googleAI = new GoogleGenAI({apiKey: GOOGLEAI_API_KEY});
}

const DAYTIME=24*3600*1000;
const USERINFO_PROJECTION={rank:1,rankExpire:1,points:1,coins:1,token:1,tokenExpire:1,lastLogin:1,tokens:1,AIUsage:1};

//***************************************************************************
//Stream utils:
//***************************************************************************
const streamMap=new Map();
let nextStreamId=0;
let getStreamId,shutdownStream;
{
	//-----------------------------------------------------------------------
	getStreamId=function(){
		nextStreamId++;
		return "STREAM_"+nextStreamId;
	};

	//-----------------------------------------------------------------------
	shutdownStream=function(streamId){
		let streamVO;
		streamVO=streamMap.get(streamId);
		if(!streamVO)
			return;
		if(!streamVO.closed) {
			if (streamVO.errorFunc) {
				streamVO.errorFunc("Timeout")
			}
		}
		streamMap.delete(streamId);
	};
}

//---------------------------------------------------------------------------
//API for AI calls
export default async function(app,router,apiMap) {
	let setupTokenUtils,tokenForMessages,checkAITokenCall,chargePointsByChat,chargePointsByUsage;
	let getUserInfo,getPVUserInfo;
	const env = app.get("env");
	const dbUser = app.get("DBUser");
	const dbPreview= app.get("DBPreview");
	
	try{
		const m=await import("../util/TokenUtils.mjs");
		setupTokenUtils=m.setupTokenUtils;
		tokenForMessages=m.tokenForMessages;
		checkAITokenCall=m.checkAITokenCall;
		chargePointsByChat=m.chargePointsByChat;
		chargePointsByUsage=m.chargePointsByUsage;
		setupTokenUtils(app);
	}catch(err){
		//do nothing
		checkAITokenCall=function(){return {code:200};};
		tokenForMessages=()=>{return 0;};
		chargePointsByChat=function(){};
		chargePointsByUsage=function(){};
	}

	if(dbUser) {
		const m=await import("../util/UserUtils.js");
		getUserInfo=m.getUserInfo;
		getPVUserInfo=m.getPVUserInfo;
	}else{
		getUserInfo=null;
		getPVUserInfo=null;
	}
	
	//***********************************************************************
	//Basic AI Calls:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		apiMap['checkAICallStatus']=async function(req,res,next){
			let reqVO, userInfo, resVO;
			reqVO = req.body.vo;
			if(getUserInfo) {
				let userId,token;
				userId = reqVO.userId;
				token = reqVO.token;
				if (!userId) {
					res.json({ code: 403, info: "UserId/Token invalid." });
					return;
				}
				userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
				if (!userInfo) {
					userInfo = await getPVUserInfo(req, USERINFO_PROJECTION);
					if (!userInfo) {
						res.json({ code: 403, info: "UserId/Token invalid." });
						return;
					}
				}
				resVO = await checkAITokenCall(userInfo, reqVO.platform, reqVO.model);
				if (resVO.code !== 200) {
					res.json({code: 401,info:"Gas is not enough to make AICall."});
					return;
				}
			}
			res.json({ code: 200, info: "AICall is ready." });
		};
		
		//-------------------------------------------------------------------
		apiMap['readAIChatStream'] = async function (req, res, next) {
			let reqVO, streamId, streamVO, textRead, textGot, pms, functionCall,toolCalls;
			reqVO = req.body.vo;
			streamId = reqVO.streamId;
			if (!streamId) {
				res.json({ code: -100, info: "Missing streamId." });
				return;
			}
			streamVO = streamMap.get(streamId);
			if (!streamVO) {
				await proxyCall(req,res,next);
				return;
			}
			functionCall=streamVO.functionCall;
			toolCalls=streamVO.toolCalls;
			if(functionCall){
				textGot = JSON.stringify(functionCall);
			}else if(toolCalls){
				textGot = JSON.stringify(toolCalls);
			
			}else{
				textGot = streamVO.content;
			}
			textRead = streamVO.textRead;
			if(streamVO.closed && streamVO.refusal){
				streamVO.textRead = textGot;
				res.json({ code: 500, info:`AI refused: ${streamVO.refusal}`});
				return;
			}else if (textRead !== textGot || streamVO.closed) {
				if(functionCall){
					res.json({ code: 200, message: textGot, closed: streamVO.closed, functionCall: functionCall,inputTokens:streamVO.inputTokens,outputTokens:streamVO.outputTokens});
				}else if(toolCalls){
					res.json({ code: 200, message: textGot, closed: streamVO.closed, toolCalls: toolCalls,inputTokens:streamVO.inputTokens,outputTokens:streamVO.outputTokens});
				}else {
					res.json({ code: 200, message: textGot, closed: streamVO.closed ,inputTokens:streamVO.inputTokens,outputTokens:streamVO.outputTokens});
				}
				streamVO.textRead = textGot;
				return;
			}
			//Wait content:
			pms = new Promise((resolve, reject) => {
				streamVO.waitFunc = resolve;
				streamVO.errorFunc = reject;
			})
			await pms;
			textGot = streamVO.content;
			streamVO.textRead = textGot;
			res.json({ code: 200, message: textGot, closed: streamVO.closed,inputTokens:streamVO.inputTokens,outputTokens:streamVO.outputTokens });
		};
		
		//-------------------------------------------------------------------
		let fixHostPrompt=async function(messages,userId,token,userInfo){
			let systemPmt,res;
			systemPmt=messages[0];
			if(systemPmt.prompt && systemPmt.args){
				if(!getUserInfo){
					return false;//We can't process this call here, must call AI at www.ai2apps.com
				}
				res=await invokeApi("HostPromptExec",{userId:userId,token:token,prompt:systemPmt.prompt,args:systemPmt.args},userInfo);
				if(res){
					if(res==="API-NOT-FOUND"){
						return false;////We can't process this call here, must call AI at www.ai2apps.com
					}else if(res.code!==200){
						throw Error(`Call host prompt error ${res?res.code:""}: ${(res.info||"unknown")}`);
					}
				}else {
					throw Error(`Call host prompt error.`);
				}
				messages[0]=res.result;
				return true;//OK to go:
			}
			return true;//OK to go
		};
		
		//-------------------------------------------------------------------
		let AICall = async function (callAIObj, req, res, next) {
			let reqVO,userInfo=null;
			let platform;
			let callVO, rawResVO, resVO;
			reqVO = req.body.vo;
			if(!reqVO.userId) {
				reqVO.userId = process.env.localUserId;
			}
			if(!reqVO.token){
				reqVO.token = process.env.localUserToken;
			}
			if(getUserInfo) {
				let userId, token;
				userId = reqVO.userId;
				token = reqVO.token;
				userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
				if (!userInfo) {
					userInfo = await getPVUserInfo(req, USERINFO_PROJECTION);
					if (!userInfo) {
						res.json({ code: 403, info: "UserId/Token invalid." });
						return;
					}
				}
			}
			
			if(await fixHostPrompt(reqVO.messages,reqVO.userId,reqVO.token,userInfo)===false){
				await proxyCall(req,res,next);
				return;
			}
			
			platform = reqVO.platform || "OpenAI";//Only OpenAI supported by now.
			//Make AI-Call:
			switch (platform) {
				case "Claude":{
					if(!anthropic){
						await proxyCall(req,res,next);
						return;
					}
					callVO = callAIObj.buildCallVO(reqVO,platform);
					//Check gas
					{
						resVO = await checkAITokenCall(userInfo, platform, callVO.model);
						if (resVO.code !== 200) {
							res.json(resVO);
							return;
						}
					}
					
					try {
						let content="";
						let messages=reqVO.messages;
						if(messages[0].role==="system"){
							callVO.system=messages[0].content;
							messages.shift();
						}
						//Fix image messages:
						for(let line of messages){
							let cnt,pt;
							cnt=line.content;
							if(Array.isArray(cnt)){
								for(pt of cnt){
									if(pt.type==="image_url"){
										let url,pos,data;
										pt.type="image";
										url=pt.image_url.url;
										pos=url.indexOf(",");
										data=url.substring(pos+1);
										pt.source={
											type:"base64",
											media_type:url.startsWith("data:image/jpeg")?"image/jpeg":"image/png",
											data:data
										};
										delete pt.image_url;
									}
								}
							}
						}
						callVO.messages=messages;
						
						try {
							rawResVO = await anthropic.messages.create(callVO);
						}catch(error){
							console.error(error);
							res.json({code: 500,info:`Anthropic messages.create error: ${""+error}`});
							return;
						}
						content=rawResVO.content[0];
						resVO = { code: 200,message:content.text||content};
						res.json(resVO);
						
						//Charge user token:
						chargePointsByUsage(userInfo,rawResVO.usage.input_tokens,rawResVO.usage.output_tokens,platform,callVO.model);
					} catch (err) {
						console.log(err);
					}
					return;
				}
				case "OpenAI": {
					if(!openAI){
						await proxyCall(req,res,next);
						return;
					}
					callVO = callAIObj.buildCallVO(reqVO);
					//Check gas
					{
						resVO = await checkAITokenCall(userInfo, platform, callVO.model);
						if (resVO.code !== 200) {
							res.json(resVO);
							return;
						}
					}
					
					try {
						let content="";
						try {
							rawResVO = await openAI.chat.completions.create(callVO, {});
						}catch(error){
							if (error instanceof OpenAI.APIError) {
								console.error(error.status);  // e.g. 401
								console.error(error.message); // e.g. The authentication token you passed was invalid...
								console.error(error.code);  // e.g. 'invalid_api_key'
								console.error(error.type);  // e.g. 'invalid_request_error'
								res.json({code: error.status,info:`Error ${error.code}(error.type): ${error.message}`});
							} else {
								// Non-API error
								console.log(error);
								res.json({code: 500,info:`openAI.chat.completions.create error: ${""+error}`});
							}
							return;
						}
						content=rawResVO.choices[0].message;
						resVO = { code: 200,message:content.content||content};
						res.json(resVO);
						
						//Charge user token:
						chargePointsByChat(userInfo, callVO.messages, content, platform, callVO.model);
					} catch (err) {
						console.log(err);
					}
					return;
				}
				case "Google":{
					let chat,modelName,messages,history,prompt,result,usage;
					if(!googleAI){
						await proxyCall(req,res,next);
						return;
					}
					modelName=reqVO.model || 'gemini-2.5-flash';
					//Check gas
					{
						resVO = await checkAITokenCall(userInfo, platform, modelName);
						if (resVO.code !== 200) {
							res.json(resVO);
							return;
						}
					}
					callVO = callAIObj.buildCallVO(reqVO);
					messages=reqVO.messages;
					history=[];
					for(let msg of messages){
						let role;
						role=msg.role;
						if(role==="system"){
							history.push({ role: "user", parts: [{text:"Chat background: "+msg.content }]});
							history.push({ role: "model", parts: [{text:"OK, let's start!"}]});
						}else {
							role = role === "user" ? "user" : "model";
							history.push({ role: role, parts: [{text:msg.content }]});
						}
					}
					prompt=history.pop().parts;
					chat = googleAI.chats.create({
						model:modelName,
						history:history,
						config:callVO
					});
					
					result=await chat.sendMessage({message:prompt});
					resVO = { code: 200,message:result.text};
					res.json(resVO);
					let tokenUsage=result.usageMetadata;
					if(tokenUsage){
						let inputTokens=tokenUsage.promptTokenCount;
						let outputTokens=(tokenUsage.candidatesTokenCount||0)+(tokenUsage.thoughtsTokenCount||0);
						chargePointsByUsage(userInfo,inputTokens,outputTokens,platform,modelName);
					}
					return;
				}
				//TODO: Code more:
				default: {
					res.json({ code: 405, info: `Platform ${platform} is not supported.` });
					return;
				}
			}
		};
		
		//-------------------------------------------------------------------
		let AIStreamCall = async function (callAIObj, req, res,next) {
			let reqVO,userInfo=null;
			let platform, callVO, resVO;
			
			reqVO = req.body.vo;

			if(getUserInfo) {
				let userId, token;
				userId = reqVO.userId;
				token = reqVO.token;
				userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
				if (!userInfo) {
					userInfo = await getPVUserInfo(req, USERINFO_PROJECTION);
					if (!userInfo) {
						res.json({ code: 403, info: "UserId/Token invalid." });
						return;
					}
				}
			}

			if(await fixHostPrompt(reqVO.messages,reqVO.userId,reqVO.token,userInfo)===false){
				await proxyCall(req,res,next);
				return;
			}
			
			platform = reqVO.platform || "OpenAI";
			
			//Make AI-Call:
			switch (platform) {
				case "Ollama":{
					let streamId,streamVO,chatStream,func,messages;
					callVO = callAIObj.buildCallVO(reqVO,platform);
					callVO.stream=true;
					try {
						streamId = getStreamId();
						streamVO = {
							streamId,
							role:"",
							content: "",
							textRead: "",
							closed: false,
							waitFunc: null,
							errorFunc: null,
							timer: null
						}
						messages=reqVO.messages;
						callVO.messages=messages;
						
						try {
							chatStream = await ollama.chat(callVO, { responseType: 'stream' });
						}catch(error){
							console.log(error);
							res.json({code: 500,info:`Ollama chat error: ${""+error}`});
							return;
						}
						streamVO.timer = setTimeout(() => {shutdownStream(streamId)}, 20000);
						
						resVO = { code: 200, streamId: streamId };
						streamMap.set(streamId, streamVO);
						res.json(resVO);
						
						{
							let content;
							for await (const part of chatStream) {
								content = part.message.content;
								if (content) {
									streamVO.content += content;
								}
								if(streamVO.timer){
									clearTimeout(streamVO.timer);
									streamVO.timer = setTimeout(() => {shutdownStream(streamId)}, 20000);
								}
								if (streamVO.content !== streamVO.textRead) {
									func = streamVO.waitFunc;
									if (func) {
										streamVO.waitFunc = null;
										func();
									}
								}
							}
						}
						streamVO.closed = true;
						func = streamVO.waitFunc;
						if (func) {
							streamVO.waitFunc = null;
							func();
						}
					}catch(err){
						console.error(err);
						if(!res.headersSent) {
							res.json({ code: 500, err: "" + err });
						}
					}
					break;
				}
				case "Claude":{
					let streamId,streamVO,stream,func,messages;
					if(!anthropic){
						await proxyCall(req,res,next);
						return;
					}
					callVO = callAIObj.buildCallVO(reqVO,platform);
					//Check gas
					{
						resVO = await checkAITokenCall(userInfo, platform, callVO.model);
						if (resVO.code !== 200) {
							res.json(resVO);
							return;
						}
					}
					try {
						let line;
						streamId = getStreamId();
						streamVO = {
							streamId,
							role:"",
							content: "",
							textRead: "",
							closed: false,
							waitFunc: null,
							errorFunc: null,
							timer: null
						}
						messages=reqVO.messages;
						if(messages[0].role==="system"){
							callVO.system=messages[0].content;
							messages.shift();
						}
						//Fix image messages:
						for(line of messages){
							let cnt,pt;
							cnt=line.content;
							if(Array.isArray(cnt)){
								for(pt of cnt){
									if(pt.type==="image_url"){
										let url,pos,data;
										pt.type="image";
										url=pt.image_url.url;
										pos=url.indexOf(",");
										data=url.substring(pos+1);
										pt.source={
											type:"base64",
											media_type:url.startsWith("data:image/jpeg")?"image/jpeg":"image/png",
											data:data
										};
										delete pt.image_url;
									}
								}
							}
						}
						callVO.messages=messages;
						stream = anthropic.messages
							.stream(callVO)
							.on('text', (text) => {
								let func;
								streamVO.content+=text;
								if(streamVO.timer){
									clearTimeout(streamVO.timer);
									streamVO.timer = setTimeout(() => {shutdownStream(streamId)}, 20000);
								}
								if (streamVO.content !== streamVO.textRead) {
									func = streamVO.waitFunc;
									if (func) {
										streamVO.waitFunc = null;
										func();
									}
								}
							});
						streamVO.timer = setTimeout(() => {shutdownStream(streamId)}, 20000);
						
						resVO = { code: 200, streamId: streamId };
						streamMap.set(streamId, streamVO);
						res.json(resVO);

						const message = await stream.finalMessage();
						streamVO.closed = true;
						func = streamVO.waitFunc;
						if (func) {
							streamVO.waitFunc = null;
							streamVO.inputTokens=message.usage.input_tokens;
							streamVO.outputTokens=message.usage.output_tokens;
							func();
						}
						chargePointsByUsage(userInfo,message.usage.input_tokens,message.usage.output_tokens,platform,callVO.model);
					}catch(err){
						console.error(err);
						if(!res.headersSent) {
							res.json({ code: 500, err: "" + err });
						}
					}
					break;
				}
				case "OpenAI": {
					if(!openAI){
						await proxyCall(req,res,next);
						return;
					}
					callVO = callAIObj.buildCallVO(reqVO,platform);
					{
						resVO = await checkAITokenCall(userInfo, platform, callVO.model);
						if (resVO.code !== 200) {
							res.json(resVO);
							return;
						}
					}
					
					try {
						let streamVO, streamId,chatStream;
						let dataLeft="";
						callVO.stream = true;
						callVO.stream_options={include_usage:true};
						//console.log("Call Code VO:");
						//console.log(callVO);
						try {
							chatStream = await openAI.chat.completions.create(callVO, { responseType: 'stream' });
						}catch(error){
							if (error instanceof OpenAI.APIError) {
								console.error(error.status);  // e.g. 401
								console.error(error.message); // e.g. The authentication token you passed was invalid...
								console.error(error.code);  // e.g. 'invalid_api_key'
								console.error(error.type);  // e.g. 'invalid_request_error'
								res.json({code: error.status,info:`Error ${error.code}(error.type): ${error.message}`});
							} else {
								// Non-API error
								console.log(error);
								res.json({code: 500,info:`openAI.chat.completions.create error: ${""+error}`});
							}
							return;
						}
						
						streamId = getStreamId();
						streamVO = {
							streamId,
							role:"",
							content: "",
							textRead: "",
							closed: false,
							waitFunc: null,
							errorFunc: null,
							timer: null
						}
						streamVO.timer = setTimeout(() => {shutdownStream(streamId)}, 20000);
						
						resVO = { code: 200, streamId: streamId };
						streamMap.set(streamId, streamVO);
						res.json(resVO);
						
						{
							let choice0,delta,content,funcCall,toolCalls,func,refusal;
							let inputTokens=0,outputTokens=0;
							for await (const part of chatStream) {
								choice0=part.choices[0];
								if (choice0) {
									delta = choice0.delta;
									if (delta) {
										if (delta.role) {
											streamVO.role = streamVO.role ? streamVO.role + delta.role : delta.role;
										}
										content = delta.content;
										if (content) {
											streamVO.content += content;
										}
										funcCall = delta.function_call;
										if (funcCall) {
											let stub, name, args;
											stub = streamVO.functionCall;
											if (!stub) {
												stub = streamVO.functionCall = { name: "", arguments: "" };
											}
											name = funcCall.name;
											args = funcCall['arguments'];
											if (name) {
												stub.name += funcCall.name;
											}
											if (args) {
												stub["arguments"] += args;
											}
										}
										//toolCalls support:
										toolCalls = delta.tool_calls;
										if (toolCalls) {
											let srcList, tgtList, i, n, idx, srcStub, tgtStub, srcFunc, tgtFunc;
											srcList = toolCalls;
											tgtList = streamVO.toolCalls;
											if (!tgtList) {
												tgtList = streamVO.toolCalls = [];
											}
											n = srcList.length;
											for (i = 0; i < n; i++) {
												srcStub = srcList[i];
												idx = srcStub.index >= 0 ? srcStub.index : i;
												tgtStub = tgtList[idx];
												if (!tgtStub) {
													tgtStub = tgtList[idx] = {
														index: idx, id: "", type: "function",
														function: {
															name: "", arguments: ""
														}
													};
												}
												if ("index" in srcStub) {
													tgtStub.index = srcStub.index;
												}
												if ("id" in srcStub) {
													tgtStub.id += srcStub.id;
												}
												if ("type" in srcStub) {
													tgtStub.type = "function";//srcStub.type;
												}
												srcFunc = srcStub.function;
												tgtFunc = tgtStub.function;
												if (srcFunc) {
													tgtFunc.name += srcFunc.name || "";
													tgtFunc["arguments"] += srcFunc["arguments"] || "";
												}
											}
										}
										refusal=delta.refusal;
										if(refusal){
											streamVO.refusal=(streamVO.refusal||"")+refusal;
										}
									}
								}else{
									//console.log(part);
									if(part.usage){
										inputTokens=part.usage.prompt_tokens||0;
										outputTokens=part.usage.completion_tokens||0;
									}
								}
								
								if(streamVO.timer){
									clearTimeout(streamVO.timer);
									streamVO.timer = setTimeout(() => {shutdownStream(streamId)}, 20000);
								}
								if (streamVO.content !== streamVO.textRead) {
									func = streamVO.waitFunc;
									if (func) {
										streamVO.waitFunc = null;
										func();
									}
								}
							}
							streamVO.closed = true;
							streamVO.inputTokens=inputTokens||0;
							streamVO.outputTokens=outputTokens||0;
							func = streamVO.waitFunc;
							if (func) {
								streamVO.waitFunc = null;
								func();
							}
							//console.log("Fin: "+streamVO.content);
							//charge points by chat:
							if(inputTokens>0){
								chargePointsByUsage(userInfo,inputTokens,outputTokens,platform,callVO.model);
							}else {
								chargePointsByChat(userInfo, callVO.messages, streamVO.content, platform, callVO.model);
							}
						}
					} catch (err) {
						console.error(err);
					}
					return;
				}
				default: {
					res.json({ code: 405, info: `Platform ${platform} is no supported.` });
					return;
				}
				case "Google":{
					let streamId,streamVO,stream,func;
					let tokenUsage,inputTokens,outputTokens;
					if(!googleAI){
						await proxyCall(req,res,next);
						return;
					}
					callVO = callAIObj.buildCallVO(reqVO,platform);
					try {
						let modelName,chat,messages,history,result,prompt;
						modelName=reqVO.model || 'gemini-2.5-flash';
						messages=reqVO.messages;
						history=[];
						for(let msg of messages){
							let role;
							role=msg.role;
							if(role==="system"){
								history.push({ role: "user", parts: [{text:"Chat background: "+msg.content }]});
								history.push({ role: "model", parts: [{text:"OK, let's start!"}]});
							}else {
								role = role === "user" ? "user" : "model";
								history.push({ role: role, parts: [{text:msg.content }]});
							}
						}
						prompt=history.pop().parts;
						//chat=model.startChat({history:history,generationConfig:callVO});
						chat=googleAI.chats.create({
							model:modelName,
							history:history,
							config:callVO
						});
						result = await chat.sendMessageStream({message:prompt});

						streamId = getStreamId();
						streamVO = {
							streamId,
							role:"",
							content: "",
							textRead: "",
							closed: false,
							waitFunc: null,
							errorFunc: null,
							timer: null
						}
						resVO = { code: 200, streamId: streamId };
						streamMap.set(streamId, streamVO);
						streamVO.timer = setTimeout(() => {shutdownStream(streamId)}, 20000);
						res.json(resVO);
						
						for await (const chunk of result) {
							const chunkText = chunk.text;
							//console.log(chunk);
							streamVO.content += chunkText;
							if(streamVO.timer){
								clearTimeout(streamVO.timer);
								streamVO.timer = setTimeout(() => {shutdownStream(streamId)}, 20000);
							}
							if (streamVO.content !== streamVO.textRead) {
								func = streamVO.waitFunc;
								if (func) {
									streamVO.waitFunc = null;
									func();
								}
							}
							if(chunk.usageMetadata){
								tokenUsage=chunk.usageMetadata;
							}
						}
						streamVO.closed = true;

						if(tokenUsage){
							inputTokens=tokenUsage.promptTokenCount;
							outputTokens=(tokenUsage.candidatesTokenCount||0)+(tokenUsage.thoughtsTokenCount||0);
							chargePointsByUsage(userInfo,inputTokens,outputTokens,platform,modelName);
						}

						func = streamVO.waitFunc;
						if (func) {
							streamVO.waitFunc = null;
							func();
						}
					}catch(err){
						console.error(err);
						if(!res.headersSent) {
							res.json({ code: 500, err: "" + err });
						}
					}
				}
			}
		};
		
		//-------------------------------------------------------------------
		let plainCall = {
			buildCallVO (reqVO,platform) {
				switch(platform){
					default:
					case "OpenAI":{
						let callVO = {
							model: reqVO.model || "gpt-3.5-turbo",
							//temperature: reqVO.temperature || 0.7,
							//max_tokens: reqVO.max_tokens || 3092,
							//top_p: reqVO.top_p || 1,
							//n: reqVO.best_of || reqVO.n || 1,
							//frequency_penalty: reqVO.frequency_penalty || 0,
							//presence_penalty: reqVO.presence_penalty || 0,
							messages: reqVO.messages,
						};
						if(reqVO.response_format && reqVO.response_format!=="text"){
							if(typeof(reqVO.response_format)==="object"){
								callVO.response_format = reqVO.response_format;
							}else{
								callVO.response_format = { type: reqVO.response_format };
							}
						}
						if(reqVO.seed!==undefined){
							let seed=parseInt(reqVO.seed);
							if(seed>=0) {
								callVO.seed = seed;
							}
						}
						if(reqVO.functions){
							if(reqVO.parallelFunction){
								let funcStub
								let list=reqVO.functions;
								let tools=[];
								for(funcStub of list){
									tools.push({
										type:"function",
										function:funcStub
									});
								}
								callVO.tools = tools;
								callVO.tool_choice = reqVO.function_call || "auto";
							}else {
								callVO.functions = reqVO.functions;
								callVO.function_call = reqVO.function_call || "auto";
							}
						}
						return callVO;
					}
					case "Claude":{
						let callVO;
						callVO={
							model: reqVO.model || 'claude-3-sonnet-20240229',
							max_tokens: reqVO.max_tokens || 1024,
						};
						if(reqVO.temperature>=0) {
							callVO.temperature = reqVO.temperature;
						}else if(reqVO.top_p>=0) {
							callVO.top_p = reqVO.top_p;
						}else{
							callVO.temperature = 1.0;
						}
						return callVO;
					}
					case "Google":{
						let callVO;
						callVO={
							//maxOutputTokens: reqVO.max_tokens || 1024,
							//temperature: reqVO.temperature || 0.7,
						};
						/*if(reqVO.temperature>=0) {
							callVO.temperature = reqVO.temperature;
						}else if(reqVO.top_p>=0) {
							callVO.topP = reqVO.top_p;
						}*/
						if(reqVO.thinking!==true){
							callVO.thinkingConfig={thinkingBudget: 0};// Disables thinking
						}
						return callVO;
					}
					case "Ollama":{
						let callVO;
						callVO={
							model: reqVO.model,
						};
						if(reqVO.response_format && reqVO.response_format!=="text"){
							callVO.format="json";
						}
						return callVO;
					}
				}
			}
		};
		
		//-------------------------------------------------------------------
		apiMap['AICall'] = async function (req, res, next) {
			return await AICall(plainCall, req, res, next);
		};

		//-------------------------------------------------------------------
		apiMap['AICallStream'] = async function (req, res, next) {
			return await AIStreamCall(plainCall, req, res, next);
		};
		
		//-------------------------------------------------------------------
		apiMap['AICalculateTokens'] = async function(req,res,next){
			let reqVO;
			let platform,messages;
			reqVO = req.body.vo;
			platform=reqVO.platform||"OpenAI";
			messages=reqVO.messages;
			switch(platform){
				default:
				case "OpenAI": {
					let totalNum,list=[];
					if(typeof(messages)==="string"){
						messages=[{role:"user",content:messages}];
					}
					totalNum=tokenForMessages(messages,list);
					res.json({code:200,tokens:totalNum,messageTokens:list});
					break;
				}
			}
			res.json({code:400,info:"Platform not supported."});
		};
		
		//-------------------------------------------------------------------
		apiMap['AIGetPlatforms'] = async function (req, res, next) {
			res.json({code:200,platforms:["OpenAI","Claude","Google","Ollama"]});
		
		};
		
		//-------------------------------------------------------------------
		apiMap['AIGetModels'] = async function (req, res, next) {
			let reqVO=req.body.vo;
			let platform,models;
			switch(reqVO.platform){
				case "Ollama":
					platform=AIPlatforms["Ollama"];
					models=Object.values(platform);
					//TODO: Call Ollama API to get models:
					break;
				default:
					platform=AIPlatforms[reqVO.platform];
					if(!platform){
						res.json({code:400,info:`Unknown platform: ${reqVO.platform}`});
						return;
					}
					models=Object.values(platform);
					break;
			}
			res.json({code:200,models:models});
			
		};
	}
	
	//***********************************************************************
	//Image related:
	//***********************************************************************
	if(openAI){
		let dataURLtoBuffer=function (dataUrl) {
			const matches = dataUrl.match(/^data:(.*?);base64,(.*)$/);
			if (!matches) return null;
			
			const [, mimeType, base64Data] = matches;
			const buffer = Buffer.from(base64Data, "base64");
			return { buffer, mimeType };
		}
		
		//-------------------------------------------------------------------
		apiMap['AIDraw']=async function (req,res,next){
			let reqVO,userInfo=null;
			let platform;
			let callVO, resVO;
			let orgImages;
			let prompt,model,img,size;
			reqVO = req.body.vo;
			
			if(getUserInfo) {
				let userId = reqVO.userId;
				let token = reqVO.token;
				userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
				if (!userInfo) {
					userInfo = await getPVUserInfo(req, USERINFO_PROJECTION);
					if (!userInfo) {
						res.json({ code: 403, info: "UserId/Token invalid." });
						return;
					}
				}
			}
			platform = reqVO.platform;
			model=reqVO.model||"gpt-image-1";
			prompt= reqVO.prompt;
			size=reqVO.size||"1024x1024";

			if(!platform){
				switch(model){
					case "dall-e-3":
						platform="OpenAI";
						break;
					case "dall-e-2":
						platform="OpenAI";
						break;
					case "gpt-image-1":
						platform="OpenAI";
						break;
					default:
						platform="OpenAI";
						break;
				}
			}
			
			//Check gas
			{
				resVO = await checkAITokenCall(userInfo, platform, model);
				if (resVO.code !== 200) {
					res.json(resVO);
					return;
				}
			}
			switch(platform){
				case "OpenAI":{
					callVO={
						model: model,
						prompt: prompt,
						n: reqVO.n||1,
						size: size,
						//response_format:"b64_json"
					};
					orgImages=reqVO.images||reqVO.image;
					if(orgImages){
						let i,n,images,stub;
						images=[];
						if(!Array.isArray(orgImages)){
							orgImages=[orgImages];
						}
						n=orgImages.length;
						for(i=0;i<n;i++){
							stub=dataURLtoBuffer(orgImages[i]);
							if(stub){
								if(stub.mimeType==="image/png"){
									images.push(await toFile(stub.buffer, `image${i}.png`, { type: stub.mimeType }))
								}else if(stub.mimeType==="image/jpeg" || stub.mimeType==="image/jpg"){
									images.push(await toFile(stub.buffer, `image${i}.jpg`, { type: stub.mimeType }))
								}
							}
						}
						if(images.length===1){
							orgImages=images[0];
						}else if(images.length>1){
							orgImages=images;
						}else{
							orgImages=null;
						}
					}
					if(reqVO.seed!==undefined){
						let seed=parseInt(reqVO.seed);
						if(seed>=0) {
							callVO.seed = seed;
						}
					}
					try {
						if(orgImages){
							let mask;
							callVO.image = orgImages;
							mask=reqVO.mask;
							if(mask){
								let stub=dataURLtoBuffer(mask);
								if(stub){
									if(stub.mimeType==="image/png"){
										mask=await toFile(stub.buffer, `mask.png`, { type: stub.mimeType });
										callVO.mask=mask;
									}
								}
							}
							const response = await openAI.images.edit(callVO);
							img = response.data[0].b64_json;
						}else {
							const response = await openAI.images.generate(callVO);
							img = response.data[0].b64_json;
						}
						resVO = { code: 200, img: img};
						res.json(resVO);
					}catch(error){
						if (error instanceof OpenAI.APIError) {
							console.error(error.status);  // e.g. 401
							console.error(error.message); // e.g. The authentication token you passed was invalid...
							console.error(error.code);  // e.g. 'invalid_api_key'
							console.error(error.type);  // e.g. 'invalid_request_error'
							res.json({code: error.status,info:`Error ${error.code}(error.type): ${error.message}`});
						} else {
							// Non-API error
							console.log(error);
							res.json({code: 500,info:`openAI.chat.completions.create error: ${""+error}`});
						}
						return;
					}
					//charge points by chat:
					chargePointsByChat(userInfo, prompt, "", platform, model);
					return;
				}
				default: {
					res.json({code: 400,info:`Platform: ${platform} not supported.`});
					return;
				}
			}
		};
		
		//-------------------------------------------------------------------
		apiMap['AIEditDraw']=async function (req,res,next){
			let reqVO, userInfo=null;
			let platform;
			let callVO, resVO;
			let prompt,model,img,size;
			let orgImg,mskImg;
			reqVO = req.body.vo;
			if(getUserInfo) {
				let userId = reqVO.userId;
				let token = reqVO.token;
				userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
				if (!userInfo) {
					userInfo = await getPVUserInfo(req, USERINFO_PROJECTION);
					if (!userInfo) {
						res.json({ code: 403, info: "UserId/Token invalid." });
						return;
					}
				}
			}
			platform = reqVO.platform || "OpenAI";//Only OpenAI supported by now.
			model=reqVO.model||"dall-e-2";
			prompt= reqVO.prompt;
			size=reqVO.size||"1024x1024";
			orgImg=reqVO.image;
			if(!orgImg){
				res.json({ code: 400, info: "Missing image to edit." });
				return;
			}
			mskImg=reqVO.mask;
			
			//Check gas
			{
				resVO = await checkAITokenCall(userInfo, platform, model);
				if (resVO.code !== 200) {
					res.json(resVO);
					return;
				}
			}
			callVO={
				model: model,
				image:orgImg,
				prompt: prompt,
				n: 1,
				size: size,
				response_format:"b64_json"
			};
			if(mskImg){
				callVO.mask=mskImg;
			}
			if(reqVO.seed!==undefined){
				let seed=parseInt(reqVO.seed);
				if(seed>=0) {
					callVO.seed = seed;
				}
			}
			const response = await openAI.createImageEdit(callVO);
			//console.log(response);
			//console.log(response.data.data[0].b64_json);
			img = response.data.data[0].b64_json;
			resVO={code: 200, img: img, revised_prompt:response.data.data[0].revised_prompt};
			res.json(resVO);
			//charge points by chat:
			chargePointsByChat(userInfo, prompt, "", platform, model);
		};

		//-------------------------------------------------------------------
		apiMap['AIDrawVariation']=async function (req,res,next){
			let reqVO,userInfo=null;
			let platform;
			let callVO, resVO;
			let model,orgImg,img,size;
			reqVO = req.body.vo;
			
			function createStreamFromBase64(base64String) {
				const buffer = Buffer.from(base64String, 'base64');
				return Readable.from(buffer);
			}

			if(getUserInfo) {
				let userId = reqVO.userId;
				let token = reqVO.token;
				userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
				if (!userInfo) {
					userInfo = await getPVUserInfo(req, USERINFO_PROJECTION);
					if (!userInfo) {
						res.json({ code: 403, info: "UserId/Token invalid." });
						return;
					}
				}
			}
			
			platform = reqVO.platform || "OpenAI";//Only OpenAI supported by now.
			model=reqVO.model||"dall-e-2";
			size=reqVO.size||"1024x1024";
			orgImg=reqVO.image;
			if(!orgImg){
				res.json({ code: 400, info: "Missing image to edit." });
				return;
			}
			{
				let pos=orgImg.indexOf("base64,");
				if(pos>=0){
					orgImg=orgImg.substring(pos+7);
				}
				orgImg=createStreamFromBase64(orgImg);
			}
			
			//Check gas
			{
				resVO = await checkAITokenCall(userInfo, platform, model);
				if (resVO.code !== 200) {
					res.json(resVO);
					return;
				}
			}
			callVO={
				model: model,
				image: orgImg,
				n: 1,
				size: size,
				response_format:"b64_json"
			};
			if(reqVO.seed!==undefined){
				let seed=parseInt(reqVO.seed);
				if(seed>=0) {
					callVO.seed = seed;
				}
			}

			const response = await openAI.createImageVariation(orgImg,1,size,"b64_json");
			//const response = await openAI.createImageVariation(orgImg,1);
			//console.log(response);
			//console.log(response.data.data[0].b64_json);
			img = response.data.data[0].b64_json;
			resVO={code: 200, img: img, revised_prompt:response.data.data[0].revised_prompt};
			res.json(resVO);
			//charge points by chat:
			chargePointsByChat(userInfo, "", "", platform, model);
		};
	}
	
	//***********************************************************************
	//Audio related:
	//***********************************************************************
	if(openAI){
		//-------------------------------------------------------------------
		apiMap['AITTS']=async function (req,res,next){
			let reqVO, userInfo=null;
			let platform;
			let callVO, rawResVO, resVO;
			let callDone,apiURL,httpOpts,postText,postAPI,httpReq;
			let inputText,model,mp3,voice;
			reqVO = req.body.vo;
			
			if(getUserInfo) {
				let userId = reqVO.userId;
				let token = reqVO.token;
				userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
				if (!userInfo) {
					userInfo = await getPVUserInfo(req, USERINFO_PROJECTION);
					if (!userInfo) {
						res.json({ code: 403, info: "UserId/Token invalid." });
						return;
					}
				}
			}
			platform = reqVO.platform || "OpenAI";//Only OpenAI supported by now.
			model=reqVO.model||"tts-1";
			inputText= reqVO.input||reqVO.text;
			voice= reqVO.voice||"alloy";
			
			//Check gas
			{
				resVO = await checkAITokenCall(userInfo, platform, model);
				if (resVO.code !== 200) {
					res.json(resVO);
					return;
				}
			}
			
			//charge points by chat:
			chargePointsByChat(userInfo, inputText, "", platform, model);

			{
				callDone=false;
				apiURL = "https://api.openai.com/v1/audio/speech";
				httpOpts = {
					method: "POST",
					headers: {
						"Authorization": `Bearer ${OPENAI_API_KEY}`,
						'User-Agent': 'node.js',
					}
				};
				postText=JSON.stringify({
					"model": model,
					"input": inputText,
					"voice": voice
				});
				httpOpts.headers['Content-Type']='application/json';
				httpOpts.headers['Content-Length']=Buffer.byteLength(postText);
				postAPI=followRedirects.https;
				httpReq = postAPI.request(apiURL, httpOpts, (response) => {
					let data = [];
					if (response.statusCode !== 200) {
						httpReq.destroy();
						res.json({ code: response.statusCode, info: response.statusMessage || "Network error" });
						callDone=true;
						return;
					}
					response.on('data', function (chunk) {
						data.push(chunk);
					});
					response.on('end', function () {
						try {
							let buffer = Buffer.concat(data);
							let text = buffer.toString("base64");
							callDone=true;
							res.json({code:200,mp3:text});
							//TODO: charge gas:
						} catch (err) {
							callDone=true;
							res.json({ code: 500, info: "" + err });
						}
					});
				});
				httpReq.on('error', (e) => {
					if(!callDone) {
						res.json({ code: 500, info: "" + e });
					}
				});
				if(postText) {
					httpReq.write(postText);
				}
				httpReq.end();
			}
		};
	}
	
	//***********************************************************************
	//Web API Call
	//***********************************************************************
	{
		apiMap['webAPICall']=async function(req,res,next){
			let reqVO, userInfo=null, resVO;
			let apiURL, httpOpts, httpReq, postText,callDone,postAPI,headers;
			reqVO = req.body.vo;
			if(getUserInfo) {
				let userId = reqVO.userId;
				let token = reqVO.token;
				if(!userId){
					res.json({ code: 403, info: "UserId/Token invalid." });
					return;
				}
				userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
				if (!userInfo) {
					userInfo = await getPVUserInfo(req, USERINFO_PROJECTION);
					if (!userInfo) {
						res.json({ code: 403, info: "UserId/Token invalid." });
						return;
					}
				}
			}
			{
				let bodyType;
				callDone=false;
				apiURL = reqVO.url;
				if(process.env["WEBCALL_"+apiURL]){
					apiURL=process.env["WEBCALL_"+apiURL];
				}
				httpOpts = {
					method: reqVO.method,
					headers: {
						'User-Agent': 'node.js',
					}
				};
				bodyType=reqVO.argMode;
				headers=reqVO.headers;
				switch(bodyType){
					case "JSON":
						postText=JSON.stringify(reqVO.json);
						httpOpts.headers['Content-Type']='application/json';
						httpOpts.headers['Content-Length']=Buffer.byteLength(postText);
						break;
					case "TEXT":
						postText=reqVO.data;
						httpOpts.headers['Content-Type']='text/plain';
						httpOpts.headers['Content-Length']=Buffer.byteLength(postText);
						break;
				}
				if(headers) {
					Object.assign(httpOpts.headers, headers);
				}
				if(apiURL.startsWith("http://")){
					postAPI=followRedirects.http;
				}else{
					postAPI=followRedirects.https;
				}
				httpReq = postAPI.request(apiURL, httpOpts, (response) => {
					let data = [];
					if (response.statusCode !== 200) {
						httpReq.destroy();
						res.json({ code: response.statusCode, info: response.statusMessage || "Network error" });
						callDone=true;
						return;
					}
					response.on('data', function (chunk) {
						data.push(chunk);
					});
					response.on('end', function () {
						try {
							let buffer = Buffer.concat(data);
							let text = buffer.toString();
							callDone=true;
							res.json({code:200,data:text});
						} catch (err) {
							callDone=true;
							res.json({ code: 500, info: "" + err });
						}
					});
				});
				httpReq.on('error', (e) => {
					if(!callDone) {
						res.json({ code: 500, info: "" + e });
					}
				});
				if(postText) {
					httpReq.write(postText);
				}
				httpReq.end();
			}
		};
		
		apiMap['WebFetch']=async function(req,res,next){
			let reqVO, userInfo=null, resVO,replaceKey;
			let apiURL, httpOpts, httpReq, postText,callDone,postAPI,headers;
			reqVO = req.body.vo;
			replaceKey=reqVO.replaceKey;
			if(typeof(replaceKey)==="string"){
				//TODO: Apply replaceKey
				/*
				let userId = reqVO.userId;
				let token = reqVO.token;
				if(!userId){
					res.json({ code: 403, info: "UserId/Token invalid." });
					return;
				}
				userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
				if (!userInfo) {
					userInfo= await getPVUserInfo(req,USERINFO_PROJECTION);
					if(!userInfo) {
						res.json({ code: 403, info: "UserId/Token invalid." });
						return;
					}
				}
				*/
			}
			{
				let result;
				result=await ApiProxy.proxy(req, res);
				if (result) {
					return;
				}
			}
			{
				let body;
				callDone=false;
				apiURL = reqVO.url;
				httpOpts = {
					method: reqVO.method,
					headers: {
						'User-Agent': 'node.js',
					}
				};
				headers=reqVO.headers;
				if(headers) {
					Object.assign(httpOpts.headers, headers);
				}
				body=reqVO.body;
				if(body) {
					body = Buffer.from(body, "base64");
					httpOpts.headers['Content-Length'] = ""+Buffer.byteLength(body);
				}else{
					httpOpts.headers['Content-Length'] = "0";
				}
				if(apiURL.startsWith("http://")){
					postAPI=followRedirects.http;
				}else{
					postAPI=followRedirects.https;
				}
				httpReq = postAPI.request(apiURL, httpOpts, (response) => {
					let data = [];
					let headers;
					headers=response.headers;
					if(headers["Content-Type"]){
						res.setHeader('Content-Type',headers["Content-Type"]);
					}
					response.on('data', function (chunk) {
						data.push(chunk);
					});
					response.on('end', function () {
						try {
							let buffer = Buffer.concat(data);
							res.status(response.statusCode);
							if(headers["Content-Type"]){
								res.setHeader('Content-Type',headers["Content-Type"]);
							}
							res.setHeader('Content-Length',""+Buffer.byteLength(buffer));
							res.send(buffer);
							res.end();
							callDone=true;
						} catch (err) {
							res.status(500);
							res.send(Buffer.from("Http fetch error" + err));
							res.end();
							callDone=true;
						}
					});
				});
				httpReq.on('error', (e) => {
					if(!callDone) {
						res.status(500);
						res.send(Buffer.from("Http fetch error" + e));
						res.end();
						callDone=true;
					}
				});
				if(body) {
					httpReq.write(body);
				}
				httpReq.end();
			}
		};
	}
};
