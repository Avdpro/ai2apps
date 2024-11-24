import pathLib from 'path';
import { promises as fs } from 'fs';
import {AAWebBot} from "./AAWebBot.mjs"
import crypto from 'crypto';
import WebSocket from 'ws';

import {AAUsers} from './AAUser.mjs';
import { openBrowser } from './aaee.mjs'
import {lock,unlock} from "../util/locker.mjs";

async function sleep(time){
	let func,pms;
	pms=new Promise((resolve,reject)=>{
		setTimeout(resolve,time);
	});
	return pms;
}
async function appendLineToFile(filePath, line) {
	const lockPath = `${filePath}.lock`;
	
	try {
		await lock(lockPath);
		await fs.appendFile(filePath, `${line}\n`, 'utf8');
		await unlock(lockPath);
	} catch (error) {
		console.error('Error appending line to file:', error);
	}
}

//***************************************************************************
//AABotNode
//***************************************************************************
let AABotNode,aaBotNode;
{
	const AABots_ConfigPath=process.env.AABOTS_CONFIG;
	const AABots_MsgServer=process.env.AABOTS_MESSAGESERVER;
	
	//-----------------------------------------------------------------------
	AABotNode=function(app){
		this.app=app;
		this.id=null;
		this.type="Web";//By default
		this.description="AI2Apps bot node.";
		this.packages=null;
		this.browsers=null;
		this.configPath=null;
		this.nodeDef=null;
		this.botsMap=new Map();

		this.hubConnected=false;
		this.ws=null;//WebSocket to message server.
	};
	aaBotNode=AABotNode.prototype={};
	
	//-----------------------------------------------------------------------
	aaBotNode.connectHub=async function(cbkOk) {
		let ws,self,pms;
		
		if(this.hubConnected){
			return true;
		}
		
		if(cbkOk) {
			pms=null;
		}else{
			pms = new Promise((resolve, reject) => {
				cbkOk = resolve;
			});
		}
		
		self=this;
		//Connect message server:
		ws=this.ws=new WebSocket(AABots_MsgServer);
		ws.on('open', async function() {
			let cbk,bots;
			bots=await self.listBots();
			ws.send(JSON.stringify({msg:"CONNECT",selector:"BotNode",id:self.id,bots:bots,def:self.nodeDef}));
			self.hubConnected=true;
			console.log(`BotNode ${self.id}: connected to hub.`);
			cbk=cbkOk;
			if(cbk){
				cbkOk=null;
				cbk();
			}
		});
		
		ws.on('message', async function incoming(message) {
			let msgVO;
			if (message instanceof Buffer || message instanceof Uint8Array) {
				message = message.toString();
			}
			try{
				message=JSON.parse(message);
			}catch{
				message={};
			}
			if(message.msg==="Message"){
				let msgVO,botId,bot;
				botId=message.bot;
				msgVO=message.message;
				bot = self.getBot(botId);
				if(!bot){
					console.error(`Can't locate message bot: ${botId}`);
					return;
				}
				await bot.appendMessage(msgVO);
			}
		});
		
		ws.on('error', function(err) {
			let cbk;
			if(!self.hubConnected) {
				//TODO: Retry later
				console.log(`BotNode ${self.id}: connect to hub failed.`);
				console.log(err);
				setTimeout(()=>{
					console.log(`BotNode ${self.id}: retry connect...`);
					self.connectHub(cbkOk);
				},3000);
			}
		});
		
		ws.on('close', function() {
			ws=null;
			self.ws=null;
			console.log(`BotNode ${self.id}: connection lost.`);
			if(self.hubConnected){
				self.hubConnected=false;
				setTimeout(()=>{
					console.log(`BotNode ${self.id}: retry connect...`);
					self.connectHub(cbkOk);
				},3000);
			}
		});
		
		try {
			await pms;
		}catch(err){
			return false;
		}
		return true;
	};
	
	//-----------------------------------------------------------------------
	aaBotNode.start=async function(){
		let cfgPath,cfgJSON,botsDef,ws,self;
		let pms,cbkOk,cbkError;
		self=this;

		console.log("AABotNode: Starting...");
		cfgPath = AABots_ConfigPath;
		if (!cfgPath) {
			return;
		}
		if (cfgPath[0] !== "/") {
			cfgPath = pathLib.join(this.app.get("AppHomePath"), cfgPath);
		}
		this.configPath = cfgPath;
		
		try {
			console.log(`AABotNode: Reading config: ${cfgPath}...`);
			cfgJSON = await fs.readFile(cfgPath, "utf8");
			cfgJSON = JSON.parse(cfgJSON);
		} catch (err) {
			console.error(err);
			console.log("AABots: Start failed.");
		}
		
		this.nodeDef=cfgJSON;
		this.id = cfgJSON.id;
		this.description=cfgJSON.description||this.description;
		this.type=cfgJSON.type||this.type;
		this.packages=cfgJSON.packages||[];
		this.browsers=cfgJSON.browsers||[];
		console.log(`AABotNode: Init bots by config...`);
		botsDef = cfgJSON.bots;
		for (let botDef of botsDef) {
			await this.loadBot(botDef);
		}
		
		return await this.connectHub();
	};
	
	//-----------------------------------------------------------------------
	aaBotNode.loadBot=async function(botDef){
		let bot,botType;
		botType=botDef.type;
		console.log(`AABots: Loading bot: id=${botDef.id}, alias=${botDef.alias}`);
		switch(botType){
			case "Node":
				//TODO: Create node bot
				break;
			case "Python":
				//TODO: Create python bot
				break;
			default:
				bot=new AAWebBot(this);
				break;
		}
		if(bot){
			await bot.load(botDef);
			this.botsMap.set(bot.id,bot);
			console.log(`AABotNode: Loading bot: id=${botDef.id} done.`);
		}
		return bot||null;
	};
	
	//-----------------------------------------------------------------------
	aaBotNode.sendMessage=async function(msgVO){
		await this.ws.send(JSON.stringify({msg:"Message",message:msgVO}));
	};
	
	//-----------------------------------------------------------------------
	aaBotNode.sendLog=async function(log){
		//TODO: Save this log?
		if(this.ws) {
			await this.ws.send(JSON.stringify({ msg: "Log", log: log }));
		}
	};
	
	//-----------------------------------------------------------------------
	aaBotNode.getBot= function(id) {
		return this.botsMap.get(id);
	};
	
	//-----------------------------------------------------------------------
	aaBotNode.listBots=async function(){
		let bots,list,bot;
		bots=Array.from(this.botsMap.values());
		list=[];
		for(bot of bots){
			list.push(await bot.getInfo());
		}
		return list;
	};
}

export default async function(app,router,apiMap) {
	const appNode=new AABotNode(app);
	await appNode.start();
	
	//-----------------------------------------------------------------------
	apiMap['AAEBotNodeGetNodeInfo'] = async function (req, res, next) {
		let info;
		info={
			id:appNode.id,
			description:appNode.description,
			browsers:appNode.browsers,
			packages:appNode.packages
		}
		res.json({ code: 200, info: info});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAEBotNodeGetBots'] = async function (req, res, next) {
		let bots;
		bots=await appNode.listBots();
		res.json({ code: 200, bots: bots});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAEBotNodeGetBotDef']=async function(req,res,next){
		let reqVO,botId,bot;
		reqVO = req.body.vo;
		botId=reqVO.bot;
		bot=appNode.getBot(botId);
		if(!bot){
			res.json({ code: 400,info:`BotId ${botId} error.`});
			return;
		}
		res.json({ code: 200,def:bot.def});
	};
	
	//-----------------------------------------------------------------------
	const AABotNodeGetMessages_REQVO={
		tgtBot:"",fromTime:0,toTime:0,num:0
	};
	//-----------------------------------------------------------------------
	apiMap['AAEBotNodeStartBot']=async function(req,res,next){
		let reqVO,botId,bot,sessionId;
		reqVO = req.body.vo;
		botId=reqVO.bot;
		bot=appNode.getBot(botId);
		if(!bot){
			res.json({ code: 400,info:`BotId ${botId} error.`});
			return;
		}
		//TODO: Start bot?
		res.json({ code: 200,sessionId:sessionId});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAEBotNodeStartBotClient']=async function(req,res,next){
		let reqVO,botId,bot,sessionId;
		reqVO = req.body.vo;
		botId=reqVO.bot;
		bot=appNode.getBot(botId);
		if(!bot){
			res.json({ code: 400,info:`BotId ${botId} error.`});
			return;
		}
		sessionId=await bot.startClient();
		res.json({ code: 200,sessionId:sessionId});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAEBotNodeStartMessageClient']=async function(req,res,next){
		let reqVO,botId,bot,sessionId,selector;
		reqVO = req.body.vo;
		botId=reqVO.bot;
		sessionId=reqVO.sessionId;
		bot=appNode.getBot(botId);
		if(!bot){
			res.json({ code: 400,info:`BotId ${botId} error.`});
			return;
		}
		if(sessionId!==bot.sessionId){
			res.json({ code: 403,info:`SessionId error.`});
			return;
		}
		selector=await bot.startMessageClient();
		res.json({ code: 200,selectCode:selector});
	};
}
