#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
##{1IEJ7R4AB0MoreImports#
##}1IEJ7R4AB0MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

##{1IEJ7R4AB0StartDoc#
##}1IEJ7R4AB0StartDoc#
##----------------------------------------------------------------------------
async def nodeChat(session):
	execInput=None
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	BuildIndex, ChooseTool, CheckTool, ShowReply, AskNext, Exit, ResetMsg, AskNewCmd, ShowResult, CallNode, RunNode, ShowNodeResult, PushNodeResult, ShowNodeError, LogNodeError, CallTool, RunTool, ShowToolResult, PushToolResult, ShowToolError, LogToolError, ShowMissing = None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None
	##{1IEJ7R4AB0LocalVals#
	##}1IEJ7R4AB0LocalVals#
	
	
	def parseAgentArgs(input):
		execInput=input
		##{1IEJ7R4AB0ParseArgs#
		##}1IEJ7R4AB0ParseArgs#
	
	##{1IEJ7R4AB0PreContext#
	##}1IEJ7R4AB0PreContext#
	globalContext = session.globalContext
	context = {}
	##{1IEJ7R4AB0PostContext#
	##}1IEJ7R4AB0PostContext#
	agent,segs = None, {}
	
	async def BuildIndex_exec(input):#//:1IEJ7T8890
		result=input
		##{1IEJ7T8890Code#
		##}1IEJ7T8890Code#
		return {"seg":ChooseTool,"result":(result),"preSeg":"1IEJ7T8890","outlet":"1IEJMKM2E0"}
	segs["BuildIndex"]=BuildIndex={
		"exec":BuildIndex_exec,
		"name":"BuildIndex",
		"jaxId":"1IEJ7T8890",
		"url":"BuildIndex@"+agentURL
	}
	
	async def ChooseTool_exec(input):#//:1IEJ7TVC40
		prompt=None
		result=None
		
		opts={
			"mode":"gpt-3.5-turbo",
			"maxToken":2000,
			"temperature":0,
			"topP":1,
			"fqcP":0,
			"prcP":0,
			"secret":false,
			"responseFormat":"text"
		}
		chatMem=ChooseTool.get("messages",[])
		seed=""
		if(seed):
			opts.seed=seed
		messages=[
			{"role":"system","content":"You are a smart assistant."},
		]
		prompt=input
		if(prompt):
			if not isinstance(prompt,str):
				prompt=json.dumps(prompt,indent=4)
			messages.append({"role":"user","content":prompt})
		result=await session.callSegLLM("ChooseTool@"+agentURL,opts,messages,true)
		return {"seg":CheckTool,"result":(result),"preSeg":"1IEJ7TVC40","outlet":"1IEJMKM2F0"}
	segs["ChooseTool"]=ChooseTool={
		"exec":ChooseTool_exec,
		"name":"ChooseTool",
		"jaxId":"1IEJ7TVC40",
		"url":"ChooseTool@"+agentURL
	}
	
	async def CheckTool_exec(input):#//:1IEJ7V0MT0
		if input=="Missing":
			return {"seg":ShowMissing,"result":(input),"preSeg":"1IEJ7V0MT0","outlet":"1IEJMKM2F1"}
		if input=="CallNode":
			return {"seg":CallNode,"result":(input),"preSeg":"1IEJ7V0MT0","outlet":"1IEJ7VLQU0"}
		if input=="UseTool":
			return {"seg":CallTool,"result":(input),"preSeg":"1IEJ7V0MT0","outlet":"1IEJ7VTFJ0"}
		if input=="Finish":
			return {"seg":ShowReply,"result":(input),"preSeg":"1IEJ7V0MT0","outlet":"1IEJ809VN0"}
		if input=="Abort":
			return {"seg":ShowReply,"result":(input),"preSeg":"1IEJ7V0MT0","outlet":"1IEJ80G8R0"}
		if input=="Reply":
			return {"seg":ShowReply,"result":(input),"preSeg":"1IEJ7V0MT0","outlet":"1IEJ80QAS0"}
		#default/else:
		return {"seg":ShowResult,"result":(input),"preSeg":"1IEJ7V0MT0","outlet":"1IEJMKM2G0"}
	segs["CheckTool"]=CheckTool={
		"exec":CheckTool_exec,
		"name":"CheckTool",
		"jaxId":"1IEJ7V0MT0",
		"url":"CheckTool@"+agentURL
	}
	
	async def ShowReply_exec(input):#//:1IEJ81VLD0
		result=input
		role="assistant"
		content=input
		await session.addChatText(role,content,{})
		return {"seg":AskNext,"result":(result),"preSeg":"1IEJ81VLD0","outlet":"1IEJMKM2G1"}
	segs["ShowReply"]=ShowReply={
		"exec":ShowReply_exec,
		"name":"ShowReply",
		"jaxId":"1IEJ81VLD0",
		"url":"ShowReply@"+agentURL
	}
	
	async def AskNext_exec(input):#//:1IEJ83OM50
		prompt=("Please confirm") or input
		items=[
			{"icon":"/~/-tabos/shared/assets/hudbox.svg","text":"Item 2","code":0},
			{"icon":"/~/-tabos/shared/assets/hudbox.svg","text":"Item 1","code":1},
		]
		result=""
		item=None
		multi=false
		
		result,item=await session.askUserRaw({"type":"menu","prompt":prompt,"multiSelect":multi,"items":items})
		if(multi):
			return {"seg":Exit,"result":(result),"preSeg":"1IEJ83OM50","outlet":"1IEJ83OLF1"}
		
		if(item["code"]==0):
			return {"seg":Exit,"result":(result),"preSeg":"1IEJ83OM50","outlet":"1IEJ83OLF1"}
		if(item["code"]==1):
			return {"seg":ResetMsg,"result":(result),"preSeg":"1IEJ83OM50","outlet":"1IEJ83OLF0"}
		return {"result":result}
	segs["AskNext"]=AskNext={
		"exec":AskNext_exec,
		"name":"AskNext",
		"jaxId":"1IEJ83OM50",
		"url":"AskNext@"+agentURL
	}
	
	async def Exit_exec(input):#//:1IEJ856AD0
		result=input
		##{1IEJ856AD0Code#
		##}1IEJ856AD0Code#
		return {"result":result}
	segs["Exit"]=Exit={
		"exec":Exit_exec,
		"name":"Exit",
		"jaxId":"1IEJ856AD0",
		"url":"Exit@"+agentURL
	}
	
	async def ResetMsg_exec(input):#//:1IEJ85PII0
		result=input
		##{1IEJ85PII0Code#
		##}1IEJ85PII0Code#
		return {"seg":AskNewCmd,"result":(result),"preSeg":"1IEJ85PII0","outlet":"1IEJMKM2G3"}
	segs["ResetMsg"]=ResetMsg={
		"exec":ResetMsg_exec,
		"name":"ResetMsg",
		"jaxId":"1IEJ85PII0",
		"url":"ResetMsg@"+agentURL
	}
	
	async def AskNewCmd_exec(input):#//:1IEJ86QVV0
		tip=""
		tipRole="assistant"
		prompt=undefined
		placeholder=""
		text=""
		result=""
		if tip:
			await session.addChatText(tipRole,tip,{})
		result=await session.askChatInput({"type":"input","prompt":prompt,"placeholder":placeholder,"text":text})
		await session.addChatText("user",result,{})
		return {"seg":ChooseTool,"result":(result),"preSeg":"1IEJ86QVV0","outlet":"1IEJMKM2G4"}
	segs["AskNewCmd"]=AskNewCmd={
		"exec":AskNewCmd_exec,
		"name":"AskNewCmd",
		"jaxId":"1IEJ86QVV0",
		"url":"AskNewCmd@"+agentURL
	}
	
	async def ShowResult_exec(input):#//:1IEJ882R40
		result=input
		role="assistant"
		content=input
		await session.addChatText(role,content,{})
		return {"seg":ChooseTool,"result":(result),"preSeg":"1IEJ882R40","outlet":"1IEJMKM2G5"}
	segs["ShowResult"]=ShowResult={
		"exec":ShowResult_exec,
		"name":"ShowResult",
		"jaxId":"1IEJ882R40",
		"url":"ShowResult@"+agentURL
	}
	
	async def CallNode_exec(input):#//:1IEJ8ABLC0
		result=input
		##{1IEJ8ABLC0Code#
		##}1IEJ8ABLC0Code#
		return {"seg":RunNode,"result":(result),"preSeg":"1IEJ8ABLC0","outlet":"1IEJMKM2G6","catchSeg":ShowNodeError,"catchlet":"1IEJMKM2G7"}
	segs["CallNode"]=CallNode={
		"exec":CallNode_exec,
		"name":"CallNode",
		"jaxId":"1IEJ8ABLC0",
		"url":"CallNode@"+agentURL
	}
	
	async def RunNode_exec(input):#//:1IEJ8B6FV0
		result=input
		##{1IEJ8B6FV0Code#
		##}1IEJ8B6FV0Code#
		return {"seg":ShowNodeResult,"result":(result),"preSeg":"1IEJ8B6FV0","outlet":"1IEJMKM2G8"}
	segs["RunNode"]=RunNode={
		"exec":RunNode_exec,
		"name":"RunNode",
		"jaxId":"1IEJ8B6FV0",
		"url":"RunNode@"+agentURL
	}
	
	async def ShowNodeResult_exec(input):#//:1IEJ8BIPV0
		result=input
		role="assistant"
		content=input
		await session.addChatText(role,content,{})
		return {"seg":PushNodeResult,"result":(result),"preSeg":"1IEJ8BIPV0","outlet":"1IEJMKM2G9"}
	segs["ShowNodeResult"]=ShowNodeResult={
		"exec":ShowNodeResult_exec,
		"name":"ShowNodeResult",
		"jaxId":"1IEJ8BIPV0",
		"url":"ShowNodeResult@"+agentURL
	}
	
	async def PushNodeResult_exec(input):#//:1IEJ8D4V50
		result=input
		role="assistant"
		content=input
		await session.addChatText(role,content,{})
		return {"seg":ChooseTool,"result":(result),"preSeg":"1IEJ8D4V50","outlet":"1IEJMKM2G10"}
	segs["PushNodeResult"]=PushNodeResult={
		"exec":PushNodeResult_exec,
		"name":"PushNodeResult",
		"jaxId":"1IEJ8D4V50",
		"url":"PushNodeResult@"+agentURL
	}
	
	async def ShowNodeError_exec(input):#//:1IEJ8DHOF0
		result=input
		role="assistant"
		content=input
		await session.addChatText(role,content,{})
		return {"seg":LogNodeError,"result":(result),"preSeg":"1IEJ8DHOF0","outlet":"1IEJMKM2G11"}
	segs["ShowNodeError"]=ShowNodeError={
		"exec":ShowNodeError_exec,
		"name":"ShowNodeError",
		"jaxId":"1IEJ8DHOF0",
		"url":"ShowNodeError@"+agentURL
	}
	
	async def LogNodeError_exec(input):#//:1IEJ8EECR0
		result=input
		##{1IEJ8EECR0Code#
		##}1IEJ8EECR0Code#
		return {"seg":ChooseTool,"result":(result),"preSeg":"1IEJ8EECR0","outlet":"1IEJMKM2G12"}
	segs["LogNodeError"]=LogNodeError={
		"exec":LogNodeError_exec,
		"name":"LogNodeError",
		"jaxId":"1IEJ8EECR0",
		"url":"LogNodeError@"+agentURL
	}
	
	async def CallTool_exec(input):#//:1IEJ8GR760
		result=input
		##{1IEJ8GR760Code#
		##}1IEJ8GR760Code#
		return {"seg":RunTool,"result":(result),"preSeg":"1IEJ8GR760","outlet":"1IEJMKM2G13","catchSeg":ShowToolError,"catchlet":"1IEJMKM2G14"}
	segs["CallTool"]=CallTool={
		"exec":CallTool_exec,
		"name":"CallTool",
		"jaxId":"1IEJ8GR760",
		"url":"CallTool@"+agentURL
	}
	
	async def RunTool_exec(input):#//:1IEJ8H8B40
		result=input
		##{1IEJ8H8B40Code#
		##}1IEJ8H8B40Code#
		return {"seg":ShowToolResult,"result":(result),"preSeg":"1IEJ8H8B40","outlet":"1IEJMKM2G15"}
	segs["RunTool"]=RunTool={
		"exec":RunTool_exec,
		"name":"RunTool",
		"jaxId":"1IEJ8H8B40",
		"url":"RunTool@"+agentURL
	}
	
	async def ShowToolResult_exec(input):#//:1IEJ8I5EL0
		result=input
		role="assistant"
		content=input
		await session.addChatText(role,content,{})
		return {"seg":PushToolResult,"result":(result),"preSeg":"1IEJ8I5EL0","outlet":"1IEJMKM2G16"}
	segs["ShowToolResult"]=ShowToolResult={
		"exec":ShowToolResult_exec,
		"name":"ShowToolResult",
		"jaxId":"1IEJ8I5EL0",
		"url":"ShowToolResult@"+agentURL
	}
	
	async def PushToolResult_exec(input):#//:1IEJ8IIJO0
		result=input
		##{1IEJ8IIJO0Code#
		##}1IEJ8IIJO0Code#
		return {"seg":ChooseTool,"result":(result),"preSeg":"1IEJ8IIJO0","outlet":"1IEJMKM2H0"}
	segs["PushToolResult"]=PushToolResult={
		"exec":PushToolResult_exec,
		"name":"PushToolResult",
		"jaxId":"1IEJ8IIJO0",
		"url":"PushToolResult@"+agentURL
	}
	
	async def ShowToolError_exec(input):#//:1IEJ8L3RI0
		result=input
		role="assistant"
		content=input
		await session.addChatText(role,content,{})
		return {"seg":LogToolError,"result":(result),"preSeg":"1IEJ8L3RI0","outlet":"1IEJMKM2H1"}
	segs["ShowToolError"]=ShowToolError={
		"exec":ShowToolError_exec,
		"name":"ShowToolError",
		"jaxId":"1IEJ8L3RI0",
		"url":"ShowToolError@"+agentURL
	}
	
	async def LogToolError_exec(input):#//:1IEJ8LPQ80
		result=input
		##{1IEJ8LPQ80Code#
		##}1IEJ8LPQ80Code#
		return {"seg":ChooseTool,"result":(result),"preSeg":"1IEJ8LPQ80","outlet":"1IEJMKM2H2"}
	segs["LogToolError"]=LogToolError={
		"exec":LogToolError_exec,
		"name":"LogToolError",
		"jaxId":"1IEJ8LPQ80",
		"url":"LogToolError@"+agentURL
	}
	
	async def ShowMissing_exec(input):#//:1IEJ8PN5M0
		result=input
		role="assistant"
		content=input
		await session.addChatText(role,content,{})
		return {"result":result}
	segs["ShowMissing"]=ShowMissing={
		"exec":ShowMissing_exec,
		"name":"ShowMissing",
		"jaxId":"1IEJ8PN5M0",
		"url":"ShowMissing@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1IEJ7R4AB0PreEntry#
		##}1IEJ7R4AB0PreEntry#
		result = {"seg":BuildIndex,"input":input}
		##{1IEJ7R4AB0PostEntry#
		##}1IEJ7R4AB0PostEntry#
		return result
	agent = {
		"isAIAgent": true,
		"session": session,
		"name": "nodeChat",
		"url": agentURL,
		"baseDir": basePath,
		"autoStart": true,
		"jaxId": "1IEJ7R4AB0",
		"context": context,
		"livingSeg": None,
		"execChat": execAgent,
		##{1IEJ7R4AB0MoreAgentAttrs#
		##}1IEJ7R4AB0MoreAgentAttrs#
	}
	##{1IEJ7R4AB0PostAgent#
	##}1IEJ7R4AB0PostAgent#
	return agent
##{1IEJ7R4AB0ExCodes#
##}1IEJ7R4AB0ExCodes#

ChatAPI=None

default=nodeChat
__all__=["default","nodeChat","ChatAPI"]
""">>>CodyExport
let ChatAPI,Exports;

return {api:ChatAPI,export:Exports};
>>>CodyExport"""
#Cody Project Doc
#{
#	"type": "docfile",
#	"def": "DocAIAgent",
#	"jaxId": "1IEJ7R4AB0",
#	"attrs": {
#		"editObjs": {
#			"jaxId": "1IEJ7R4AB1",
#			"attrs": {
#				"nodeChat": {
#					"type": "objclass",
#					"def": "ObjClass",
#					"jaxId": "1IEJ7R4AC0",
#					"attrs": {
#						"exportType": "UI Data Template",
#						"constructArgs": {
#							"jaxId": "1IEJ7R4AC1",
#							"attrs": {}
#						},
#						"superClass": "",
#						"properties": {
#							"jaxId": "1IEJ7R4AC2",
#							"attrs": {}
#						},
#						"functions": {
#							"jaxId": "1IEJ7R4AC3",
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
#			"jaxId": "1IEJ7R4AB2",
#			"attrs": {}
#		},
#		"entry": "",
#		"autoStart": "true",
#		"inBrowser": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1IEJ7R4AB3",
#			"attrs": {}
#		},
#		"localVars": {
#			"jaxId": "1IEJ7R4AB4",
#			"attrs": {}
#		},
#		"context": {
#			"jaxId": "1IEJ7R4AB5",
#			"attrs": {}
#		},
#		"globalMockup": {
#			"jaxId": "1IEJ7R4AB6",
#			"attrs": {}
#		},
#		"segs": {
#			"attrs": [
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEJ7T8890",
#					"attrs": {
#						"id": "BuildIndex",
#						"viewName": "",
#						"label": "",
#						"x": "80",
#						"y": "475",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJMKM2E0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ7TVC40"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "callLLM",
#					"jaxId": "1IEJ7TVC40",
#					"attrs": {
#						"id": "ChooseTool",
#						"viewName": "",
#						"label": "",
#						"x": "340",
#						"y": "475",
#						"desc": "执行一次LLM调用。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"platform": "\"OpenAI\"",
#						"mode": "GPT-3.5",
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
#							"jaxId": "1IEJMKM2F0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ7V0MT0"
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
#					"def": "brunch",
#					"jaxId": "1IEJ7V0MT0",
#					"attrs": {
#						"id": "CheckTool",
#						"viewName": "",
#						"label": "",
#						"x": "605",
#						"y": "475",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K4",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K5",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJMKM2G0",
#							"attrs": {
#								"id": "Default",
#								"desc": "输出节点。",
#								"output": ""
#							},
#							"linkedSeg": "1IEJ882R40"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IEJMKM2F1",
#									"attrs": {
#										"id": "Missing",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEJMKM2K6",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEJMKM2K7",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": ""
#									},
#									"linkedSeg": "1IEJ8PN5M0"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IEJ7VLQU0",
#									"attrs": {
#										"id": "CallNode",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEJMKM2K8",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEJMKM2K9",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": ""
#									},
#									"linkedSeg": "1IEJ8ABLC0"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IEJ7VTFJ0",
#									"attrs": {
#										"id": "UseTool",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEJMKM2K10",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEJMKM2K11",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": ""
#									},
#									"linkedSeg": "1IEJ8GR760"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IEJ809VN0",
#									"attrs": {
#										"id": "Finish",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEJMKM2K12",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEJMKM2K13",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": ""
#									},
#									"linkedSeg": "1IEJ81VLD0"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IEJ80G8R0",
#									"attrs": {
#										"id": "Abort",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEJMKM2K14",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEJMKM2K15",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": ""
#									},
#									"linkedSeg": "1IEJ81VLD0"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IEJ80QAS0",
#									"attrs": {
#										"id": "Reply",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEJMKM2K16",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEJMKM2K17",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": ""
#									},
#									"linkedSeg": "1IEJ81VLD0"
#								}
#							]
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IEJ81VLD0",
#					"attrs": {
#						"id": "ShowReply",
#						"viewName": "",
#						"label": "",
#						"x": "880",
#						"y": "505",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K18",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K19",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1IEJMKM2G1",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ83OM50"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "askMenu",
#					"jaxId": "1IEJ83OM50",
#					"attrs": {
#						"id": "AskNext",
#						"viewName": "",
#						"label": "",
#						"x": "1115",
#						"y": "505",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"prompt": "Please confirm",
#						"multi": "false",
#						"withChat": "false",
#						"outlet": {
#							"jaxId": "1IEJMKM2K20",
#							"attrs": {
#								"id": "ChatInput",
#								"desc": "输出节点。",
#								"codes": "false"
#							},
#							"linkedSeg": "1IEJ87GIJ0"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIButtonOutlet",
#									"jaxId": "1IEJ83OLF1",
#									"attrs": {
#										"id": "Exit",
#										"desc": "输出节点。",
#										"text": "Item 2",
#										"result": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEJMKM2K21",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEJMKM2K22",
#											"attrs": {
#												"cast": ""
#											}
#										}
#									},
#									"linkedSeg": "1IEJ856AD0"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIButtonOutlet",
#									"jaxId": "1IEJ83OLF0",
#									"attrs": {
#										"id": "NewChat",
#										"desc": "输出节点。",
#										"text": "Item 1",
#										"result": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEJMKM2K23",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEJMKM2K24",
#											"attrs": {
#												"cast": ""
#											}
#										}
#									},
#									"linkedSeg": "1IEJ85PII0"
#								}
#							]
#						},
#						"silent": "false"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEJ856AD0",
#					"attrs": {
#						"id": "Exit",
#						"viewName": "",
#						"label": "",
#						"x": "1365",
#						"y": "435",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "flag.svg",
#						"context": {
#							"jaxId": "1IEJMKM2K25",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K26",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJMKM2G2",
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
#					"def": "code",
#					"jaxId": "1IEJ85PII0",
#					"attrs": {
#						"id": "ResetMsg",
#						"viewName": "",
#						"label": "",
#						"x": "1365",
#						"y": "505",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K27",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K28",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJMKM2G3",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ86QVV0"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "askChat",
#					"jaxId": "1IEJ86QVV0",
#					"attrs": {
#						"id": "AskNewCmd",
#						"viewName": "",
#						"label": "",
#						"x": "1595",
#						"y": "505",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K29",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K30",
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
#							"jaxId": "1IEJMKM2G4",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ87B6Q0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IEJ87B6Q0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1755",
#						"y": "685",
#						"outlet": {
#							"jaxId": "1IEJMKM2K31",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ87GIJ0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IEJ87GIJ0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1265",
#						"y": "685",
#						"outlet": {
#							"jaxId": "1IEJMKM2K32",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ88HEV0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IEJ882R40",
#					"attrs": {
#						"id": "ShowResult",
#						"viewName": "",
#						"label": "",
#						"x": "880",
#						"y": "605",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K33",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K34",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1IEJMKM2G5",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ88HEV0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IEJ88HEV0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1030",
#						"y": "685",
#						"outlet": {
#							"jaxId": "1IEJMKM2K35",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ88PTS0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IEJ88PTS0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "560",
#						"y": "685",
#						"outlet": {
#							"jaxId": "1IEJMKM2K36",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ88VFV0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IEJ88VFV0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "365",
#						"y": "555",
#						"outlet": {
#							"jaxId": "1IEJMKM2K37",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ7TVC40"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "tryCatch",
#					"jaxId": "1IEJ8ABLC0",
#					"attrs": {
#						"id": "CallNode",
#						"viewName": "",
#						"label": "",
#						"x": "880",
#						"y": "170",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K38",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K39",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJMKM2G6",
#							"attrs": {
#								"id": "Try",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8B6FV0"
#						},
#						"catchlet": {
#							"jaxId": "1IEJMKM2G7",
#							"attrs": {
#								"id": "Catch",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8DHOF0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEJ8B6FV0",
#					"attrs": {
#						"id": "RunNode",
#						"viewName": "",
#						"label": "",
#						"x": "1115",
#						"y": "90",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K40",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K41",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJMKM2G8",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8BIPV0"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IEJ8BIPV0",
#					"attrs": {
#						"id": "ShowNodeResult",
#						"viewName": "",
#						"label": "",
#						"x": "1370",
#						"y": "90",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K42",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K43",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1IEJMKM2G9",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8D4V50"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IEJ8D4V50",
#					"attrs": {
#						"id": "PushNodeResult",
#						"viewName": "",
#						"label": "",
#						"x": "1655",
#						"y": "90",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K44",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K45",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1IEJMKM2G10",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8EVHG0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IEJ8DHOF0",
#					"attrs": {
#						"id": "ShowNodeError",
#						"viewName": "",
#						"label": "",
#						"x": "1115",
#						"y": "185",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K46",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K47",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1IEJMKM2G11",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8EECR0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEJ8EECR0",
#					"attrs": {
#						"id": "LogNodeError",
#						"viewName": "",
#						"label": "",
#						"x": "1365",
#						"y": "185",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K48",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K49",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJMKM2G12",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8F4EA0"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IEJ8EVHG0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1845",
#						"y": "-55",
#						"outlet": {
#							"jaxId": "1IEJMKM2K50",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8FLL30"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connectorL",
#					"jaxId": "1IEJ8F4EA0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1810",
#						"y": "185",
#						"outlet": {
#							"jaxId": "1IEJMKM2K51",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8EVHG0"
#						},
#						"dir": "L2R"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IEJ8FLL30",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1130",
#						"y": "-55",
#						"outlet": {
#							"jaxId": "1IEJMKM2K52",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8G31B0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IEJ8G31B0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "715",
#						"y": "-55",
#						"outlet": {
#							"jaxId": "1IEJMKM2K53",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8G6L20"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IEJ8G6L20",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "365",
#						"y": "395",
#						"outlet": {
#							"jaxId": "1IEJMKM2K54",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ7TVC40"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "tryCatch",
#					"jaxId": "1IEJ8GR760",
#					"attrs": {
#						"id": "CallTool",
#						"viewName": "",
#						"label": "",
#						"x": "880",
#						"y": "355",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K55",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K56",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJMKM2G13",
#							"attrs": {
#								"id": "Try",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8H8B40"
#						},
#						"catchlet": {
#							"jaxId": "1IEJMKM2G14",
#							"attrs": {
#								"id": "Catch",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8L3RI0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEJ8H8B40",
#					"attrs": {
#						"id": "RunTool",
#						"viewName": "",
#						"label": "",
#						"x": "1115",
#						"y": "280",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K57",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K58",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJMKM2G15",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8I5EL0"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IEJ8I5EL0",
#					"attrs": {
#						"id": "ShowToolResult",
#						"viewName": "",
#						"label": "",
#						"x": "1365",
#						"y": "280",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K59",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K60",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1IEJMKM2G16",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8IIJO0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEJ8IIJO0",
#					"attrs": {
#						"id": "PushToolResult",
#						"viewName": "",
#						"label": "",
#						"x": "1655",
#						"y": "280",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K61",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K62",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJMKM2H0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8EVHG0"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IEJ8L3RI0",
#					"attrs": {
#						"id": "ShowToolError",
#						"viewName": "",
#						"label": "",
#						"x": "1115",
#						"y": "370",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K63",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K64",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1IEJMKM2H1",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8LPQ80"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEJ8LPQ80",
#					"attrs": {
#						"id": "LogToolError",
#						"viewName": "",
#						"label": "",
#						"x": "1365",
#						"y": "370",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJMKM2K65",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K66",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEJMKM2H2",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8O1ML0"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connectorL",
#					"jaxId": "1IEJ8O1ML0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1810",
#						"y": "370",
#						"outlet": {
#							"jaxId": "1IEJMKM2K67",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJ8EVHG0"
#						},
#						"dir": "L2R"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IEJ8PN5M0",
#					"attrs": {
#						"id": "ShowMissing",
#						"viewName": "",
#						"label": "",
#						"x": "880",
#						"y": "15",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "flag.svg",
#						"context": {
#							"jaxId": "1IEJMKM2K68",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJMKM2K69",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1IEJMKM2H3",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						}
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