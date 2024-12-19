import { promises as fs, promises as tabFS } from 'fs'
import pathLib from 'path';
import {URL} from "url";

let AIQuery,aiQuery;
AIQuery=function(webRpa,session,context,agentPath,agentJaxId){
	if(agentPath[0]==="/" && agentPath[1]==="/"){
		agentPath=agentPath.substring(1);
	}else if(agentPath[0]==="/" && agentPath[1]==="~"){
		agentPath=agentPath.substring(2);
	}
	this.session=session;
	this.context=context;
	context.$aiQuery=this;
	this.agentPath=agentPath;
	this.agentJaxId=agentJaxId;
	this.webRpa=webRpa;
	this.queryMap=null;
};
aiQuery=AIQuery.prototype={};

//----------------------------------------------------------------------------
aiQuery.setup=async function(){
	let json;
	try{
		json=await tabFS.readFile(pathLib.join(this.agentPath,"querymap_"+this.agentJaxId+".json"),"utf8");
		json=JSON.parse(json);
		this.queryMap=json||{};
	}catch(err){
		this.queryMap={};
	}
};

//----------------------------------------------------------------------------
aiQuery.getQuery=async function(page,orgQuery,queryHint,segId){
	let node,query,queryMap,gctx,webRpa,logger;
	let pageQuery,url,parsedUrl;
	url=await page.url();
	parsedUrl = new URL(url);
	url=parsedUrl.host+parsedUrl.pathname;
	
	gctx=this.session.globalContext;
	webRpa=gctx.webRpa||gctx.RPA||this.webRpa;
	if(webRpa){
		logger=webRpa.logger;
	}
	queryMap=this.queryMap;
	pageQuery=queryMap[url];
	if(!pageQuery){
		pageQuery=queryMap[url]={};
	}
	query=pageQuery[queryHint]||orgQuery;
	node=null;
	if(query){
		try{
			node=await webRpa.queryNode(page,null,query,{});
		}catch(err){
			node=null;
		}
	}
	if(node){
		return query;
	}
	if(orgQuery && logger){
		logger.warn(`Query may broken: ${orgQuery} with hint: ${queryHint}.`);
	}
	query=await this.session.pipeChat("/@WebRpa/SmartQuery.js",{targetPage:page,query:queryHint,aaeId:null},false);
	if(query){
		pageQuery[queryHint]=query;
		//Save query map:
		await tabFS.writeFile(pathLib.join(this.agentPath,"querymap_"+this.agentJaxId+".json"),JSON.stringify(queryMap,null,"\t"),"utf8");
	}
	if(orgQuery && logger && (!query)){
		logger.warn(`Attempt to create (rebuild) query condition failed: ${orgQuery} with hint: ${queryHint}.`);
	}
	return query;
};

export {AIQuery};

