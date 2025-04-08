#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
from session import trimJSON
##{1ID3S33F20MoreImports#
from remotesession import RemoteSession
##}1ID3S33F20MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

argsTemplate={
	"properties":{
		"nodeName":{
			"name":"nodeName","type":"string",
			"label":"Agent Node",
			"defaultValue":"",
			"desc":"",
		},
		"callAgent":{
			"name":"callAgent","type":"string",
			"label":"Agent",
			"defaultValue":"",
			"desc":"",
		},
		"callArg":{
			"name":"callArg","type":"auto",
			"label":"Call argument(s)",
			"defaultValue":"",
			"desc":"",
		},
		"checkUpdate":{
			"name":"checkUpdate","type":"bool",
			"label":"Check Update",
			"defaultValue":"",
			"desc":"",
		},
		"options":{
			"name":"options","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	##{1ID3S33F20ArgsView#
	##}1ID3S33F20ArgsView#
}

##{1ID3S33F20StartDoc#
##}1ID3S33F20StartDoc#
##----------------------------------------------------------------------------
async def RemoteChat(session):
	nodeName=None
	callAgent=None
	callArg=None
	checkUpdate=None
	options=None
	
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	Exec = None
	##{1ID3S33F20LocalVals#
	##}1ID3S33F20LocalVals#
	
	
	def parseAgentArgs(input):
		nonlocal nodeName,callAgent,callArg,checkUpdate,options
		if isinstance(input, dict):
			nodeName=input.get("nodeName")
			callAgent=input.get("callAgent")
			callArg=input.get("callArg")
			checkUpdate=input.get("checkUpdate")
			options=input.get("options")
		else:
			nodeName=None
			callAgent=None
			callArg=None
			checkUpdate=None
			options=None
		##{1ID3S33F20ParseArgs#
		##}1ID3S33F20ParseArgs#
	
	##{1ID3S33F20PreContext#
	##}1ID3S33F20PreContext#
	globalContext = session.globalContext
	context = {}
	##{1ID3S33F20PostContext#
	##}1ID3S33F20PostContext#
	agent,segs = None, {}
	
	async def Exec_exec(input):#//:1ID3S3D7Q0
		result=input
		##{1ID3S3D7Q0Code#
		options=options or {}
		result=await RemoteSession.exec(session,nodeName,callAgent,callArg,{**options,"checkUpdate":checkUpdate});
		##}1ID3S3D7Q0Code#
		return {"result":result}
	segs["Exec"]=Exec={
		"exec":Exec_exec,
		"name":"Exec",
		"jaxId":"1ID3S3D7Q0",
		"url":"Exec@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1ID3S33F20PreEntry#
		##}1ID3S33F20PreEntry#
		result = {"seg":Exec,"input":input}
		##{1ID3S33F20PostEntry#
		##}1ID3S33F20PostEntry#
		return result
	agent = {
		"isAIAgent": true,
		"session": session,
		"name": "RemoteChat",
		"url": agentURL,
		"baseDir": basePath,
		"autoStart": true,
		"jaxId": "1ID3S33F20",
		"context": context,
		"livingSeg": None,
		"execChat": execAgent,
		##{1ID3S33F20MoreAgentAttrs#
		##}1ID3S33F20MoreAgentAttrs#
	}
	##{1ID3S33F20PostAgent#
	##}1ID3S33F20PostAgent#
	return agent
##{1ID3S33F20ExCodes#
##}1ID3S33F20ExCodes#

ChatAPI=[{
	"def":{
		"name": "RemoteChat",
		"description": "This is an AI agent.",
		"parameters":{
			"type": "object",
			"properties":{
				"nodeName":{"type":"string","description":""},
				"callAgent":{"type":"string","description":""},
				"callArg":{"type":"auto","description":""},
				"checkUpdate":{"type":"bool","description":""},
				"options":{"type":"auto","description":""}
			}
		}
	},
	"path": "/@tabos/RemoteChat.py",
	"label": "Remote Call",
	"agent": RemoteChat
}]

default=RemoteChat
__all__=["default","RemoteChat","ChatAPI"]
""">>>CodyExport
let ChatAPI,Exports;
ChatAPI=[{
	def:{
		name: "RemoteChat",
		description: "This is an AI agent.",
		parameters:{
			type: "object",
			properties:{
				nodeName:{type:"string",description:""},
				callAgent:{type:"string",description:""},
				callArg:{type:"auto",description:""},
				checkUpdate:{type:"bool",description:""},
				options:{type:"auto",description:""}
			}
		}
	},
	path: "/@tabos/RemoteChat.py",
	label: "Remote Call",
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
		name:"RemoteChat",showName:"Remote Call",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"nodeName":{name:"nodeName",showName:(($ln==="CN")?("代理节点"):("Agent Node")),type:"string",key:1,fixed:1,initVal:""},
			"callAgent":{name:"callAgent",showName:(($ln==="CN")?("代理"):("Agent")),type:"string",key:1,fixed:1,initVal:""},
			"callArg":{name:"callArg",showName:(($ln==="CN")?("调用参数"):("Call argument(s)")),type:"auto",key:1,fixed:1,initVal:""},
			"checkUpdate":{name:"checkUpdate",showName:(($ln==="CN")?("检查更新"):("Check Update")),type:"bool",key:1,fixed:1,initVal:""},
			"options":{name:"options",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","nodeName","callAgent","callArg","checkUpdate","options","codes","desc"],
		desc:"This is an AI agent."
	});
	
	DocPyAgentExporter.segTypeExporters["RemoteChat"]=
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
			coder.packText("args['nodeName']=");this.genAttrStatement(seg.getAttr("nodeName"));coder.newLine();
			coder.packText("args['callAgent']=");this.genAttrStatement(seg.getAttr("callAgent"));coder.newLine();
			coder.packText("args['callArg']=");this.genAttrStatement(seg.getAttr("callArg"));coder.newLine();
			coder.packText("args['checkUpdate']=");this.genAttrStatement(seg.getAttr("checkUpdate"));coder.newLine();
			coder.packText("args['options']=");this.genAttrStatement(seg.getAttr("options"));coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/@tabos/RemoteChat.py",args,false)`);coder.newLine();
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
#	"jaxId": "1ID3S33F20",
#	"attrs": {
#		"editObjs": {
#			"jaxId": "1ID3S33F21",
#			"attrs": {
#				"RemoteChat": {
#					"type": "objclass",
#					"def": "ObjClass",
#					"jaxId": "1ID3S33F30",
#					"attrs": {
#						"exportType": "UI Data Template",
#						"constructArgs": {
#							"jaxId": "1ID3S33F31",
#							"attrs": {}
#						},
#						"superClass": "",
#						"properties": {
#							"jaxId": "1ID3S33F32",
#							"attrs": {}
#						},
#						"functions": {
#							"jaxId": "1ID3S33F33",
#							"attrs": {}
#						},
#						"mockupOnly": "false",
#						"nullMockup": "false",
#						"exportClass": "false"
#					},
#					"mockups": {}
#				}
#			}
#		},
#		"agent": {
#			"jaxId": "1ID3S33F22",
#			"attrs": {}
#		},
#		"entry": "",
#		"autoStart": "true",
#		"inBrowser": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1ID3S33F23",
#			"attrs": {
#				"nodeName": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1ID3S994E0",
#					"attrs": {
#						"type": "String",
#						"mockup": "\"\"",
#						"desc": "",
#						"label": {
#							"type": "string",
#							"valText": "Agent Node",
#							"localize": {
#								"EN": "Agent Node",
#								"CN": "代理节点"
#							},
#							"localizable": true
#						}
#					}
#				},
#				"callAgent": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1ID3S994E1",
#					"attrs": {
#						"type": "String",
#						"mockup": "\"\"",
#						"desc": "",
#						"label": {
#							"type": "string",
#							"valText": "Agent",
#							"localize": {
#								"EN": "Agent",
#								"CN": "代理"
#							},
#							"localizable": true
#						}
#					}
#				},
#				"callArg": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1ID3S994E2",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "\"\"",
#						"desc": "",
#						"label": {
#							"type": "string",
#							"valText": "Call argument(s)",
#							"localize": {
#								"EN": "Call argument(s)",
#								"CN": "调用参数"
#							},
#							"localizable": true
#						}
#					}
#				},
#				"checkUpdate": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1ID3S994E3",
#					"attrs": {
#						"type": "Boolean",
#						"mockup": "\"\"",
#						"desc": "",
#						"label": {
#							"type": "string",
#							"valText": "Check Update",
#							"localize": {
#								"EN": "Check Update",
#								"CN": "检查更新"
#							},
#							"localizable": true
#						}
#					}
#				},
#				"options": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1INU07M7Q0",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "\"\"",
#						"desc": ""
#					}
#				}
#			}
#		},
#		"localVars": {
#			"jaxId": "1ID3S33F24",
#			"attrs": {}
#		},
#		"context": {
#			"jaxId": "1ID3S33F25",
#			"attrs": {}
#		},
#		"globalMockup": {
#			"jaxId": "1ID3S33F26",
#			"attrs": {}
#		},
#		"segs": {
#			"attrs": [
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1ID3S3D7Q0",
#					"attrs": {
#						"id": "Exec",
#						"viewName": "",
#						"label": "",
#						"x": "120",
#						"y": "110",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1ID3S994E4",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1ID3S994E5",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1ID3S994D0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						},
#						"result": "#input"
#					},
#					"icon": "tab_css.svg"
#				}
#			]
#		},
#		"desc": "This is an AI agent.",
#		"exportAPI": "true",
#		"exportAddOn": "true",
#		"addOnOpts": "{\"name\":\"\",\"label\":\"Remote Call\",\"path\":\"/@tabos/RemoteChat.py\",\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\"}"
#	}
#}