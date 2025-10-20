import {GoogleGenAI} from '@google/genai';
import OpenAI from "openai";
import { toFile } from "openai/uploads";
import fsp from "fs/promises";
import pathLib from "path";
import ProxyCall from '../util/ProxyCall.js';
const { callProxy,proxyCall }=ProxyCall;
import {getUserInfo,getPVUserInfo} from "../util/UserUtils.js";
import ApiProxy from "../apiproxy/FetchProxy.mjs";
import invokeApi from '../util/InvokeApi.mjs'

let GoogleAIKey=process.env.GOOGLEAI_API_KEY;
let GoogleAI=null;
if(GoogleAIKey){
	GoogleAI = new GoogleGenAI({
		apiKey: GoogleAIKey,
	});
}

let OpenAIKey = process.env.OPENAI_API_KEY;
let OpenAIClient = null;
if (OpenAIKey) {
	OpenAIClient = new OpenAI({ apiKey: OpenAIKey });
}
const AIPlatforms={
	"Google":{},
	"OpenAI":{}
};

//Try load token utils:

function getBase64FromDataUrl(str) {
	if (typeof str !== 'string' || !str.startsWith('data:')) return str;
	const commaIndex = str.indexOf(',');
	return commaIndex !== -1 ? str.slice(commaIndex + 1) : str;
}
//----------------------------------------------------------------------------
let APITiPainter=async function(app,router,apiMap) {
	let getUserInfo,checkAITokenCall,chargePointsByUsage;
	try{
		let m=await import("../util/TokenUtils.mjs");
		checkAITokenCall=m.checkAITokenCall;
		chargePointsByUsage=m.chargePointsByUsage;
	}catch(err){
		//do nothing
		checkAITokenCall=function(){return {code:200};};
		chargePointsByUsage=function(){}
	}
	try{
		let m=await import("../util/UserUtils.js");
		getUserInfo=m.getUserInfo;
	}catch(err){
		getUserInfo=null;
	}

	const DBUsers = app.get("DBUser");
	let admins = process.env.AF_ADMINS || "10000";
	admins = new Set(admins.split(","));
	
	const USERINFO_PROJECTION={rank:1,rankExpire:1,points:1,coins:1,token:1,tokenExpire:1,lastLogin:1,tokens:1,AIUsage:1};

	//-----------------------------------------------------------------------
	apiMap["TiDraw"] = async function (req, res,next) {
		let reqVO=req.body.vo;
		let userId,token,userInfo;
		let platform=reqVO.platform||"Google";
		let model,resVO;

		if(getUserInfo) {
			userInfo = await getUserInfo(req, null, null, USERINFO_PROJECTION);
			if (!userInfo) {
				userInfo = await getPVUserInfo(req, USERINFO_PROJECTION);
				if (!userInfo) {
					res.json({ code: 403, info: "UserId/Token invalid." });
					return;
				}
			}
		}
		
		switch (platform){
			case "OpenAI": {
				// 若服务端未配置 OPENAI_API_KEY，则走你的代理兜底
				if (!OpenAIClient) {
					await proxyCall(req, res, next);
					return;
				}
				model=reqVO.model||"gpt-image-1";

				//Check gas
				resVO = await checkAITokenCall(userInfo, platform, model);
				if (resVO.code !== 200) {
					res.json({ code: 401, info: "Gas is not enough to make AICall." });
					return;
				}

				try {
					const images = reqVO.images;
					const promptText = reqVO.prompt || "";
					const size = reqVO.size || "1024x1024"; // 可按需透传 256x256 / 512x512 / 1024x1024
					const fidelity=reqVO.fidelity;
					const quality=reqVO.quality;
					
					let dataUrl = null;
					let textOutput = "";
					
					
					if (images && images.length > 0) {
						let i,n,editImages;
						// 图生图 / 编辑路径：使用 images.edits
						// 约定：images[0] 为要编辑的底图（PNG/JPEG 的 dataURL 均可）
						// 可选：reqVO.mask（PNG dataURL，透明区域为“保留原图”，不透明区域为“编辑区域”）
						editImages=[];
						n=images.length;
						for(i=0;i<n;i++){
							const imageB64 = getBase64FromDataUrl(images[0]);
							const imageFile = await toFile(
								Buffer.from(imageB64, "base64"),
								"input.png",
								{ contentType: "image/png" }
							);
							editImages.push(imageFile);
						}
						
						let maskFile = undefined;
						if (reqVO.mask) {
							const maskB64 = getBase64FromDataUrl(reqVO.mask);
							maskFile = await toFile(
								Buffer.from(maskB64, "base64"),
								"mask.png",
								{ contentType: "image/png" }
							);
						}
						let callVo={
							model: model,
							image: editImages,
							...(maskFile ? { mask: maskFile } : {}),
							prompt: promptText,
							size,
							input_fidelity:fidelity||"low",
							quality:quality||"medium",
							// n: 1, // 需要多张时可放开
						};
						if(reqVO.background==="transparent"){
							callVo.background="transparent";
						}
						const resp = await OpenAIClient.images.edit(callVo);
						
						const b64 = resp?.data?.[0]?.b64_json;
						if (b64) dataUrl = "data:image/png;base64," + b64;
						// OpenAI 的 Images API 通常无额外文本输出，这里留空字符串与 Google 对齐
					} else {
						// 纯文生图：使用 images.generate
						let callVo={
							model: "gpt-image-1",
							prompt: promptText,
							size,
							quality:quality||"medium",
						}
						if(reqVO.background==="transparent"){
							callVo.background="transparent";
						}
						const resp = await OpenAIClient.images.generate(callVo);
						const b64 = resp?.data?.[0]?.b64_json;
						if (b64) dataUrl = "data:image/png;base64," + b64;
					}
					
					//Charge gas:
					chargePointsByUsage(userInfo,0,0,platform,model);
					
					if (dataUrl) {
						res.json({ code: 200, image: dataUrl, text: textOutput });
						return;
					}
					res.json({ code: 500, info: "OpenAI: output missing image data." });
				} catch (err) {
					console.error("OpenAI-draw error:", err);
					res.json({ code: 500, info: "OpenAI draw failed: "+String(err?.message || err), error: String(err?.message || err) });
				}
				break;
			}
			case "Google": {
				let images,imgData,aspect,callVo;
				if(!GoogleAI){
					await proxyCall(req,res,next);
					return;
				}
				model=reqVO.model||"gemini-2.5-flash-image";
				aspect=reqVO.aspect;
				
				//Check gas:
				resVO = await checkAITokenCall(userInfo, platform, model);
				if (resVO.code !== 200) {
					res.json({ code: 401, info: "Gas is not enough to make AICall." });
					return;
				}
				
				const prompt = [
				];
				images=reqVO.images;
				if(images && images.length>0){
					for(imgData of images) {
						prompt.push({
							inlineData: {
								mimeType: "image/png",
								data: getBase64FromDataUrl(imgData),
							},
						});
					}
				}
				prompt.push({ text: reqVO.prompt });
				callVo={
					model: model,
					contents: prompt,
				};
				if(aspect){
					callVo.config={
						imageConfig: {
							aspectRatio: aspect,
						}
					};
				}
				const response = await GoogleAI.models.generateContent(callVo);
				console.log("Google-draw result: ",response);
				let textOutput=[];
				let imageData,dataUrl;
				for (const part of response.candidates[0].content.parts) {
					if (part.text) {
						textOutput.push(part.text);
					} else if (part.inlineData && !imageData) {
						imageData = part.inlineData.data;
						dataUrl="data:image/png;base64,"+imageData;
					}
				}
				textOutput=textOutput.join("\n");
				let tokenUsage=response.usageMetadata;
				if(tokenUsage){
					let inputTokens=tokenUsage.promptTokenCount||0;
					let outputTokens=(tokenUsage.candidatesTokenCount||0)+(tokenUsage.thoughtsTokenCount||0);
					chargePointsByUsage(userInfo,inputTokens,outputTokens,platform,model);
				}else{
					chargePointsByUsage(userInfo,0,0,platform,model);
				}
				if(dataUrl){
					res.json({code:200,image:dataUrl,text:textOutput});
					return;
				}
				res.json({code:500,info:"Can't find image data from AI output: "+(textOutput?textOutput:"missing image data.")});
				break;
			}
		}
	};
};

export default APITiPainter;
export{APITiPainter};
