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
		},
		"smartAsk":{
			"name":"smartAsk","type":"auto",
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
	smartAsk=None

	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	CheckCommand, CallGPT, HasMissing, Done, InputArgs, CheckSmart, SmartCheck, SmartMissing, AskUpward = None, None, None, None, None, None, None, None, None
	##{1ID42HC6Q0LocalVals#
	##}1ID42HC6Q0LocalVals#


	def parseAgentArgs(input):
		nonlocal argTemplate,command,smartAsk
		if isinstance(input, dict):
			argTemplate=input.get("argTemplate")
			command=input.get("command")
			smartAsk=input.get("smartAsk")
		else:
			argTemplate=None
			command=None
			smartAsk=None
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
	_agent,agent,segs = None, None, {}

	async def CheckCommand_exec(input):#//:1ID42IJ6S0
		result=input
		if command and isinstance(command, str):
			return {"seg":CheckSmart,"result":(input),"preSeg":"1ID42IJ6S0","outlet":"1ID42JIAC0"}
		if isinstance(command,dict):
			output=command
			context["args"]=command;
			return {"seg":HasMissing,"result":(output),"preSeg":"1ID42IJ6S0","outlet":"1ID6H1N7K0"}
		#default/else:
		return {"seg":InputArgs,"result":(result),"preSeg":"1ID42IJ6S0","outlet":"1ID42JIAC1"}
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
{("自然语言指令："+command) if isinstance(command, str) else ("指令JSON表达："+json.dumps(command))}
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
		result=input
		##{1ID42ODO30Start#
		hasMissing=False
		pptDefs=argTemplate.get("properties",{})

		for key in list(input.keys()):
			value=input[key]
			if value=="$$MISSING" or value=="":
				input.pop(key,None)
				if pptDefs.get(key,{}).get("required")!=False:
					hasMissing=True
		##}1ID42ODO30Start#
		if not hasMissing:
			return {"seg":Done,"result":(input),"preSeg":"1ID42ODO30","outlet":"1ID42P0370"}
		##{1ID42ODO30Post#
		##}1ID42ODO30Post#
		#default/else:
		return {"seg":InputArgs,"result":(result),"preSeg":"1ID42ODO30","outlet":"1ID42P0371"}
	segs["HasMissing"]=HasMissing={
		"exec":HasMissing_exec,
		"name":"HasMissing",
		"jaxId":"1ID42ODO30",
		"url":"HasMissing@"+agentURL
	}

	async def Done_exec(input):#//:1ID42PMCH0
		nonlocal segs
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

	async def CheckSmart_exec(input):#//:1IOCH6LMU0
		result=input
		if smartAsk:
			output="请分析并用JSON给出函数调用参数或给出提问内容。"
			return {"seg":SmartCheck,"result":(output),"preSeg":"1IOCH6LMU0","outlet":"1IOCH9J2B0"}
		#default/else:
		return {"seg":CallGPT,"result":(result),"preSeg":"1IOCH6LMU0","outlet":"1IOCH9J2B1"}
	segs["CheckSmart"]=CheckSmart={
		"exec":CheckSmart_exec,
		"name":"CheckSmart",
		"jaxId":"1IOCH6LMU0",
		"url":"CheckSmart@"+agentURL
	}

	async def SmartCheck_exec(input):#//:1IOCH9TAD0
		prompt=None
		result=None

		opts={
			"mode":"gpt-4o",
			"maxToken":2000,
			"temperature":0,
			"topP":1,
			"fqcP":0,
			"prcP":0,
			"secret":false,
			"responseFormat":"json_object"
		}
		chatMem=SmartCheck.get("messages",[])
		seed=""
		if(seed):
			opts.seed=seed
		messages=[
			{"role":"system","content":f"""
### 角色
你是一个解析自然语言命令，生成函数调用参数的AI
- 用户会输入要调用的函数的参数描述以及自然语言命令。

### 函数参数
- 当前函数参数的JSON定义是：
```
{json.dumps(argsTemplate.get("properties"), indent=4, ensure_ascii=False)}
```

{(f"### 用户初始输入的自然语言的调用指令:{chr(10)}" + command) if isinstance(command, str) else "### 调用指令的JSON表达：" + json.dumps(command, ensure_ascii=False)}

### 对话
- 在每一轮对话中，请分析根据输入的调用指令以及当前对话过程，是否可以给出符合要求的完整函数调用参数

- 你必须用JSON格式做出回复

- 如果当前信息可以给出完整的函数调用参数，请在返回JSON中的"arguments"属性中给出当前函数参数。例如：
```
{{
	"arguments":{{
		"name":"Alex",
		"gender":"Male"
	}}
}}
```

- 如果当前信息无法给出完整的函数调用参数，请在返回JSON中的"ask"属性中给出向用户提问补全信息的问题。你的问题应该明确详细，包括缺失参数的简单说明，请用用户容易理解的自然语言提问。例如：
```
{{
	"ask":"请提供要查询的用户的电子邮箱地址，用户的性别，以及用户的年龄范围。"
}}
```

- 提问后收到用户回复后，根据当前对话信息，如果不足以返回完整的调用参数，请继续向用户提问，直到返回完整函数调用信息为止。

### 返回JSON属性
- "arguments" optional, {{object}}: 完整的函数调用参数列表，其中每一项属性的名称是对应的参数名称，内容是参数的值。
- "ask" optional, {{string}}: 向用户提问的内容。
"""},
		]
		messages.extend(chatMem)
		prompt=input
		if(prompt):
			if not isinstance(prompt,str):
				prompt=json.dumps(prompt,indent=4)
			messages.append({"role":"user","content":prompt})
		result=await session.callSegLLM("SmartCheck@"+agentURL,opts,messages,true)
		chatMem.append({"role":"user","content":prompt})
		chatMem.append({"role":"assistant","content":result})
		if len(chatMem)>20:
			removedMsgs=chatMem[2:]
			del chatMem[:2]
		result=trimJSON(result)
		return {"seg":SmartMissing,"result":(result),"preSeg":"1IOCH9TAD0","outlet":"1IOCHABUN0"}
	segs["SmartCheck"]=SmartCheck={
		"exec":SmartCheck_exec,
		"name":"SmartCheck",
		"jaxId":"1IOCH9TAD0",
		"messages":[],
		"url":"SmartCheck@"+agentURL
	}

	async def SmartMissing_exec(input):#//:1IOCHFH5K0
		result=input
		##{1IOCHFH5K0Start#
		##}1IOCHFH5K0Start#
		if input.get("ask",None):
			output=input["ask"]
			return {"seg":AskUpward,"result":(output),"preSeg":"1IOCHFH5K0","outlet":"1IOCHI6DC0"}
		##{1IOCHFH5K0Post#
		result=input.get("arguments",None)
		##}1IOCHFH5K0Post#
		#default/else:
		return {"seg":Done,"result":(result),"preSeg":"1IOCHFH5K0","outlet":"1IOCHI6DC1"}
	segs["SmartMissing"]=SmartMissing={
		"exec":SmartMissing_exec,
		"name":"SmartMissing",
		"jaxId":"1IOCHFH5K0",
		"url":"SmartMissing@"+agentURL
	}

	async def AskUpward_exec(input):#//:1IOCHHANI0
		tip=input
		tipRole="assistant"
		prompt=undefined
		placeholder=""
		allowFile=(false) or False
		askUpward=(true) or False
		text=""
		result=""
		if askUpward and tip:
			result=await session.askUpward(_agent,tip)
		else:
			if tip:
				await session.addChatText(tipRole,tip,{})
			result=await session.askChatInput({"type":"input","prompt":prompt,"placeholder":placeholder,"text":text,"allowFile":allowFile})
			if isinstance(result, str):
				session.addChatText("user",result,{})
			elif result.get("assets",None) and result.get("prompt",None):
				assets_text = "- - -\n".join(map(str, result.get('assets', [])))
				session.addChatText("user",f"{result.get('prompt')}\n- - -\n{assets_text}",{"render":True})
			else:
				session.addChatText("user",getattr(result,"text",None) or getattr(result,"prompt", None) or result)
		return {"seg":SmartCheck,"result":(result),"preSeg":"1IOCHHANI0","outlet":"1IOCHI6DC2"}
	segs["AskUpward"]=AskUpward={
		"exec":AskUpward_exec,
		"name":"AskUpward",
		"jaxId":"1IOCHHANI0",
		"url":"AskUpward@"+agentURL
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
	_agent = agent = {
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
				"command":{"type":"auto","description":""},
				"smartAsk":{"type":"auto","description":""}
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
				command:{type:"auto",description:""},
				smartAsk:{type:"auto",description:""}
			}
		}
	},
	path: "/@tabos/FixArg.py",
	icon: "args.svg",
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
			"smartAsk":{name:"smartAsk",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","argTemplate","command","smartAsk","codes","desc"],
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
			coder.packText("args['smartAsk']=");this.genAttrStatement(seg.getAttr("smartAsk"));coder.newLine();
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
#				},
#				"smartAsk": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IOCGFRH00",
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
#						"y": "320",
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
#									"linkedSeg": "1IOCH6LMU0"
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
#					},
#					"icon": "condition.svg",
#					"reverseOutlets": true
#				},
#				{
#					"type": "aiseg",
#					"def": "callLLM",
#					"jaxId": "1ID42M5R60",
#					"attrs": {
#						"id": "CallGPT",
#						"viewName": "",
#						"label": "",
#						"x": "580",
#						"y": "240",
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
#						"prompt": "#f\"\"\"\n函数参数JSON：\n{json.dumps(argTemplate.get(\"properties\",{}),indent=4)}\n{(\"自然语言指令：\"+command) if isinstance(command, str) else (\"指令JSON表达：\"+json.dumps(command))}\n\"\"\"",
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
#					},
#					"icon": "llm.svg"
#				},
#				{
#					"type": "aiseg",
#					"def": "brunch",
#					"jaxId": "1ID42ODO30",
#					"attrs": {
#						"id": "HasMissing",
#						"viewName": "",
#						"label": "",
#						"x": "810",
#						"y": "240",
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
#					},
#					"icon": "condition.svg",
#					"reverseOutlets": true
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1ID42PMCH0",
#					"attrs": {
#						"id": "Done",
#						"viewName": "",
#						"label": "",
#						"x": "1070",
#						"y": "225",
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
#						"outlets": {
#							"attrs": []
#						},
#						"result": "#input"
#					},
#					"icon": "tab_css.svg"
#				},
#				{
#					"type": "aiseg",
#					"def": "askEditObj",
#					"jaxId": "1ID42QILS0",
#					"attrs": {
#						"id": "InputArgs",
#						"viewName": "",
#						"label": "",
#						"x": "1070",
#						"y": "350",
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
#					},
#					"icon": "rename.svg"
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1ID6H35110",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "690",
#						"y": "320",
#						"outlet": {
#							"jaxId": "1ID6H5LTI0",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1ID42ODO30"
#						},
#						"dir": "L2R"
#					},
#					"icon": "arrowright.svg",
#					"isConnector": true
#				},
#				{
#					"type": "aiseg",
#					"def": "brunch",
#					"jaxId": "1IOCH6LMU0",
#					"attrs": {
#						"id": "CheckSmart",
#						"viewName": "",
#						"label": "",
#						"x": "340",
#						"y": "225",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IOCH9J2C0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IOCH9J2C1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IOCH9J2B1",
#							"attrs": {
#								"id": "Default",
#								"desc": "输出节点。",
#								"output": ""
#							},
#							"linkedSeg": "1ID42M5R60"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IOCH9J2B0",
#									"attrs": {
#										"id": "Smart",
#										"desc": "输出节点。",
#										"output": "请分析并用JSON给出函数调用参数或给出提问内容。",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IOCH9J2C2",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IOCH9J2C3",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#smartAsk"
#									},
#									"linkedSeg": "1IOCH9TAD0"
#								}
#							]
#						}
#					},
#					"icon": "condition.svg",
#					"reverseOutlets": true
#				},
#				{
#					"type": "aiseg",
#					"def": "callLLM",
#					"jaxId": "1IOCH9TAD0",
#					"attrs": {
#						"id": "SmartCheck",
#						"viewName": "",
#						"label": "",
#						"x": "580",
#						"y": "125",
#						"desc": "执行一次LLM调用。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IOCHABUQ0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IOCHABUQ1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"platform": "\"OpenAI\"",
#						"mode": "gpt-4o",
#						"system": "#f\"\"\"\n### 角色\n你是一个解析自然语言命令，生成函数调用参数的AI\n- 用户会输入要调用的函数的参数描述以及自然语言命令。\n\n### 函数参数\n- 当前函数参数的JSON定义是：\n```\n{json.dumps(argsTemplate.get(\"properties\"), indent=4, ensure_ascii=False)}\n```\n\n{(f\"### 用户初始输入的自然语言的调用指令:{chr(10)}\" + command) if isinstance(command, str) else \"### 调用指令的JSON表达：\" + json.dumps(command, ensure_ascii=False)}\n\n### 对话\n- 在每一轮对话中，请分析根据输入的调用指令以及当前对话过程，是否可以给出符合要求的完整函数调用参数\n\n- 你必须用JSON格式做出回复\n\n- 如果当前信息可以给出完整的函数调用参数，请在返回JSON中的\"arguments\"属性中给出当前函数参数。例如：\n```\n{{\n\t\"arguments\":{{\n\t\t\"name\":\"Alex\",\n\t\t\"gender\":\"Male\"\n\t}}\n}}\n```\n\n- 如果当前信息无法给出完整的函数调用参数，请在返回JSON中的\"ask\"属性中给出向用户提问补全信息的问题。你的问题应该明确详细，包括缺失参数的简单说明，请用用户容易理解的自然语言提问。例如：\n```\n{{\n\t\"ask\":\"请提供要查询的用户的电子邮箱地址，用户的性别，以及用户的年龄范围。\"\n}}\n```\n\n- 提问后收到用户回复后，根据当前对话信息，如果不足以返回完整的调用参数，请继续向用户提问，直到返回完整函数调用信息为止。\n\n### 返回JSON属性\n- \"arguments\" optional, {{object}}: 完整的函数调用参数列表，其中每一项属性的名称是对应的参数名称，内容是参数的值。\n- \"ask\" optional, {{string}}: 向用户提问的内容。\n\"\"\"",
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
#							"jaxId": "1IOCHABUN0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IOCHFH5K0"
#						},
#						"secret": "false",
#						"allowCheat": "false",
#						"GPTCheats": {
#							"attrs": []
#						},
#						"shareChatName": "",
#						"keepChat": "20 messages",
#						"clearChat": "2",
#						"apiFiles": {
#							"attrs": []
#						},
#						"parallelFunction": "false",
#						"responseFormat": "json_object",
#						"formatDef": "\"\""
#					},
#					"icon": "llm.svg"
#				},
#				{
#					"type": "aiseg",
#					"def": "brunch",
#					"jaxId": "1IOCHFH5K0",
#					"attrs": {
#						"id": "SmartMissing",
#						"viewName": "",
#						"label": "",
#						"x": "810",
#						"y": "125",
#						"desc": "这是一个AISeg。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IOCHI6DE0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IOCHI6DE1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IOCHI6DC1",
#							"attrs": {
#								"id": "Default",
#								"desc": "输出节点。",
#								"output": ""
#							},
#							"linkedSeg": "1ID42PMCH0"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IOCHI6DC0",
#									"attrs": {
#										"id": "Ask",
#										"desc": "输出节点。",
#										"output": "#input[\"ask\"]",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IOCHI6DE2",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IOCHI6DE3",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#input.get(\"ask\",None)"
#									},
#									"linkedSeg": "1IOCHHANI0"
#								}
#							]
#						}
#					},
#					"icon": "condition.svg",
#					"reverseOutlets": true
#				},
#				{
#					"type": "aiseg",
#					"def": "askChat",
#					"jaxId": "1IOCHHANI0",
#					"attrs": {
#						"id": "AskUpward",
#						"viewName": "",
#						"label": "",
#						"x": "1070",
#						"y": "110",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IOCHI6DE4",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IOCHI6DE5",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"tip": "#input",
#						"tipRole": "Assistant",
#						"placeholder": "",
#						"text": "",
#						"file": "false",
#						"showText": "true",
#						"askUpward": "true",
#						"outlet": {
#							"jaxId": "1IOCHI6DC2",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IOCHHORK0"
#						}
#					},
#					"icon": "chat.svg"
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IOCHHORK0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1215",
#						"y": "20",
#						"outlet": {
#							"jaxId": "1IOCHI6DE6",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IOCHHTSC0"
#						},
#						"dir": "R2L"
#					},
#					"icon": "arrowright.svg",
#					"isConnector": true
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IOCHHTSC0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "610",
#						"y": "20",
#						"outlet": {
#							"jaxId": "1IOCHI6DE7",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IOCH9TAD0"
#						},
#						"dir": "R2L"
#					},
#					"icon": "arrowright.svg",
#					"isConnector": true
#				}
#			]
#		},
#		"desc": "这是一个AI智能体。",
#		"exportAPI": "true",
#		"exportAddOn": "true",
#		"addOnOpts": "{\"name\":\"fixArgs\",\"label\":\">#(($ln===\\\"CN\\\")?(\\\"修正参数\\\"):/*EN*/(\\\"Fix arguments\\\"))\",\"path\":\"/@tabos/FixArg.py\",\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"args.svg\",\"catalog\":\"Code\"}"
#	}
#}
