#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
##{1IDM7J6OE0MoreImports#
import sys
import importlib
import importlib.util
from session import trimJSON
from remotesession import RemoteSession
##}1IDM7J6OE0MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

argsTemplate={
	"properties":{
		"command":{
			"name":"command","type":"auto",
			"defaultValue":"",
			"desc":"要执行的操作指令",
		}
	},
	##{1IDM7J6OE0ArgsView#
	##}1IDM7J6OE0ArgsView#
}

##{1IDM7J6OE0StartDoc#
def import_module_from_file(file_path):
	name = pathLib.basename(file_path)
	if name.endswith(".py"):
		name = name[:-3]
	if name in sys.modules:
		module = sys.modules[name]
	else:
		spec = importlib.util.spec_from_file_location(name, file_path)
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)
	return module

##}1IDM7J6OE0StartDoc#
##----------------------------------------------------------------------------
async def NodeChat(session):
	command=None
	
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	BuildToolIndex, ChooseTool, ApplyTool, CallTool, ShowFinish, ShowAbort, ShowReply, ShowOther, PickTool, LogToolError, RunTool, ToolResult, AppendToolMsg, CallNode, RunNode, NodeResult, LogNodeError, Result, AskReply = None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None
	agentNode = session.agentNode
	
	##{1IDM7J6OE0LocalVals#
	##}1IDM7J6OE0LocalVals#
	
	
	def parseAgentArgs(input):
		nonlocal command
		if isinstance(input, dict):
			command=input.get("command")
		else:
			command=None
		##{1IDM7J6OE0ParseArgs#
		##}1IDM7J6OE0ParseArgs#
	
	##{1IDM7J6OE0PreContext#
	##}1IDM7J6OE0PreContext#
	globalContext = session.globalContext
	context = {
		"curTool":None,
		"toolsIndexVO":None,
		"tools":None,
		"callAgentNode":None,
		"agentNodes":None,
		"nodesIndexVO":None
	}
	##{1IDM7J6OE0PostContext#
	async def addTaskLog(log):
		logs=globalContext.get("taskLogs")
		if not logs:
			logs=globalContext["taskLogs"]=[]
		logs.append(log)
	
	async def resetTaskLog():
		logs = globalContext.get("taskLogs")
		if logs:
			logs = globalContext["taskLogs"] = []
	
	if not globalContext.get("resetTaskLog"):
		globalContext["resetTaskLog"]=resetTaskLog
		globalContext["addTaskLog"]=addTaskLog
	else:
		addTaskLog=globalContext["addTaskLog"]
		resetTaskLog=globalContext["resetTaskLog"]
	##}1IDM7J6OE0PostContext#
	agent,segs = None, {}
	
	async def BuildToolIndex_exec(input):#//:1IDM7PH5T0
		result=input
		##{1IDM7PH5T0Code#
		nonlocal context
		tools=context["tools"]=[]
		toolsIdx=context["toolsIndexVO"]={}
		nodeJSON=agentNode.nodeJSON
		agents=nodeJSON.get("tools")
		# Build indexVO:
		if agents:
			for i in range(len(agents)):
				pathName=agents[i]
				path=pathLib.join(agentNode.path,pathName)
				module=import_module_from_file(path)
				info=getattr(module,"ChatAPI")
				if info:
					tools.append(path)
					toolsIdx[f"Tool-{i}"]=info[0]["def"]["description"]
					
		nodes=context["agentNodes"]={}
		res=await session.callHub("AhListAgentNodes",{});
		if res and res.get("code")==200:
			list=res.get("nodes")
			for node in list:
				nodes[node.get("name")]={
					"descritption":node.get("description"),
					"workload":node.get("workload")
				}
		##}1IDM7PH5T0Code#
		return {"seg":ChooseTool,"result":(result),"preSeg":"1IDM7PH5T0","outlet":"1IDM7VJSD0"}
	segs["BuildToolIndex"]=BuildToolIndex={
		"exec":BuildToolIndex_exec,
		"name":"BuildToolIndex",
		"jaxId":"1IDM7PH5T0",
		"url":"BuildToolIndex@"+agentURL
	}
	
	async def ChooseTool_exec(input):#//:1IDM7V6NG0
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
		chatMem=ChooseTool.get("messages",[])
		seed=""
		if(seed):
			opts.seed=seed
		messages=[
			{"role":"system","content":f"""
你是一个根据用户输入，选择适合的Tool(本地智能体)或Node(外部智能体节点)运行，与用户对话，完成任务的AI。
当前的Tools（本地智能体工具）有:
{json.dumps(context.get("toolsIndexVO"),indent=4)}
当前的Nodes（外部智能体节点）有:
{json.dumps(context.get("agentNodes"),indent=4)}

- 第一轮对话时，用户输入的是要完成的任务，你根据用户的输入，选择合适的Tool或者Node

- 每一回合对话，跟根据当前任务执行的情况，回复一个JSON对象。
- 如果需要执行一个Tool，回复JSON中的"tool"属性是下一步要执行的Tool(智能体)的名称; 回复JSON中的prompt属性是调用这个Tool的输入指令。例如：
{{
	"tool":"Tool-3",
    "prompt":"Search for: Who is the winner of 2024 F1?"
}}

- 如果需要执行一个Node，回复JSON中的"node"属性是下一步要执行的Node（外部智能体）的名称; 回复JSON中的prompt属性是调用这个Tool的输入指令。例如：
{{
	"node":"DrawNode",
    "prompt":"Draw picture of a cute fat cat."
}}

- 执行Tool或Node的结果会在对话中告知。你根据任务目标以及当前的执行情况，可能需要继续选择新的Tool/Node进一步执行。

- 如果同时有Tool和Node可以执行当前的任务需求，优先使用Tool，如果Tool执行失败或无法完成任务再尝试Node。

- 如果成功的完成了用户提出的任务，回复将JSON中的"finish"属性设置为true。并通过"result"属性总结汇报执行情况。例如
{{
	"finish":true,
    "result":"论坛帖子已经成功发布。"
}}

- 如果执行Tool出现错误，你认为无法完成用户的任务，设置回复JSON中的"abort"属性为true，并在"reason"属性中说明原因。例如:
{{
	"abort":true,
    "reason":"没有登录脸书账号，无法发布新的内容。"
}}

- 如果没有Tool或Node可以完成用户的要求，请设计一个或多个用来完成用户需求的Tool，在回复JSON中用"missingTools"数组属性里描述缺失的Tool。例如：
{{
	"missingTools":[
    	"检查脸书账号登录状态",
        "发布脸书动态"
    ]
}}

- 如果回答用户的输入不需要使用任何tool，用回复JSON中的"replay"属性回答用户，如果对话已结束，同时设置"finish"属性为true。例如：当用户询问："西瓜是一种水果么？"，你的回复：
{{
	"finish":true,
	"result":"是的，西瓜是一种水果。"
}}

- 如果执行任务需要用户提供更多的信息，用回复JSON中的"ask"属性询问用户，同时设置finish属性为false。例如，需要用户
提供邮箱地址：
{{
	"finish":false,
	"ask":"请告诉我你的电子邮箱地址"
}}
"""},
		]
		messages.extend(chatMem)
		prompt=input
		if(prompt):
			if not isinstance(prompt,str):
				prompt=json.dumps(prompt,indent=4)
			messages.append({"role":"user","content":prompt})
		result=await session.callSegLLM("ChooseTool@"+agentURL,opts,messages,true)
		chatMem.append({"role":"user","content":prompt})
		chatMem.append({"role":"assistant","content":result})
		if len(chatMem)>50:
			removedMsgs=chatMem[2:]
			del chatMem[:2]
		result=trimJSON(result)
		return {"seg":ApplyTool,"result":(result),"preSeg":"1IDM7V6NG0","outlet":"1IDM7VJSE0"}
	segs["ChooseTool"]=ChooseTool={
		"exec":ChooseTool_exec,
		"name":"ChooseTool",
		"jaxId":"1IDM7V6NG0",
		"messages":[],
		"url":"ChooseTool@"+agentURL
	}
	
	async def ApplyTool_exec(input):#//:1IDM801C80
		if input.get("node"):
			output=input
			return {"seg":CallNode,"result":(output),"preSeg":"1IDM801C80","outlet":"1IDNFDD380"}
		if input.get("tool"):
			output=input
			return {"seg":CallTool,"result":(output),"preSeg":"1IDM801C80","outlet":"1IDM8TC5H0"}
		if input.get("finish"):
			output=input.get("result")
			return {"seg":ShowFinish,"result":(output),"preSeg":"1IDM801C80","outlet":"1IDM80RIT0"}
		if input.get("abort"):
			output=input.get("reason")
			return {"seg":ShowAbort,"result":(output),"preSeg":"1IDM801C80","outlet":"1IDM81GTJ0"}
		if input.get("ask"):
			output=input.get("ask")
			return {"seg":AskReply,"result":(output),"preSeg":"1IDM801C80","outlet":"1IDM820RT0"}
		#default/else:
		return {"seg":ShowOther,"result":(input),"preSeg":"1IDM801C80","outlet":"1IDM8TC5H1"}
	segs["ApplyTool"]=ApplyTool={
		"exec":ApplyTool_exec,
		"name":"ApplyTool",
		"jaxId":"1IDM801C80",
		"url":"ApplyTool@"+agentURL
	}
	
	async def CallTool_exec(input):#//:1IDM82RPT0
		result=input
		##{1IDM82RPT0Code#
		##}1IDM82RPT0Code#
		return {"seg":PickTool,"result":(result),"preSeg":"1IDM82RPT0","outlet":"1IDM8TC5H2","catchSeg":LogToolError,"catchlet":"1IDM8TC5H3"}
	segs["CallTool"]=CallTool={
		"exec":CallTool_exec,
		"name":"CallTool",
		"jaxId":"1IDM82RPT0",
		"url":"CallTool@"+agentURL
	}
	
	async def ShowFinish_exec(input):#//:1IDM83BES0
		result=input
		role="assistant"
		content=f"Finish: {json.dumps(input)}"
		##{1IDM83BES0PreCodes#
		await addTaskLog({"type":"TaskFinish","result":json.dumps(input)})
		##}1IDM83BES0PreCodes#
		await session.addChatText(role,content,{})
		##{1IDM83BES0PostCodes#
		##}1IDM83BES0PostCodes#
		return {"seg":Result,"result":(result),"preSeg":"1IDM83BES0","outlet":"1IDM8TC5H4"}
	segs["ShowFinish"]=ShowFinish={
		"exec":ShowFinish_exec,
		"name":"ShowFinish",
		"jaxId":"1IDM83BES0",
		"url":"ShowFinish@"+agentURL
	}
	
	async def ShowAbort_exec(input):#//:1IDM83MIO0
		result=input
		role="system"
		content=f"Abort: {input}"
		##{1IDM83MIO0PreCodes#
		await addTaskLog({"type":"TaskAbort","reason":content})
		##}1IDM83MIO0PreCodes#
		await session.addChatText(role,content,{})
		##{1IDM83MIO0PostCodes#
		##}1IDM83MIO0PostCodes#
		return {"seg":Result,"result":(result),"preSeg":"1IDM83MIO0","outlet":"1IDM8TC5H5"}
	segs["ShowAbort"]=ShowAbort={
		"exec":ShowAbort_exec,
		"name":"ShowAbort",
		"jaxId":"1IDM83MIO0",
		"url":"ShowAbort@"+agentURL
	}
	
	async def ShowReply_exec(input):#//:1IDM8424C0
		result=input
		role="assistant"
		content=input
		##{1IDM8424C0PreCodes#
		await addTaskLog({"type":"TaskReply","content":content})
		##}1IDM8424C0PreCodes#
		await session.addChatText(role,content,{})
		##{1IDM8424C0PostCodes#
		##}1IDM8424C0PostCodes#
		return {"result":result}
	segs["ShowReply"]=ShowReply={
		"exec":ShowReply_exec,
		"name":"ShowReply",
		"jaxId":"1IDM8424C0",
		"url":"ShowReply@"+agentURL
	}
	
	async def ShowOther_exec(input):#//:1IDM857TI0
		result=input
		role="assistant"
		content=f"Continue: {json.dumps(input)}"
		##{1IDM857TI0PreCodes#
		##}1IDM857TI0PreCodes#
		await session.addChatText(role,content,{})
		##{1IDM857TI0PostCodes#
		##}1IDM857TI0PostCodes#
		return {"seg":ChooseTool,"result":(result),"preSeg":"1IDM857TI0","outlet":"1IDM8TC5H7"}
	segs["ShowOther"]=ShowOther={
		"exec":ShowOther_exec,
		"name":"ShowOther",
		"jaxId":"1IDM857TI0",
		"url":"ShowOther@"+agentURL
	}
	
	async def PickTool_exec(input):#//:1IDM86UJG0
		result=input
		##{1IDM86UJG0Code#
		toolId=input["tool"]
		toolId = int(toolId[len("Tool-"):])
		tool=context["curTool"]=context["tools"][toolId]
		await session.addChatText("log",f"Use tool: {tool}.")
		##}1IDM86UJG0Code#
		return {"seg":RunTool,"result":(result),"preSeg":"1IDM86UJG0","outlet":"1IDM8TC5H8"}
	segs["PickTool"]=PickTool={
		"exec":PickTool_exec,
		"name":"PickTool",
		"jaxId":"1IDM86UJG0",
		"url":"PickTool@"+agentURL
	}
	
	async def LogToolError_exec(input):#//:1IDM8BKPN0
		result=input
		role="assistant"
		content=((f"出现错误：{input}") if(__Ln=="CN") else (f"Error occurred: {input}"))
		##{1IDM8BKPN0PreCodes#
		await addTaskLog({"type":"ToolError","error":content})
		##}1IDM8BKPN0PreCodes#
		await session.addChatText(role,content,{})
		##{1IDM8BKPN0PostCodes#
		##}1IDM8BKPN0PostCodes#
		return {"seg":AppendToolMsg,"result":(result),"preSeg":"1IDM8BKPN0","outlet":"1IDM8TC5H9"}
	segs["LogToolError"]=LogToolError={
		"exec":LogToolError_exec,
		"name":"LogToolError",
		"jaxId":"1IDM8BKPN0",
		"url":"LogToolError@"+agentURL
	}
	
	async def RunTool_exec(input):#//:1IDM8ERN60
		result=input
		##{1IDM8ERN60Code#
		nonlocal context
		tool=context["curTool"]
		prompt=json.dumps(input["prompt"]) if input["prompt"] else ""
		await addTaskLog({"type":"CallTool","tool":tool,"prompt":prompt})
		result=await session.pipeChat(tool,prompt)
		##}1IDM8ERN60Code#
		return {"seg":ToolResult,"result":(result),"preSeg":"1IDM8ERN60","outlet":"1IDM8TC5H10"}
	segs["RunTool"]=RunTool={
		"exec":RunTool_exec,
		"name":"RunTool",
		"jaxId":"1IDM8ERN60",
		"url":"RunTool@"+agentURL
	}
	
	async def ToolResult_exec(input):#//:1IDM8FICJ0
		result=input
		role="assistant"
		content=input
		await session.addChatText(role,content,{})
		return {"seg":AppendToolMsg,"result":(result),"preSeg":"1IDM8FICJ0","outlet":"1IDM8TC5H11"}
	segs["ToolResult"]=ToolResult={
		"exec":ToolResult_exec,
		"name":"ToolResult",
		"jaxId":"1IDM8FICJ0",
		"url":"ToolResult@"+agentURL
	}
	
	async def AppendToolMsg_exec(input):#//:1IDM8FVCO0
		result=input
		##{1IDM8FVCO0Code#
		result=f"Run tool result: {json.dumps(input,indent=4)}"
		##}1IDM8FVCO0Code#
		return {"seg":ChooseTool,"result":(result),"preSeg":"1IDM8FVCO0","outlet":"1IDM8TC5H12"}
	segs["AppendToolMsg"]=AppendToolMsg={
		"exec":AppendToolMsg_exec,
		"name":"AppendToolMsg",
		"jaxId":"1IDM8FVCO0",
		"url":"AppendToolMsg@"+agentURL
	}
	
	async def CallNode_exec(input):#//:1IDNFGGSI0
		result=input
		##{1IDNFGGSI0Code#
		##}1IDNFGGSI0Code#
		return {"seg":RunNode,"result":(result),"preSeg":"1IDNFGGSI0","outlet":"1IDNFKO8H0","catchSeg":LogNodeError,"catchlet":"1IDNFKO8H1"}
	segs["CallNode"]=CallNode={
		"exec":CallNode_exec,
		"name":"CallNode",
		"jaxId":"1IDNFGGSI0",
		"url":"CallNode@"+agentURL
	}
	
	async def RunNode_exec(input):#//:1IDNFHMRQ0
		result=input
		##{1IDNFHMRQ0Code#
		nodes=context["agentNodes"]
		if not nodes.get(input.get("node")):
			raise Exception(f'Node \"{input.get("node")}\" not found. Are you confusing Node and Tool? Choose tool or agent node.')
		await addTaskLog({"type":"CallAgentNode","node":input.get("node"),"prompt":input.get("prompt")})
		await session.addChatText("log",f"Call agent-node: \"{input.get('node')}.\"")
		result=await RemoteSession.exec(session,input.get("node"),"/@tabos/NodeChat.py",input.get("prompt"),{});
		##}1IDNFHMRQ0Code#
		return {"seg":NodeResult,"result":(result),"preSeg":"1IDNFHMRQ0","outlet":"1IDNFKO8H3"}
	segs["RunNode"]=RunNode={
		"exec":RunNode_exec,
		"name":"RunNode",
		"jaxId":"1IDNFHMRQ0",
		"url":"RunNode@"+agentURL
	}
	
	async def NodeResult_exec(input):#//:1IDNFI3P00
		result=input
		role="assistant"
		content=input
		await session.addChatText(role,content,{})
		return {"seg":AppendToolMsg,"result":(result),"preSeg":"1IDNFI3P00","outlet":"1IDNFKO8H4"}
	segs["NodeResult"]=NodeResult={
		"exec":NodeResult_exec,
		"name":"NodeResult",
		"jaxId":"1IDNFI3P00",
		"url":"NodeResult@"+agentURL
	}
	
	async def LogNodeError_exec(input):#//:1IDNFIH8A0
		result=input
		role="assistant"
		content=input
		await session.addChatText(role,content,{})
		return {"seg":AppendToolMsg,"result":(result),"preSeg":"1IDNFIH8A0","outlet":"1IDNFKO8H5"}
	segs["LogNodeError"]=LogNodeError={
		"exec":LogNodeError_exec,
		"name":"LogNodeError",
		"jaxId":"1IDNFIH8A0",
		"url":"LogNodeError@"+agentURL
	}
	
	async def Result_exec(input):#//:1IDNJLF4G0
		result=input
		##{1IDNJLF4G0Code#
		result={
			"result":input,
			"runLog":globalContext.get("taskLogs") or []
		}
		##}1IDNJLF4G0Code#
		return {"result":result}
	segs["Result"]=Result={
		"exec":Result_exec,
		"name":"Result",
		"jaxId":"1IDNJLF4G0",
		"url":"Result@"+agentURL
	}
	
	async def AskReply_exec(input):#//:1IDSKPHB10
		tip=input
		tipRole="assistant"
		prompt=undefined
		placeholder=""
		text=""
		result=""
		##{1IDSKPHB10PreCodes#
		##}1IDSKPHB10PreCodes#
		if tip:
			await session.addChatText(tipRole,tip,{})
		result=await session.askChatInput({"type":"input","prompt":prompt,"placeholder":placeholder,"text":text})
		await session.addChatText("user",result,{})
		##{1IDSKPHB10PostCodes#
		await addTaskLog({"type":"UserReply","content":result})
		##}1IDSKPHB10PostCodes#
		return {"seg":ChooseTool,"result":(result),"preSeg":"1IDSKPHB10","outlet":"1IDSKQM4B0"}
	segs["AskReply"]=AskReply={
		"exec":AskReply_exec,
		"name":"AskReply",
		"jaxId":"1IDSKPHB10",
		"url":"AskReply@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1IDM7J6OE0PreEntry#
		##}1IDM7J6OE0PreEntry#
		result = {"seg":BuildToolIndex,"input":input}
		##{1IDM7J6OE0PostEntry#
		##}1IDM7J6OE0PostEntry#
		return result
	agent = {
		"isAIAgent": true,
		"session": session,
		"name": "NodeChat",
		"url": agentURL,
		"baseDir": basePath,
		"autoStart": true,
		"jaxId": "1IDM7J6OE0",
		"context": context,
		"livingSeg": None,
		"execChat": execAgent,
		##{1IDM7J6OE0MoreAgentAttrs#
		##}1IDM7J6OE0MoreAgentAttrs#
	}
	##{1IDM7J6OE0PostAgent#
	agent["baseDir"] = agentNode.path
	##}1IDM7J6OE0PostAgent#
	return agent
##{1IDM7J6OE0ExCodes#
##}1IDM7J6OE0ExCodes#

ChatAPI=None

default=NodeChat
__all__=["default","NodeChat","ChatAPI"]
""">>>CodyExport
let ChatAPI,Exports;

return {api:ChatAPI,export:Exports};
>>>CodyExport"""
#Cody Project Doc
#{
#	"type": "docfile",
#	"def": "DocAIAgent",
#	"jaxId": "1IDM7J6OE0",
#	"attrs": {
#		"editObjs": {
#			"jaxId": "1IDM7J6OE1",
#			"attrs": {
#				"NodeChat": {
#					"type": "objclass",
#					"def": "ObjClass",
#					"jaxId": "1IDM7J6OF0",
#					"attrs": {
#						"exportType": "UI Data Template",
#						"constructArgs": {
#							"jaxId": "1IDM7J6OF1",
#							"attrs": {}
#						},
#						"superClass": "",
#						"properties": {
#							"jaxId": "1IDM7J6OF2",
#							"attrs": {}
#						},
#						"functions": {
#							"jaxId": "1IDM7J6OF3",
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
#			"jaxId": "1IDM7J6OE2",
#			"attrs": {}
#		},
#		"entry": "BuildToolIndex",
#		"autoStart": "true",
#		"inBrowser": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1IDM7J6OE3",
#			"attrs": {
#				"command": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IDM7VJSG0",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "\"\"",
#						"desc": "要执行的操作指令"
#					}
#				}
#			}
#		},
#		"localVars": {
#			"jaxId": "1IDM7J6OE4",
#			"attrs": {
#				"agentNode": {
#					"type": "auto",
#					"valText": "#session.agentNode"
#				}
#			}
#		},
#		"context": {
#			"jaxId": "1IDM7J6OE5",
#			"attrs": {
#				"curTool": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IDM9HG3J0",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "#None",
#						"desc": ""
#					}
#				},
#				"toolsIndexVO": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IDM9BF8C0",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "#None",
#						"desc": ""
#					}
#				},
#				"tools": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IDN1SEO20",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "#None",
#						"desc": ""
#					}
#				},
#				"callAgentNode": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IDNFQB2P0",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "#None",
#						"desc": ""
#					}
#				},
#				"agentNodes": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IDNFQB2P1",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "#None",
#						"desc": ""
#					}
#				},
#				"nodesIndexVO": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IDNFQB2P2",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "#None",
#						"desc": ""
#					}
#				}
#			}
#		},
#		"globalMockup": {
#			"jaxId": "1IDM7J6OE6",
#			"attrs": {}
#		},
#		"segs": {
#			"attrs": [
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IDM7PH5T0",
#					"attrs": {
#						"id": "BuildToolIndex",
#						"viewName": "",
#						"label": "",
#						"x": "65",
#						"y": "360",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDM7VJSG1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDM7VJSG2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDM7VJSD0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM7V6NG0"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "callLLM",
#					"jaxId": "1IDM7V6NG0",
#					"attrs": {
#						"id": "ChooseTool",
#						"viewName": "",
#						"label": "",
#						"x": "330",
#						"y": "360",
#						"desc": "执行一次LLM调用。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDM7VJSG3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDM7VJSG4",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"platform": "\"OpenAI\"",
#						"mode": "gpt-4o",
#						"system": "#f\"\"\"\n你是一个根据用户输入，选择适合的Tool(本地智能体)或Node(外部智能体节点)运行，与用户对话，完成任务的AI。\n当前的Tools（本地智能体工具）有:\n{json.dumps(context.get(\"toolsIndexVO\"),indent=4)}\n当前的Nodes（外部智能体节点）有:\n{json.dumps(context.get(\"agentNodes\"),indent=4)}\n\n- 第一轮对话时，用户输入的是要完成的任务，你根据用户的输入，选择合适的Tool或者Node\n\n- 每一回合对话，跟根据当前任务执行的情况，回复一个JSON对象。\n- 如果需要执行一个Tool，回复JSON中的\"tool\"属性是下一步要执行的Tool(智能体)的名称; 回复JSON中的prompt属性是调用这个Tool的输入指令。例如：\n{{\n\t\"tool\":\"Tool-3\",\n    \"prompt\":\"Search for: Who is the winner of 2024 F1?\"\n}}\n\n- 如果需要执行一个Node，回复JSON中的\"node\"属性是下一步要执行的Node（外部智能体）的名称; 回复JSON中的prompt属性是调用这个Tool的输入指令。例如：\n{{\n\t\"node\":\"DrawNode\",\n    \"prompt\":\"Draw picture of a cute fat cat.\"\n}}\n\n- 执行Tool或Node的结果会在对话中告知。你根据任务目标以及当前的执行情况，可能需要继续选择新的Tool/Node进一步执行。\n\n- 如果同时有Tool和Node可以执行当前的任务需求，优先使用Tool，如果Tool执行失败或无法完成任务再尝试Node。\n\n- 如果成功的完成了用户提出的任务，回复将JSON中的\"finish\"属性设置为true。并通过\"result\"属性总结汇报执行情况。例如\n{{\n\t\"finish\":true,\n    \"result\":\"论坛帖子已经成功发布。\"\n}}\n\n- 如果执行Tool出现错误，你认为无法完成用户的任务，设置回复JSON中的\"abort\"属性为true，并在\"reason\"属性中说明原因。例如:\n{{\n\t\"abort\":true,\n    \"reason\":\"没有登录脸书账号，无法发布新的内容。\"\n}}\n\n- 如果没有Tool或Node可以完成用户的要求，请设计一个或多个用来完成用户需求的Tool，在回复JSON中用\"missingTools\"数组属性里描述缺失的Tool。例如：\n{{\n\t\"missingTools\":[\n    \t\"检查脸书账号登录状态\",\n        \"发布脸书动态\"\n    ]\n}}\n\n- 如果回答用户的输入不需要使用任何tool，用回复JSON中的\"replay\"属性回答用户，如果对话已结束，同时设置\"finish\"属性为true。例如：当用户询问：\"西瓜是一种水果么？\"，你的回复：\n{{\n\t\"finish\":true,\n\t\"result\":\"是的，西瓜是一种水果。\"\n}}\n\n- 如果执行任务需要用户提供更多的信息，用回复JSON中的\"ask\"属性询问用户，同时设置finish属性为false。例如，需要用户\n提供邮箱地址：\n{{\n\t\"finish\":false,\n\t\"ask\":\"请告诉我你的电子邮箱地址\"\n}}\n\"\"\"",
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
#							"jaxId": "1IDM7VJSE0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM801C80"
#						},
#						"secret": "false",
#						"allowCheat": "false",
#						"GPTCheats": {
#							"attrs": []
#						},
#						"shareChatName": "",
#						"keepChat": "50 messages",
#						"clearChat": "2",
#						"apiFiles": {
#							"attrs": []
#						},
#						"parallelFunction": "false",
#						"responseFormat": "json_object"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "brunch",
#					"jaxId": "1IDM801C80",
#					"attrs": {
#						"id": "ApplyTool",
#						"viewName": "",
#						"label": "",
#						"x": "555",
#						"y": "360",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDM8TC5K0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDM8TC5K1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDM8TC5H1",
#							"attrs": {
#								"id": "Default",
#								"desc": "输出节点。",
#								"output": ""
#							},
#							"linkedSeg": "1IDM857TI0"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IDNFDD380",
#									"attrs": {
#										"id": "CallNode",
#										"desc": "输出节点。",
#										"output": "#input",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IDNFKO8K0",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IDNFKO8K1",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#input.get(\"node\")"
#									},
#									"linkedSeg": "1IDNFGGSI0"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IDM8TC5H0",
#									"attrs": {
#										"id": "UseTool",
#										"desc": "输出节点。",
#										"output": "#input",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IDM8TC5K2",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IDM8TC5K3",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#input.get(\"tool\")"
#									},
#									"linkedSeg": "1IDM82RPT0"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IDM80RIT0",
#									"attrs": {
#										"id": "Finish",
#										"desc": "输出节点。",
#										"output": "#input.get(\"result\")",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IDM8TC5K4",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IDM8TC5K5",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#input.get(\"finish\")"
#									},
#									"linkedSeg": "1IDM83BES0"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IDM81GTJ0",
#									"attrs": {
#										"id": "Abort",
#										"desc": "输出节点。",
#										"output": "#input.get(\"reason\")",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IDM8TC5K6",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IDM8TC5K7",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#input.get(\"abort\")"
#									},
#									"linkedSeg": "1IDM83MIO0"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IDM820RT0",
#									"attrs": {
#										"id": "Ask",
#										"desc": "输出节点。",
#										"output": "#input.get(\"ask\")",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IDM8TC5K8",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IDM8TC5K9",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#input.get(\"ask\")"
#									},
#									"linkedSeg": "1IF5TL40A0"
#								}
#							]
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "tryCatch",
#					"jaxId": "1IDM82RPT0",
#					"attrs": {
#						"id": "CallTool",
#						"viewName": "",
#						"label": "",
#						"x": "815",
#						"y": "230",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDM8TC5K10",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDM8TC5K11",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDM8TC5H2",
#							"attrs": {
#								"id": "Try",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM86UJG0"
#						},
#						"catchlet": {
#							"jaxId": "1IDM8TC5H3",
#							"attrs": {
#								"id": "Catch",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM8BKPN0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IDM83BES0",
#					"attrs": {
#						"id": "ShowFinish",
#						"viewName": "",
#						"label": "",
#						"x": "815",
#						"y": "320",
#						"desc": "这是一个AISeg。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDM8TC5K12",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDM8TC5K13",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#f\"Finish: {json.dumps(input)}\"",
#						"outlet": {
#							"jaxId": "1IDM8TC5H4",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDNJLF4G0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IDM83MIO0",
#					"attrs": {
#						"id": "ShowAbort",
#						"viewName": "",
#						"label": "",
#						"x": "815",
#						"y": "375",
#						"desc": "这是一个AISeg。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDM8TC5K14",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDM8TC5K15",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "System",
#						"text": "#f\"Abort: {input}\"",
#						"outlet": {
#							"jaxId": "1IDM8TC5H5",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDNJLF4G0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IDM8424C0",
#					"attrs": {
#						"id": "ShowReply",
#						"viewName": "",
#						"label": "",
#						"x": "795",
#						"y": "660",
#						"desc": "这是一个AISeg。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "working.svg",
#						"context": {
#							"jaxId": "1IDM8TC5K16",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDM8TC5K17",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1IDM8TC5H6",
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
#					"jaxId": "1IDM84KIB0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "960",
#						"y": "575",
#						"outlet": {
#							"jaxId": "1IDM8TC5K18",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDNJRMJI0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IDM84Q6B0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "355",
#						"y": "460",
#						"outlet": {
#							"jaxId": "1IDM8TC5K19",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM7V6NG0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IDM857TI0",
#					"attrs": {
#						"id": "ShowOther",
#						"viewName": "",
#						"label": "",
#						"x": "815",
#						"y": "500",
#						"desc": "这是一个AISeg。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDM8TC5K20",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDM8TC5K21",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#f\"Continue: {json.dumps(input)}\"",
#						"outlet": {
#							"jaxId": "1IDM8TC5H7",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM84KIB0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IDM86UJG0",
#					"attrs": {
#						"id": "PickTool",
#						"viewName": "",
#						"label": "",
#						"x": "1015",
#						"y": "190",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDM8TC5K22",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDM8TC5K23",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDM8TC5H8",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM8ERN60"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IDM8BKPN0",
#					"attrs": {
#						"id": "LogToolError",
#						"viewName": "",
#						"label": "",
#						"x": "1015",
#						"y": "265",
#						"desc": "这是一个AISeg。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDM8TC5K24",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDM8TC5K25",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": {
#							"type": "string",
#							"valText": "#f\"Error occurred: {input}\"",
#							"localize": {
#								"EN": "#f\"Error occurred: {input}\"",
#								"CN": "#f\"出现错误：{input}\""
#							},
#							"localizable": true
#						},
#						"outlet": {
#							"jaxId": "1IDM8TC5H9",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM8N0HP0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IDM8ERN60",
#					"attrs": {
#						"id": "RunTool",
#						"viewName": "",
#						"label": "",
#						"x": "1235",
#						"y": "190",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDM8TC5K26",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDM8TC5K27",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDM8TC5H10",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM8FICJ0"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IDM8FICJ0",
#					"attrs": {
#						"id": "ToolResult",
#						"viewName": "",
#						"label": "",
#						"x": "1445",
#						"y": "190",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDM8TC5K28",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDM8TC5K29",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1IDM8TC5H11",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM8FVCO0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IDM8FVCO0",
#					"attrs": {
#						"id": "AppendToolMsg",
#						"viewName": "",
#						"label": "",
#						"x": "1750",
#						"y": "190",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDM8TC5K30",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDM8TC5K31",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDM8TC5H12",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM9JES60"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IDM8L51I0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1730",
#						"y": "575",
#						"outlet": {
#							"jaxId": "1IDM8TC5L4",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDSKPVJ00"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connectorL",
#					"jaxId": "1IDM8N0HP0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1545",
#						"y": "265",
#						"outlet": {
#							"jaxId": "1IDM8TC5L5",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM8FVCO0"
#						},
#						"dir": "L2R"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IDM9JES60",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1925",
#						"y": "300",
#						"outlet": {
#							"jaxId": "1IDM9KQ2H0",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM8L51I0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "tryCatch",
#					"jaxId": "1IDNFGGSI0",
#					"attrs": {
#						"id": "CallNode",
#						"viewName": "",
#						"label": "",
#						"x": "815",
#						"y": "105",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDNFKO8K2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDNFKO8K3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDNFKO8H0",
#							"attrs": {
#								"id": "Try",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDNFHMRQ0"
#						},
#						"catchlet": {
#							"jaxId": "1IDNFKO8H1",
#							"attrs": {
#								"id": "Catch",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDNFIH8A0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IDNFHMRQ0",
#					"attrs": {
#						"id": "RunNode",
#						"viewName": "",
#						"label": "",
#						"x": "1015",
#						"y": "60",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDNFKO8K6",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDNFKO8K7",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDNFKO8H3",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDNFI3P00"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IDNFI3P00",
#					"attrs": {
#						"id": "NodeResult",
#						"viewName": "",
#						"label": "",
#						"x": "1445",
#						"y": "60",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDNFKO8K8",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDNFKO8K9",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1IDNFKO8H4",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM8FVCO0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IDNFIH8A0",
#					"attrs": {
#						"id": "LogNodeError",
#						"viewName": "",
#						"label": "",
#						"x": "1015",
#						"y": "120",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDNFKO8K10",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDNFKO8K11",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1IDNFKO8H5",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDNFJIS30"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connectorL",
#					"jaxId": "1IDNFJIS30",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1550",
#						"y": "120",
#						"outlet": {
#							"jaxId": "1IDNFKO8K12",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM8FVCO0"
#						},
#						"dir": "L2R"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IDNJLF4G0",
#					"attrs": {
#						"id": "Result",
#						"viewName": "",
#						"label": "",
#						"x": "1065",
#						"y": "350",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "flag.svg",
#						"context": {
#							"jaxId": "1IDNJO4F74",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDNJO4F75",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDNJO4F32",
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
#					"def": "connector",
#					"jaxId": "1IDNJRMJI0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "580",
#						"y": "575",
#						"outlet": {
#							"jaxId": "1IDNJSBKV0",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM84Q6B0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "askChat",
#					"jaxId": "1IDSKPHB10",
#					"attrs": {
#						"id": "AskReply",
#						"viewName": "",
#						"label": "",
#						"x": "1065",
#						"y": "440",
#						"desc": "这是一个AISeg。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "lint_bug.svg",
#						"context": {
#							"jaxId": "1IDSKQM4H0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDSKQM4H1",
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
#						"outlet": {
#							"jaxId": "1IDSKQM4B0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDSKPVJ00"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IDSKPVJ00",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1200",
#						"y": "575",
#						"outlet": {
#							"jaxId": "1IDSKQM4H2",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDM84KIB0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IF5TL40A0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "810",
#						"y": "440",
#						"outlet": {
#							"jaxId": "1IF5TMHHI0",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDSKPHB10"
#						},
#						"dir": "L2R"
#					}
#				}
#			]
#		},
#		"desc": "这是一个AI智能体。",
#		"exportAPI": "false",
#		"exportAddOn": "false",
#		"addOnOpts": ""
#	}
#}