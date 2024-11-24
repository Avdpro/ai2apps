import pathLib from 'path';
import { promises as fs } from 'fs';
import crypto from 'crypto';
import {AAUsers} from './AAUser.mjs';
import {AANodeBot} from './AANodeBot.mjs';
import {AAChatFlows} from './AAChatFlow.mjs';
import {AATasks} from './AATask.mjs';
import {AAFileLib} from './AAFileLib.mjs';
import { openBrowser } from './aaee.mjs'
import {lock,unlock} from "../util/locker.mjs";
import {AADataBaseMem} from './AADataBaseMem.mjs';

async function sleep(time){
	let func,pms;
	pms=new Promise((resolve,reject)=>{
		setTimeout(resolve,time);
	});
	return pms;
}

//***************************************************************************
//AABotsNode
//***************************************************************************
let AABotNodeSlot,aaBotNodeSlot;
{
	//-----------------------------------------------------------------------
	AABotNodeSlot=function(msgSys,ws,initMsg){
		let message;
		this.msgSys=msgSys;
		this.id=initMsg.id;
		this.bots=initMsg.bots;
		this.def=initMsg.def||{};
		this.botMap=new Map();
		this.ws=ws;
		ws.on("message",(message)=>{
			let msg;
			if (message instanceof Buffer || message instanceof Uint8Array) {
				message = message.toString();
			}
			try{
				message=JSON.parse(message);
			}catch{
				message={};
			}
			msg=message.msg;
			switch (msg){
				case "Message":{
					let msgVO;
					msgVO=message.message||message.msgVO;
					this.msgSys.sendMessage(msgVO);
					return;
				}
				case "Log":{
					this.msgSys.sendMessage(message.log);
					return;
				}
				case "BotState":{
					let botId,bot;
					botId=message.bot;
					bot=this.msgSys.getBot(botId);
					if(!bot){
						//TODO: Report error:
						return;
					}
					if(bot.node!==this){
						//TODO: Report error:
						return;
					}
					if("active" in message) {
						bot.active = message.active;
					}
					bot.name=message.name||bot.name;
					bot.description=message.description||bot.description;
					//TODO: More states?
					return;
				}
				default:{
					let handler;
					handler=this.msgSys["BNMSG_"+msg];
					if(handler){
						handler.call(this.msgSys,message);
					}else{
						console.log(`Unknown BotNodeSlot message: ${msg}`);
					}
					return;
				}
			}
		});
	};
	aaBotNodeSlot=AABotNodeSlot.prototype={};
	
	//-----------------------------------------------------------------------
	aaBotNodeSlot.regBot=function(bot){
		this.botMap.set(bot.id,bot);
	};
	
	//-----------------------------------------------------------------------
	aaBotNodeSlot.appendMessage=async function(botId,msgVO){
		let bot;
		bot=this.botMap.get(botId);
		if(bot){
			bot.appendMessage(msgVO);
		}else{
			//TODO: report error:
		}
		await this.ws.send(JSON.stringify({msg:"Message",bot:botId,message:msgVO}));
	};
}

//***************************************************************************
//AAMessages
//***************************************************************************
let AAMsgSys,aaMsgSys;
{
	const AABots_HubID=process.env.AABOTS_HUBID;
	const AABots_ConfigPath=process.env.AABOTS_CONFIG;
	const AABots_BotDirPath=process.env.AABOT_DIRPATH;
	let lastMsgTime=0;

	//-----------------------------------------------------------------------
	AAMsgSys=function(app,aaDB){
		let selectorMap,bot;
		this.id=AABots_HubID||"HUB";
		this.app=app;
		this.nodeMap=new Map();
		this.botMap=new Map();
		this.bot2NodeMap=new Map();
		
		this.aaDB=aaDB||new AADataBaseMem();
		
		this.users=null;
		this.flows=null;
		this.tasks=null;
		this.fileLib=null;
		
		this.botDirPath=null;
	};
	aaMsgSys=AAMsgSys.prototype={};
	
	//-----------------------------------------------------------------------
	aaMsgSys.regNode=async function(node){
		let bots,botId,botMap,bot2NodeMap,bot;
		botMap=this.botMap;
		bot2NodeMap=this.bot2NodeMap;
		this.nodeMap.set(node.id,node);
		bots=node.bots;
		for(bot of bots){
			bot=new AANodeBot(node,bot);
			await bot.load();
			node.regBot(bot);
			botMap.set(bot.id,bot);
			bot2NodeMap.set(bot.id,node);
		}
	};
	
	//-----------------------------------------------------------------------
	aaMsgSys.getBot=function(botId){
		return this.botMap.get(botId);
	}
	
	//-----------------------------------------------------------------------
	aaMsgSys.getBotNode=function(botId){
		return this.bot2NodeMap.get(botId);
	};
	
	//-----------------------------------------------------------------------
	aaMsgSys.getNextMessageId=async function(){
		return await this.aaDB.newMessageId();
	};
	
	//-----------------------------------------------------------------------
	aaMsgSys.sendMessage=async function(msgVO){
		let fromId,toId,botNode,user,time,flowId;
		time = Date.now();
		while (time === lastMsgTime) {
			await sleep(1);
			time = Date.now();
		}
		lastMsgTime = time;
		msgVO.time = time;
		msgVO.id = await this.getNextMessageId();
		
		//Ensure chatFlow:
		flowId=msgVO.chatFlow;
		if(flowId){
			await this.flows.addMessage(flowId,msgVO);
		}else{
			await this.flows.newFlow(msgVO);
			flowId=msgVO.chatFlow;
			//Write log:
			this.log({
				chatFlow:flowId,
				log:{
					catalog:"ChatFlow",
					action:"NewFlow",
					chatFlow:flowId,
					from:msgVO.from,
				},
				reflection:false,
				visibility:2
			});
		}
		
		this.log({
			chatFlow:flowId,
			log:{
				catalog:"Chat",
				action:"Chat",
				chatFlow:flowId,
				from:msgVO.from,
				to:msgVO.to,
				message:msgVO,
			},
			reflection:false,
			visibility:1
		});

		//Deal with ask/reply:
		if(msgVO.type==="Ask"){
			await this.flows.newAsk(flowId,msgVO);
		}else if(msgVO.type==="ReplyAsk"){
			let askId,askVO;
			askId=msgVO.askId;
			askVO=await this.flows.getAsk(flowId,askId);
			if(!askVO){
				console.error(`Can't locate ask mesage:  ChatFlow: ${flowId}, AskId: ${askId}`);
				return;
			}
			if(msgVO.from!==askVO.to){
				console.error(`Reply target error: ${msgVO.from} vs ${askVO.to}`);
				return;
			}
			msgVO.to=askVO.from;
			await this.flows.closeAsk(flowId,askId);
		}
		
		fromId=msgVO.from;
		botNode = this.getBotNode(fromId);
		if(botNode) {
			botNode.appendMessage(fromId,msgVO);
		}else{
			user=await this.users.getUser(fromId);
			if(user) {
				user.appendMessage(msgVO);
			}else{
				console.error(`Can't locate bot or user: ${fromId}`);
			}
		}
		toId=msgVO.to;
		if(toId!==fromId){
			botNode = this.getBotNode(toId);
			if(botNode) {
				botNode.appendMessage(toId,msgVO);
			}else{
				user=await this.users.getUser(toId);
				if(user){
					user.appendMessage(msgVO);
				}else{
					console.error(`Can't locate bot or user: ${toId}`);
				}
			}
		}
		await this.aaDB.addMessage(msgVO);
	};
	
	//-----------------------------------------------------------------------
	aaMsgSys.log=async function(log){
		log.fromType="Hub";
		log.from=this.id;
		await this.sendLog(log);
	};
	
	//-----------------------------------------------------------------------
	aaMsgSys.sendLog=async function(log){
		let fromId,toId,botNode,user,time,flowId,flowObj;
		time = Date.now();
		log.time=time;
		
		//If log is from user, notify:
		if(log.from && log.srcType==="User"){
			user = await this.users.getUser(log.from);
		}

		//Save log into flow:
		flowId=log.chatFlow;
		if(flowId){
			flowObj=await this.flows.getFlow(flowId,log);
			if(flowObj){
				flowObj.addLog(log);
				
				//Maybe notify flow's user:
				if(!user || user.id!==flowObj.from){
					user=await this.users.getUser(flowObj.from);
					if(user){
						user.appendLog(log);
					}
				}
			}
		}
		await this.aaDB.saveLog(log);
	};
	
	//-----------------------------------------------------------------------
	aaMsgSys.setup=async function(router,apiMap){
		let app,cfgPath,self;
		self=this;
		app=self.app;
		await this.aaDB.init();
		this.users=await AAUsers.setup(this,this.app,router,apiMap);
		this.flows=await AAChatFlows.setup(this,this.app,router,apiMap);
		this.tasks=await AATasks.setup(this,this.app,router,apiMap);
		this.fileLib=AAFileLib.setup(this,this.app,router,apiMap);
		
		//Setup bot-dir:
		cfgPath=AABots_BotDirPath;
		if(cfgPath[0]!=="/"){
			cfgPath=pathLib.join(this.app.get("AppHomePath"),cfgPath);
		}
		this.botDirPath=cfgPath;

		//Setup websocket:
		let selectorMap=app.get("WebSocketSelectorMap");
		selectorMap.set("BotNode",(ws,msg)=>{
			let nodeId,bots,node,bot;
			node=new AABotNodeSlot(this,ws,msg);
			this.regNode(node);
		});
		
		//Setup WebAPI
		//-------------------------------------------------------------------
		apiMap['AAEBotHubGetNodes']=async function(req,res){
			let reqVO,nodeId,node,defs;
			reqVO = req.body.vo;
			nodeId=reqVO.node||reqVO.nodeId||reqVO.id;
			node=self.nodeMap.get(nodeId);
			if(!node){
				res.json({ code: 404, info:`Can't find botNode: ${nodeId}`});
				return;
			}
			res.json({ code: 200, def: node.nodeDef});
		};

		//-------------------------------------------------------------------
		apiMap['AAEBotNodeGetPackages']=async function(req,res){
			let reqVO,nodeId,node,defs;
			reqVO = req.body.vo;
			nodeId=reqVO.node||reqVO.nodeId||reqVO.id;
			node=self.nodeMap.get(nodeId);
			if(!node){
				res.json({ code: 404, info:`Can't find botNode: ${nodeId}`});
				return;
			}
			res.json({ code: 200, def: node.nodeDef});
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEGetBotInfo']=async function(req,res){
			let reqVO,botId,bot,defs;
			reqVO = req.body.vo;
			botId=reqVO.bot||reqVO.botId||reqVO.id;
			bot=self.getBot(botId);
			if(!bot){
				res.json({ code: 404, info:`Can't find bot: ${gotId}`});
				return;
			}
			res.json({ code: 200, info: bot.getInfo()});
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEBotGetMessages']=async function(req,res){
			let reqVO,botId,bot,msgs;
			reqVO = req.body.vo;
			botId=reqVO.bot;
			bot=self.getBot(botId);
			msgs=await bot.getMessages(reqVO.tgtBot,reqVO.fromTime||0,reqVO.toTime||0,reqVO.num||0);
			res.json({ code: 200, messages: msgs});
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEBotHandleMessage']=async function(req,res){
			let reqVO,botId,bot,msgId;
			reqVO=req.body.vo;
			botId=reqVO.bot;
			msgId=reqVO.msgId||reqVO.message;
			bot=self.getBot(botId);
			if(!bot){
				res.json({ code: 400, messages: `Bot ${botId} not found.`});
				return;
			}
			await bot.handleMessage(msgId);
			res.json({ code: 200});
		};
	};
}

export default async function(app,router,apiMap) {
	let appMsgSys;
	appMsgSys=new AAMsgSys(app);
	await appMsgSys.setup(router,apiMap);
	return appMsgSys;
};