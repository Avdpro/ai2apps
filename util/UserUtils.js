var getSysConfig=require('../util/SysConfig.js').getSysConfig;
const https = require('https');
const querystring = require('querystring');

let dbUser=null;
let dbPreview=null;
const DAYTIME=24*3600*1000;
const USERINFO_PROJECTION={email:1,rank:1,rankExpire:1,points:1,coins:1,token:1,tokenExpire:1,lastLogin:1,tokens:1,AIUsage:1};

//--------------------------------------------------------------------------
function initUserUtils(app){
	dbUser=app.get("DBUser");
	dbPreview= app.get("DBPreview");
}

//---------------------------------------------------------------------------
function getHost(req){
	let host;
	host=req.headers.host||"www";
	host=host.replaceAll(".","_");
	host=host.replaceAll(":","_");
	return host;
}

//---------------------------------------------------------------------------
async function getUserInfo(req,userId,token,projection){
	let vo,devKey,userInfo,nowTime,nowDay;
	let saveVO;
	if(!dbUser){
		return null;
	}
	if(!userId){
		userId=req.body.vo.userId;
	}
	if(!token){
		token=req.body.vo.token;
	}
	devKey=req.body.devKey;
	if(userId && token) {
		let host;
		host=getHost(req);
		vo = {
			_id: userId
		};
		vo[`tokens.${host}`]=token;
	}else if(devKey){
		let pts;
		pts=devKey.split("-");
		userId=pts[0];
		vo={
			_id:userId,devKeys:devKey
		};
	}else{
		return null;
	}
	if(projection==="all"){
		userInfo=await dbUser.findOne(vo);
	}else {
		if (projection) {
			projection.name = 1;
			projection.activeDay = 1;
			projection.points = 1;
			projection.rank = 1;
			projection.rankExpire = 1;
			projection.email = 1;
		} else if (projection !== "all") {
			projection = {
				name: 1, email: 1, activeDay: 1, points: 1, rank: 1, rankExpire: 1,
			}
		}
		userInfo=await dbUser.findOne(vo,projection?{projection}:{});
	}
	if(userInfo){
		nowTime = Date.now();
		nowDay = Math.floor(nowTime / DAYTIME);
		if(userInfo.activeDay!==nowDay) {
			let userRank;
			let rankCfg = await getSysConfig("USER-RANK");
			
			vo = {
				_id: userId, activeDay: { $ne: nowDay }
			};
			saveVO = {};
			saveVO.$set = {
				activeDay: nowDay
			};
			
			//Deal with login gas:
			{
				userRank = userInfo.rank;
				if (userInfo.rankExpire > 0 && userInfo.rankExpire < nowTime) {
					userRank = (userRank === "MEMBER") ? "MEMBER" : "PRIME";
				}
				rankCfg = rankCfg[userRank];
				if (rankCfg) {
					if (userInfo.points < rankCfg.loginGas) {
						//Refill loginGas:
						vo.points = { $lt: rankCfg.loginGas };
						saveVO.$set.points = rankCfg.loginGas;
					}
				}
			}
			
			saveVO.$unset = { todayAIUsage: "" };
			dbUser.findOneAndUpdate(vo, saveVO);
			userInfo.activeDay = nowDay;
		}
	}
	return userInfo;
}

//---------------------------------------------------------------------------
async function getGitHubUserInfo(accessToken){
	let apiURL,httpOpts,httpReq;
	if(!dbUser){
		return null;
	}
	apiURL="https://api.github.com/user";
	httpOpts={
		method:"GET",
		headers: {
			'User-Agent': 'node.js',
			'Accept': 'application/json',
			'Authorization': `token ${accessToken}`,
		}
	};
	return new Promise(async(resolve,reject)=>{
		const httpReq = https.request(apiURL,httpOpts, (res) => {
			if(res.statusCode!==200){
				reject(`Http error ${res.statusCode}: ${res.statusMessage||"Network Error"}`);
			}
			res.setEncoding('utf8');
			let rawData = '';
			res.on('data', (chunk) => { rawData += chunk; });
			res.on('end', () => {
				try {
					resolve(JSON.parse(rawData));
				}catch (err) {
					reject(err);
				}
			});
		});
		
		httpReq.on('error', (e) => {
			console.error(`problem with request: ${e.message}`);
		});
		httpReq.end();
	});
}

//---------------------------------------------------------------------------
async function getPVUserInfo (req,projection) {
	let reqVO,host, vo, userId,slot,key,userInfo,pvInfo,nowTime,pvTime;
	if(!dbUser){
		return null;
	}
	reqVO=req.body.vo;
	userId=reqVO.pvUserId;
	slot=reqVO.pvSlot;
	key=reqVO.pvKey;
	if(!userId){
		return null;
	}
	slot=parseInt(slot);
	if(!(slot>=0)){
		return null;
	}
	pvInfo=await dbPreview.findOne({_id:userId});
	if(!pvInfo || !pvInfo.slots){
		return null;
	}
	slot=pvInfo.slots[slot];
	if(!slot){
		return null;
	}
	if(slot.key!==key){
		return null;
	}
	nowTime = Date.now();
	if(nowTime-slot.time>30*60*1000){
		return null;
	}
	userInfo = await dbUser.findOne(vo, projection ? { projection } : USERINFO_PROJECTION);
	return userInfo;
}

module.exports= {
	initUserUtils,
	getUserInfo,
	getGitHubUserInfo,
	getPVUserInfo
};
