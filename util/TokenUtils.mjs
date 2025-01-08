import {encode} from "gpt-3-encoder";
import { getSysConfig } from './SysConfig.js'

let dbUser=null;
let app=null;
function setupTokenUtils(_app){
	app=_app;
	dbUser = app.get("DBUser");
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
function charForMessages(messages){
	let message,msgType,num_chars,key,value,num;
	num_chars=0;
	if(Array.isArray(messages)) {
		for (message of messages) {
			msgType=typeof(message);
			if(msgType==="string") {
				num_chars += message.length;
			}else if(msgType==="object"){
				for(key in message){
					
					value=message[key];
					if(value) {
						num = value.length;
					}else{
						num=0;
					}
					num_chars+=num;
					num_chars+=key.length;
				}
			}
		}
		return num_chars;
	}
	msgType=typeof(messages);
	if(msgType==="string"){
		return messages.length;
	}
	return 0;
}

//-----------------------------------------------------------------------
async function checkAITokenCall (userInfo, platform, model) {
	return {code:200};//Local AI2Apps instance.
}

//-----------------------------------------------------------------------
async function useAITokens (userInfo, platform, model, usageVO) {
	return {
		promptTokens: 0, completionTokens: 0,
		pendingPromptTokens: 0, pendingCompletionTokens: 0,
		pendingPromptChars: 0, pendingCompletionChars: 0,
		pointsUsed: 0,
		coinUsed: 0
	};
}

//-----------------------------------------------------------------------
async function chargePointsByChat (userInfo, messages, replay, platform, model) {
	//Do nothing
}

//-----------------------------------------------------------------------
async function chargePointsByUsage (userInfo, input_tokens, output_tokens, platform, model) {
	//Do nothing
}

export {setupTokenUtils,tokenForMessages,charForMessages,checkAITokenCall,useAITokens,chargePointsByChat,chargePointsByUsage};