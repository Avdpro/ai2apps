import pathLib from 'path';
import { promises as fs } from 'fs';
import {lock,unlock} from "../util/locker.mjs";
async function sleep(time){
	let func,pms;
	pms=new Promise((resolve,reject)=>{
		setTimeout(resolve,time);
	});
	return pms;
}

const MAX_LOGS=10000;
const MAX_MESSAGES=1000;

//***************************************************************************
//AANodeBot: this is the Bot-Handle in Message-Server:
//***************************************************************************
let AANodeBot,aaNodeBot;
{
	//-----------------------------------------------------------------------
	AANodeBot=function(node,vo){
		this.node=node;
		this.msgSys=node.msgSys;
		this.aaDB=this.msgSys.aaDB;
		this.id=vo.id;
		this.name=vo.name;
		this.type=vo.type||"Bot";
		this.active = vo.active||false;
		this.description = vo.description;
		
		this.logs=[];
		this.messages=[];

		this.requestTasks=[];
		this.waitingWorks=[];
		this.doingWorks=[];
	};
	aaNodeBot=AANodeBot.prototype={};

	//***********************************************************************
	//I/O:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaNodeBot.getInfo=function(){
			return {
				id:this.id,
				name:this.name,
				type:this.type,
				active:this.active,
				description:this.description,
			};
		};
		//-------------------------------------------------------------------
		aaNodeBot.loadMessages=async function(){
			let msgSys,aaDB,i,n,msg;
			msgSys=this.msgSys;
			aaDB=msgSys.aaDB;
			if(aaDB){
				this.messages=await aaDB.getUnitMessages(this.id);
			}else{
				this.messages=[];
			}
		};
		
		//-------------------------------------------------------------------
		aaNodeBot.load=async function(){
			await this.loadMessages();
		};
	}
	
	//***********************************************************************
	//Messages:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaNodeBot.getMessages=async function(tgtId,fromTime,toTime,maxNum){
			let list,msgs,msg,i,n,cnt;
			fromTime=fromTime||0;
			toTime=toTime||Date.now();
			maxNum=maxNum||1000;
			list=this.messages;
			msgs=[];
			cnt=0;
			n=list.length;
			if(tgtId) {
				for (i=n-1;i>=0;i--) {
					msg=list[i];
					if (msg.time > fromTime) {
						if(msg.time < toTime && msg.from===tgtId||msg.to===tgtId){
							msgs.push(msg);
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
							msgs.push(msg);
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
			msgs.reverse();
			return msgs;
		};
		
		//-------------------------------------------------------------------
		aaNodeBot.appendMessage=async function(msgVO){
			this.messages.push(msgVO);
		};
		
		//-------------------------------------------------------------------
		aaNodeBot.handleMessage=async function(msgId){
			await this.aaDB.updateMessage(msgId,{handled:true});
		};
	}

	//***********************************************************************
	//Task request:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaNodeBot.newTaskReq=async function(task){
			if(this.id===task.initiator){
				this.requestTasks.push(task);
			}else{
				throw Error(`Task is not belong to this bot`);
			}
		};
		
		//-------------------------------------------------------------------
		aaNodeBot.taskReqRejected=async function(task){
			let idx;
			if(this.id===task.initiator) {
				idx=this.requestTasks.indexOf(task);
				if(idx<0){
					throw Error(`Task is not in executor bot's requesting list.`);
				}
				this.requestTasks.splice(idx,1);
			}else{
				throw Error(`Task is not belong to this bot`);
				
			}
		};
		
		//-------------------------------------------------------------------
		aaNodeBot.taskReqFinished=async function(task){
			let idx;
			if(this.id===task.initiator) {
				idx=this.requestTasks.indexOf(task);
				if(idx<0){
					throw Error(`Task is not in executor bot's requesting list.`);
				}
				this.requestTasks.splice(idx,1);
			}else{
				throw Error(`Task is not belong to this bot`);
			}
		};
		
		//-------------------------------------------------------------------
		aaNodeBot.taskReqFailed=async function(task){
			let idx;
			if(this.id===task.initiator) {
				idx=this.requestTasks.indexOf(task);
				if(idx<0){
					throw Error(`Task is not in executor bot's requesting list.`);
				}
				this.requestTasks.splice(idx,1);
			}else{
				throw Error(`Task is not belong to this bot`);
			}
		};
		
		//-------------------------------------------------------------------
		aaNodeBot.taskReqGaveUp=async function(task,reason){
			let idx;
			if(this.id===task.initiator) {
				idx=this.requestTasks.indexOf(task);
				if(idx<0){
					throw Error(`Task is not in executor bot's requesting list.`);
				}
				this.requestTasks.splice(idx,1);
			}else{
				throw Error(`Task is not belong to this bot`);
			}
		};
	}
	//***********************************************************************
	//Task work:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaNodeBot.getNextTaskWork=async function(){
			let work;
			work=this.waitingWorks.shift();
			return work;
		};
		
		//-------------------------------------------------------------------
		aaNodeBot.taskWorkAccepted=async function(task){
			if(this.id!==task.executor){
				throw Error(`Task is not belong to this bot`);
			}
			this.waitingWorks.push(task);
		};
		
		//-------------------------------------------------------------------
		aaNodeBot.taskWorkStarted=async function(task){
			if(this.id===task.executor){
				let idx;
				idx=this.waitingWorks.indexOf(task);
				if(idx>=0) {
					this.waitingWorks.splice(idx, 1);
				}
				this.doingWorks.push(task);
			}else{
				throw Error(`Task is not belong to this bot`);
			}
		};
		
		//-------------------------------------------------------------------
		aaNodeBot.taskWorkFinished=async function(task){
			let idx;
			if(this.id===task.executor){
				idx=this.doingWorks.indexOf(task);
				if(idx>=0){
					this.doingWorks.splice(idx,1);
				}
			}else{
				throw Error(`Task is not belong to this bot`);
			}
		};
		
		//-------------------------------------------------------------------
		aaNodeBot.taskWorkFailed=async function(task){
			let idx;
			if(this.id===task.executor){
				idx=this.doingWorks.indexOf(task);
				if(idx>=0){
					this.doingWorks.splice(idx,1);
				}
			}else{
				throw Error(`Task is not belong to this bot`);
			}
		};
		
		//-------------------------------------------------------------------
		aaNodeBot.taskWorkGaveUp=async function(task){
			let idx;
			if(!this.workMap.get(task.id)){
				throw Error(`Task is not in this bot.`);
			}
			this.workMap.delete(task.id);
			if(this.id===task.executor){
				idx=this.waitingWorks.indexOf(task);
				if(idx>=0) {
					this.waitingWorks.splice(idx, 1);
				}
				idx=this.doingWorks.indexOf(task);
				if(idx>=0) {
					this.doingWorks.splice(idx, 1);
				}
			}else{
				throw Error(`Task is not belong to this bot`);
			}
		};
	}
}
export {AANodeBot};
export default AANodeBot;
