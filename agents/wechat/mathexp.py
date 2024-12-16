#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
##{1IEJQB1RM0MoreImports#
from sympy import sympify
##}1IEJQB1RM0MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

argsTemplate={
	"properties":{
		"exp":{
			"name":"exp","type":"string",
			"defaultValue":"",
			"desc":"Python的通过SymPy执行的计算表达式",
		}
	},
	##{1IEJQB1RM0ArgsView#
	##}1IEJQB1RM0ArgsView#
}

##{1IEJQB1RM0StartDoc#
##}1IEJQB1RM0StartDoc#
##----------------------------------------------------------------------------
async def mathexp(session):
	exp=None
	
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	FixArg, ExecExp = None, None
	##{1IEJQB1RM0LocalVals#
	##}1IEJQB1RM0LocalVals#
	
	
	def parseAgentArgs(input):
		nonlocal exp
		if isinstance(input, dict):
			exp=input.get("exp")
		else:
			exp=None
		##{1IEJQB1RM0ParseArgs#
		##}1IEJQB1RM0ParseArgs#
	
	##{1IEJQB1RM0PreContext#
	##}1IEJQB1RM0PreContext#
	globalContext = session.globalContext
	context = {}
	##{1IEJQB1RM0PostContext#
	##}1IEJQB1RM0PostContext#
	agent,segs = None, {}
	
	async def FixArg_exec(input):#//:1IEJQBFDR0
		result=None
		args={}
		args['argTemplate']=(argsTemplate) or argsTemplate
		args['command']=(input) or input
		result= await session.pipeChat("/@tabos/FixArg.py",args,false)
		parseAgentArgs(result)
		return {"seg":ExecExp,"result":(result),"preSeg":"1IEJQBFDR0","outlet":"1IEJQDR2L1"}
	segs["FixArg"]=FixArg={
		"name":"FixArg",
		"exec":FixArg_exec,
		"jaxId":"1IEJQBFDR0",
		"url":"FixArg@"+agentURL
	}
	
	async def ExecExp_exec(input):#//:1IEJQB7SK0
		result=input
		##{1IEJQB7SK0Code#
		value=sympify(exp)
		try:
			# 尝试转为整数
			result=int(""+value)
		except (ValueError, TypeError):
			try:
				# 尝试转为浮点数
				result=float(value)
			except (ValueError, TypeError):
				result=f"{value}"
		return {"result":result}
		##}1IEJQB7SK0Code#
		return {"result":result}
	segs["ExecExp"]=ExecExp={
		"exec":ExecExp_exec,
		"name":"ExecExp",
		"jaxId":"1IEJQB7SK0",
		"url":"ExecExp@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1IEJQB1RM0PreEntry#
		##}1IEJQB1RM0PreEntry#
		result = {"seg":FixArg,"input":input}
		##{1IEJQB1RM0PostEntry#
		##}1IEJQB1RM0PostEntry#
		return result
	agent = {
		"isAIAgent": true,
		"session": session,
		"name": "mathexp",
		"url": agentURL,
		"baseDir": basePath,
		"autoStart": true,
		"jaxId": "1IEJQB1RM0",
		"context": context,
		"livingSeg": None,
		"execChat": execAgent,
		##{1IEJQB1RM0MoreAgentAttrs#
		##}1IEJQB1RM0MoreAgentAttrs#
	}
	##{1IEJQB1RM0PostAgent#
	##}1IEJQB1RM0PostAgent#
	return agent
##{1IEJQB1RM0ExCodes#
##}1IEJQB1RM0ExCodes#

ChatAPI=[{
	"def":{
		"name": "mathexp",
		"description": "这是进行算术计算的智能体，给出要计算的描述或Python的SymPy表达式，返回计算结果。对于有关算术的问题，包括比较数字大小，请使用本智能体获得正确结果。",
		"parameters":{
			"type": "object",
			"properties":{
				"exp":{"type":"string","description":"Python的通过SymPy执行的计算表达式"}
			}
		}
	},
	"agent": mathexp
}]

default=mathexp
__all__=["default","mathexp","ChatAPI"]
""">>>CodyExport
let ChatAPI,Exports;
ChatAPI=[{
	def:{
		name: "mathexp",
		description: "这是进行算术计算的智能体，给出要计算的描述或Python的SymPy表达式，返回计算结果。对于有关算术的问题，包括比较数字大小，请使用本智能体获得正确结果。",
		parameters:{
			type: "object",
			properties:{
				exp:{type:"string",description:"Python的通过SymPy执行的计算表达式"}
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
		name:"mathexp",showName:"mathexp",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"exp":{name:"exp",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","exp","codes","desc"],
		desc:"这是进行算术计算的智能体，给出要计算的描述或Python的SymPy表达式，返回计算结果。对于有关算术的问题，包括比较数字大小，请使用本智能体获得正确结果。"
	});
	
	DocPyAgentExporter.segTypeExporters["mathexp"]=
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
			coder.packText("args['exp']=");this.genAttrStatement(seg.getAttr("exp"));coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("mathexp.py",args,false)`);coder.newLine();
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
#	"jaxId": "1IEJQB1RM0",
#	"attrs": {
#		"editObjs": {
#			"jaxId": "1IEJQB1RN0",
#			"attrs": {
#				"mathexp": {
#					"type": "objclass",
#					"def": "ObjClass",
#					"jaxId": "1IEJQB1RN6",
#					"attrs": {
#						"exportType": "UI Data Template",
#						"constructArgs": {
#							"jaxId": "1IEJQB1RO0",
#							"attrs": {}
#						},
#						"superClass": "",
#						"properties": {
#							"jaxId": "1IEJQB1RO1",
#							"attrs": {}
#						},
#						"functions": {
#							"jaxId": "1IEJQB1RO2",
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
#			"jaxId": "1IEJQB1RN1",
#			"attrs": {}
#		},
#		"entry": "",
#		"autoStart": "true",
#		"inBrowser": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1IEJQB1RN2",
#			"attrs": {
#				"exp": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IEJQDR2O0",
#					"attrs": {
#						"type": "String",
#						"mockup": "\"\"",
#						"desc": "Python的通过SymPy执行的计算表达式"
#					}
#				}
#			}
#		},
#		"localVars": {
#			"jaxId": "1IEJQB1RN3",
#			"attrs": {}
#		},
#		"context": {
#			"jaxId": "1IEJQB1RN4",
#			"attrs": {}
#		},
#		"globalMockup": {
#			"jaxId": "1IEJQB1RN5",
#			"attrs": {}
#		},
#		"segs": {
#			"attrs": [
#				{
#					"type": "aiseg",
#					"def": "fixArgs",
#					"jaxId": "1IEJQBFDR0",
#					"attrs": {
#						"id": "FixArg",
#						"viewName": "",
#						"label": "",
#						"x": "105",
#						"y": "265",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJQDR2O3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJQDR2O4",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"argTemplate": "#argsTemplate",
#						"command": "#input",
#						"outlet": {
#							"jaxId": "1IEJQDR2L1",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJQB7SK0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEJQB7SK0",
#					"attrs": {
#						"id": "ExecExp",
#						"viewName": "",
#						"label": "",
#						"x": "315",
#						"y": "265",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJQDR2O1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJQDR2O2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJQDR2L0",
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
#		"desc": "这是进行算术计算的智能体，给出要计算的描述或Python的SymPy表达式，返回计算结果。对于有关算术的问题，包括比较数字大小，请使用本智能体获得正确结果。",
#		"exportAPI": "true",
#		"exportAddOn": "true",
#		"addOnOpts": ""
#	}
#}