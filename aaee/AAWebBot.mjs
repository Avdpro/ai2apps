import {AABot} from "./AABot.mjs";
import {inherits} from 'util';
import pathLib from 'path'
import { promises as fs } from 'fs'
import { openBrowser } from './aaee.mjs'
import crypto from 'crypto'

const AAFarm_DataDirRoot=process.env.AAF_DATADIR_PATH;
const AABots_BotPage=process.env.AABOTS_BOTPAGE;

//***************************************************************************
//AAWebBot
//***************************************************************************
let AAWebBot,aaWebBot;
{
	//-----------------------------------------------------------------------
	AAWebBot=function(botNode,id){
		AABot.call(this,botNode);
		this.id=null;
		this.envAlias=null;

		this.configPath=null;
		this.dataPath=null;
		this.def=null;
		this.autoStart=false;
		this.headless=false;
		this.botJob="";

		this.packages=[];
		this.skills=[];

		this.sessionId=null;
		this.lastActiveTime=0;
		
		this.browser=null;
		this.page=null;

		this.wsSelectorCode=null;
		this.clientWS=null;
	};
	inherits(AAWebBot,AABot);
	aaWebBot=AAWebBot.prototype;
	
	//-----------------------------------------------------------------------
	aaWebBot.load=async function(cfgJSON){
		this.id=cfgJSON.id;
		this.def=cfgJSON;
		this.envAlias=cfgJSON.alias;
		this.name=cfgJSON.name;
		this.autoStart=cfgJSON.autoStart;
		this.description=cfgJSON.description;
		this.headless=cfgJSON.headless;
		this.botJob=cfgJSON.botJob;
		this.packages=cfgJSON.packages;
		this.skills=cfgJSON.skills;
		
		if(this.autoStart){
			this.start().then();
		}
	};
	
	//-----------------------------------------------------------------------
	aaWebBot.getInfo=function() {
		let vo,active;
		active = this.sessionId && (!!this.clientWS);
		vo={
			id:this.id,	name:this.name,	alias:this.envAlias,headless:this.headless,
			description:this.description,
			active:active
		};
		return vo;
	};
	
	//-----------------------------------------------------------------------
	aaWebBot.start=async function(){
		let browser,page,pages;
		if(this.page){
			return;
		}
		browser=this.browser;
		if(!browser) {
			browser = this.browser = await openBrowser(this.envAlias, { headless: this.headless }, true);
		}
		page = this.page=await browser.newPage();
		try {
			//Open bot-page:
			await page.goto(AABots_BotPage, {});
			page.on("close",()=>{
				this.page=null;
			});
			browser.on("disconnected",()=>{
				this.browser=null;
				this.page=null;
			});
			pages=await browser.pages();
			pages[0].close().then();
		}catch(err){
		}
	};
	
	//-----------------------------------------------------------------------
	aaWebBot.stop=async function(){
		if(this.browser && this.page){
			//TODO: Code this:
		}
	};
	
	//-----------------------------------------------------------------------
	aaWebBot.startClient=async function(){
		let time=Date.now();
		if(this.sessionId){
			if(time-this.lastHeartBeat<30*1000){
				throw Error("Bot already has an active session.");
			}
			//Check last heartbeat time:
		}
		this.sessionId=crypto.randomUUID();
		this.lastHeartBeat=time;
		return this.sessionId;
	};
	
	//-----------------------------------------------------------------------
	aaWebBot.startMessageClient=async function(){
		let selectorMap,selectCode;
		if(this.wsSelectorCode){
			return this.wsSelectorCode;
		}
		selectorMap=this.app.get("WebSocketSelectorMap");
		this.wsSelectorCode=selectCode="BOTMESSAGE-"+this.id;
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
				try {
					if(message.msg === "Message") {
						let msgVO=message.message || message.msgVO;
						msgVO.srcType="Bot";
						this.botNode.sendMessage(msgVO);
					}else if(message.msg === "Log") {
						this.sendLog(message.log);
					}else{
						//TODO: Code this:
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
	aaWebBot.sendLog=async function(logVO){
		//Write log:
		logVO.srcType="Bot";
		logVO.from=this.id;
		logVO.time=Date.now();
		await this.appendLog(logVO);
		await this.botNode.sendLog(logVO);
	};

	//-----------------------------------------------------------------------
	aaWebBot.appendMessage=async function(msgVO){
		if(this.clientWS){
			this.clientWS.send(JSON.stringify({msg:"Message",message:msgVO}));
		}
	};
}

export {AAWebBot};