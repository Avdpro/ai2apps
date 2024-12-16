#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
##{1IDQ1CIS10MoreImports#
##}1IDQ1CIS10MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

##{1IDQ1CIS10StartDoc#
##}1IDQ1CIS10StartDoc#
##----------------------------------------------------------------------------
async def ChatDraw(session):
	execInput=None
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	AskDraw, Draw, ShowImage = None, None, None
	##{1IDQ1CIS10LocalVals#
	##}1IDQ1CIS10LocalVals#
	
	
	def parseAgentArgs(input):
		execInput=input
		##{1IDQ1CIS10ParseArgs#
		##}1IDQ1CIS10ParseArgs#
	
	##{1IDQ1CIS10PreContext#
	##}1IDQ1CIS10PreContext#
	globalContext = session.globalContext
	context = {}
	##{1IDQ1CIS10PostContext#
	##}1IDQ1CIS10PostContext#
	agent,segs = None, {}
	
	async def AskDraw_exec(input):#//:1IDQ1CRN00
		tip=(("你想画什么？") if(__Ln=="CN") else ("What do you want to draw?"))
		tipRole="assistant"
		prompt=undefined
		placeholder=""
		text=""
		result=""
		if tip:
			await session.addChatText(tipRole,tip,{})
		result=await session.askChatInput({"type":"input","prompt":prompt,"placeholder":placeholder,"text":text})
		await session.addChatText("user",result,{})
		return {"seg":Draw,"result":(result),"preSeg":"1IDQ1CRN00","outlet":"1IDQ1DUHR0"}
	segs["AskDraw"]=AskDraw={
		"exec":AskDraw_exec,
		"name":"AskDraw",
		"jaxId":"1IDQ1CRN00",
		"url":"AskDraw@"+agentURL
	}
	
	async def Draw_exec(input):#//:1IDQ1ECPH0
		result=None
		sourcePath=pathLib.join(basePath,"./DrawSD.py")
		arg={"drawPrompt":input,"model":"","device":""}
		result= await session.pipeChat(sourcePath,arg,false)
		return {"seg":ShowImage,"result":(result),"preSeg":"1IDQ1ECPH0","outlet":"1IDQ1ERAE0"}
	segs["Draw"]=Draw={
		"exec":Draw_exec,
		"name":"Draw",
		"jaxId":"1IDQ1ECPH0",
		"url":"Draw@"+agentURL
	}
	
	async def ShowImage_exec(input):#//:1IDQ1GL870
		result=input
		role="assistant"
		content="图片:"
		result=await session.resizeImage(result,512,"JPEG")
		await session.addChatText(role,content,{"image":result})
		return {"seg":AskDraw,"result":(result),"preSeg":"1IDQ1GL870","outlet":"1IDQ1HM5F0"}
	segs["ShowImage"]=ShowImage={
		"exec":ShowImage_exec,
		"name":"ShowImage",
		"jaxId":"1IDQ1GL870",
		"url":"ShowImage@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1IDQ1CIS10PreEntry#
		##}1IDQ1CIS10PreEntry#
		result = {"seg":AskDraw,"input":input}
		##{1IDQ1CIS10PostEntry#
		##}1IDQ1CIS10PostEntry#
		return result
	agent = {
		"isAIAgent": true,
		"session": session,
		"name": "ChatDraw",
		"url": agentURL,
		"baseDir": basePath,
		"autoStart": true,
		"jaxId": "1IDQ1CIS10",
		"context": context,
		"livingSeg": None,
		"execChat": execAgent,
		##{1IDQ1CIS10MoreAgentAttrs#
		##}1IDQ1CIS10MoreAgentAttrs#
	}
	##{1IDQ1CIS10PostAgent#
	##}1IDQ1CIS10PostAgent#
	return agent
##{1IDQ1CIS10ExCodes#
##}1IDQ1CIS10ExCodes#

ChatAPI=[{
	"def":{
		"name": "ChatDraw",
		"description": "这是一个AI智能体。",
		"parameters":{
			"type": "object",
			"properties":{
			}
		}
	},
	"agent": ChatDraw
}]

default=ChatDraw
__all__=["default","ChatDraw","ChatAPI"]
""">>>CodyExport
let ChatAPI,Exports;
ChatAPI=[{
	def:{
		name: "ChatDraw",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	agent: true
}];

//:Export Edit-AddOn:
const DocPyAgentExporter=VFACT.classRegs.DocPyAgentExporter;
if(DocPyAgentExporter){
	const $ln=VFACT.lanCode;
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
		name:"ChatDraw",showName:"ChatDraw",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocPyAgentExporter.segTypeExporters["ChatDraw"]=
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
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("ChatDraw.py",args,false)`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
			this.packResult(coder,seg,seg.outlet);
		}
		coder.indentLess();coder.maybeNewLine();
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
#	"jaxId": "1IDQ1CIS10",
#	"attrs": {
#		"editObjs": {
#			"jaxId": "1IDQ1CIS11",
#			"attrs": {
#				"ChatDraw": {
#					"type": "objclass",
#					"def": "ObjClass",
#					"jaxId": "1IDQ1CIS17",
#					"attrs": {
#						"exportType": "UI Data Template",
#						"constructArgs": {
#							"jaxId": "1IDQ1CIS18",
#							"attrs": {}
#						},
#						"superClass": "",
#						"properties": {
#							"jaxId": "1IDQ1CIS19",
#							"attrs": {}
#						},
#						"functions": {
#							"jaxId": "1IDQ1CIS110",
#							"attrs": {}
#						},
#						"mockupOnly": "false",
#						"nullMockup": "false"
#					},
#					"mockups": {}
#				}
#			}
#		},
#		"agent": {
#			"jaxId": "1IDQ1CIS12",
#			"attrs": {}
#		},
#		"entry": "",
#		"autoStart": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1IDQ1CIS13",
#			"attrs": {}
#		},
#		"localVars": {
#			"jaxId": "1IDQ1CIS14",
#			"attrs": {}
#		},
#		"context": {
#			"jaxId": "1IDQ1CIS15",
#			"attrs": {}
#		},
#		"globalMockup": {
#			"jaxId": "1IDQ1CIS16",
#			"attrs": {}
#		},
#		"segs": {
#			"attrs": [
#				{
#					"type": "aiseg",
#					"def": "askChat",
#					"jaxId": "1IDQ1CRN00",
#					"attrs": {
#						"id": "AskDraw",
#						"viewName": "",
#						"label": "",
#						"x": "165",
#						"y": "125",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDQ1DUHS0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDQ1DUHS1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"tip": {
#							"type": "string",
#							"valText": "What do you want to draw?",
#							"localize": {
#								"EN": "What do you want to draw?",
#								"CN": "你想画什么？"
#							},
#							"localizable": true
#						},
#						"tipRole": "Assistant",
#						"placeholder": "",
#						"text": "",
#						"file": "false",
#						"showText": "true",
#						"outlet": {
#							"jaxId": "1IDQ1DUHR0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDQ1ECPH0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "aiBot",
#					"jaxId": "1IDQ1ECPH0",
#					"attrs": {
#						"id": "Draw",
#						"viewName": "",
#						"label": "",
#						"x": "380",
#						"y": "125",
#						"desc": "调用其它AI Agent，把调用的结果作为输出",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDQ1ERAE1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDQ1ERAE2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"source": "ai/DrawSD.py",
#						"argument": "{\"drawPrompt\":\"#input\",\"model\":\"\",\"device\":\"\"}",
#						"secret": "false",
#						"outlet": {
#							"jaxId": "1IDQ1ERAE0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDQ1GL870"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IDQ1G8DK0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "715",
#						"y": "220",
#						"outlet": {
#							"jaxId": "1IDQ1HM5F1",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDQ1H4TS0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "image",
#					"jaxId": "1IDQ1GL870",
#					"attrs": {
#						"id": "ShowImage",
#						"viewName": "",
#						"label": "",
#						"x": "570",
#						"y": "125",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDQ1HM5F2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDQ1HM5F3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"text": "图片:",
#						"image": "#input",
#						"role": "Assistant",
#						"sizeLimit": "512",
#						"format": "JEPG",
#						"outlet": {
#							"jaxId": "1IDQ1HM5F0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDQ1G8DK0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IDQ1H4TS0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "195",
#						"y": "220",
#						"outlet": {
#							"jaxId": "1IDQ1HM5F4",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDQ1CRN00"
#						},
#						"dir": "R2L"
#					}
#				}
#			]
#		},
#		"desc": "这是一个AI智能体。",
#		"exportAPI": "true",
#		"exportAddOn": "true",
#		"addOnOpts": ""
#	}
#}