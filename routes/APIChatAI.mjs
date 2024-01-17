import OpenAI from "openai";
import {encode} from "gpt-3-encoder";
import {proxyCall} from "../util/ProxyCall.js";
import { Readable } from "stream"
import followRedirects from "follow-redirects";

const OPENAI_API_KEY=process.env.OPENAI_API_KEY;
let openAI;
if(OPENAI_API_KEY && OPENAI_API_KEY!=="[YOUR OPENAI KEY]") {
	openAI = new OpenAI({
		apiKey:OPENAI_API_KEY,
	});
}else{
	openAI=null;
}
const streamMap=new Map();
let nextStreamId=0;

//---------------------------------------------------------------------------
function getStreamId(){
	nextStreamId++;
	return "STREAM_"+nextStreamId;
}

//---------------------------------------------------------------------------
function shutdownStream(streamId){
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
}


//---------------------------------------------------------------------------
function tokenForMessages(messages,list){
	let message,num_tokens,num,curMsgNum;
	const token_per_message=4;
	let key,value;
	num_tokens=0;
	for(message of messages){
		num_tokens+=token_per_message;
		curMsgNum=token_per_message;
		for(key in message){
			value=message[key];
			if(value) {
				num = encode(""+value).length;
			}else{
				num=0;
			}
			num+=key.length;
			num_tokens+=num;
			curMsgNum+=num;
		}
		if(list){
			list.push(curMsgNum);
		}
	}
	return num_tokens;
}

//---------------------------------------------------------------------------
//API for AI calls
export default function(app,router,apiMap) {
	
	//-----------------------------------------------------------------------
	async function getUserInfo (req, userId, token, projection) {
		return null;
	}
	
	//-----------------------------------------------------------------------
	async function checkAITokenCall (userInfo, platform, model) {
		return { code: 200 };
	}

	//-----------------------------------------------------------------------
	async function useAITokens (userInfo, platform, model, usageVO) {
		return null;
	}
	
	//-----------------------------------------------------------------------
	async function chargePointsByChat (userInfo, messages, replay, platform, model) {
		return;
	}
	
	//***********************************************************************
	//Basic AI Calls:
	//***********************************************************************
	if(openAI){
		//-------------------------------------------------------------------
		apiMap['checkAICallStatus']=async function(req,res,next){
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
				res.json({ code: -101, info: "Missing stream obj." });
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
			if (textRead !== textGot || streamVO.closed) {
				if(functionCall){
					res.json({ code: 200, message: textGot, closed: streamVO.closed, functionCall: functionCall});
				}else if(toolCalls){
					res.json({ code: 200, message: textGot, closed: streamVO.closed, toolCalls: toolCalls});
				}else {
					res.json({ code: 200, message: textGot, closed: streamVO.closed });
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
			res.json({ code: 200, message: textGot, closed: streamVO.closed });
		};
		
		//-------------------------------------------------------------------
		let AICall = async function (callAIObj, req, res) {
			let reqVO;
			let platform;
			let callVO, rawResVO, resVO;
			reqVO = req.body.vo;
			
			platform = reqVO.platform || "OpenAI";//Only OpenAI supported by now.
			//Make AI-Call:
			switch (platform) {
				case "OpenAI": {
					callVO = callAIObj.buildCallVO(reqVO);
					console.log(callVO);
					//Check gas
					{
						resVO = await checkAITokenCall(null, platform, callVO.model);
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
						resVO = { code: 200,message:content};
						res.json(resVO);
						
						//Charge user token:
						chargePointsByChat(null, callVO.messages, content, platform, callVO.model);
					} catch (err) {
						console.log(err);
					}
					return;
				}
				default: {
					res.json({ code: 405, info: `Platform ${platform} is not supported.` });
					return;
				}
			}
		};
		
		//-------------------------------------------------------------------
		let AIStreamCall = async function (callAIObj, req, res) {
			let reqVO, needRawResponse;
			let platform;
			let callVO, rawResVO, resVO;
			reqVO = req.body.vo;
			needRawResponse = !!reqVO.rawResponse;
			
			platform = reqVO.platform || "OpenAI";//Only OpenAI supported by now.
			//Make AI-Call:
			switch (platform) {
				case "OpenAI": {
					callVO = callAIObj.buildCallVO(reqVO);
					//console.log(callVO);
					//Check gas
					{
						resVO = await checkAITokenCall(null, platform, callVO.model);
						if (resVO.code !== 200) {
							res.json(resVO);
							return;
						}
					}
					
					try {
						let streamVO, streamId,chatStream;
						let dataLeft="";
						callVO.stream = true;
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
							let choice0,delta,content,funcCall,toolCalls,func;
							for await (const part of chatStream) {
								choice0=part.choices[0];
								//console.log(choice0);
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
							func = streamVO.waitFunc;
							if (func) {
								streamVO.waitFunc = null;
								func();
							}
							//console.log("Fin: "+streamVO.content);
							//charge points by chat:
							chargePointsByChat(null, callVO.messages, streamVO.content, platform, callVO.model);
						}
					} catch (err) {
						console.log(err);
						throw err;
					}
					return;
				}
				default: {
					res.json({ code: 405, info: `Platform ${platform} is no supported.` });
					return;
				}
			}
		};
		
		//-------------------------------------------------------------------
		let plainCall = {
			buildCallVO (reqVO) {
				let callVO = {
					model: reqVO.model || "gpt-3.5-turbo",
					temperature: reqVO.temperature || 0.7,
					max_tokens: reqVO.max_tokens || 3092,
					top_p: reqVO.top_p || 1,
					n: reqVO.best_of || reqVO.n || 1,
					frequency_penalty: reqVO.frequency_penalty || 0,
					presence_penalty: reqVO.presence_penalty || 0,
					messages: reqVO.messages,
				};
				if(reqVO.response_format && reqVO.response_format!=="text"){
					callVO.response_format={type:reqVO.response_format};
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
		};
		
		//-------------------------------------------------------------------
		apiMap['AICall'] = async function (req, res, next) {
			return await AICall(plainCall, req, res);
		};

		//-------------------------------------------------------------------
		apiMap['AICallStream'] = async function (req, res, next) {
			let reqVO = req.body.vo;
			if(reqVO.model==="gpt-4-32k"){
				//TODO: 1. Build callVO that match your API:
				let callVO = await Make_YOUR_LLM_CALL_VO(reqVO);
				//TODO: 2. Call your own LLM API:
				let result= await YOUR_WON_LLM_API(callVO);
				//TODO: 2. add a call stream
				let streamId = getStreamId();
				let streamVO = {
					streamId,
					textGot: result,
					textRead: "",
					closed: true,
					waitFunc: null,
					errorFunc: null,
					timer: null
				};
				streamMap.set(streamId, streamVO);
				//Response client:
				let resVO = { code: 200, streamId: streamId };
				res.json(resVO);
				return;
			}
			return await AIStreamCall(plainCall, req, res);
		};
		
		//-------------------------------------------------------------------
		apiMap['AICalculateTokens'] = async function(req,res,next){
			let reqVO;
			let platform,messages;
			reqVO = req.body.vo;
			platform=reqVO.platform||"OpenAI";
			messages=reqVO.messages;
			switch(platform){
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
			
		};
		
		//-------------------------------------------------------------------
		apiMap['AIDraw']=async function (req,res,next){
			let reqVO;
			let platform;
			let callVO, resVO;
			let prompt,model,img,size;
			reqVO = req.body.vo;
			
			platform = reqVO.platform;
			model=reqVO.model||"dall-e-3";
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
					default:
						platform="OpenAI";
						break;
				}
			}
			
			//Check gas
			{
				resVO = await checkAITokenCall(null, platform, model);
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
					try {
						const response = await openAI.images.generate(callVO);
						img = response.data[0].b64_json;
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
					chargePointsByChat(null, prompt, "", platform, model);
					return;
				}
				default: {
					res.json({code: 400,info:`Platform: ${platform} not supported.`});
					return;
				}
			}
		};
		
		//-------------------------------------------------------------------
		apiMap['AITTS']=async function (req,res,next){
			let reqVO;
			let platform;
			let callDone,apiURL,httpOpts,postText,postAPI,httpReq;
			let inputText,model,mp3,voice;
			reqVO = req.body.vo;
			
			platform = reqVO.platform || "OpenAI";//Only OpenAI supported by now.
			model=reqVO.model||"tts-1";
			inputText= reqVO.input||reqVO.text;
			voice= reqVO.voice||"alloy";
			
			//Here we use plain Http call:
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
			let reqVO;
			let apiURL, httpOpts, httpReq, postText,callDone,postAPI,headers;
			reqVO = req.body.vo;
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
			let reqVO;
			let apiURL, httpOpts, httpReq, postText,callDone,postAPI,headers;
			reqVO = req.body.vo;
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
					httpReq.send(body);
				}
				httpReq.end();
			}
		};
	}
};
