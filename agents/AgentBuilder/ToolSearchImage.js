//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IO2H32QN0MoreImports*/
import axios from 'axios';
import querystring from 'querystring'
/*}#1IO2H32QN0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"query":{
			"name":"query","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"搜索图像的描述",
		},
		"top_k":{
			"name":"top_k","type":"integer",
			"required":false,
			"defaultValue":5,
			"desc":"要搜索的图片数量",
		}
	},
	/*#{1IO2H32QN0ArgsView*/
	/*}#1IO2H32QN0ArgsView*/
};

/*#{1IO2H32QN0StartDoc*/

function getUrlsAsString(nodes, separator = '\n') {
return nodes.map(node => node.url).join(separator);
}

class ImageSearchTool {
constructor(apiKey, searchEngineId) {
if (!apiKey || !searchEngineId) {
throw new Error('API key and search engine ID are required');
}

this.apiKey = apiKey;
this.searchEngineId = searchEngineId;
this.baseUrl = 'https://www.googleapis.com/customsearch/v1';
this.seenUrls = new Set();

}
async validateImage(url, proxies = {}) {
try {
const config = {
method: 'head',
timeout: 3000,
validateStatus: status => status >= 200 && status < 400
};

if (proxies && proxies.ip && proxies.port) {
config.proxy = {
protocol: "http",
host: proxies.ip,
port: proxies.port
};
}

await axios.get(url, config);
return true;
} catch (error) {
return false;
}
}
async fetchImageResults(params, proxies, page) {
try {
params.start = (page - 1) * 10 + 1;

const config = proxies && proxies.ip && proxies.port ? {
proxy: {
protocol: "http",
host: proxies.ip,
port: proxies.port
}
} : {};

const response = await axios.get(`${this.baseUrl}?${querystring.stringify(params)}`, config);
return response.data.items || [];
} catch (error) {
console.error(`Page ${page} request failed:`, error.message);
return [];
}
}
async searchImages(query, options = {}, proxies = {}) {
if (!query) throw new Error('Search query is required');

const totalRequested = options.num || 10;
const maxPages = Math.ceil(totalRequested / 10) + 2;
let validResults = [];

const params = {
q: encodeURIComponent(query),
key: this.apiKey,
cx: this.searchEngineId,
searchType: 'image',
num: 10,
safe: options.safeSearch || 'medium',
fields: 'items(link,title)'
};

if (options.fileType) params.fileType = options.fileType;
if (options.size) params.imgSize = options.size;

const pagePromises = [];
for (let page = 1; page <= maxPages && validResults.length < totalRequested; page++) {
pagePromises.push(this.fetchImageResults(params, proxies, page));
}

const allPages = await Promise.all(pagePromises);

for (const pageResults of allPages) {
if (validResults.length >= totalRequested) break;
const validationPromises = pageResults
.filter(item => item && !this.seenUrls.has(item.link))
.map(async item => {
const isValid = await this.validateImage(item.link, proxies);
if (isValid) {
this.seenUrls.add(item.link);
return {
url: item.link,
title: item.title || 'No title available'
};
}
return null;
});

const pageValidResults = (await Promise.all(validationPromises))
.filter(item => item !== null);

validResults.push(...pageValidResults);
}

return validResults.slice(0, totalRequested);
}
}

async function googleSearchImage(query, topk, apiKey, cx, proxies) {
try {
const imageSearch = new ImageSearchTool(apiKey, cx);
const results = await imageSearch.searchImages(query, {
num: Math.min(topk, 50),
size: 'medium',
fileType: 'jpg',
safeSearch: 'high'
}, proxies);

if (results.length < topk) {
const additionalResults = await imageSearch.searchImages(query, {
num: topk - results.length,
size: undefined,
fileType: undefined,
safeSearch: 'medium'
}, proxies);

results.push(...additionalResults);
}

return results.slice(0, topk);
} catch (error) {
console.error('Error:', error.message);
return [];
}
}



/*}#1IO2H32QN0StartDoc*/
//----------------------------------------------------------------------------
let ToolSearchImage=async function(session){
	let query,top_k;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,SearchImage,output;
	/*#{1IO2H32QN0LocalVals*/
	/*}#1IO2H32QN0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			query=input.query;
			top_k=input.top_k;
		}else{
			query=undefined;
			top_k=undefined;
		}
		/*#{1IO2H32QN0ParseArgs*/
		/*}#1IO2H32QN0ParseArgs*/
	}
	
	/*#{1IO2H32QN0PreContext*/
	/*}#1IO2H32QN0PreContext*/
	context={};
	/*#{1IO2H32QN0PostContext*/
	/*}#1IO2H32QN0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IO2HTKPE0
		let result=input;
		let missing=false;
		if(query===undefined || query==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:SearchImage,result:(result),preSeg:"1IO2HTKPE0",outlet:"1IO2HUVR50"};
	};
	FixArgs.jaxId="1IO2HTKPE0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["SearchImage"]=SearchImage=async function(input){//:1IO2I6PQN0
		let result=input
		/*#{1IO2I6PQN0Code*/
		let hubJSON,apis,searchApiKey;
		hubJSON=session.agentNode.hubJSON;
		if(hubJSON){
			apis=hubJSON.api_keys;
			if(apis){
				searchApiKey=apis.google_search;
			}
		}
		result=await googleSearchImage(query,top_k,searchApiKey.key,searchApiKey.cx,hubJSON.proxies);
		/*}#1IO2I6PQN0Code*/
		return {seg:output,result:(result),preSeg:"1IO2I6PQN0",outlet:"1IO2I71L50"};
	};
	SearchImage.jaxId="1IO2I6PQN0"
	SearchImage.url="SearchImage@"+agentURL
	
	segs["output"]=output=async function(input){//:1IO2JVJHU0
		let result=input;
		let opts={};
		let role="assistant";
		let content=`成功获取到了图片。下面是${top_k}张图片的URL\n${getUrlsAsString(input)}`;
		/*#{1IO2JVJHU0PreCodes*/
		/*}#1IO2JVJHU0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IO2JVJHU0PostCodes*/
		result=`成功获取到了图片。下面是${top_k}张${query}的图片的URL\n` + getUrlsAsString(result);
		/*}#1IO2JVJHU0PostCodes*/
		return {result:result};
	};
	output.jaxId="1IO2JVJHU0"
	output.url="output@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ToolSearchImage",
		url:agentURL,
		autoStart:true,
		jaxId:"1IO2H32QN0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{query,top_k}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IO2H32QN0PreEntry*/
			/*}#1IO2H32QN0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IO2H32QN0PostEntry*/
			/*}#1IO2H32QN0PostEntry*/
			return result;
		},
		/*#{1IO2H32QN0MoreAgentAttrs*/
		/*}#1IO2H32QN0MoreAgentAttrs*/
	};
	/*#{1IO2H32QN0PostAgent*/
	/*}#1IO2H32QN0PostAgent*/
	return agent;
};
/*#{1IO2H32QN0ExCodes*/
/*}#1IO2H32QN0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IO2H32QN0PostDoc*/
/*}#1IO2H32QN0PostDoc*/


export default ToolSearchImage;
export{ToolSearchImage};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IO2H32QN0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IO2HUVR90",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1IO2HTT6O0",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IO2HUVR91",
//			"attrs": {
//				"query": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IO2HUVR92",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "搜索图像的描述",
//						"label": "",
//						"required": "true"
//					}
//				},
//				"top_k": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IO2I32VF0",
//					"attrs": {
//						"type": "Integer",
//						"mockup": "5",
//						"desc": "要搜索的图片数量",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IO2HUVR93",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IO2HUVR94",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IO2HUVR95",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IO2HTKPE0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "200",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IO2HUVR50",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IO2I6PQN0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IO2I6PQN0",
//					"attrs": {
//						"id": "SearchImage",
//						"viewName": "",
//						"label": "",
//						"x": "425",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IO2I9VIF0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IO2I9VIF1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IO2I71L50",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IO2JVJHU0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IO2JVJHU0",
//					"attrs": {
//						"id": "output",
//						"viewName": "",
//						"label": "",
//						"x": "655",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IO2K1NC30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IO2K1NC31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`成功获取到了图片。下面是${top_k}张图片的URL\\n${getUrlsAsString(input)}`",
//						"outlet": {
//							"jaxId": "1IO2K1NBL0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}