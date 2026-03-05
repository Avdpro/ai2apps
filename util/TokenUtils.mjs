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
	let billCfg,modelCfg,platformCfg,callCost;
	if(platform==="OpenRouter"){
		callCost=100;
		if(!userInfo || userInfo.points>=callCost){
			return {code:200};
		}
		return {
			code: 401,
			info: `Not enough gas. You need at least ${callCost} gas to initial this AI Call`,
			infoCN: `活力不足，至少需要${callCost}能量才能发起本次AI调用`
		};
	}
	billCfg = await getSysConfig("AI-API-TO-GAS");
	if(!billCfg){
		return {code:200};//Local AI2Apps instance.
	}
	model = model.replaceAll(".", "_");
	if (!billCfg) {
		return {code:500,info:"Can't read system bill info"};
	}
	platformCfg = billCfg[platform];
	if (!platformCfg) {
		return {code:400,info:"Can't find platform: "+platform};
	}
	modelCfg = platformCfg[model];
	if (!modelCfg) {
		return {code:400,info:"Can't find model: "+model};
	}
	callCost=modelCfg.call||0;
	if(callCost && callCost.gas>0){
		callCost=callCost.gas||0;
	}else{
		callCost=0;
	}
	callCost+=10;
	if (userInfo.points < callCost) {
		return {
			code: 401,
			info: `Not enough gas. You need at least ${callCost} gas to initial this AI Call`,
			infoCN: `活力不足，至少需要${callCost}能量才能发起本次AI调用`
		}
	}
	return { code: 200 };
}

//-----------------------------------------------------------------------
async function useAITokens (userInfo, platform, model, usageVO) {
	let billCfg, platformCfg, modelCfg, saveVO;
	let usedPromptTokens, usedCompletionTokens,usedPromptChars,usedCompletionChars;
	let userUsage, platformUsage, modelUsage, pmtTokens, cmpTokens,pmtChars,cmpChars;
	let batch, ptsUsed, pmtTokenDec, cmpTokenDec, pmtCharDec, cmpCharDec;
	let usedCost, gasByCost;
	
	if(!userInfo || !dbUser){
		return;
	}
	model = model.replaceAll(".", "_");
	switch (platform) {
		case "OpenAI":
		case "OpenRouter":
			usedPromptTokens = usageVO.prompt_tokens||0;
			usedPromptChars = usageVO.prompt_chars||0;
			usedCompletionTokens = usageVO.completion_tokens||0;
			usedCompletionChars = usageVO.completion_chars||0;
			break;
		case "Claude":
			usedPromptTokens = usageVO.prompt_tokens||0;
			usedPromptChars = usageVO.prompt_chars||0;
			usedCompletionTokens = usageVO.completion_tokens||0;
			usedCompletionChars = usageVO.completion_chars||0;
			break;
		case "Google":
			usedPromptTokens = usageVO.prompt_tokens||0;
			usedPromptChars = usageVO.prompt_chars||0;
			usedCompletionTokens = usageVO.completion_tokens||0;
			usedCompletionChars = usageVO.completion_chars||0;
			break;
	}
	usedCost=usageVO.cost;
	usedCost=Number(usedCost);
	if(!Number.isFinite(usedCost) || usedCost<0){
		usedCost=0;
	}
	saveVO = {}
	saveVO.$inc = {};
	saveVO.$inc[`AIUsage.${platform}.${model}.call`] = 1;
	if(usedPromptChars>0) {
		saveVO.$inc[`AIUsage.${platform}.${model}.promptChar`] = usedPromptChars;
		saveVO.$inc[`totalAIUsage.${platform}.${model}.promptChar`] = usedPromptChars;
		saveVO.$inc[`todayAIUsage.${platform}.${model}.promptChar`] = usedPromptChars;
	}
	if(usedCompletionChars>0){
		saveVO.$inc[`AIUsage.${platform}.${model}.completionChar`] = usedCompletionChars;
		saveVO.$inc[`totalAIUsage.${platform}.${model}.completionChar`] = usedCompletionChars;
		saveVO.$inc[`todayAIUsage.${platform}.${model}.completionChar`] = usedCompletionChars;
	}
	if(usedPromptTokens>0) {
		saveVO.$inc[`AIUsage.${platform}.${model}.prompt`] = usedPromptTokens;
		saveVO.$inc[`totalAIUsage.${platform}.${model}.prompt`] = usedPromptTokens;
		saveVO.$inc[`todayAIUsage.${platform}.${model}.prompt`] = usedPromptTokens;
	}
	if(usedCompletionTokens>0) {
		saveVO.$inc[`AIUsage.${platform}.${model}.completion`] = usedCompletionTokens;
		saveVO.$inc[`totalAIUsage.${platform}.${model}.completion`] = usedCompletionTokens;
		saveVO.$inc[`todayAIUsage.${platform}.${model}.completion`] = usedCompletionTokens;
	}
	if(usedCost>0){
		saveVO.$inc[`AIUsage.${platform}.${model}.cost`] = usedCost;
		saveVO.$inc[`totalAIUsage.${platform}.${model}.cost`] = usedCost;
		saveVO.$inc[`todayAIUsage.${platform}.${model}.cost`] = usedCost;
	}
	await dbUser.updateOne({ _id: userInfo._id }, saveVO);
	if(platform==="OpenRouter"){
		gasByCost=Math.ceil(usedCost/0.001);
		if(gasByCost>0){
			saveVO = {$inc:{points:-gasByCost}};
			await dbUser.updateOne({ _id: userInfo._id }, saveVO);
			userInfo.points -= gasByCost;
		}
		return {
			promptTokens: usedPromptTokens, completionTokens: usedCompletionTokens,
			pendingPromptTokens: 0, pendingCompletionTokens: 0,
			pendingPromptChars: 0, pendingCompletionChars: 0,
			pointsUsed: gasByCost||0,
			cost: usedCost||0,
			coinUsed: 0
		};
	}
	billCfg = await getSysConfig("AI-API-TO-GAS");
	if (!billCfg) {
		return;
	}
	platformCfg = billCfg[platform];
	if (!platformCfg) {
		return;
	}
	modelCfg = platformCfg[model];
	if (!modelCfg) {
		return;
	}
	userUsage = userInfo.AIUsage;
	if (!userUsage) {
		return null;
	}
	platformUsage = userUsage[platform];
	if (!platformUsage) {
		return null;
	}
	modelUsage = platformUsage[model];
	if (!modelUsage) {
		return null;
	}
	modelUsage.promptChar+=usedPromptChars;
	modelUsage.completionChar+=usedCompletionChars;
	modelUsage.prompt += usedPromptTokens;
	modelUsage.completion += usedCompletionTokens;
	pmtTokens = modelUsage.prompt||0;
	pmtChars=modelUsage.promptChar||0;
	cmpChars=modelUsage.completionChar||0;
	cmpTokens = modelUsage.completion||0;
	ptsUsed = 0;
	if (modelCfg.call && modelCfg.call.count===1) {
		ptsUsed += modelCfg.call.gas;
	}
	if (modelCfg.prompt && modelCfg.prompt.count > 0) {
		batch = Math.floor(pmtTokens / modelCfg.prompt.count);
		if (batch > 0) {
			ptsUsed += modelCfg.prompt.gas * batch;
			pmtTokenDec = batch * modelCfg.prompt.count;
			pmtTokens -= pmtTokenDec;
		}
	}
	if (modelCfg.prompt && modelCfg.prompt.char > 0) {
		batch = Math.floor(pmtChars / modelCfg.prompt.char);
		if (batch > 0) {
			ptsUsed += modelCfg.prompt.gas * batch;
			pmtCharDec = batch * modelCfg.prompt.char;
			pmtChars -= pmtTokenDec;
		}
	}
	if (modelCfg.completion && modelCfg.completion.count > 0) {
		batch = Math.floor(cmpTokens / modelCfg.completion.count);
		if (batch > 0) {
			ptsUsed += modelCfg.completion.gas * batch;
			cmpTokenDec = batch * modelCfg.completion.count;
			cmpTokens -= cmpTokenDec;
		}
	}
	if (modelCfg.completion && modelCfg.completion.char > 0) {
		batch = Math.floor(cmpChars / modelCfg.completion.char);
		if (batch > 0) {
			ptsUsed += modelCfg.completion.gas * batch;
			cmpCharDec = batch * modelCfg.completion.char;
			cmpChars -= cmpCharDec;
		}
	}
	if (ptsUsed > 0) {
		saveVO = {}
		saveVO.$inc = {};
		saveVO.$inc[`points`] = -ptsUsed;
		if (pmtTokenDec > 0) {
			saveVO.$inc[`AIUsage.${platform}.${model}.prompt`] = -pmtTokenDec;
		}
		if (cmpTokenDec > 0) {
			saveVO.$inc[`AIUsage.${platform}.${model}.completion`] = -cmpTokenDec;
		}
		if (pmtCharDec > 0) {
			saveVO.$inc[`AIUsage.${platform}.${model}.promptChar`] = -pmtCharDec;
		}
		if (cmpCharDec > 0) {
			saveVO.$inc[`AIUsage.${platform}.${model}.completionChar`] = -cmpCharDec;
		}
		dbUser.updateOne({ _id: userInfo._id }, saveVO);
		userInfo.points -= ptsUsed;
	}
	return {
		promptTokens: usedPromptTokens, completionTokens: usedCompletionTokens,
		pendingPromptTokens: pmtTokens, pendingCompletionTokens: cmpTokens,
		pendingPromptChars: pmtChars, pendingCompletionChars: cmpChars,
		pointsUsed: ptsUsed,
		coinUsed: 0
	};
}

//-----------------------------------------------------------------------
async function chargePointsByChat (userInfo, messages, replay, platform, model) {
	let usage = {};
	try {
		usage.prompt_tokens = tokenForMessages(messages);
		usage.prompt_chars=charForMessages(messages);
		usage.completion_tokens = replay?encode(replay).length + 3:0;
		usage.completion_chars=replay.length;
		await useAITokens(userInfo, platform, model, usage);
	}catch(err){
		console.error("token error:"+err);
		console.error("messages:"+messages);
		console.error("replay:"+replay);
	}
}

//-----------------------------------------------------------------------
async function chargePointsByUsage (userInfo, input_tokens, output_tokens, platform, model, cost) {
	let usage = {};
	try {
		usage.prompt_tokens = input_tokens;
		usage.prompt_chars=0;
		usage.completion_tokens = output_tokens;
		usage.completion_chars=0;
		usage.cost=cost;
		await useAITokens(userInfo, platform, model, usage);
	}catch(err){
		console.error("token error:"+err);
	}
}

export {setupTokenUtils,tokenForMessages,charForMessages,checkAITokenCall,useAITokens,chargePointsByChat,chargePointsByUsage};
