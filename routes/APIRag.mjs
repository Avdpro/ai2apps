import {getUserInfo,getPVUserInfo} from "../util/UserUtils.js";
import pathLib from "path";
import { checkAITokenCall } from '../util/TokenUtils.mjs'
import { proxyCall } from '../util/ProxyCall.js'

const APIRoot=process.env.APIROOT;
const RagServerAddr=process.env.RAG_API
const USERINFO_PROJECTION={rank:1,rankExpire:1,points:1,coins:1,token:1,tokenExpire:1,lastLogin:1,tokens:1,AIUsage:1};

export default async function(app,router,apiMap) {
	//-----------------------------------------------------------------------
	apiMap['RAGIndex'] = async function (req, res, next) {
		let reqVO, userInfo, resVO,isMaster;
		let userId, token,apiAddress;
		let indexMeta;
		
		reqVO = req.body.vo;
		userId = reqVO.userId;
		token = reqVO.token;
		indexMeta=reqVO.index;
		apiAddress=reqVO.apiURL;
		if(!apiAddress) {
			if (!userId) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
			userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
			if (!userInfo) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
			isMaster = userInfo.rank === "MASTER" || userInfo.rank === "LORD";
			if (!isMaster) {
				res.json({ code: 403, info: "User rank invalid." });
				return;
			}
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
			if (response.status !== 200) {
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
		if(!apiAddress) {
			if (!userId) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
			userInfo = await getUserInfo(req, userId, token, USERINFO_PROJECTION);
			if (!userInfo) {
				res.json({ code: 403, info: "UserId/Token invalid." });
				return;
			}
			isMaster = userInfo.rank === "MASTER" || userInfo.rank === "LORD";
			if (!isMaster) {
				res.json({ code: 403, info: "User rank invalid." });
				return;
			}
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
