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

//***************************************************************************
//AATaskReq
//***************************************************************************
let AATaskReq,aaTaskReq;
{
	//-----------------------------------------------------------------------
	AATaskReq=function(tasks){
		this.tasks=tasks;
		this.msgSys=tasks.msgSys;
		this.aaDB=tasks.aaDB;
		this.id=null;
		this.chatFlow=null;
		this.initiator=null;
		this.executor=null;
		this.prompt=null;
		this.state="NONE";//NONE,WAIT,ACCEPTED,WORKING,FINISH,REJECTED,FAILED
		this.startTime=0;
		this.lastActiveTime=0;
		this.parentTask=null;
		this.subTasks=null;
	};
	aaTaskReq=AATaskReq.prototype={};
	
	//-----------------------------------------------------------------------
	aaTaskReq.request=async function(from,to,prompt,flowId,parentTaskId){
		let time,msgVO,tasks,msgSys,fromBot;
		tasks=this.tasks;
		msgSys=this.msgSys;
		time=Date.now();
		//Make sure bots:
		this.id=await this.aaDB.newTaskId();
		this.prompt=prompt;
		this.initiator=from;
		this.executor=to;
		this.chatFlow=flowId;
		this.startTime=this.lastActiveTime=time;
		this.state="WAIT";
		if(parentTaskId){
			let parentReq;
			parentReq=await tasks.getTaskReq(parentTaskId);
			if(parentReq){
				this.parentTask=parentTaskId;
				await parentReq.addSubTask(this.id);
			}
		}
		fromBot=this.msgSys.getBot(from);
		if(!fromBot){
			throw Error(`Can't find task bot: ${from}`);
		}
		await fromBot.newTaskReq(this);
		//Create message:
		msgVO={
			type:"Task",from:this.initiator,to:this.executor,chatFlow:flowId,
			content:{
				action:"Request",prompt:prompt,taskId:this.id
			}
		};
		await this.save();
		await msgSys.sendMessage(msgVO);
		//TODO: Add log?
	};
	
	//-----------------------------------------------------------------------
	aaTaskReq.rejected=async function(reason){
		let tasks=this.tasks;
		let msgSys=this.msgSys;
		let iBot=msgSys.getBot(this.initiator);
		if(!iBot){
			throw Error(`Can't find task bot: ${this.initiator}`);
		}
		this.lastActiveTime=Date.now();
		this.state="REJECTED";
		//TODO: Add log:
		iBot.taskReqRejected(this);
		tasks.removeTaskReq(this.id);
		await this.save();
	};
	
	//-----------------------------------------------------------------------
	aaTaskReq.finished=async function(result){
		let tasks=this.tasks;
		let msgSys=this.msgSys;
		let iBot=msgSys.getBot(this.initiator);
		if(!iBot){
			throw Error(`Can't find task bot: ${this.initiator}`);
		}
		this.lastActiveTime=Date.now();
		this.state="FINISH";
		//TODO: Add log:
		iBot.taskReqFinished(this);
		tasks.removeTaskReq(this.id);
		await this.save();
	};
	
	//-----------------------------------------------------------------------
	aaTaskReq.failed=async function(reason){
		let tasks=this.tasks;
		let msgSys=this.msgSys;
		let iBot=msgSys.getBot(this.initiator);
		if(!iBot){
			throw Error(`Can't find task bot: ${this.initiator}`);
		}
		this.lastActiveTime=Date.now();
		this.state="FAILED";
		//TODO: Add log:
		iBot.taskReqFailed(this);
		tasks.removeTaskReq(this.id);
		await this.save();
	};
	
	//-----------------------------------------------------------------------
	aaTaskReq.giveUp=async function(reason){
		let msgVO;
		let tasks=this.tasks;
		let msgSys=this.msgSys;
		let iBot=msgSys.getBot(this.initiator);
		if(!iBot){
			throw Error(`Can't find task bot: ${this.initiator}`);
		}
		this.lastActiveTime=Date.now();
		this.state="GIVEUP";
		//Create message:
		msgVO={
			type:"Task",from:this.initiator,to:this.executor,
			content:{
				action:"GiveUp",result:reason,
			}
		};
		await msgSys.sendMessage(msgVO);
		//TODO: Add log:
		iBot.taskReqGaveUp(this,reason);
		tasks.removeTaskReq(this.id);
		await this.save();
	};
	
	//-----------------------------------------------------------------------
	aaTaskReq.addSubTask=async function(taskId){
		if(!this.subTasks){
			this.subTasks=[];
		}
		this.subTasks.push(taskId);
		await this.save();
	};
	
	//-----------------------------------------------------------------------
	aaTaskReq.save=async function(){
		await this.msgSys.aaDB.saveTaskReq(this);
	};
	
	//-----------------------------------------------------------------------
	aaTaskReq.loadFromVO=async function(vo){
		this.id=vo.id;
		this.chatFlow=vo.chatFlow;
		this.initiator=vo.initiator;
		this.executor=vo.executor;
		this.prompt=vo.prompt;
		this.state=vo.state;
		this.startTime=vo.startTime;
		this.lastActiveTime=vo.lastActiveTime;
		this.parentTask=vo.parentTask||null;
		this.subTasks=vo.subTasks?vo.subTasks.slice(0):null;
	};

	//-----------------------------------------------------------------------
	aaTaskReq.genSaveVO=async function(){
		let vo;
		vo={};
		vo.id=this.id;
		vo.chatFlow=this.chatFlow;
		vo.initiator=this.initiator;
		vo.executor=this.executor;
		vo.prompt=this.prompt;
		vo.state=this.state;
		vo.startTime=this.startTime;
		vo.lastActiveTime=this.lastActiveTime;
		vo.parentTask=this.parentTask||null;
		vo.subTasks=this.subTasks?this.subTasks.slice(0):null;
		return vo;
	};
}

//***************************************************************************
//AATaskWork
//***************************************************************************
let AATaskWork,aaTaskWork;
{
	//-----------------------------------------------------------------------
	AATaskWork=function(tasks){
		this.tasks=tasks;
		this.msgSys=tasks.msgSys;
		this.id=null;
		this.initiator=null;
		this.executor=null;
		this.prompt=null;
		this.chatFlow=null;
		this.state="NONE";//NONE,WAIT,WORKING,FINISH,REJECTED,FAILED
		this.startTime=0;
		this.lastActiveTime=0;
		this.parentTask=null;
		this.subTasks=null;
	};
	aaTaskWork=AATaskWork.prototype={};
	
	//-----------------------------------------------------------------------
	aaTaskWork.accept=async function(taskId){
		let msgSys,tasks,eBot,taskReq;
		msgSys=this.msgSys;
		tasks=this.tasks;
		this.aaDB=tasks.aaDB;
		taskReq=await tasks.getTaskReq(taskId);
		if(!taskReq){
			throw Error(`Can't find task req: ${taskId}`);
		}
		this.id=taskReq.id;
		this.initiator=taskReq.initiator;
		this.executor=taskReq.executor;
		this.prompt=taskReq.prompt;
		this.chatFlow=taskReq.chatFlow;
		this.parentTask=taskReq.parentTask;
		this.subTasks=taskReq.subTasks;
		this.lastActiveTime=Date.now();
		this.state="WAIT";
		eBot=msgSys.getBot(this.executor);
		if(!eBot){
			throw Error(`Can't find task bot: ${this.executor}`);
		}
		await eBot.taskWorkAccepted(this);
		
		if(this.parentTask){
			let pTask;
			pTask=await tasks.getTaskWork(this.parentTask);
			if(pTask){
				pTask.addSubTask(this.id)
			}
		}
		
		//Write log:
		this.msgSys.log({
			chatFlow:this.chatFlow,
			task:this.id,
			log:{
				catalog:"TaskWork",
				action:"AcceptTask",
				task:this.id
			},
			reflection:true
		});
		await this.save();
	};
	
	//-----------------------------------------------------------------------
	aaTaskWork.addSubTask=async function(taskId){
		if(!this.subTasks){
			this.subTasks=[];
		}
		this.subTasks.push(taskId);
		await this.save();
	};
	
	//-----------------------------------------------------------------------
	aaTaskWork.startWork=async function(){
		let msgVO;
		let msgSys=this.msgSys;
		let eBot=msgSys.getBot(this.executor);
		if(!eBot){
			throw Error(`Can't find task bot: ${this.executor}`);
		}
		this.startTime=this.lastActiveTime=Date.now();
		this.state="WORKING";
		//Create message:
		msgVO={
			type:"Task",from:this.executor,to:this.initiator,chatFlow:this.chatFlow,
			content:{
				action:"Start",taskId:this.id
			}
		};
		await msgSys.sendMessage(msgVO);
		await eBot.taskWorkStarted(this);
		
		//Write log:
		this.msgSys.log({
			chatFlow:this.chatFlow,
			task:this.id,
			log:{
				catalog:"TaskWork",
				action:"StartTask",
				task:this.id,
			},
			reflection:true
		});
		
		await this.save();
	};
	
	//-----------------------------------------------------------------------
	aaTaskWork.finish=async function(result,assets){
		let msgVO,parentTask;
		let msgSys=this.msgSys;
		let eBot=msgSys.getBot(this.executor);
		if(!eBot){
			throw Error(`Can't find task bot: ${this.executor}`);
		}
		this.lastActiveTime=Date.now();
		this.state="FINISH";
		parentTask=this.parentTask;
		if(parentTask){
			//TODO: Handle this:
		}else {
			//Create message:
			msgVO = {
				type: "Task", from: this.executor, to: this.initiator, chatFlow: this.chatFlow,
				content: {
					action: "Finish", taskId: this.id, result: result,assets:assets
				}
			};
			await msgSys.sendMessage(msgVO);
		}
		//TODO: Add log:
		await eBot.taskWorkFinished(this);
		await this.tasks.removeTaskWork(this.id);

		//Write log:
		this.msgSys.log({
			chatFlow:this.chatFlow,
			task:this.id,
			log:{
				catalog:"TaskWork",
				action:"FinishTask",
				task:this.id,
				result:result,assets:assets,
			},
			reflection:true
		});

		await this.save();
	};
	
	//-----------------------------------------------------------------------
	aaTaskWork.fail=async function(reason,assets){
		let msgVO,parentTask;
		let msgSys=this.msgSys;
		let eBot=msgSys.getBot(this.executor);
		if(!eBot){
			throw Error(`Can't find task bot: ${this.executor}`);
		}
		this.lastActiveTime=Date.now();
		this.state="FAILED";
		parentTask=this.parentTask;
		if(parentTask){
			//TODO: Code this:
		}else {
			//Create message:
			msgVO = {
				type: "Task", from: this.executor, to: this.initiator, chatFlow: this.chatFlow,
				content: {
					action:"Fail", taskId:this.id, reason:reason, assets:assets
				}
			};
			await msgSys.sendMessage(msgVO);
		}
		//TODO: Add log:
		await eBot.taskWorkFailed(this);
		await this.tasks.removeTaskWork(this.id);
		
		//Write log:
		this.msgSys.log({
			chatFlow:this.chatFlow,
			task:this.id,
			log:{
				catalog:"TaskWork",
				action:"FailTask",
				task:this.id,
				result:reason,assets:assets,
			},
			reflection:true
		});
		
		await this.save();
	};
	
	//-----------------------------------------------------------------------
	aaTaskWork.giveUp=async function(reason){
		let msgSys=this.msgSys;
		let eBot=msgSys.getBot(this.executor);
		if(!eBot){
			throw Error(`Can't find task bot: ${this.executor}`);
		}
		this.lastActiveTime=Date.now();
		this.state="GIVEUP";
		//TODO: Add log:
		await eBot.taskWorkGaveUp(this,reason);
		await this.tasks.removeTaskWork(this.id);
		
		//Write log:
		this.msgSys.log({
			chatFlow:this.chatFlow,
			task:this.id,
			log:{
				catalog:"TaskWork",
				action:"GiveUpTask",
				task:this.id,
				result:reason,
			},
			reflection:true
		});
		
		await this.save();
	};
	
	//-----------------------------------------------------------------------
	aaTaskWork.save=async function(){
		let aaDB;
		aaDB=this.msgSys.aaDB;
		if(aaDB && aaDB.saveTaskWork){
			await aaDB.saveTaskWork(this.genSaveVO());
		}
	};
	
	//-----------------------------------------------------------------------
	aaTaskWork.loadFromVO=async function(vo){
		this.id=vo.id;
		this.initiator=vo.initiator;
		this.executor=vo.executor;
		this.prompt=vo.prompt;
		this.chatFlow=vo.chatFlow;
		this.parentTask=vo.parentTask;
		this.subTasks=(vo.subTasks&&vo.subTasks.length>0)?vo.subTasks.slice(0):null;
		this.lastActiveTime=vo.lastActiveTime;
		this.state=vo.state;
	};
	
	//-----------------------------------------------------------------------
	aaTaskWork.genSaveVO=async function(){
		let vo={};
		vo.id=this.id;
		vo.initiator=this.initiator;
		vo.executor=this.executor;
		vo.prompt=this.prompt;
		vo.chatFlow=this.chatFlow;
		vo.parentTask=this.parentTask;
		vo.subTasks=(this.subTasks && this.subTasks.length>0)?this.subTasks.slice(0):null;
		vo.lastActiveTime=this.lastActiveTime;
		vo.state=this.state;
		return vo;
	};
}

//***************************************************************************
//AATasks
//***************************************************************************
let AATasks,aaTasks;
{
	let lastTaskTime=0;
	let lastTaskTimeFix=0;

	//-----------------------------------------------------------------------
	AATasks=function(msgSys){
		this.msgSys=msgSys;
		this.aaDB=msgSys.aaDB;
		this.reqMap=new Map();
		this.workMap=new Map();
	};
	aaTasks=AATasks.prototype={};
	
	//-----------------------------------------------------------------------
	aaTasks.loadFromDB=async function(){
		let taskReqs,taskWorks,reqMap,workMap,taskVO,task;
		taskReqs=await this.aaDB.loadOpenTaskReqs();
		taskWorks=await this.aaDB.loadOpenTaskWorks();
		reqMap=this.reqMap;
		workMap=this.workMap;
		for(taskVO of taskWorks){
			task=new AATaskWork(this);
			await task.loadFromVO(taskVO);
			workMap.set(task.id,task);
		}

		for(taskVO of taskReqs){
			task=new AATaskReq(this);
			await task.loadFromVO(taskVO);
			reqMap.set(task.id,task);
		}
	};
	
	//-----------------------------------------------------------------------
	aaTasks.newTaskReq=async function(msgVO){
		let task;
		task=new AATaskReq(this);
		await task.request(msgVO.from,msgVO.to,msgVO.prompt,msgVO.chatFlow,msgVO.parentTask);
		this.reqMap.set(task.id,task);

		//Write log:
		this.msgSys.log({
			chatFlow:msgVO.chatFlow,
			task:task.id,
			log:{
				catalog:"TaskWork",
				action:"NewTask",
				task:task.id,
				initiator:msgVO.from,
				executor:msgVO.to,
				prompt:msgVO.prompt,
			},
			reflection:true
		});
		return task;
	};
	
	//-----------------------------------------------------------------------
	aaTasks.acceptTaskWork=async function(reqVO){
		let task,taskReq;
		task=new AATaskWork(this);
		await task.accept(reqVO.taskId);
		this.workMap.set(task.id,task);
		return task;
	};
	
	//-----------------------------------------------------------------------
	aaTasks.rejectTaskWork=async function(reqVO){
		let msgVO;
		//Create message:
		msgVO={
			type:"Task",from:reqVO.from,to:reqVO.to,
			content:{
				action:"Reject",taskId:reqVO.taskId,reason:reqVO.reason,
			}
		};
		await this.msgSys.sendMessage(msgVO);
		//TODO: Add log:
	};
	
	//-----------------------------------------------------------------------
	aaTasks.getTaskReqs=function(){
		return Array.from(this.reqMap.values());
	};
	
	//-----------------------------------------------------------------------
	aaTasks.getTaskWorks=function(){
		return Array.from(this.workMap.values());
	};
	
	//-----------------------------------------------------------------------
	aaTasks.getTaskReq=async function(taskId){
		let req;
		req=this.reqMap.get(taskId);
		if(!req){
			let vo;
			vo=await this.aaDB.getTaskReq(taskId);
			if(!vo){
				return null;
			}
			req=new AATaskReq(this);
			await req.loadFromVO(vo);
		}
		return req;
	};
	
	//-----------------------------------------------------------------------
	aaTasks.getTaskWork=async function(taskId){
		let work;
		work=this.workMap.get(taskId);
		if(!work){
			let vo;
			vo=await this.aaDB.getTaskWork(taskId);
			if(!vo){
				return null;
			}
			work=new AATaskReq(this);
			await work.loadFromVO(vo);
		}
		return work;
	};
	
	//-----------------------------------------------------------------------
	aaTasks.removeTaskReq=function(taskId){
		this.reqMap.delete(taskId);
	};
	
	//-----------------------------------------------------------------------
	aaTasks.removeTaskWork=function(taskId){
		this.workMap.delete(taskId);
	};
}

//---------------------------------------------------------------------------
AATasks.setup=async function(msgSys,app,router,apiMap){
	let appTasks=new AATasks(msgSys);
	await appTasks.loadFromDB();
	
	//-----------------------------------------------------------------------
	apiMap['AAETaskNewTaskReq']=async function(req,res,next){
		let reqVO,taskReq;
		reqVO=req.body.vo;
		taskReq=await appTasks.newTaskReq(reqVO);
		res.json({ code: 200,taskId:taskReq.id});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAETaskRejectTaskReq']=async function(req,res,next){
		let reqVO,taskId,taskReq;
		reqVO=req.body.vo;
		taskId=reqVO.taskId;
		taskReq=await appTasks.getTaskReq(taskId);
		if(!taskReq){
			res.json({ code: 400, info: `Wrong task-id: ${taskId}`});
			return;
		}
		if(reqVO.from!==taskReq.initiator){
			res.json({ code: 400, info: `Wrong initiator.`});
			return;
		}
		await taskReq.rejected(reqVO.reason);
		res.json({ code: 200});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAETaskFinishTaskReq']=async function(req,res,next){
		let reqVO,taskId,taskReq;
		reqVO=req.body.vo;
		taskId=reqVO.taskId;
		taskReq=await appTasks.getTaskReq(taskId);
		if(!taskReq){
			res.json({ code: 400, info: `Wrong task-id: ${taskId}`});
			return;
		}
		if(reqVO.from!==taskReq.initiator){
			res.json({ code: 400, info: `Wrong initiator.`});
			return;
		}
		await taskReq.finished(reqVO.result);
		res.json({ code: 200});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAETaskFailTaskReq']=async function(req,res,next){
		let reqVO,taskId,taskReq;
		reqVO=req.body.vo;
		taskId=reqVO.taskId;
		taskReq=await appTasks.getTaskReq(taskId);
		if(!taskReq){
			res.json({ code: 400, info: `Wrong task-id: ${taskId}`});
			return;
		}
		if(reqVO.from!==taskReq.initiator){
			res.json({ code: 400, info: `Wrong initiator.`});
			return;
		}
		await taskReq.failed(reqVO.reason);
		res.json({ code: 200});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAETaskGiveUpTaskReq']=async function(req,res,next){
		let reqVO,taskId,task;
		reqVO=req.body.vo;
		taskId=reqVO.taskId;
		task=await appTasks.getTaskReq(taskId);
		if(!task){
			res.json({ code: 400, info: `Wrong task-id: ${taskId}`});
			return;
		}
		if(reqVO.from!==task.initiator){
			res.json({ code: 400, info: `Wrong initiator.`});
			return;
		}
		await task.giveUp(reqVO.reason);
		res.json({ code: 200});
	};
	
	//-----------------------------------------------------------------------
	//-----------------------------------------------------------------------
	apiMap['AAETaskAcceptTaskWork']=async function(req,res,next){
		let reqVO,taskId,task;
		reqVO=req.body.vo;
		task=await appTasks.acceptTaskWork(reqVO);
		res.json({code: 200, taskId:task.id});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAETaskRejectTaskWork']=async function(req,res,next){
		let reqVO;
		reqVO=req.body.vo;
		await appTasks.rejectTaskWork(reqVO);
		res.json({ code: 200});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAETaskGetNextWork']=async function(req,res,next){
		let reqVO,botId,bot,task;
		reqVO=req.body.vo;
		botId=reqVO.bot;
		bot=msgSys.getBot(botId);
		task=await bot.getNextTaskWork();
		if(task) {
			res.json({ code: 200, taskId: task.id, from: task.initiator, prompt: task.prompt });
		}else{
			res.json({ code: 200});
		}
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAETaskStartWork']=async function(req,res,next){
		let reqVO,taskId,work;
		reqVO=req.body.vo;
		taskId=reqVO.taskId;
		work=await appTasks.getTaskWork(taskId);
		if(!work){
			res.json({ code: 400, info: `Wrong task-id: ${taskId}`});
			return;
		}
		if(reqVO.from!==work.executor){
			res.json({ code: 400, info: `Wrong executor.`});
			return;
		}
		await work.startWork();
		res.json({ code: 200});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAETaskFinishWork']=async function(req,res,next){
		let reqVO,taskId,work;
		reqVO=req.body.vo;
		taskId=reqVO.taskId;
		work=await appTasks.getTaskWork(taskId);
		if(!work){
			res.json({ code: 400, info: `Wrong task-id: ${taskId}`});
			return;
		}
		if(reqVO.from!==work.executor){
			res.json({ code: 400, info: `Wrong executor.`});
			return;
		}
		await work.finish(reqVO.result,reqVO.assets);
		res.json({ code: 200});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAETaskFailWork']=async function(req,res,next){
		let reqVO,taskId,work;
		reqVO=req.body.vo;
		taskId=reqVO.taskId;
		work=await appTasks.getTaskWork(taskId);
		if(!work){
			res.json({ code: 400, info: `Wrong task-id: ${taskId}`});
			return;
		}
		if(reqVO.from!==work.executor){
			res.json({ code: 400, info: `Wrong executor.`});
			return;
		}
		await work.fail(reqVO.reason);
		res.json({ code: 200});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAETaskGiveUpTask']=async function(req,res,next){
		let reqVO,taskId,work;
		reqVO=req.body.vo;
		taskId=reqVO.taskId;
		work=await appTasks.getTaskWork(taskId);
		if(!work){
			res.json({ code: 400, info: `Wrong task-id: ${taskId}`});
			return;
		}
		if(reqVO.from!==work.executor){
			res.json({ code: 400, info: `Wrong executor.`});
			return;
		}
		await work.giveUp(reqVO.reason);
		res.json({ code: 200});
	};
	
	//-----------------------------------------------------------------------
	apiMap['AAETaskGetHierarchy']=async function(req,res,next){
		let reqVO,taskId,taskReq;
		reqVO=req.body.vo;
		taskId=reqVO.taskId;
		taskReq=await appTasks.getTaskReq(taskId);
		if(!taskReq){
			res.json({ code: 400, info: `Wrong task-id: ${taskId}`});
			return;
		}
		res.json({ code: 200, parentTask: taskReq.parentTask,subTasks:taskReq.subTasks});
	};
	return appTasks;
};
export default AATasks;
export {AATasks};