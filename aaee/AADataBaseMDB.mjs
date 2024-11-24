import {inherits} from 'util';
import { aaDataBase, AADataBase } from './AADataBase.mjs'
import MongoDB from "../util/mongo.js";

//***************************************************************************
//AADataBaseMDB: Memory only AADataBase
//***************************************************************************
let AADataBaseMDB,aaDataBaseMDB;
{
	let maxLiveMessage=DBConfig.MAX_DBMONGO_LIVE_MESSAGE||10240;
	let maxUnitMessage=DBConfig.MAX_DBMONGO_UNIT_MESSAGE||1024;
	let maxLiveLog=DBConfig.MAX_DBMEM_LIVE_LOG||102400;
	//-----------------------------------------------------------------------
	AADataBaseMDB = function (app,dbURL) {
		AADataBase.call(this);
		this.app=app;
		this.mongoDB=new MongoDB(app, dbURL);
		this.tabSys=null;
		this.tabMessage=null;
		this.tabLog=null;
		this.tabTaskReq=null;
		this.tabTaskWork=null;
		this.tabChatFlow=null;
	};
	inherits(AADataBaseMDB, AADataBase);
	aaDataBaseMDB = AADataBaseMDB.prototype;
	
	//-----------------------------------------------------------------------
	aaDataBaseMDB.init = async function (opts) {
		let mongoDB;
		mongoDB=this.mongoDB;
		await mongoDB.initDB();
		this.tabSys=mongoDB.collection("AAHub","System");
		this.tabMessage=await mongoDB.cappedCollection("AAHub","Message",100*1024*1024);
		mongoDB.ensureIndex("AAHub","Message","id");
		this.tabLog=await mongoDB.cappedCollection("AAHub","Log",100*1024*1024);
		this.tabTaskReq=await mongoDB.cappedCollection("AAHub","TaskReq",100*1024*1024);
		mongoDB.ensureIndex("AAHub","TaskReq","id");
		this.tabTaskWork=await mongoDB.cappedCollection("AAHub","TaskWork",100*1024*1024);
		mongoDB.ensureIndex("AAHub","TaskWork","id");
		this.tabChatFlow=await mongoDB.cappedCollection("AAHub","ChatFlow",100*1024*1024);
		mongoDB.ensureIndex("AAHub","ChatFlow","id");
	};
	
	//***********************************************************************
	//Messages:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaDataBaseMDB.newMessageId=async function(){
			let idVO;
			idVO=await this.tabSys.findOneAndUpdate({_id:"nextMsgId"},{'$inc':{id:1}});
			if(!idVO.ok){
				throw Error("AADataBase error: can't generate new message-id.");
			}
			idVO=idVO.value;
			return ""+(idVO.id);
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.getMessage = async function (msgId) {
			let msgVO;
			msgVO=await this.tabMessage.findOne({_id:msgId});
			return msgVO;
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.getUnitMessages = async function (unitId) {
			let csr,list,doc;
			csr=await this.tabMessage.find({$or:{from:unitId,to:unitId}},{sort:{id:-1},limit:maxUnitMessage});
			list=[];
			for await (doc of csr) {
				doc={...doc};
				delete doc._id;
				list.push(doc);
			}
			return list;
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.findMessages = async function (opts) {
			let queryVO,queryOpts;
			let csr,list,doc;
			queryVO={};
			queryOpts={};

			opts=opts||{limit:maxLiveMessage};

			if(Array.isArray(opts.id)){
				queryVO["id"]={$in:opts.id};
			}else if(opts.id){
				queryVO["id"]=opts.id;
			}

			if(opts.chatFlow){
				queryVO["chatFlow"]=opts.chatFlow;
			}
			if(opts.startTime){
				let timeVO;
				timeVO=queryVO["time"]={}
				timeVO["$gte"]=opts.startTime;
			}
			if(opts.endTime){
				let timeVO;
				timeVO=queryVO["time"];
				if(!timeVO){
					timeVO=queryVO["time"]={}
				}
				timeVO["$lte"]=opts.endTime;
			}
			if(opts.from){
				queryVO["from"]=opts.from;
			}
			if(opts.to){
				queryVO["to"]=opts.to;
			}
			if(opts.limit){
				queryOpts.limit=opts.limit;
			}
			if(opts.sort){
				queryOpts.sort= {_id:opts.sort};
			}
			csr=await this.tabMessage.find(queryVO,queryOpts);
			list=[];
			for await (doc of csr) {
				doc={...doc};
				delete doc._id;
				list.push(doc);
			}
			return list;
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.addMessage = async function (message) {
			await this.tabMessage.updateOne({id:message.id},message,{upsert:true});
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.updateMessage=async function(id,updates,unsets){
			let updateVO;
			updateVO={};
			if(updates){
				updateVO["$set"]=updates;
			}
			if(unsets){
				let key,unset;
				unsetVO=updateVO["$unset"]={};
				for(key of unsets){
					unsetVO[key]="";
				}
			}
			await this.tabMessage.updateOne({id:id},updateVO);
		};
		
		
	}
	
	//***********************************************************************
	//Logs:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaDataBaseMDB.saveLog = async function (log) {
			await this.tabLog.insertOne(log);
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.findLogs = async function (opts) {
			let queryVO,queryOpts;
			let csr,list,doc;
			queryVO={};
			queryOpts={};
			opts=opts||{limit:maxLiveLog};
			if(opts.actions){
				queryVO["log.action"]={$in:opts.actions};
			}else if(opts.action){
				queryVO["log.action"]=opts.action;
				
			}
			if(opts.catalogs){
				queryVO["log.catalog"]={$in:opts.catalogs};
			}else if(opts.catalog){
				queryVO["log.catalog"]=opts.catalog;
			}
			if(opts.startTime){
				let timeVO;
				timeVO=queryVO["time"]={}
				timeVO["$gte"]=opts.startTime;
			}
			if(opts.endTime){
				let timeVO;
				timeVO=queryVO["time"];
				if(!timeVO){
					timeVO=queryVO["time"]={}
				}
				timeVO["$lte"]=opts.endTime;
			}
			if(opts.from){
				queryVO["from"]=opts.from;
			}
			if(opts.limit){
				queryOpts.limit=opts.limit;
			}
			if(opts.sort){
				queryOpts.sort= {_id:opts.sort};
			}
			csr=await this.tabLog.find(queryVO,queryOpts);
			list=[];
			for await (doc of csr) {
				doc={...doc};
				delete doc._id;
				list.push(doc);
			}
			return list;
		};
	}
	
	//***********************************************************************
	//Chat flows:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaDataBaseMDB.loadLiveChatFlows=async function(){
			let csr,list,doc,time;
			time=Date.now()-24*2*3600*1000;
			csr=await this.tabMessage.find({closed:false,$gte:{createTime:time}},{sort:{id:1}});
			list=[];
			for await (doc of csr) {
				doc={...doc};
				delete doc._id;
				list.push(doc);
			}
			return list;
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.newChatFlow = async function (chatFlow) {
			await this.tabChatFlow.insertOne(chatFlow.genSaveVO());
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.setChatFlowTitle = async function (chatFlow,title) {
			await this.tabChatFlow.updateOne({id:chatFlow.id},{$set:{title:title}});
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.addChatFlowMessage = async function (chatFlow,message) {
			let flowId;
			flowId=chatFlow.id;
			await this.tabChatFlow.updateOne({id:flowId},{$push:{messages:message}});
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.closeChatFlow = async function (chatFlow) {
			let flowId;
			flowId=chatFlow.id;
			await this.tabChatFlow.updateOne({id:flowId},{$set:{closed:true}});
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.deleteChatFlow = async function (chatFlow) {
			await this.tabChatFlow.deleteOne({id:chatFlow.id});
		};

		//-------------------------------------------------------------------
		aaDataBaseMDB.addChatFlowAsk = async function (chatFlow,askId) {
			let flowId,askVO;
			flowId=chatFlow.id;
			askVO=chatFlow.asks[askId];
			await this.tabChatFlow.updateOne({id:flowId},{$push:{asks:askVO}});
		};

		//-------------------------------------------------------------------
		aaDataBaseMDB.closeChatFlowAsk = async function (chatFlow,askId) {
			let flowId,askVO;
			flowId=chatFlow.id;
			askVO=chatFlow.asks[askId];
			await this.tabChatFlow.updateOne({id:flowId},{$pull:{asks:{askId:askId}}});
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.addChatFlowLog = async function (chatFlow,log) {
			let flowId,askVO;
			flowId=chatFlow.id;
			await this.tabChatFlow.updateOne({id:flowId},{$push:{logs:log}});
		};
	}
	
	//***********************************************************************
	//Tasks:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaDataBaseMDB.newTaskId=async function(){
			let idVO;
			idVO=await this.tabSys.findOneAndUpdate({_id:"nextTaskId"},{'$inc':{id:1}});
			if(!idVO.ok){
				throw Error("AADataBase error: can't generate new task-id.");
			}
			idVO=idVO.value;
			return ""+(idVO.id);
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.loadOpenTaskReqs=async function(){
			let csr,list,doc;
			csr=await this.tabTaskReq.find({state:{$in:["WAIT","WORKING"]}},{sort:{id:1}});
			list=[];
			for await (doc of csr) {
				doc={...doc};
				delete doc._id;
				list.push(doc);
			}
			return list;
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.loadOpenTaskWorks=async function(){
			let csr,list,doc;
			csr=await this.tabTaskWork.find({state:{$in:["WAIT","WORKING"]}},{sort:{id:1}});
			list=[];
			for await (doc of csr) {
				doc={...doc};
				delete doc._id;
				list.push(doc);
			}
			return list;
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.getTaskReq=async function(taskId){
			let vo;
			vo=await this.tabTaskReq.findOne({id:taskId});
			return vo;
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.getTaskWork=async function(taskId){
			let vo;
			vo=await this.tabTaskWork.findOne({id:taskId});
			return vo;
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.saveTaskReq=async function(taskReq){
			let vo;
			vo=taskReq.genSaveVO();
			await this.tabTaskReq.updateOne({id:vo.id},vo,{upsert:true});
		};
		
		//-------------------------------------------------------------------
		aaDataBaseMDB.saveTaskWork=async function(taskWork){
			let vo;
			vo=taskWork.genSaveVO();
			await this.tabTaskWork.updateOne({id:vo.id},vo,{upsert:true});
		};
	}
}
