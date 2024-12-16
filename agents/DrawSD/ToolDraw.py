#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
##{1IDQ1SQTL0MoreImports#
##}1IDQ1SQTL0MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

argsTemplate={
	"properties":{
		"drawPrompt":{
			"name":"drawPrompt","type":"string",
			"defaultValue":"",
			"desc":"使用AI绘制的非自然语言的提示词，有必要的时候把用户的自然语言转为AI绘制提示词。",
		}
	},
	##{1IDQ1SQTL0ArgsView#
	##}1IDQ1SQTL0ArgsView#
}

##{1IDQ1SQTL0StartDoc#
##}1IDQ1SQTL0StartDoc#
##----------------------------------------------------------------------------
async def ToolDraw(session):
	drawPrompt=None
	
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	FixArg, Draw, ShowImage, SaveToHub = None, None, None, None
	##{1IDQ1SQTL0LocalVals#
	##}1IDQ1SQTL0LocalVals#
	
	
	def parseAgentArgs(input):
		nonlocal drawPrompt
		if isinstance(input, dict):
			drawPrompt=input.get("drawPrompt")
		else:
			drawPrompt=None
		##{1IDQ1SQTL0ParseArgs#
		##}1IDQ1SQTL0ParseArgs#
	
	##{1IDQ1SQTL0PreContext#
	##}1IDQ1SQTL0PreContext#
	globalContext = session.globalContext
	context = {}
	##{1IDQ1SQTL0PostContext#
	##}1IDQ1SQTL0PostContext#
	agent,segs = None, {}
	
	async def FixArg_exec(input):#//:1IDQ20AJT0
		result=None
		args={}
		args['argTemplate']=("") or argsTemplate
		args['command']=("") or input
		result= await session.pipeChat("/@tabos/FixArg.py",args,false)
		parseAgentArgs(result)
		return {"seg":Draw,"result":(result),"preSeg":"1IDQ20AJT0","outlet":"1IDQ22HL60"}
	segs["FixArg"]=FixArg={
		"name":"FixArg",
		"exec":FixArg_exec,
		"jaxId":"1IDQ20AJT0",
		"url":"FixArg@"+agentURL
	}
	
	async def Draw_exec(input):#//:1IDQ2188K0
		result=None
		sourcePath=pathLib.join(basePath,"./DrawSD.py")
		arg={"drawPrompt":drawPrompt,"model":"","device":""}
		result= await session.pipeChat(sourcePath,arg,false)
		return {"seg":ShowImage,"result":(result),"preSeg":"1IDQ2188K0","outlet":"1IDQ22HL61"}
	segs["Draw"]=Draw={
		"exec":Draw_exec,
		"name":"Draw",
		"jaxId":"1IDQ2188K0",
		"url":"Draw@"+agentURL
	}
	
	async def ShowImage_exec(input):#//:1IDQ23AIQ0
		result=input
		role="assistant"
		content="图片:"
		result=await session.resizeImage(result,512,"PNG")
		await session.addChatText(role,content,{"image":result})
		return {"seg":SaveToHub,"result":(result),"preSeg":"1IDQ23AIQ0","outlet":"1IDQ2BNVP0"}
	segs["ShowImage"]=ShowImage={
		"exec":ShowImage_exec,
		"name":"ShowImage",
		"jaxId":"1IDQ23AIQ0",
		"url":"ShowImage@"+agentURL
	}
	
	async def SaveToHub_exec(input):#//:1IDRQMT9Q0
		fileName="Image.png";
		content=input
		result=content
		##{1IDRQMT9Q0PreCodes#
		##}1IDRQMT9Q0PreCodes#
		fileName=pathLib.basename(fileName)
		##{1IDRQMT9Q0SaveData#
		##}1IDRQMT9Q0SaveData#
		result=await session.saveHubFile(fileName,content)
		##{1IDRQMT9Q0FinCodes#
		result="hub://"+result		
		result={
			"result":f"Done, file saved in: ${result}",
			"assets":[result]
		}
		##}1IDRQMT9Q0FinCodes#
		return {"result":result}
	segs["SaveToHub"]=SaveToHub={
		"exec":SaveToHub_exec,
		"name":"SaveToHub",
		"jaxId":"1IDRQMT9Q0",
		"url":"SaveToHub@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1IDQ1SQTL0PreEntry#
		##}1IDQ1SQTL0PreEntry#
		result = {"seg":FixArg,"input":input}
		##{1IDQ1SQTL0PostEntry#
		##}1IDQ1SQTL0PostEntry#
		return result
	agent = {
		"isAIAgent": true,
		"session": session,
		"name": "ToolDraw",
		"url": agentURL,
		"baseDir": basePath,
		"autoStart": true,
		"jaxId": "1IDQ1SQTL0",
		"context": context,
		"livingSeg": None,
		"execChat": execAgent,
		##{1IDQ1SQTL0MoreAgentAttrs#
		##}1IDQ1SQTL0MoreAgentAttrs#
	}
	##{1IDQ1SQTL0PostAgent#
	##}1IDQ1SQTL0PostAgent#
	return agent
##{1IDQ1SQTL0ExCodes#
##}1IDQ1SQTL0ExCodes#

ChatAPI=[{
	"def":{
		"name": "ToolDraw",
		"description": "Draw picture with Diffuser, Prompts should apply rule of AI-draw prompt.",
		"parameters":{
			"type": "object",
			"properties":{
				"drawPrompt":{"type":"string","description":"使用AI绘制的非自然语言的提示词，有必要的时候把用户的自然语言转为AI绘制提示词。"}
			}
		}
	},
	"agent": ToolDraw
}]

default=ToolDraw
__all__=["default","ToolDraw","ChatAPI"]
""">>>CodyExport
let ChatAPI,Exports;
ChatAPI=[{
	def:{
		name: "ToolDraw",
		description: "Draw picture with Diffuser, Prompts should apply rule of AI-draw prompt.",
		parameters:{
			type: "object",
			properties:{
				drawPrompt:{type:"string",description:"使用AI绘制的非自然语言的提示词，有必要的时候把用户的自然语言转为AI绘制提示词。"}
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
		name:"ToolDraw",showName:"ToolDraw",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"drawPrompt":{name:"drawPrompt",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","drawPrompt","codes","desc"],
		desc:"Draw picture with Diffuser, Prompts should apply rule of AI-draw prompt."
	});
	
	DocPyAgentExporter.segTypeExporters["ToolDraw"]=
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
			coder.packText("args['drawPrompt']=");this.genAttrStatement(seg.getAttr("drawPrompt"));coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("ToolDraw.py",args,false)`);coder.newLine();
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
#	"jaxId": "1IDQ1SQTL0",
#	"attrs": {
#		"editObjs": {
#			"jaxId": "1IDQ1SQTL1",
#			"attrs": {
#				"ToolDraw": {
#					"type": "objclass",
#					"def": "ObjClass",
#					"jaxId": "1IDQ1SQTM0",
#					"attrs": {
#						"exportType": "UI Data Template",
#						"constructArgs": {
#							"jaxId": "1IDQ1SQTM1",
#							"attrs": {}
#						},
#						"superClass": "",
#						"properties": {
#							"jaxId": "1IDQ1SQTM2",
#							"attrs": {}
#						},
#						"functions": {
#							"jaxId": "1IDQ1SQTM3",
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
#			"jaxId": "1IDQ1SQTL2",
#			"attrs": {}
#		},
#		"entry": "",
#		"autoStart": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1IDQ1SQTL3",
#			"attrs": {
#				"drawPrompt": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IDQ203SP0",
#					"attrs": {
#						"type": "String",
#						"mockup": "\"\"",
#						"desc": "使用AI绘制的非自然语言的提示词，有必要的时候把用户的自然语言转为AI绘制提示词。"
#					}
#				}
#			}
#		},
#		"localVars": {
#			"jaxId": "1IDQ1SQTL4",
#			"attrs": {}
#		},
#		"context": {
#			"jaxId": "1IDQ1SQTL5",
#			"attrs": {}
#		},
#		"globalMockup": {
#			"jaxId": "1IDQ1SQTL6",
#			"attrs": {}
#		},
#		"segs": {
#			"attrs": [
#				{
#					"type": "aiseg",
#					"def": "fixArgs",
#					"jaxId": "1IDQ20AJT0",
#					"attrs": {
#						"id": "FixArg",
#						"viewName": "",
#						"label": "",
#						"x": "115",
#						"y": "185",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDQ22HL62",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDQ22HL63",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"argTemplate": "\"\"",
#						"command": "\"\"",
#						"outlet": {
#							"jaxId": "1IDQ22HL60",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDQ2188K0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "aiBot",
#					"jaxId": "1IDQ2188K0",
#					"attrs": {
#						"id": "Draw",
#						"viewName": "",
#						"label": "",
#						"x": "330",
#						"y": "185",
#						"desc": "调用其它AI Agent，把调用的结果作为输出",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDQ22HL64",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDQ22HL65",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"source": "ai/DrawSD.py",
#						"argument": "{\"drawPrompt\":\"#drawPrompt\",\"model\":\"\",\"device\":\"\"}",
#						"secret": "false",
#						"outlet": {
#							"jaxId": "1IDQ22HL61",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDQ23AIQ0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "image",
#					"jaxId": "1IDQ23AIQ0",
#					"attrs": {
#						"id": "ShowImage",
#						"viewName": "",
#						"label": "",
#						"x": "530",
#						"y": "185",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDQ2BO000",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDQ2BO001",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"text": "图片:",
#						"image": "#input",
#						"role": "Assistant",
#						"sizeLimit": "512",
#						"format": "PNG",
#						"outlet": {
#							"jaxId": "1IDQ2BNVP0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDRQMT9Q0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "save",
#					"jaxId": "1IDRQMT9Q0",
#					"attrs": {
#						"id": "SaveToHub",
#						"viewName": "",
#						"label": "",
#						"x": "765",
#						"y": "185",
#						"desc": "这是一个AISeg。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDRQNS390",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDRQNS391",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"location": "Hub",
#						"fileName": "Image.png",
#						"target": "Input",
#						"format": "JSON",
#						"saveContext": {
#							"attrs": []
#						},
#						"outlet": {
#							"jaxId": "1IDRQNS360",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						}
#					}
#				}
#			]
#		},
#		"desc": "Draw picture with Diffuser, Prompts should apply rule of AI-draw prompt.",
#		"exportAPI": "true",
#		"exportAddOn": "true",
#		"addOnOpts": ""
#	}
#}