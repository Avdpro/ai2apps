import pathLib from 'path';
import { promises as fs } from 'fs';
import lockFile from 'lockfile';
import crypto from 'crypto';

const MAX_LOGS=10000;
const MAX_MESSAGES=1000;
const AAUser_UserDir=process.env.AAUSER_DIRPATH;

async function sleep(time){
	let func,pms;
	pms=new Promise((resolve,reject)=>{
		setTimeout(resolve,time);
	});
	return pms;
}

async function lock(lockPath) {
	return new Promise((resolve, reject) => {
		lockFile.lock(lockPath, { wait: 10000, retries: 10, retryWait: 100 }, (err) => {
			if (err) reject(err);
			else resolve();
		});
	});
}

async function unlock(lockPath) {
	return new Promise((resolve, reject) => {
		lockFile.unlock(lockPath, (err) => {
			if (err) reject(err);
			else resolve();
		});
	});
}

async function appendLineToFile(filePath, line) {
	const lockPath = `${filePath}.lock`;
	
	try {
		// 加锁
		await lock(lockPath);
		// 追加一行
		await fs.appendFile(filePath, `${line}\n`, 'utf8');
		// 解锁
		await unlock(lockPath);
	} catch (error) {
		console.error('Error appending line to file:', error);
	}
}

//***************************************************************************
//AAUser:
//***************************************************************************
let AAUser,aaUser;
{
	//-----------------------------------------------------------------------
	AAUser=function(users,id){
		this.msgSys=users.msgSys;
		this.users=users;
		this.id=id;
		this.name="";
		this.rank="GUEST";//"GUEST","MEMBER","ADMIN",""
		this.logs=[];
		this.messages=[];
		this.password=null;
		this.sessionId=null;
		this.lastActiveTime=0;
		this.botScope=null;
		
		this.clientWS=null;
		this.wsSelectorCode=null;
	};
	aaUser=AAUser.prototype={};
	
	//-----------------------------------------------------------------------
	aaUser.getInfo=function(){
		let info;
		info={
			id:this.id,
			name:this.name,
			rank:this.rank,
			needLogin:!!this.password,
			lastActiveTime:this.lastActiveTime,
			botScope:this.botScope
		};
		return info;
	};
	
	//-----------------------------------------------------------------------
	aaUser.load=async function(){
		let userDB,userVO;
		userDB=this.users.userDB;
		if(userDB){
			//TODO: Code this:
		}else{
			let path,userJSON;
			path=this.users.userDir;
			path=pathLib.join(path,`user_${this.id}.user.json`);
			try {
				userJSON = await fs.readFile(path, "utf8");
				userVO = JSON.parse(userJSON);
			}catch(err){
				throw err;
			}
		}
		if(this.id!==userVO.id && userVO.id){
			throw Error("User info has a wrong user id");
		}
		this.name=userVO.name;
		this.rank=userVO.rank;
		this.password=userVO.password;
		this.lastActiveTime=userVO.lastActiveTime;
		this.botScope=userVO.bots||[];
	};
	
	//-----------------------------------------------------------------------
	aaUser.save=async function(){
		let userDB,userVO;
		userVO={
			id:this.id,
			name:this.name,
			rank:this.rank,
			password:this.password,
			lastActiveTime:this.lastActiveTime,
			bots:this.botScope||[]
		};
		userDB=this.users.userDB;
		if(userDB){
			//TODO: Code this:
		}else{
			let path,userJSON;
			path=this.users.userDir;
			path=pathLib.join(path,`user_${this.id}.user.json`);
			userJSON=JSON.stringify(userVO,null,"\t");
			await fs.writeFile(path,userJSON);
		}
	};
	
	//-----------------------------------------------------------------------
	aaUser.getMessages=async function(botId,fromTime,toTime,maxNum){
		let list,messages,msg,i,n,cnt;
		fromTime=fromTime||0;
		toTime=toTime||Date.now();
		maxNum=maxNum||1000;
		list=this.messages;
		messages=[];
		cnt=0;
		n=list.length;
		if(botId) {
			for (i=n-1;i>=0;i--) {
				msg=list[i];
				if (msg.time > fromTime) {
					if(msg.time < toTime && msg.from===botId||msg.to===botId){
						messages.push(msg);
						cnt++;
						if(cnt>maxNum){
							break;
						}
					}
				}
			}
		}else{
			for (i=n-1;i>=0;i--) {
				msg=list[i];
				if (msg.time > fromTime) {
					if(msg.time < toTime) {
						messages.push(msg);
						cnt++;
						if(cnt>maxNum){
							break;
						}
					}
				}else{
					break;
				}
			}
		}
		messages.reverse();
		return messages;
	};
	
	//-----------------------------------------------------------------------
	aaUser.startMessageClient=async function(){
		let selectorMap,selectCode;
		if(this.wsSelectorCode){
			return this.wsSelectorCode;
		}
		selectorMap=this.users.app.get("WebSocketSelectorMap");
		this.wsSelectorCode=selectCode="USERMESSAGE-"+this.id;
		selectorMap.set(selectCode,(ws)=>{
			this.clientWS=ws;
			ws.on('message',(message)=>{
				if (message instanceof Buffer || message instanceof Uint8Array) {
					message = message.toString();
				}
				try{
					message=JSON.parse(message);
				}catch{
					message={};
				}
				try{
					switch(message.msg){
						case "Message":
							this.sendMessage(message.message||message.msgVO);
							break;
						case "Log":
							this.sendLog(message.log);
							break;
					}
				}catch (err){
					console.log("Handle bot message error:");
					console.error(err);
				}
			});
			ws.send(JSON.stringify({msg:"CONNECTED"}));
		});
		return selectCode;
	};
	
	//-----------------------------------------------------------------------
	aaUser.appendMessage=async function(msgVO){
		let msgDB,messages;
		messages=this.messages;
		messages.push(msgVO);
		if(messages.length>MAX_MESSAGES){
			messages.splice(Math.floor(MAX_MESSAGES*0.9));
		}
		msgDB=this.msgSys.messageDB;
		if(msgDB){
			//TODO: Code this:
		}else{
			//We don't keep user messages without DB
		}
		//if(msgVO.from!==this.id && this.clientWS){
		if(this.clientWS){
			this.clientWS.send(JSON.stringify({msg:"Message",message:msgVO}));
		}
	};
	
	//-----------------------------------------------------------------------
	aaUser.appendLog=async function(log){
		let logs;
		logs=this.logs;
		logs.push(log);
		//Logs don't save with user.
		if(this.clientWS){
			this.clientWS.send(JSON.stringify({msg:"Log",log:log}));
		}
	};
	
	//-----------------------------------------------------------------------
	aaUser.sendMessage=async function(msgVO){
		msgVO.from=this.id;
		msgVO.srcType="User";
		this.msgSys.sendMessage(msgVO);
	};
	
	//-----------------------------------------------------------------------
	aaUser.sendLog=async function(log){
		log.from=this.id;
		log.srcType="User";
		await this.msgSys.sendMessage(log);
		await this.appendLog(log);
	};
}

//***************************************************************************
//AAUsers:
//***************************************************************************
let AAUsers,aaUsers;
{
	//-----------------------------------------------------------------------
	AAUsers=function(msgSys,app){
		let path;
		this.app=app;
		this.msgSys=msgSys;
		msgSys.aaUsers=this;
		this.userDB=null;
		this.userMap=new Map();
		this.messages=[];
		this.password=null;
		
		path=AAUser_UserDir;
		if(path[0]!=="/"){
			path=pathLib.join(app.get("AppHomePath"),path);
		}
		this.userDir=path;
	};
	aaUsers=AAUsers.prototype={};
	
	//-----------------------------------------------------------------------
	aaUsers.getUser=async function(userId){
		let user;
		user=this.userMap.get(userId);
		if(user){
			return user;
		}
		//TODO: Load from DB or file:
		try {
			user = new AAUser(this,userId);
			await user.load();
			this.userMap.set(userId,user);
		}catch (err){
			user=null;
		}
		return user;
	};
	
	//-----------------------------------------------------------------------
	aaUsers.newGuestUser=async function(){
		let userId,user;
		userId='GUEST-'+Date.now();
		user=new AAUser(this,userId);
		this.userMap.set(userId,user);
		return user;
	};
	
	//-----------------------------------------------------------------------
	aaUsers.sendMessage=async function(msgVO){
		return await this.msgSys.sendMessage(msgVO);
	};
	
	//-----------------------------------------------------------------------
	AAUsers.setup=async function(appBots,app,router,apiMap){
		let appUsers=new AAUsers(appBots,app);
		let adminUser=appUsers.getUser("admin");
		//-------------------------------------------------------------------
		apiMap['AAEUserCreateUser']=async function(req,res,next){
			let reqVO,userId,user,newUserId,newUser;
			{
				const ReqVODef={
					newUserId:"",sessionId:"",
				};
			}
			reqVO=req.body.vo;
			userId=reqVO.userId;
			if(!userId) {
				user = await appUsers.getUser(userId);
			}
			if(!user){
				res.json({ code: 404,info:"User not found."});
				return;
			}
			if(!user.sessionId){
				res.json({ code: 400,info:"User not active."});
				return;
			}
			if(user.sessionId!==reqVO.sessionId){
				res.json({ code: 400,info:"SessionId error."});
				return;
			}
			if(user.rank!=="ADMIN"){
				res.json({ code: 403,info:"User rank error."});
				return;
			}
			newUserId=reqVO.newUserId;
			newUser=await appUsers.getUser(newUserId);
			if(newUser){
				res.json({ code: 400,info:"User id already used."});
				return;
			}
			//Create user profile:
			let userVO={
				id:newUserId,
				name:reqVO.name,
				rank:reqVO.rank||"MEMBER",
				password:reqVO.password||"password",
			};
			//Write user profile
			let userDB;
			userDB=appUsers.userDB;
			if(userDB){
				//TODO: Write to dataBase:
			}else{
				//TODO: Write to file:
			}
			newUser=await appUsers.getUser(newUserId);
			if(!newUser){
				res.json({ code: 500,info:"Create user failed."});
				return;
			}
			res.json({ code: 200,info:newUser.getInfo()});
		};
		
		//-------------------------------------------------------------------
		apiMap["AAEUserGetInfo"]=async function(req, res, next){
			let reqVO,userId,user;
			reqVO=req.body.vo;
			userId=reqVO.userId;
			if(userId){
				user=await appUsers.getUser(userId);
			}
			if(!user){
				res.json({ code: 404,info:"User not found."});
				return;
			}
			res.json({ code: 200,info:user.getInfo()});
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEUserLogin']=async function(req, res, next){
			let reqVO,userId,user;
			reqVO=req.body.vo;
			userId=reqVO.userId;
			if(!userId){
				user=await appUsers.newGuestUser();
			}else {
				user = await appUsers.getUser(userId);
			}
			if(!user){
				res.json({ code: 404,info:"User not found."});
				return;
			}
			if(user.password){
				if(reqVO.password!==user.password){
					res.json({ code: 403,info:"Wrong password."});
					return;
				}
			}
			user.sessionId=crypto.randomUUID();
			res.json({ code: 200,info:user.getInfo(),sessionId:user.sessionId});
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEUserLogout']=async function(req, res, next){
			let reqVO,userId,user;
			reqVO=req.body.vo;
			userId=reqVO.userId;
			user=await appUsers.getUser(userId);
			if(!user){
				res.json({ code: 404,info:"User not found."});
				return;
			}
			if(!user.sessionId){
				res.json({ code: 400,info:"User not active."});
				return;
			}
			if(user.sessionId!==reqVO.sessionId){
				res.json({ code: 403,info:"Wrong user sessionId."});
				return;
			}
			user.sessionId=null;
			res.json({ code: 200});
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEUserGetMessages']=async function(req, res, next){
			let reqVO,userId,user;
			let tgtId,fromTime,toTime,maxNum,messages;
			{
				const _ReqVO={
					bot:"",botId:"",user:"",fromTime:0,toTime:0,maxNum:0
				}
			}
			reqVO=req.body.vo;
			userId=reqVO.userId;
			user=await appUsers.getUser(userId);
			if(!user){
				res.json({ code: 404,info:"User not found."});
				return;
			}
			if(!user.sessionId){
				res.json({ code: 400,info:"User not active."});
				return;
			}
			if(user.sessionId!==reqVO.sessionId){
				res.json({ code: 403,info:"Wrong user sessionId."});
				return;
			}
			tgtId=reqVO.user||reqVO.bot||reqVO.userId||reqVO.botId||null;
			fromTime=reqVO.fromTime||0;
			toTime=reqVO.toTime||0;
			maxNum=reqVO.maxNum||reqVO.num||0;
			messages=await user.getMessages(tgtId,fromTime,toTime,maxNum);
			res.json({ code: 200, messages: messages});
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEUserSetRank']=async function(req,res,next){
			//TODO: Code this:
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEUserSetInfo']=async function(req,res,next){
			//TODO: Code this:
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEUserResetPassword']=async function(req,res,next){
			//TODO: Code this:
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEUserStartMessageClient']=async function(req, res, next){
			let reqVO,userId,user,msgVO,selectCode;
			reqVO=req.body.vo;
			userId=reqVO.userId;
			if(!userId){
				res.json({ code: 404,info:"User not found."});
				return;
			}
			user=await appUsers.getUser(userId);
			if(!user){
				res.json({ code: 404,info:"User not found."});
				return;
			}
			if(!user.sessionId){
				res.json({ code: 400,info:"User not active."});
				return;
			}
			if(user.sessionId!==reqVO.sessionId){
				res.json({ code: 403,info:"SessionID error."});
				return;
			}
			selectCode=await user.startMessageClient();
			res.json({ code: 200,selectCode:selectCode});
		};

		//-------------------------------------------------------------------
		apiMap['AAEUserSendMessage']=async function(req, res, next){
			let reqVO,userId,user,msgVO;
			reqVO=req.body.vo;
			msgVO=reqVO.message;
			userId=msgVO.from;
			if(!userId){
				res.json({ code: 404,info:"User not found."});
				return;
			}
			user=await appUsers.getUser(userId);
			if(!user){
				res.json({ code: 404,info:"User not found."});
				return;
			}
			if(!user.sessionId){
				res.json({ code: 400,info:"User not active."});
				return;
			}
			if(user.sessionId!==reqVO.sessionId){
				res.json({ code: 403,info:"SessionID error."});
				return;
			}
			await appBots.sendMessage(msgVO);
			res.json({ code: 200});
		};
		
		return appUsers;
	};
}

export {AAUsers,AAUser};
