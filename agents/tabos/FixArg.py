#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
from session import trimJSON
##{1ID42HC6Q0MoreImports#
from session import trimJSON 
##}1ID42HC6Q0MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

argsTemplate={
	"properties":{
		"argTemplate":{
			"name":"argTemplate","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"command":{
			"name":"command","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	##{1ID42HC6Q0ArgsView#
	##}1ID42HC6Q0ArgsView#
}

##{1ID42HC6Q0StartDoc#
##}1ID42HC6Q0StartDoc#
##----------------------------------------------------------------------------
async def FixArg(session):
	argTemplate=None
	command=None
	
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	CheckCommand, CallGPT, HasMissing, Done, InputArgs = None, None, None, None, None
	##{1ID42HC6Q0LocalVals#
	##}1ID42HC6Q0LocalVals#
	
	
	def parseAgentArgs(input):
		nonlocal argTemplate,command
		if isinstance(input, dict):
			argTemplate=input.get("argTemplate")
			command=input.get("command")
		else:
			argTemplate=None
			command=None
		##{1ID42HC6Q0ParseArgs#
		if command is None and isinstance(input,str):
			command=input
		##}1ID42HC6Q0ParseArgs#
	
	##{1ID42HC6Q0PreContext#
	##}1ID42HC6Q0PreContext#
	globalContext = session.globalContext
	context = {
		"args":""
	}
	##{1ID42HC6Q0PostContext#
	##}1ID42HC6Q0PostContext#
	agent,segs = None, {}
	
	async def CheckCommand_exec(input):#//:1ID42IJ6S0
		if command and isinstance(command, str):
			return {"seg":CallGPT,"result":(input),"preSeg":"1ID42IJ6S0","outlet":"1ID42JIAC0"}
		if isinstance(command,dict):
			output=command
			context["args"]=command;
			return {"seg":HasMissing,"result":(output),"preSeg":"1ID42IJ6S0","outlet":"1ID6H1N7K0"}
		#default/else:
		return {"seg":InputArgs,"result":(input),"preSeg":"1ID42IJ6S0","outlet":"1ID42JIAC1"}
	segs["CheckCommand"]=CheckCommand={
		"exec":CheckCommand_exec,
		"name":"CheckCommand",
		"jaxId":"1ID42IJ6S0",
		"url":"CheckCommand@"+agentURL
	}
	
	async def CallGPT_exec(input):#//:1ID42M5R60
		prompt=None
		result=None
		##{1ID42M5R60Input#
		##}1ID42M5R60Input#
		
		opts={
			"mode":"gpt-4o",
			"maxToken":3800,
			"temperature":0,
			"topP":1,
			"fqcP":0,
			"prcP":0,
			"secret":false,
			"responseFormat":"json_object"
		}
		chatMem=CallGPT.get("messages",[])
		seed=""
		if(seed):
			opts.seed=seed
		messages=[
			{"role":"system","content":f"""
你是一个解析自然语言命令，生成函数调用参数的AI
- 用户会输入要调用的函数的参数描述以及自然语言命令。

- 函数参数描述是以JSON形式提供，例如
{{
	"name":{{
		"name":"name","type":"string",
		"defaultValue":"",
		"desc":"User name used in this site."
	}},
	"gender":{{
		"name":"gender","type":"string",
		"defaultValue":"Male",
		"desc":"User gender."
	}}
}}

- 请根据函数参数JSON，分析用户的自然语言指令，生成调用函数的参数VO，用JSON回答。例如：
{{
	"name":"Alex",
    "gender":"Male"
}}

- 如果你无法确定某些参数的内容，请用字符串"$$MISSING"作为参数值.例如，如果你不能确定gender属性：：
{{
	"name":"Alex",
    "gender":"$$MISSING"
}}
"""},
		]
		##{1ID42M5R60PrePrompt#
		##}1ID42M5R60PrePrompt#
		prompt=f"""
函数参数JSON：
{json.dumps(argTemplate.get("properties",{}),indent=4)}
自然语言指令：{command}
"""
		if(prompt):
			if not isinstance(prompt,str):
				prompt=json.dumps(prompt,indent=4)
			messages.append({"role":"user","content":prompt})
		##{1ID42M5R60PreCall#
		##}1ID42M5R60PreCall#
		result=(await session.callSegLLM("CallGPT@"+agentURL,opts,messages,true)) if (not result) else result
		result=trimJSON(result)
		##{1ID42M5R60PostCall#
		context["args"]=result
		##}1ID42M5R60PostCall#
		return {"seg":HasMissing,"result":(result),"preSeg":"1ID42M5R60","outlet":"1ID42N3FF0"}
	segs["CallGPT"]=CallGPT={
		"exec":CallGPT_exec,
		"name":"CallGPT",
		"jaxId":"1ID42M5R60",
		"url":"CallGPT@"+agentURL
	}
	
	async def HasMissing_exec(input):#//:1ID42ODO30
		##{1ID42ODO30Start#
		hasMissing=False
		pptDefs=argTemplate.get("properties",{})
		
		for key in list(input.keys()):
			value=input[key]
			if value=="$$MISSING":
				input.pop(key,None)
				if pptDefs.get(key,{}).get("required")!=False:
					hasMissing=True
		##}1ID42ODO30Start#
		if not hasMissing:
			return {"seg":Done,"result":(input),"preSeg":"1ID42ODO30","outlet":"1ID42P0370"}
		##{1ID42ODO30Post#
		##}1ID42ODO30Post#
		#default/else:
		return {"seg":InputArgs,"result":(input),"preSeg":"1ID42ODO30","outlet":"1ID42P0371"}
	segs["HasMissing"]=HasMissing={
		"exec":HasMissing_exec,
		"name":"HasMissing",
		"jaxId":"1ID42ODO30",
		"url":"HasMissing@"+agentURL
	}
	
	async def Done_exec(input):#//:1ID42PMCH0
		result=input
		##{1ID42PMCH0Code#
		##}1ID42PMCH0Code#
		return {"result":result}
	segs["Done"]=Done={
		"exec":Done_exec,
		"name":"Done",
		"jaxId":"1ID42PMCH0",
		"url":"Done@"+agentURL
	}
	
	async def InputArgs_exec(input):#//:1ID42QILS0
		role="assistant"
		text=(("完善智能体调用参数:") if(__Ln=="CN") else ("Complete agent arguments:"))
		template=argTemplate
		data=context["args"]
		edit=true
		resultText=""
		result=""
		inputVO={"template":template,"data":data,"options":{edit:edit}};
		[resultText,result]=await session.askUserRaw({"type":"object","text":text,"object":data,"template":template,"role":role,"edit":edit});
		return {"result":result}
	segs["InputArgs"]=InputArgs={
		"exec":InputArgs_exec,
		"name":"InputArgs",
		"jaxId":"1ID42QILS0",
		"url":"InputArgs@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1ID42HC6Q0PreEntry#
		##}1ID42HC6Q0PreEntry#
		result = {"seg":CheckCommand,"input":input}
		##{1ID42HC6Q0PostEntry#
		##}1ID42HC6Q0PostEntry#
		return result
	agent = {
		"isAIAgent": true,
		"session": session,
		"name": "FixArg",
		"url": agentURL,
		"baseDir": basePath,
		"autoStart": true,
		"jaxId": "1ID42HC6Q0",
		"context": context,
		"livingSeg": None,
		"execChat": execAgent,
		##{1ID42HC6Q0MoreAgentAttrs#
		##}1ID42HC6Q0MoreAgentAttrs#
	}
	##{1ID42HC6Q0PostAgent#
	##}1ID42HC6Q0PostAgent#
	return agent
##{1ID42HC6Q0ExCodes#
##}1ID42HC6Q0ExCodes#

ChatAPI=[{
	"def":{
		"name": "FixArg",
		"description": "这是一个AI智能体。",
		"parameters":{
			"type": "object",
			"properties":{
				"argTemplate":{"type":"auto","description":""},
				"command":{"type":"auto","description":""}
			}
		}
	},
	"path": "/@tabos/FixArg.py",
	"label": ">#(($ln===\"CN\")?(\"修正参数\"):/*EN*/(\"Fix arguments\"))",
	"agent": FixArg
}]

default=FixArg
__all__=["default","FixArg","ChatAPI"]
""">>>CodyExport
let ChatAPI,Exports;
ChatAPI=[{
	def:{
		name: "FixArg",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				argTemplate:{type:"auto",description:""},
				command:{type:"auto",description:""}
			}
		}
	},
	path: "/@tabos/FixArg.py",
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
		name:"fixArgs",showName:(($ln==="CN")?("修正参数"):/*EN*/("Fix arguments")),icon:"args.svg",catalog:["Code"],
		attrs:{
			...SegObjShellAttr,
			"argTemplate":{name:"argTemplate",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"command":{name:"command",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","argTemplate","command","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocPyAgentExporter.segTypeExporters["fixArgs"]=
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
			coder.packText("args['argTemplate']=");this.genAttrStatement(seg.getAttr("argTemplate"));coder.newLine();
			coder.packText("args['command']=");this.genAttrStatement(seg.getAttr("command"));coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/@tabos/FixArg.py",args,false)`);coder.newLine();
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
#	"jaxId": "1ID42HC6Q0",
#	"attrs": {
#		"editObjs": {
#			"jaxId": "1ID42HC6Q1",
#			"attrs": {
#				"FixArg": {
#					"type": "objclass",
#					"def": "ObjClass",
#					"jaxId": "1ID42HC6R0",
#					"attrs": {
#						"exportType": "UI Data Template",
#						"constructArgs": {
#							"jaxId": "1ID42HC6R1",
#							"attrs": {}
#						},
#						"superClass": "",
#						"properties": {
#							"jaxId": "1ID42HC6R2",
#							"attrs": {}
#						},
#						"functions": {
#							"jaxId": "1ID42HC6R3",
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
#			"jaxId": "1ID42HC6Q2",
#			"attrs": {}
#		},
#		"entry": "",
#		"autoStart": "true",
#		"inBrowser": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1ID42HC6Q3",
#			"attrs": {
#				"argTemplate": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1ID42LD270",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "\"\"",
#						"desc": ""
#					}
#				},
#				"command": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1ID42LD271",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "\"\"",
#						"desc": ""
#					}
#				}
#			}
#		},
#		"localVars": {
#			"jaxId": "1ID42HC6Q4",
#			"attrs": {}
#		},
#		"context": {
#			"jaxId": "1ID42HC6Q5",
#			"attrs": {
#				"args": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1ID42UIBH0",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "\"\"",
#						"desc": ""
#					}
#				}
#			}
#		},
#		"globalMockup": {
#			"jaxId": "1ID42HC6Q6",
#			"attrs": {}
#		},
#		"segs": {
#			"attrs": [
#				{
#					"type": "aiseg",
#					"def": "brunch",
#					"jaxId": "1ID42IJ6S0",
#					"attrs": {
#						"id": "CheckCommand",
#						"viewName": "",
#						"label": "",
#						"x": "65",
#						"y": "140",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1ID42JIAD0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1ID42JIAD1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1ID42JIAC1",
#							"attrs": {
#								"id": "Default",
#								"desc": "输出节点。",
#								"output": ""
#							},
#							"linkedSeg": "1ID42QILS0"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1ID42JIAC0",
#									"attrs": {
#										"id": "HasArg",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1ID42JIAD2",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1ID42JIAD3",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#command and isinstance(command, str)"
#									},
#									"linkedSeg": "1ID42M5R60"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1ID6H1N7K0",
#									"attrs": {
#										"id": "IsDict",
#										"desc": "输出节点。",
#										"output": "#command",
#										"codes": "false",
#										"context": {
#											"jaxId": "1ID6H1N7Q0",
#											"attrs": {
#												"cast": "{\"args\":\"#command\"}"
#											}
#										},
#										"global": {
#											"jaxId": "1ID6H1N7Q1",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#isinstance(command,dict)"
#									},
#									"linkedSeg": "1ID6H35110"
#								}
#							]
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "callLLM",
#					"jaxId": "1ID42M5R60",
#					"attrs": {
#						"id": "CallGPT",
#						"viewName": "",
#						"label": "",
#						"x": "315",
#						"y": "85",
#						"desc": "执行一次LLM调用。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1ID42N3FG0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1ID42N3FG1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"platform": "\"OpenAI\"",
#						"mode": "gpt-4o",
#						"system": "#f\"\"\"\n你是一个解析自然语言命令，生成函数调用参数的AI\n- 用户会输入要调用的函数的参数描述以及自然语言命令。\n\n- 函数参数描述是以JSON形式提供，例如\n{{\n\t\"name\":{{\n\t\t\"name\":\"name\",\"type\":\"string\",\n\t\t\"defaultValue\":\"\",\n\t\t\"desc\":\"User name used in this site.\"\n\t}},\n\t\"gender\":{{\n\t\t\"name\":\"gender\",\"type\":\"string\",\n\t\t\"defaultValue\":\"Male\",\n\t\t\"desc\":\"User gender.\"\n\t}}\n}}\n\n- 请根据函数参数JSON，分析用户的自然语言指令，生成调用函数的参数VO，用JSON回答。例如：\n{{\n\t\"name\":\"Alex\",\n    \"gender\":\"Male\"\n}}\n\n- 如果你无法确定某些参数的内容，请用字符串\"$$MISSING\"作为参数值.例如，如果你不能确定gender属性：：\n{{\n\t\"name\":\"Alex\",\n    \"gender\":\"$$MISSING\"\n}}\n\"\"\"",
#						"temperature": "0",
#						"maxToken": "3800",
#						"topP": "1",
#						"fqcP": "0",
#						"prcP": "0",
#						"messages": {
#							"attrs": []
#						},
#						"prompt": "#f\"\"\"\n函数参数JSON：\n{json.dumps(argTemplate.get(\"properties\",{}),indent=4)}\n自然语言指令：{command}\n\"\"\"",
#						"seed": "",
#						"outlet": {
#							"jaxId": "1ID42N3FF0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1ID42ODO30"
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
#						"responseFormat": "json_object",
#						"formatDef": "\"\""
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "brunch",
#					"jaxId": "1ID42ODO30",
#					"attrs": {
#						"id": "HasMissing",
#						"viewName": "",
#						"label": "",
#						"x": "530",
#						"y": "85",
#						"desc": "这是一个AISeg。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1ID42P0372",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1ID42P0373",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1ID42P0371",
#							"attrs": {
#								"id": "Default",
#								"desc": "输出节点。",
#								"output": ""
#							},
#							"linkedSeg": "1ID42QILS0"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1ID42P0370",
#									"attrs": {
#										"id": "NoMissing",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1ID42P0374",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1ID42P0375",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#not hasMissing"
#									},
#									"linkedSeg": "1ID42PMCH0"
#								}
#							]
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1ID42PMCH0",
#					"attrs": {
#						"id": "Done",
#						"viewName": "",
#						"label": "",
#						"x": "790",
#						"y": "70",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "flag.svg",
#						"context": {
#							"jaxId": "1ID42Q1MR0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1ID42Q1MR1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1ID42Q1MQ0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "askEditObj",
#					"jaxId": "1ID42QILS0",
#					"attrs": {
#						"id": "InputArgs",
#						"viewName": "",
#						"label": "",
#						"x": "795",
#						"y": "170",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1ID42TFIS0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1ID42TFIS1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"text": {
#							"type": "string",
#							"valText": "Complete agent arguments:",
#							"localize": {
#								"EN": "Complete agent arguments:",
#								"CN": "完善智能体调用参数:"
#							},
#							"localizable": true
#						},
#						"role": "Assistant",
#						"data": "#context[\"args\"]",
#						"template": "#argTemplate",
#						"editData": "true",
#						"outlet": {
#							"jaxId": "1ID42TFIS2",
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
#					"jaxId": "1ID6H35110",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "410",
#						"y": "140",
#						"outlet": {
#							"jaxId": "1ID6H5LTI0",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1ID42ODO30"
#						},
#						"dir": "L2R"
#					}
#				}
#			]
#		},
#		"desc": "这是一个AI智能体。",
#		"exportAPI": "true",
#		"exportAddOn": "true",
#		"addOnOpts": "{\"name\":\"fixArgs\",\"label\":\">#(($ln===\\\"CN\\\")?(\\\"修正参数\\\"):/*EN*/(\\\"Fix arguments\\\"))\",\"path\":\"/@tabos/FixArg.py\",\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"args.svg\",\"catalog\":\"Code\"}"
#	}
#}