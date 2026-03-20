//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1JJ0HPTQ70MoreImports*/
/*}#1JJ0HPTQ70MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?decodeURI(baseURL):baseURL;
const $ln=VFACT.lanCode||"EN";
/*#{1JJ0HPTQ70StartDoc*/
function extractHtmlCodeBlocks(str) {
	const regex = /```html([\s\S]*?)```/g;
	const matches = [];
	let match;

	while ((match = regex.exec(str)) !== null) {
		matches.push(match[1].trim());
	}

	return matches;
}
/*}#1JJ0HPTQ70StartDoc*/
//----------------------------------------------------------------------------
let ShowOutput=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Output;
	/*#{1JJ0HPTQ70LocalVals*/
	/*}#1JJ0HPTQ70LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1JJ0HPTQ70ParseArgs*/
		/*}#1JJ0HPTQ70ParseArgs*/
	}
	
	/*#{1JJ0HPTQ70PreContext*/
	/*}#1JJ0HPTQ70PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1JJ0HPTQ70PostContext*/
	/*}#1JJ0HPTQ70PostContext*/
	let $agent,agent,segs={};
	segs["Output"]=Output=async function(input){//:1JJ0HPLRK0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		/*#{1JJ0HPLRK0PreCodes*/
		if(typeof(input) === 'object' && input.images && input.images.length > 0){
			content=input.content;
			if(input.content && input.content.length>0){
				session.addChatText(role,content,opts);
				let htmlCodes = extractHtmlCodeBlocks(content);
				for(const html of htmlCodes){
					await session.WSCall_WebSandbox(html);
				}
			}
			const images = input.images;
			let fileOpts = { channel: $channel }; 
			for(let i = 0; i < images.length; i ++){
				let image = images[i];
				if(image.type==="image_url"){
					const regex = /^data:image\/(\w+);base64,/;
					const data = image.image_url.url;
					if(data){
						last_generated_image=data;
						flag=true;
						const matches = data.match(regex);
						if (matches && matches.length === 2) {
							let saveName = `output_${Date.now()}_${i}.${matches[1]}`;
							let savedHubName = await session.saveHubFile(saveName, data);
							let hubUrl = "hub://" + savedHubName;
							fileOpts.image = hubUrl;
							session.addChatText(role, " ", fileOpts);
						}
					}
				}
			}
		}
		else{
			session.addChatText(role,content,opts);
			let htmlCodes = extractHtmlCodeBlocks(content);
				for(const html of htmlCodes){
					await session.WSCall_WebSandbox(html);
				}
		}
		return {result:result};
		/*}#1JJ0HPLRK0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JJ0HPLRK0PostCodes*/
		/*}#1JJ0HPLRK0PostCodes*/
		return {result:result};
	};
	Output.jaxId="1JJ0HPLRK0"
	Output.url="Output@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ShowOutput",
		url:agentURL,
		autoStart:true,
		jaxId:"1JJ0HPTQ70",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1JJ0HPTQ70PreEntry*/
			/*}#1JJ0HPTQ70PreEntry*/
			result={seg:Output,"input":input};
			/*#{1JJ0HPTQ70PostEntry*/
			/*}#1JJ0HPTQ70PostEntry*/
			return result;
		},
		/*#{1JJ0HPTQ70MoreAgentAttrs*/
		/*}#1JJ0HPTQ70MoreAgentAttrs*/
	};
	/*#{1JJ0HPTQ70PostAgent*/
	/*}#1JJ0HPTQ70PostAgent*/
	return agent;
};
/*#{1JJ0HPTQ70ExCodes*/
/*}#1JJ0HPTQ70ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1JJ0HPTQ70PostDoc*/
/*}#1JJ0HPTQ70PostDoc*/


export default ShowOutput;
export{ShowOutput};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JJ0HPTQ70",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JJ0HPTQ80",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1JJ0HPTQ81",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JJ0HPTQ82",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1JJ0HPTQ83",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JJ0HPTQ84",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JJ0HPTQ85",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JJ0HPLRK0",
//					"attrs": {
//						"id": "Output",
//						"viewName": "",
//						"label": "",
//						"x": "385",
//						"y": "350",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JJ0HPTQ86",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JJ0HPTQ87",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JJ0HPTQ71",
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