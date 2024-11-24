#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
##{1HIRHBGQ60MoreImports#
##}1HIRHBGQ60MoreImports#
__Ln="EN"#Active language
true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)
##{1HIRHBGQ60StartDoc#
##}1HIRHBGQ60StartDoc#
##----------------------------------------------------------------------------
async def agent(session):
	size=None
	
	context, globalContext = None, None
	self = None
	Greeting, UserInput, CallGPT, ShowResult, FixArgs, CA, Self = None, None, None, None, None, None, None
	##{1HIRHBGQ60LocalVals#
	##}1HIRHBGQ60LocalVals#
	
	
	def parseAgentArgs(input):
		if isinstance(input, dict):
			size=input["size"]
		else:
			size=None
		##{1HIRHBGQ60ParseArgs#
		##}1HIRHBGQ60ParseArgs#
	
	##{1HIRHBGQ60PreContext#
	##}1HIRHBGQ60PreContext#
	globalContext = session.globalContext
	context = {}
	##{1HIRHBGQ60PostContext#
	##}1HIRHBGQ60PostContext#
	agent,segs = None, {}
	
	async def Greeting_exec(input):#//:1ICKPAV920
		result=input
		role="assistant"
		content="Input something?"
		await session.addChatText(role,content,{})
		return {"seg":UserInput,"result":(result),"preSeg":"1ICKPAV920","outlet":"1ICKPDSLN0"}
	segs["Greeting"]=Greeting={
		"exec":Greeting_exec,
		"name":"Greeting",
		"jaxId":"1ICKPAV920",
		"url":"Greeting@"+agentURL
	}
	
	async def UserInput_exec(input):#//:1ICKPCQIL0
		prompt=undefined
		placeholder=""
		text=""
		result=""
		result=await session.askChatInput({"type":"input","prompt":prompt,"placeholder":placeholder,"text":text})
		await session.addChatText("user",result,{})
		return {"seg":CallGPT,"result":(result),"preSeg":"1ICKPCQIL0","outlet":"1ICKPDSLN1"}
	segs["UserInput"]=UserInput={
		"exec":UserInput_exec,
		"name":"UserInput",
		"jaxId":"1ICKPCQIL0",
		"url":"UserInput@"+agentURL
	}
	
	async def CallGPT_exec(input):#//:1ICKPD4790
		prompt=None
		result=None
		
		opts={
			"mode":"gpt-4o-mini",
			"maxToken":2000,
			"temperature":0,
			"topP":1,
			"fqcP":0,
			"prcP":0,
			"secret":false,
			"responseFormat":"text"
		}
		chatMem=CallGPT.get("messages",[])
		seed=""
		if(seed):
			opts.seed=seed
		messages=[
			{"role":"system","content":"You are a smart assistant."},
		]
		prompt=input
		if(prompt):
			messages.append({"role":"user","content":prompt})
		result=await session.callSegLLM("CallGPT@"+agentURL,opts,messages,true)
		return {"seg":ShowResult,"result":(result),"preSeg":"1ICKPD4790","outlet":"1ICKPDSLO0"}
	segs["CallGPT"]=CallGPT={
		"exec":CallGPT_exec,
		"name":"CallGPT",
		"jaxId":"1ICKPD4790",
		"url":"CallGPT@"+agentURL
	}
	
	async def ShowResult_exec(input):#//:1ICKPDIRL0
		result=input
		role="assistant"
		content=input
		await session.addChatText(role,content,{})
		return {"seg":UserInput,"result":(result),"preSeg":"1ICKPDIRL0","outlet":"1ICKPDSLO1"}
	segs["ShowResult"]=ShowResult={
		"exec":ShowResult_exec,
		"name":"ShowResult",
		"jaxId":"1ICKPDIRL0",
		"url":"ShowResult@"+agentURL
	}
	
	async def CA_exec(input):#//:1ICS38PT00
		result=None
		sourcePath=pathLib.join(basePath,"./agent.py")
		arg={"size":150}
		result= await session.pipeChat(sourcePath,arg,false)
		return {"result":result}
	segs["CA"]=CA={
		"exec":CA_exec,
		"name":"CA",
		"jaxId":"1ICS38PT00",
		"url":"CA@"+agentURL
	}
	
	async def Self_exec(input):#//:1ICS6UFFF0
		result=None
		args={}
		args['size']=100
		result= await session.pipeChat("agent.py",args,false)
		return {"result":result}
	
	segs["Self"]=Self={
		"name":"Self",
		"exec":Self_exec,
		"jaxId":"1ICS6UFFF0",
		"url":"Self@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1HIRHBGQ60PreEntry#
		##}1HIRHBGQ60PreEntry#
		result = {"seg":Greeting,"input":input}
		##{1HIRHBGQ60PostEntry#
		##}1HIRHBGQ60PostEntry#
		return result
	agent = {
		"isAIAgent": true,
		"session": session,
		"name": "agent",
		"url": agentURL,
		"autoStart": true,
		"jaxId": "1HIRHBGQ60",
		"context": context,
		"livingSeg": None,
		"execChat": execAgent,
		##{1HIRHBGQ60MoreAgentAttrs#
		##}1HIRHBGQ60MoreAgentAttrs#
	}
	##{1HIRHBGQ60PostAgent#
	##}1HIRHBGQ60PostAgent#
	return agent
##{1HIRHBGQ60ExCodes#
##}1HIRHBGQ60ExCodes#

ChatAPI=[{
	"def":{
		"name": "agent",
		"description": "这是一个AI代理。",
		"parameters":{
			"type": "object",
			"properties":{
				"size":{"type":"auto","description":""}
			}
		}
	},
	"agent": agent
}]

default=agent
__all__=["default","agent","ChatAPI"]
""">>>CodyExport
let ChatAPI,Exports;
ChatAPI=[{
	def:{
		name: "agent",
		description: "这是一个AI代理。",
		parameters:{
			type: "object",
			properties:{
				size:{type:"auto",description:""}
			}
		}
	},
	agent: true
}];

//:Export Edit-AddOn:
const DocPyAgentExporter=VFACT.classRegs.DocPyAgentExporter;
if(DocPyAgentExporter){
	const EditAttr=VFACT.classRegs.EditAttr;
	const EditAISeg=VFACT.classRegs.EditAISeg;
	const EditAISegOutlet=VFACT.classRegs.EditAISegOutlet;
	const SegObjShellAttr=EditAISeg.SegObjShellAttr;
	const SegOutletDef=EditAISegOutlet.SegOutletDef;
	const docPyAgentExporter=DocPyAgentExporter.prototype;
	const packExtraCodes=docPyAgentExporter.packExtraCodes;
	const packResult=docPyAgentExporter.packResult;
	const varNameRegex = /^[a-zA-Z_$][a-zA-Z0-9_$]*$/;
	
	EditAISeg.regDef({
		name:"agent",showName:"agent",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"size":{name:"size",type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","size","codes","desc"],
		desc:"这是一个AI代理。"
	});
	
	DocPyAgentExporter.segTypeExporters["agent"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`async def ${segName}_exec(input):#//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`result=None`);coder.newLine();
			coder.packText(`args={}`);coder.newLine();
			coder.packText("args['size']=");this.genAttrStatement(seg.getAttr("size"));coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("agent.py",args,false)`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
			this.packResult(coder,seg,seg.outlet);
		}
		coder.indentLess();coder.maybeNewLine();
		coder.newLine();
		coder.packText(`segs["${segName}"]=${segName}={`);
		coder.indentMore();coder.newLine();
		coder.packText(`"name":"${segName}",`);coder.newLine()
		coder.packText(`"exec":${segName}_exec,`);coder.newLine()
		coder.packText(`"jaxId":"${seg.jaxId}",`);coder.newLine()
		coder.packText(`"url":"${segName}@"+agentURL`);coder.newLine()
		coder.indentLess();coder.maybeNewLine();coder.packText("}");coder.newLine();
		coder.newLine();
	};
}

return {api:ChatAPI,export:Exports};
>>>CodyExport"""
#Cody Project Doc
#{
#	"type": "docfile",
#	"def": "DocAIAgent",
#	"jaxId": "1HIRHBGQ60",
#	"attrs": {
#		"editObjs": {
#			"jaxId": "1HIRHBM1Q0",
#			"attrs": {}
#		},
#		"agent": {
#			"jaxId": "1HIRHBM1R0",
#			"attrs": {}
#		},
#		"entry": "GetInput",
#		"autoStart": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1HIRHBM1R4",
#			"attrs": {
#				"size": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1ICS3SQVF0",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "\"\"",
#						"desc": ""
#					}
#				}
#			}
#		},
#		"localVars": {
#			"jaxId": "1HIRHBM1R1",
#			"attrs": {}
#		},
#		"context": {
#			"jaxId": "1HIRHBM1R2",
#			"attrs": {}
#		},
#		"globalMockup": {
#			"jaxId": "1HIRHBM1R3",
#			"attrs": {}
#		},
#		"segs": {
#			"attrs": [
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1ICKPAV920",
#					"attrs": {
#						"id": "Greeting",
#						"viewName": "",
#						"label": "",
#						"x": "115",
#						"y": "155",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1ICKPDSLQ0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1ICKPDSLQ1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "Input something?",
#						"outlet": {
#							"jaxId": "1ICKPDSLN0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1ICKPCQIL0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "askChat",
#					"jaxId": "1ICKPCQIL0",
#					"attrs": {
#						"id": "UserInput",
#						"viewName": "",
#						"label": "",
#						"x": "340",
#						"y": "155",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1ICKPDSLQ2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1ICKPDSLQ3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"tip": "",
#						"tipRole": "Assistant",
#						"placeholder": "",
#						"text": "",
#						"file": "false",
#						"showText": "true",
#						"outlet": {
#							"jaxId": "1ICKPDSLN1",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1ICKPD4790"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "callLLM",
#					"jaxId": "1ICKPD4790",
#					"attrs": {
#						"id": "CallGPT",
#						"viewName": "",
#						"label": "",
#						"x": "570",
#						"y": "155",
#						"desc": "执行一次LLM调用。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1ICKPDSLQ4",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1ICKPDSLQ5",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"platform": "OpenAI",
#						"mode": "gpt-4o-mini",
#						"system": "You are a smart assistant.",
#						"temperature": "0",
#						"maxToken": "2000",
#						"topP": "1",
#						"fqcP": "0",
#						"prcP": "0",
#						"messages": {
#							"attrs": []
#						},
#						"prompt": "#input",
#						"seed": "",
#						"outlet": {
#							"jaxId": "1ICKPDSLO0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1ICKPDIRL0"
#						},
#						"secret": "false",
#						"allowCheat": "false",
#						"GPTCheats": {
#							"attrs": []
#						},
#						"shareChatName": "",
#						"keepChat": "No",
#						"clearChat": "2",
#						"apiFiles": {
#							"attrs": []
#						},
#						"parallelFunction": "false",
#						"responseFormat": "text"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1ICKPDIRL0",
#					"attrs": {
#						"id": "ShowResult",
#						"viewName": "",
#						"label": "",
#						"x": "790",
#						"y": "155",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1ICKPDSLQ6",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1ICKPDSLQ7",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1ICKPDSLO1",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1ICUMSL620"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "fixArgs",
#					"jaxId": "1ICR4N3K80",
#					"attrs": {
#						"id": "FixArgs",
#						"viewName": "",
#						"label": "",
#						"x": "115",
#						"y": "235",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"outlet": {
#							"jaxId": "1ICR5TVNS0",
#							"attrs": {
#								"id": "Next",
#								"desc": "输出节点。"
#							}
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "aiBot",
#					"jaxId": "1ICS38PT00",
#					"attrs": {
#						"id": "CA",
#						"viewName": "",
#						"label": "",
#						"x": "320",
#						"y": "245",
#						"desc": "调用其它AI Agent，把调用的结果作为输出",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1ICS3DAP70",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1ICS3DAP71",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"source": "ai/agent.py",
#						"argument": "{\"size\":150}",
#						"secret": "false",
#						"outlet": {
#							"jaxId": "1ICS3CARD0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "agent",
#					"jaxId": "1ICS6UFFF0",
#					"attrs": {
#						"id": "Self",
#						"viewName": "",
#						"label": "",
#						"x": "105",
#						"y": "385",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1ICS760A50",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1ICS760A51",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"size": "100",
#						"outlet": {
#							"jaxId": "1ICS6UI7B0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1ICUMSL620",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "940",
#						"y": "55",
#						"outlet": {
#							"jaxId": "1ICUMSREB0",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1ICUMSOSL0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1ICUMSOSL0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "380",
#						"y": "55",
#						"outlet": {
#							"jaxId": "1ICUMSREB1",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1ICKPCQIL0"
#						},
#						"dir": "R2L"
#					}
#				}
#			]
#		},
#		"desc": "这是一个AI代理。",
#		"exportAPI": "true",
#		"exportAddOn": "true",
#		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\"}"
#	}
#}