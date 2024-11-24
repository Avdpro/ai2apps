//***************************************************************************
//AAChatFlow
//***************************************************************************
const FlowCloseTime=5*60*1000;
let AAChatFlow,aaChatFlow;
AAChatFlow=function(flows,orgMsg,id,from){
	this.flows=flows;
	if(orgMsg) {
		this.from = orgMsg.from;
		this.title=null;
		this.id = id||orgMsg.id;
		this.createTime = orgMsg.time;
		this.messages = [orgMsg];
		this.logs = [];
		this.closing = false;
		this.closed = false;
		this.closeTimer = null;
		this.nextAskId = 1;
		this.asks = {};
	}else{
		this.from=from;
		this.title=null;
		this.id=id;
		this.createTime=Date.now();
		this.messages=[];
		this.logs=[];
		this.closing = false;
		this.closed = false;
		this.closeTimer = null;
		this.nextAskId = 1;
		this.asks = {};
	}
};
aaChatFlow=AAChatFlow.prototype={};

//---------------------------------------------------------------------------
aaChatFlow.addMessage=async function(msg){
	if(this.closed){
		return;
	}
	this.messages.push(msg);
	if(this.closing) {
		if (this.closeTimer) {
			clearTimeout(this.closeTimer);
		}
		this.closeTimer=setTimeout(()=>{
			this.closeTimer=null;
			this.close();
		},FlowCloseTime);
	}
	//TODO: Save to DB?
};

//---------------------------------------------------------------------------
aaChatFlow.addLog=async function(log){
	this.logs.push(log);
};

//---------------------------------------------------------------------------
aaChatFlow.trash=async function(){
	if(this.closing || this.closed){
		return;
	}
	this.closing=true;
	this.closeTimer=setTimeout(()=>{
		this.closeTimer=null;
		this.close();
	},FlowCloseTime);
};

//---------------------------------------------------------------------------
aaChatFlow.close=async function(){
	this.closed=true;
	if(this.closeTimer){
		clearTimeout(this.closeTimer);
		this.closeTimer=null;
	}
	this.flows.flowClosed(this.id);
};

//---------------------------------------------------------------------------
aaChatFlow.getStartRank=async function(){
	//TODO: Code this:
};

//---------------------------------------------------------------------------
aaChatFlow.getMaxRank=async function(){
	//TODO: Code this:
};

//---------------------------------------------------------------------------
aaChatFlow.newAsk=async function(msgVO){
	let askId;
	askId=""+(this.nextAskId++);
	this.asks[askId]=msgVO;
	msgVO.askId=askId;
	return askId;
};

//---------------------------------------------------------------------------
aaChatFlow.getAsk=async function(askId){
	return this.asks[askId];
};

//---------------------------------------------------------------------------
aaChatFlow.closeAsk=async function(askId){
	delete this.asks[askId];
};

//---------------------------------------------------------------------------
aaChatFlow.genSaveVO=function(){
	let vo,askId,asks,askList;
	vo={};
	vo.from=this.from;
	vo.id=this.id;
	vo.createTime=this.createTime;
	vo.messages=this.messages.slice(0);
	vo.logs=this.logs.slice(0);
	vo.closed=this.closed||this.closing;
	vo.nextAskId=this.nextAskId;
	askList=vo.asks=[];
	asks=this.asks;
	for(askId in asks){
		askList.push(asks[askId]);
	}
	return vo;
};

//---------------------------------------------------------------------------
aaChatFlow.loadFromVO=function(vo){
	let ask,asks,askList;
	this.from=vo.from;
	this.id=vo.id;
	this.createTime=vo.createTime;
	this.messages=vo.messages||[];
	this.logs=vo.logs||[];
	this.closed=vo.closed;
	this.nextAskId=vo.nextAskId||1;
	asks=this.asks={};
	askList=vo.asks;
	for(ask of askList){
		asks[ask.askId]=ask;
	}
};

//***************************************************************************
//AAChatFlows
//***************************************************************************
let AAChatFlows,aaChatFlows;
{
	AAChatFlows=function(msgSys){
		this.msgSys=msgSys;
		this.aaDB=msgSys.aaDB;
		this.flowMap=new Map();
	};
	aaChatFlows=AAChatFlows.prototype={};
	
	//----------------------------------------------------------------------
	aaChatFlows.loadFromDB=async function(){
		let aaDB,flowMap,flowList,flowVO,flow;
		aaDB=this.aaDB;
		flowMap=this.flowMap;
		flowList=await aaDB.loadLiveChatFlows();
		for(flowVO of flowList){
			flow=new new AAChatFlow(this);
			flow.loadFromVO(flowVO);
			flowMap.set(flow.id,flow);
		}
	};
	
	//----------------------------------------------------------------------
	aaChatFlows.newFlow=async function(orgMsg,id,from){
		let flow,flowId;
		if(orgMsg) {
			flowId = id||("" + orgMsg.id);//TODO: Make id?
			flow=new AAChatFlow(this,orgMsg,flowId);
			orgMsg.chatFlow=flowId;
		}else{
			flowId = id;
			flow=new AAChatFlow(this,null,flowId,from);
		}
		this.flowMap.set(flowId,flow);
		await this.aaDB.newChatFlow(flow);
		return flow;
	};
	
	//-----------------------------------------------------------------------
	aaChatFlows.getFlow=async function(id){
		return this.flowMap.get(id);
	};
	
	//-----------------------------------------------------------------------
	aaChatFlows.addMessage=async function(flowId,msgVO){
		let flow;
		flow=await this.getFlow(flowId);
		if(!flow){
			return;
		}
		msgVO.chatFlow=flowId;
		flow.addMessage(msgVO);
		await this.aaDB.addChatFlowMessage(flow,msgVO);
	};
	
	//-----------------------------------------------------------------------
	aaChatFlows.newAsk=async function(flowId,msgVO){
		let flow,askId;
		flow=await this.getFlow(flowId);
		if(!flow){
			return;
		}
		askId=await flow.newAsk(msgVO)
		await this.aaDB.addChatFlowAsk(flow,askId);
		return askId;
	};
	
	//-----------------------------------------------------------------------
	aaChatFlows.getAsk=async function(flowId,askId){
		let flow,askVO;
		flow=await this.getFlow(flowId);
		if(!flow){
			return;
		}
		askVO=await flow.getAsk(askId);
		return askVO;
	};
	
	//-----------------------------------------------------------------------
	aaChatFlows.closeAsk=async function(flowId,askId){
		let flow;
		flow=await this.getFlow(flowId);
		if(!flow){
			return;
		}
		await flow.closeAsk(askId);
		await this.aaDB.closeChatFlowAsk(flow,askId);
	};
	
	//-----------------------------------------------------------------------
	aaChatFlows.setFlowTitle=async function(id,title){
		let flow;
		flow=this.flowMap.get(id);
		if(!flow){
			return false;
		}
		flow.title=title;
		await this.aaDB.setChatFlowTitle(flow,title);
		return true;
	};
	

	//-----------------------------------------------------------------------
	aaChatFlows.closeFlow=async function(id){
		let flow;
		flow=this.flowMap.get(id);
		if(!flow){
			return false;
		}
		await flow.trash();
		await this.aaDB.closeChatFlow(flow);
		return true;
	};
	
	//-----------------------------------------------------------------------
	aaChatFlows.flowClosed=async function(id){
		let flow;
		flow=this.flowMap.get(id);
		if(!flow){
			return false;
		}
		this.flowMap.delete(id);
		return true;
	};
	
	//-----------------------------------------------------------------------
	aaChatFlows.deleteFlow=async function(id){
		let flow;
		flow=this.flowMap.get(id);
		if(!flow){
			return false;
		}
		this.flowMap.delete(id);
		await this.aaDB.deleteChatFlow(flow);
		return true;
	};
	
	//-----------------------------------------------------------------------
	AAChatFlows.setup=async function(msgSys,app,router,apiMap){
		let appFlows;
		appFlows=new AAChatFlows(msgSys);
		await appFlows.loadFromDB();
		
		//-------------------------------------------------------------------
		apiMap['AAEChatFlowsNewFlow']=async function(req,res,next){
			let reqVO,userId,flowId,flow;
			reqVO=req.body.vo;
			userId=reqVO.user||reqVO.userId;
			flowId=await msgSys.getNextMessageId();
			flow=await appFlows.newFlow(null,flowId,userId);
			res.json({ code: 200,id:flow.id,from:flow.from,messages:flow.messages});
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEChatFlowsGetFlow']=async function(req,res,next){
			let reqVO,flowId,flow;
			reqVO=req.body.vo;
			flowId=reqVO.flow||reqVO.chatFlow;
			flow=await appFlows.getFlow(flowId);
			if(!flow){
				res.json({ code: 404,info:"Flow not found."});
				return;
			}
			res.json({ code: 200,id:flow.id,from:flow.from,messages:flow.messages});
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEChatFlowsGetFlowLogs']=async function(req,res,next){
			let reqVO,flowId,flow;
			reqVO=req.body.vo;
			flowId=reqVO.flow||reqVO.chatFlow||reqVO.flowId;
			flow=await appFlows.getFlow(flowId);
			if(!flow){
				res.json({ code: 404,info:"Flow not found."});
				return;
			}
			res.json({ code: 200,id:flow.id,from:flow.from,logs:flow.logs});
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEChatFlowsSetTitle']=async function(req,res,next){
			let reqVO,flowId,flow;
			reqVO=req.body.vo;
			flowId=reqVO.flow;
			await appFlows.setFlowTitle(flowId,reqVO.title);
			res.json({ code: 200});
		};

		//-------------------------------------------------------------------
		apiMap['AAEChatFlowsCloseFlow']=async function(req,res,next){
			let reqVO,flowId,flow;
			reqVO=req.body.vo;
			flowId=reqVO.flow;
			await appFlows.closeFlow(flowId);
			res.json({ code: 200});
		};
		
		//-------------------------------------------------------------------
		apiMap['AAEChatFlowsDeleteFlow']=async function(req,res,next){
			let reqVO,flowId,flow;
			reqVO=req.body.vo;
			flowId=reqVO.flow;
			await appFlows.deleteFlow(flowId);
			res.json({ code: 200});
		};
		return appFlows;
	};

}

export default AAChatFlows;
export {AAChatFlow,AAChatFlows};