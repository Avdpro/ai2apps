#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
##{1IEJRGR8N0MoreImports#
from datetime import datetime
import locale
##}1IEJRGR8N0MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

##{1IEJRGR8N0StartDoc#
def get_local_datetime():
	locale.setlocale(locale.LC_TIME, '')
	return datetime.now().strftime('%c')
##}1IEJRGR8N0StartDoc#
##----------------------------------------------------------------------------
async def datetime(session):
	execInput=None
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	GetDateTime = None
	##{1IEJRGR8N0LocalVals#
	##}1IEJRGR8N0LocalVals#
	
	
	def parseAgentArgs(input):
		execInput=input
		##{1IEJRGR8N0ParseArgs#
		##}1IEJRGR8N0ParseArgs#
	
	##{1IEJRGR8N0PreContext#
	##}1IEJRGR8N0PreContext#
	globalContext = session.globalContext
	context = {}
	##{1IEJRGR8N0PostContext#
	##}1IEJRGR8N0PostContext#
	agent,segs = None, {}
	
	async def GetDateTime_exec(input):#//:1IEJRH0AK0
		result=input
		##{1IEJRH0AK0Code#
		result=get_local_datetime()
		##}1IEJRH0AK0Code#
		return {"result":result}
	segs["GetDateTime"]=GetDateTime={
		"exec":GetDateTime_exec,
		"name":"GetDateTime",
		"jaxId":"1IEJRH0AK0",
		"url":"GetDateTime@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1IEJRGR8N0PreEntry#
		##}1IEJRGR8N0PreEntry#
		result = {"seg":GetDateTime,"input":input}
		##{1IEJRGR8N0PostEntry#
		##}1IEJRGR8N0PostEntry#
		return result
	agent = {
		"isAIAgent": true,
		"session": session,
		"name": "datetime",
		"url": agentURL,
		"baseDir": basePath,
		"autoStart": true,
		"jaxId": "1IEJRGR8N0",
		"context": context,
		"livingSeg": None,
		"execChat": execAgent,
		##{1IEJRGR8N0MoreAgentAttrs#
		##}1IEJRGR8N0MoreAgentAttrs#
	}
	##{1IEJRGR8N0PostAgent#
	##}1IEJRGR8N0PostAgent#
	return agent
##{1IEJRGR8N0ExCodes#
##}1IEJRGR8N0ExCodes#

ChatAPI=[{
	"def":{
		"name": "datetime",
		"description": "返回当前日期时间字符串的智能体",
		"parameters":{
			"type": "object",
			"properties":{
			}
		}
	},
	"agent": datetime
}]

default=datetime
__all__=["default","datetime","ChatAPI"]
""">>>CodyExport
let ChatAPI,Exports;
ChatAPI=[{
	def:{
		name: "datetime",
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
		name:"datetime",showName:"datetime",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","codes","desc"],
		desc:"返回当前日期时间字符串的智能体"
	});
	
	DocPyAgentExporter.segTypeExporters["datetime"]=
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
			coder.packText(`result= await session.pipeChat("datetime.py",args,false)`);coder.newLine();
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
#	"jaxId": "1IEJRGR8N0",
#	"attrs": {
#		"editObjs": {
#			"jaxId": "1IEJRGR8N1",
#			"attrs": {
#				"datetime": {
#					"type": "objclass",
#					"def": "ObjClass",
#					"jaxId": "1IEJRGR8O0",
#					"attrs": {
#						"exportType": "UI Data Template",
#						"constructArgs": {
#							"jaxId": "1IEJRGR8O1",
#							"attrs": {}
#						},
#						"superClass": "",
#						"properties": {
#							"jaxId": "1IEJRGR8O2",
#							"attrs": {}
#						},
#						"functions": {
#							"jaxId": "1IEJRGR8O3",
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
#			"jaxId": "1IEJRGR8N2",
#			"attrs": {}
#		},
#		"entry": "",
#		"autoStart": "true",
#		"inBrowser": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1IEJRGR8N3",
#			"attrs": {}
#		},
#		"localVars": {
#			"jaxId": "1IEJRGR8N4",
#			"attrs": {}
#		},
#		"context": {
#			"jaxId": "1IEJRGR8N5",
#			"attrs": {}
#		},
#		"globalMockup": {
#			"jaxId": "1IEJRGR8N6",
#			"attrs": {}
#		},
#		"segs": {
#			"attrs": [
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEJRH0AK0",
#					"attrs": {
#						"id": "GetDateTime",
#						"viewName": "",
#						"label": "",
#						"x": "120",
#						"y": "140",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJRH8OU0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJRH8OU1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJRH8OT0",
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