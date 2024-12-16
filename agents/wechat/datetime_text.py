#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
##{1IEJRO8020MoreImports#
from datetime import datetime
import locale
##}1IEJRO8020MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

##{1IEJRO8020StartDoc#
def get_local_datetime():
	return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
##}1IEJRO8020StartDoc#
##----------------------------------------------------------------------------
async def datetime_text(session):
	execInput=None
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	GetDateTime = None
	##{1IEJRO8020LocalVals#
	##}1IEJRO8020LocalVals#
	
	
	def parseAgentArgs(input):
		execInput=input
		##{1IEJRO8020ParseArgs#
		##}1IEJRO8020ParseArgs#
	
	##{1IEJRO8020PreContext#
	##}1IEJRO8020PreContext#
	globalContext = session.globalContext
	context = {}
	##{1IEJRO8020PostContext#
	##}1IEJRO8020PostContext#
	agent,segs = None, {}
	
	async def GetDateTime_exec(input):#//:1IEJROB0V0
		result=input
		##{1IEJROB0V0Code#
		result=get_local_datetime()
		##}1IEJROB0V0Code#
		return {"result":result}
	segs["GetDateTime"]=GetDateTime={
		"exec":GetDateTime_exec,
		"name":"GetDateTime",
		"jaxId":"1IEJROB0V0",
		"url":"GetDateTime@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1IEJRO8020PreEntry#
		##}1IEJRO8020PreEntry#
		result = {"seg":GetDateTime,"input":input}
		##{1IEJRO8020PostEntry#
		##}1IEJRO8020PostEntry#
		return result
	agent = {
		"isAIAgent": true,
		"session": session,
		"name": "datetime_text",
		"url": agentURL,
		"baseDir": basePath,
		"autoStart": true,
		"jaxId": "1IEJRO8020",
		"context": context,
		"livingSeg": None,
		"execChat": execAgent,
		##{1IEJRO8020MoreAgentAttrs#
		##}1IEJRO8020MoreAgentAttrs#
	}
	##{1IEJRO8020PostAgent#
	##}1IEJRO8020PostAgent#
	return agent
##{1IEJRO8020ExCodes#
##}1IEJRO8020ExCodes#

ChatAPI=[{
	"def":{
		"name": "datetime_text",
		"description": "返回当前日期时间字符串的智能体",
		"parameters":{
			"type": "object",
			"properties":{
			}
		}
	},
	"agent": datetime_text
}]

default=datetime_text
__all__=["default","datetime_text","ChatAPI"]
""">>>CodyExport
let ChatAPI,Exports;
ChatAPI=[{
	def:{
		name: "datetime_text",
		description: "返回当前日期时间字符串的智能体",
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
		name:"datetime_text",showName:"datetime_text",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","codes","desc"],
		desc:"返回当前日期时间字符串的智能体"
	});
	
	DocPyAgentExporter.segTypeExporters["datetime_text"]=
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
			coder.packText(`result= await session.pipeChat("datetime_text.py",args,false)`);coder.newLine();
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
#	"jaxId": "1IEJRO8020",
#	"attrs": {
#		"editObjs": {
#			"jaxId": "1IEJRO8030",
#			"attrs": {
#				"datetime_text": {
#					"type": "objclass",
#					"def": "ObjClass",
#					"jaxId": "1IEJRO8036",
#					"attrs": {
#						"exportType": "UI Data Template",
#						"constructArgs": {
#							"jaxId": "1IEJRO8037",
#							"attrs": {}
#						},
#						"superClass": "",
#						"properties": {
#							"jaxId": "1IEJRO8038",
#							"attrs": {}
#						},
#						"functions": {
#							"jaxId": "1IEJRO8039",
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
#			"jaxId": "1IEJRO8031",
#			"attrs": {}
#		},
#		"entry": "",
#		"autoStart": "true",
#		"inBrowser": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1IEJRO8032",
#			"attrs": {}
#		},
#		"localVars": {
#			"jaxId": "1IEJRO8033",
#			"attrs": {}
#		},
#		"context": {
#			"jaxId": "1IEJRO8034",
#			"attrs": {}
#		},
#		"globalMockup": {
#			"jaxId": "1IEJRO8035",
#			"attrs": {}
#		},
#		"segs": {
#			"attrs": [
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEJROB0V0",
#					"attrs": {
#						"id": "GetDateTime",
#						"viewName": "",
#						"label": "",
#						"x": "115",
#						"y": "155",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJROOIA0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJROOIA1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJROMIT0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						},
#						"result": "#input"
#					}
#				}
#			]
#		},
#		"desc": "返回当前日期时间字符串的智能体",
#		"exportAPI": "true",
#		"exportAddOn": "true",
#		"addOnOpts": ""
#	}
#}