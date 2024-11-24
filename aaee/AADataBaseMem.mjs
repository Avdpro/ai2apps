import {inherits} from 'util';
import { aaDataBase, AADataBase } from './AADataBase.mjs'

const DBConfig=AADataBase.config;

//***************************************************************************
//AADBUnit
//***************************************************************************
let AADBUnit,aaDBUnit;
{
	let maxLiveMessage=DBConfig.MAX_UNIT_LIVE_MESSAGE||1024;
	//-----------------------------------------------------------------------
	AADBUnit=function(unitId){
		this.id=unitId;
		this.messages=[];
		this.taskReqs=[];
		this.taskWorks=[];
	};
	aaDBUnit=AADBUnit.prototype={};
	
	//-----------------------------------------------------------------------
	aaDBUnit.load=async function(){
		return;
	};
	
	//-----------------------------------------------------------------------
	aaDBUnit.getMessages=async function(){
		await this.load();
		return this.messages.slice(0);
	};

	//-----------------------------------------------------------------------
	aaDBUnit.addMessage=async function(msg){
		const messages=this.messages;
		messages.push(msg);
		if(messages.length>maxLiveMessage){
			messages.splice(0,Math.floor(maxLiveMessage*0.1));
		}
	};
	
	//-----------------------------------------------------------------------
	aaDBUnit.getTaskReqs=async function(){
		return this.taskReqs.slice(0);
	};

	//-----------------------------------------------------------------------
	aaDBUnit.getTaskWorks=async function(){
		return this.taskReqs.slice(0);
	};
}

//***************************************************************************
//AADataBaseMem: Memory only AADataBase
//***************************************************************************
let AADataBaseMem,aaDBMem;
{
	let maxLiveMessage=DBConfig.MAX_DBMEM_LIVE_MESSAGE||10240;
	let maxLiveLog=DBConfig.MAX_DBMEM_LIVE_LOG||102400;
	//-----------------------------------------------------------------------
	AADataBaseMem = function () {
		AADataBase.call(this);
		this.nextMsgId = 1;
		this.nextTaskId = 1;
		this.unitMap=null;
		this.messages=null;
		this.logs=null;
		this.messageMap=null;
		this.flowMap=null;
	};
	inherits(AADataBaseMem, AADataBase);
	aaDBMem = AADataBaseMem.prototype;

	//-----------------------------------------------------------------------
	aaDBMem.init = async function (opts) {
		this.nextMsgId = 1;
		this.nextTaskId = 1;
		this.messages=[];
		this.logs=[];
		this.unitMap=new Map();
		this.messageMap=new Map();
		this.flowMap=new Map();
		
		this.unitClass=AADBUnit;
	};
	
	//***********************************************************************
	//Units:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaDBMem.getUnit=async function(unitId){
			let unit;
			unit=this.unitMap.get(unitId);
			if(!unit){
				unit=new this.unitClass(unitId);
				await unit.load();
			}
			return unit;
		};
	}
	
	//***********************************************************************
	//Messages:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaDBMem.newMessageId=async function(){
			return ""+(this.nextMsgId++);
		};
		
		//-------------------------------------------------------------------
		aaDBMem.getMessage = async function (msgId) {
			return this.messageMap.get(msgId);
		};
		
		//-------------------------------------------------------------------
		aaDBMem.getUnitMessages = async function (unitId) {
			let unit;
			unit=await this.getUnit(unitId);
			return unit.messages.slice(0);
		};

		//-------------------------------------------------------------------
		aaDBMem.findMessages = async function (opts) {
			//TODO: Code this:
			return [];
		};
		
		//-------------------------------------------------------------------
		aaDBMem.addMessage = async function (message) {
			const messages=this.messages;
			const messageMap=this.messageMap;
			messages.push(message);
			messageMap.set(message.id,message);
			if(messages.length>maxLiveMessage){
				let cnt=Math.floor(maxLiveMessage*0.1);
				let keys=messageMap.keys();
				messages.splice(0,cnt);
				for(let key of keys){
					messageMap.delete(key);
				}
			}
		};
		
		//-------------------------------------------------------------------
		aaDBMem.updateMessage = async function (msgId,updates,unsets) {
			const messageMap=this.messageMap;
			const dbMsg=messageMap.get(msgId);
			if(dbMsg){
				let name;
				Object.assign(dbMsg,updates);
				if(unsets) {
					for (name of unsets) {
						delete dbMsg[name];
					}
				}
			}
		};
	}
	
	//***********************************************************************
	//Logs:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaDBMem.getUnitLogs = async function (unitId) {
			let unit;
			unit=await this.getUnit(unitId);
			return unit.logs.slice(0);
		};
		
		//-------------------------------------------------------------------
		aaDBMem.saveLog = async function (log) {
			const logs=this.logs;
			logs.push(log);
			if(logs.length>maxLiveLog){
				let cnt=Math.floor(maxLiveLog*0.1);
				logs.splice(0,cnt);
			}
		};
		
		//-------------------------------------------------------------------
		aaDBMem.findLogs = async function (opts) {
			let logs,outLogs,actions,catalogs,time;
			logs=this.logs;
			if(!opts) {
				return logs;
			}
			if(opts.actions){
				actions=new Set(opts.actions);
			}
			if(opts.catalogs){
				catalogs=new Set(opts.catalogs);
			}
			logs=logs.filter((log)=>{
				time=log.time;
				log=log.log||log;
				if(opts.startTime && time<opts.startTime){
					return false;
				}
				if(opts.endTime && time>opts.endTime){
					return false;
				}
				if(opts.from && log.from!==opts.from){
					return false;
				}
				if(opts.catalog && log.catalog!==opts.catalog){
					return false;
				}
				if(opts.action && log.action!==opts.action){
					return false;
				}
				if(catalogs && !catalogs.has(log.catalog)){
					return false;
				}
				if(actions && !actions.has(log.action)){
					return false;
				}
				if(opts.filter && ops.filter(log)!==true){
					return false;
				}
				return true;
			});
			return logs;
		};
	}
	
	//***********************************************************************
	//Tasks:
	//***********************************************************************
	{
		//Nothing new here:
	}
}

export {AADataBaseMem,AADBUnit};