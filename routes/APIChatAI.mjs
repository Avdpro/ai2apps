import { Configuration, OpenAIApi } from "openai";
import {encode} from "gpt-3-encoder";
import {proxyCall} from "../util/ProxyCall.js";

const OPENAI_API_KEY=process.env.OPENAI_API_KEY;
let configuration,openAI;
if(OPENAI_API_KEY && OPENAI_API_KEY!=="[YOUR OPENAI KEY]") {
	configuration = new Configuration({
		apiKey: OPENAI_API_KEY,
	});
	openAI = new OpenAIApi(configuration);
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
			let reqVO, streamId, streamVO, textRead, textGot, pms, functionCall;
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
			if(functionCall){
				textGot = JSON.stringify(functionCall);
			}else{
				textGot = streamVO.textGot;
			}
			textRead = streamVO.textRead;
			if (textRead !== textGot || streamVO.closed) {
				if(functionCall){
					res.json({ code: 200, message: textGot, closed: streamVO.closed, functionCall: functionCall});
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
			streamVO.textRead = streamVO.textGot;
			res.json({ code: 200, message: textGot, closed: streamVO.closed });
		};
		
		//-------------------------------------------------------------------
		let AIStreamCall = async function (callAIObj, req, res) {
			let reqVO, needRawResponse;
			let platform;
			let callVO, rawResVO, resVO;
			reqVO = req.body.vo;
			needRawResponse = !!reqVO.rawResponse;
			
			platform = reqVO.platform || "OpenAI";//Only OpenAI supported.
			//Make AI-Call:
			switch (platform) {
				case "OpenAI": {
					callVO = callAIObj.buildCallVO(reqVO);
					
					try {
						let streamVO, streamId;
						callVO.stream = true;
						console.log("Call Code VO:");
						console.log(callVO);
						rawResVO = await openAI.createChatCompletion(callVO, { responseType: 'stream' });
						if (rawResVO.status !== 200) {
							throw rawResVO;
						}
						
						streamId = getStreamId();
						streamVO = {
							streamId,
							textGot: "",
							textRead: "",
							closed: false,
							waitFunc: null,
							errorFunc: null,
							timer: null
						}
						streamVO.timer = setTimeout(() => {shutdownStream(streamId)}, 20000);
						rawResVO.data.on('data', (data) => {
							let txtData;
							let pts, pos, choices, choice0, delta, content, func, funcCall;
							txtData = data.toString().trim();
							//console.log(JSON.stringify(txtData));
							//console.log(rawResVO);
							clearTimeout(streamVO.timer);
							pts = txtData.split("\n\n");
							for (txtData of pts) {
								if (txtData.endsWith("[DONE]")) {
									let func;
									streamVO.closed = true;
									func = streamVO.waitFunc;
									if (func) {
										streamVO.waitFunc = null;
										func();
									}
								} else {
									pos = txtData.indexOf("{");
									if (pos > 0) {
										txtData = txtData.substring(pos);
										try {
											data = JSON.parse(txtData);
											choices = data.choices;
											if (choices) {
												choice0 = choices[0];
												if (choice0) {
													delta = choice0.delta;
													if (delta) {
														content = delta.content;
														if (content) {
															streamVO.textGot += content;
														}
														funcCall=delta.function_call;
														if(funcCall){
															let stub,name,args;
															stub=streamVO.functionCall;
															if(!stub){
																stub=streamVO.functionCall={name:"",arguments:""};
															}
															name=funcCall.name;
															args=funcCall["arguments"];
															if(name){
																stub.name+=funcCall.name;
															}
															if(args){
																stub["arguments"]+=args;
															}
														}
													}
												}
											}
										}catch(err){
											console.log("Error parse stream: ");
											console.log(txtData);
										}
									}
								}
								if (streamVO.textGot !== streamVO.textRead) {
									func = streamVO.waitFunc;
									if (func) {
										streamVO.waitFunc = null;
										func();
									}
								}
							}
							streamVO.timer = setTimeout(() => {shutdownStream(streamId)}, 20000);
						});
						resVO = { code: 200, streamId: streamId };
						streamMap.set(streamId, streamVO);
						if (needRawResponse) {
							resVO.rawResponse = rawResVO;
						}
						res.json(resVO);
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
				if(reqVO.functions){
					callVO.functions=reqVO.functions;
					callVO.function_call=reqVO.function_call||"auto";
				}
				return callVO;
			}
		};
		
		//-------------------------------------------------------------------
		apiMap['AICallStream'] = async function (req, res, next) {
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
	}else{
		//-------------------------------------------------------------------
		apiMap['checkAICallStatus'] = proxyCall;
		apiMap['readAIChatStream'] = proxyCall;
		apiMap['AICallStream'] = proxyCall;
		apiMap['AICalculateTokens'] = proxyCall;
	}
	
};