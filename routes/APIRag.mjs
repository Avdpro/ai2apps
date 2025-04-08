import {getUserInfo,getPVUserInfo} from "../util/UserUtils.js";
import pathLib from "path";
import { checkAITokenCall } from '../util/TokenUtils.mjs'
import ProxyCall from '../util/ProxyCall.js'
const { callProxy,proxyCall }=ProxyCall;

const APIRoot=process.env.APIROOT;
const RagServerAddr=process.env.RAG_API;
const IsRagRoot=process.env.RAG_Root==="TRUE";
const USERINFO_PROJECTION={email:1,rank:1,rankExpire:1,points:1,coins:1,token:1,tokenExpire:1,lastLogin:1,tokens:1,AIUsage:1};
let masterEmails=process.env.RAGMasters;
if(masterEmails){
	try{
		masterEmails=JSON.parse(masterEmails);
		if(!Array.isArray(masterEmails)){
			masterEmails=null;
		}
	}catch (err){
		masterEmails=null;
	}
}else{
	masterEmails=null;
}

export default async function(app,router,apiMap) {
	
	//-----------------------------------------------------------------------
	apiMap['RagIndexPrjSetup'] = async function (req, res, next) {
		let reqVO, userInfo, resVO,isMaster;
		let userId, token,apiAddress,userEmail;
		let indexMeta,postToRoot,ragBase;
		
		if(!RagServerAddr){//Use proxy-call for upper API
			await proxyCall(req,res,next);
			return;
		}
		
		reqVO = req.body.vo;
		userId = reqVO.userId;
		token = reqVO.token;
		
		indexMeta=reqVO.index;
		apiAddress=reqVO.apiURL;
		postToRoot=reqVO.postToRoot;
		
		if(postToRoot && APIRoot){
			await proxyCall(req,res,next);
			return;
		}
		if(!IsRagRoot){
			userInfo=await callProxy("userLogin",{userId:userId,token:token});
			if(userInfo.code!==200){
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}else {
			if (!userId) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
			userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
			if (!userInfo) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}
		if(!apiAddress) {
			apiAddress=RagServerAddr;
		}
		userEmail=userInfo.email;
		if(masterEmails){
			isMaster = masterEmails.indexOf(userEmail) >= 0;
		}else {
			isMaster = (userInfo.rank === "MASTER") || (userInfo.rank === "LORD");
		}
		if (!isMaster) {
			res.json({ code: 403, info: "User rank invalid." });
			return;
		}
		

		if(!apiAddress) {
			res.json({ code: 500, info: "No RAG service." });
			return;
		}
		
		try{
			const response = await fetch(apiAddress+"/solution/index", {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(indexMeta),
			});
			if (response.status !== 200 && response.status !== 201) {
				res.json({ code: response.status, info: `HTTP error! Status: ${response.status}` });
				return;
			}
		} catch (error) {
			res.json({ code: 500, info: `RAG-Index internal error: ${error}` });
			return;
		}
		res.json({ code: 200, info: "Index done." });
	};
	
	//-----------------------------------------------------------------------
	apiMap['RagQueryPrjSetup'] = async function (req, res, next) {
		let reqVO, userInfo, resVO,isMaster;
		let userId, token,apiAddress;
		let queryMeta;
		
		if(!RagServerAddr){//Use proxy-call for upper API
			await proxyCall(req,res,next);
			return;
		}
		
		reqVO = req.body.vo;
		userId = reqVO.userId;
		token = reqVO.token;
		queryMeta=reqVO.query;
		apiAddress=reqVO.apiURL;
		
		if(!RagServerAddr && !apiAddress){
			if(APIRoot){
				await proxyCall(req,res,next);
				return;
			}
		}
		if(!IsRagRoot){
			userInfo=await callProxy("userLogin",{userId:userId,token:token});
			if(userInfo.code!==200){
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}else {
			if (!userId) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
			userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
			if (!userInfo) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}
		if(!apiAddress) {
			apiAddress=RagServerAddr;
		}
		try{
			const response = await fetch(apiAddress+"/solution/retrieve", {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(queryMeta),
			});
			if (response.status !== 200) {
				if(APIRoot){
					await proxyCall(req,res,next);
					return;
				}
				res.json({ code: response.status, info: `HTTP error! Status: ${response.status}` });
				return;
			}
			const result = await response.json();
			if (result && result.code===200 && result.data && result.data[0]) {
				res.json({ code: 200, guide: result.data[0].page_content});
			} else {
				if(APIRoot){
					await proxyCall(req,res,next);
					return;
				}
				res.json({ code: 500, info: `result code error: ${result.code}` });
			}
		} catch (error) {
			if(APIRoot){
				await proxyCall(req,res,next);
				return;
			}
			res.json({ code: 500, info: `RAG-Query internal error: ${error}` });
		}
	};
	
	//-----------------------------------------------------------------------
	apiMap['RagIndexIssue'] = async function (req, res, next) {
		let reqVO, userInfo, resVO,isMaster;
		let userId, token,apiAddress;
		let indexMeta,postToRoot,ragBase;
		
		
		if(!RagServerAddr){//Use proxy-call for upper API
			await proxyCall(req,res,next);
			return;
		}
		
		reqVO = req.body.vo;
		userId = reqVO.userId;
		token = reqVO.token;
		
		indexMeta=reqVO.index;
		apiAddress=reqVO.apiURL;
		postToRoot=reqVO.postToRoot;
		
		if(postToRoot && APIRoot){
			await proxyCall(req,res,next);
			return;
		}
		
		if(!IsRagRoot){
			userInfo=await callProxy("userLogin",{userId:userId,token:token});
			if(userInfo.code!==200){
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}else {
			if (!userId) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
			userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
			if (!userInfo) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}
		if(!apiAddress) {
			apiAddress=RagServerAddr;
		}
		let userEmail=userInfo.email;
		if(masterEmails){
			isMaster = masterEmails.indexOf(userEmail) >= 0;
		}else {
			isMaster = (userInfo.rank === "MASTER") || (userInfo.rank === "LORD");
		}
		if (!isMaster) {
			res.json({ code: 403, info: "User rank invalid." });
			return;
		}
		
		if(!apiAddress) {
			res.json({ code: 500, info: "No RAG service." });
			return;
		}
		
		try{
			let postJSON=JSON.stringify(indexMeta);
			console.log(postJSON);
			const response = await fetch(apiAddress+"/qa/index", {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: postJSON,
			});
			if (response.status !== 200 && response.status !== 201) {
				res.json({ code: response.status, info: `HTTP error! Status: ${response.status}` });
				return;
			}
		} catch (error) {
			res.json({ code: 500, info: `RAG-Index internal error: ${error}` });
			return;
		}
		res.json({ code: 200, info: "Index done." });
	};
	
	//-----------------------------------------------------------------------
	apiMap['RagQueryIssue'] = async function (req, res, next) {
		let reqVO, userInfo, resVO,isMaster;
		let userId, token,apiAddress;
		let queryMeta;
		
		if(!RagServerAddr){//Use proxy-call for upper API
			await proxyCall(req,res,next);
			return;
		}
		
		reqVO = req.body.vo;
		userId = reqVO.userId;
		token = reqVO.token;
		queryMeta=reqVO.query;
		apiAddress=reqVO.apiURL;
		
		if(!RagServerAddr && !apiAddress){
			if(APIRoot){
				await proxyCall(req,res,next);
				return;
			}
		}
		if(!IsRagRoot){
			userInfo=await callProxy("userLogin",{userId:userId,token:token,time:Date.now()});
			if(userInfo.code!==200){
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}else {
			if (!userId) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
			userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
			if (!userInfo) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}
		if(!apiAddress) {
			apiAddress=RagServerAddr;
		}
		try{
			let postJSON=JSON.stringify(queryMeta);
			//postJSON=`{"error_desc":"代理错误","tags":["MacOS"]}`;
			console.log(postJSON);
			const response = await fetch(apiAddress+"/qa/retrieve", {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: postJSON,
			});
			if (response.status !== 200) {
				if(response.status===422){
					let err422=await response.json();
					console.log(err422);
				}
				if(APIRoot){
					await proxyCall(req,res,next);
					return;
				}
				res.json({ code: response.status, info: `HTTP error! Status: ${response.status}` });
				return;
			}
			const resultText=await response.text();
			const result = JSON.parse(resultText);//await response.json();
			if (result && result.code===200) {
				res.json({ code: 200, docs: result.data});
			} else {
				if(APIRoot){
					await proxyCall(req,res,next);
					return;
				}
				res.json({ code: 500, info: `result code error: ${result.code}` });
			}
		} catch (error) {
			if(APIRoot){
				await proxyCall(req,res,next);
				return;
			}
			res.json({ code: 500, info: `RAG-Query internal error: ${error}` });
		}
	};
	
	//-----------------------------------------------------------------------
	apiMap['RagIndexMetaDoc'] = async function (req, res, next) {
		let reqVO, userInfo, resVO,isMaster;
		let userId, token,apiAddress;
		let indexMeta,postToRoot,ragBase,kbId;
		
		if(!RagServerAddr){//Use proxy-call for upper API
			await proxyCall(req,res,next);
			return;
		}
		
		reqVO = req.body.vo;
		userId = reqVO.userId;
		token = reqVO.token;
		
		indexMeta=reqVO.index;
		apiAddress=reqVO.apiURL;
		postToRoot=reqVO.postToRoot;
		kbId=indexMeta.identifier;
		
		if(postToRoot && APIRoot){
			await proxyCall(req,res,next);
			return;
		}
		
		if(!IsRagRoot){
			userInfo=await callProxy("userLogin",{userId:userId,token:token,time:Date.now()});
			if(userInfo.code!==200){
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}else {
			if (!userId) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
			userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
			if (!userInfo) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}
		if(!apiAddress) {
			apiAddress=RagServerAddr;
		}
		let userEmail=userInfo.email;
		if(masterEmails){
			isMaster = masterEmails.indexOf(userEmail) >= 0;
		}else {
			isMaster = (userInfo.rank === "MASTER") || (userInfo.rank === "LORD");
		}
		if (!isMaster) {
			res.json({ code: 403, info: "User rank invalid." });
			return;
		}
		if(!apiAddress) {
			res.json({ code: 500, info: "No RAG service." });
			return;
		}
		if(!kbId || kbId==="personal"){
			kbId=userEmail;
		}
		//TODO: More kbId cases via user ranks
		indexMeta.identifier=kbId;
		try{
			const response = await fetch(apiAddress+"/index/chunk", {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(indexMeta),
			});
			if (response.status !== 200 && response.status !== 201) {
				res.json({ code: response.status, info: `HTTP error! Status: ${response.status}` });
				return;
			}
		} catch (error) {
			res.json({ code: 500, info: `RAG-Index internal error: ${error}` });
			return;
		}
		res.json({ code: 200, info: "Index done." });
	};
	
	//-----------------------------------------------------------------------
	apiMap['RagQueryMetaDoc'] = async function (req, res, next) {
		let reqVO, userInfo, resVO,isMaster,kbId;
		let userId, token,apiAddress;
		let queryMeta,userEmail;
		
		if(!RagServerAddr){//Use proxy-call for upper API
			await proxyCall(req,res,next);
			return;
		}
		
		reqVO = req.body.vo;
		userId = reqVO.userId;
		token = reqVO.token;
		queryMeta=reqVO.query;
		apiAddress=reqVO.apiURL;
		kbId=queryMeta.identifier;
		if(!RagServerAddr && !apiAddress){
			if(APIRoot){
				await proxyCall(req,res,next);
				return;
			}
		}
		if(!IsRagRoot){
			userInfo=await callProxy("userLogin",{userId:userId,token:token,time:Date.now()});
			if(userInfo.code!==200){
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}else {
			if (!userId) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
			userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
			if (!userInfo) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}
		if(!apiAddress) {
			apiAddress=RagServerAddr;
		}
		userEmail=userInfo.email;
		if(!kbId || kbId==="personal"){
			kbId=userEmail;
		}
		//TODO: More kbId cases via user ranks
		queryMeta.identifier=kbId;
		try{
			let postJSON=JSON.stringify(queryMeta);
			//postJSON=`{"error_desc":"代理错误","tags":["MacOS"]}`;
			console.log(postJSON);
			const response = await fetch(apiAddress+"/retrieve/chunk", {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: postJSON,
			});
			if (response.status !== 200) {
				if(response.status===422){
					let err422=await response.json();
					console.log(err422);
				}
				if(APIRoot){
					await proxyCall(req,res,next);
					return;
				}
				res.json({ code: response.status, info: `HTTP error! Status: ${response.status}` });
				return;
			}
			const result = await response.json();
			if (result && result.code===200) {
				res.json({ code: 200, docs: result.data});
			} else {
				if(APIRoot){
					await proxyCall(req,res,next);
					return;
				}
				res.json({ code: 500, info: `result code error: ${result.code}` });
			}
		} catch (error) {
			if(APIRoot){
				await proxyCall(req,res,next);
				return;
			}
			res.json({ code: 500, info: `RAG-Query internal error: ${error}` });
		}
	};

	//-----------------------------------------------------------------------
	apiMap['RAGIndex'] = async function (req, res, next) {
		let reqVO, userInfo, resVO,isMaster;
		let userId, token,apiAddress;
		let indexMeta;
		
		if(!RagServerAddr){//Use proxy-call for upper API
			await proxyCall(req,res,next);
			return;
		}
		
		reqVO = req.body.vo;
		userId = reqVO.userId;
		token = reqVO.token;
		indexMeta=reqVO.index;
		apiAddress=reqVO.apiURL;
		if(!IsRagRoot){
			userInfo=await callProxy("userLogin",{userId:userId,token:token,time:Date.now()});
			if(userInfo.code!==200){
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}else {
			if (!userId) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
			userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
			if (!userInfo) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}
		if(!apiAddress) {
			apiAddress=RagServerAddr;
		}
		try{
			const response = await fetch(apiAddress+"index", {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(indexMeta),
			});
			if (response.status !== 200 && response.status !== 201) {
				res.json({ code: response.status, info: `HTTP error! Status: ${response.status}` });
				return;
			}
		} catch (error) {
			res.json({ code: 500, info: `RAG-Index internal error: ${error}` });
			return;
		}
		res.json({ code: 200, info: "Index done." });
	};
	
	//-----------------------------------------------------------------------
	apiMap['RAGQuery'] = async function (req, res, next) {
		let reqVO, userInfo, resVO,isMaster;
		let userId, token,apiAddress;
		let queryMeta;
		
		if(!RagServerAddr){//Use proxy-call for upper API
			await proxyCall(req,res,next);
			return;
		}
		
		reqVO = req.body.vo;
		userId = reqVO.userId;
		token = reqVO.token;
		queryMeta=reqVO.query;
		apiAddress=reqVO.apiURL;
		if(!RagServerAddr && !apiAddress){
			if(APIRoot){
				await proxyCall(req,res,next);
				return;
			}
		}
		if(!IsRagRoot){
			userInfo=await callProxy("userLogin",{userId:userId,token:token,time:Date.now()});
			if(userInfo.code!==200){
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}else {
			if (!userId) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
			userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
			if (!userInfo) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
		}
		if(!apiAddress) {
			apiAddress=RagServerAddr;
		}
		try{
			const response = await fetch(apiAddress+"retrieve", {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(queryMeta),
			});
			if (response.status !== 200) {
				if(APIRoot){
					await proxyCall(req,res,next);
					return;
				}
				res.json({ code: response.status, info: `HTTP error! Status: ${response.status}` });
				return;
			}
			const result = await response.json();
			if (result && result.code===200) {
				res.json({ code: 200, guide: result.data.guide.procedure});
			} else {
				if(APIRoot){
					await proxyCall(req,res,next);
					return;
				}
				res.json({ code: 500, info: `result code error: ${result.code}` });
			}
		} catch (error) {
			if(APIRoot){
				await proxyCall(req,res,next);
				return;
			}
			res.json({ code: 500, info: `RAG-Query internal error: ${error}` });
		}
	};
};
