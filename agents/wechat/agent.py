#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
##{1HIRHBGQ60MoreImports#
##}1HIRHBGQ60MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

##{1HIRHBGQ60StartDoc#
##}1HIRHBGQ60StartDoc#
##----------------------------------------------------------------------------
async def agent(session):
	execInput=None
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	OnStart, OnLogin, OnMessage, OnLogout, OnQRCode, CheckGroup, HandleGroup, CheckFrom, IgnoreSelf, HandleMaster, Echo, HandleOthers = None, None, None, None, None, None, None, None, None, None, None, None
	config = None
	bot = None
	chatChannel = None
	masterNickname = ""
	masterId = ""
	selfId = ""
	
	##{1HIRHBGQ60LocalVals#
	##}1HIRHBGQ60LocalVals#
	
	
	def parseAgentArgs(input):
		execInput=input
		##{1HIRHBGQ60ParseArgs#
		##}1HIRHBGQ60ParseArgs#
	
	##{1HIRHBGQ60PreContext#
	##}1HIRHBGQ60PreContext#
	globalContext = session.globalContext
	context = {}
	##{1HIRHBGQ60PostContext#
	##}1HIRHBGQ60PostContext#
	agent,segs = None, {}
	
	async def OnStart_exec(input):#//:1IEG1DIP70
		result=input
		##{1IEG1DIP70Code#
		nonlocal bot,config
		bot=input
		config=bot.config
		result=True
		##}1IEG1DIP70Code#
		return {"result":result}
	segs["OnStart"]=OnStart={
		"exec":OnStart_exec,
		"name":"OnStart",
		"jaxId":"1IEG1DIP70",
		"url":"OnStart@"+agentURL
	}
	
	async def OnLogin_exec(input):#//:1IEG190QI0
		result=input
		##{1IEG190QI0Code#
		nonlocal bot,config,chatChannel,masterNickname,masterId,selfId
		chatChannel=bot.chatChannel
		masterNickname=config.get("masterNickname")
		masterId=config.get("masterId")
		selfId=chatChannel.user_id
		result=True
		##}1IEG190QI0Code#
		return {"result":result}
	segs["OnLogin"]=OnLogin={
		"exec":OnLogin_exec,
		"name":"OnLogin",
		"jaxId":"1IEG190QI0",
		"url":"OnLogin@"+agentURL
	}
	
	async def OnMessage_exec(input):#//:1IEG19O890
		result=input
		##{1IEG19O890Code#
		message=input.get("message")
		if message.from_user_id==bot.chatChannel.user_id:
			print("This is message from myself, ignore")
		if message.from_user_nickname==masterNickname or message.from_user_id==masterId:
			print("This is message from my master: "+message.content)
		result=message
		##}1IEG19O890Code#
		return {"seg":CheckGroup,"result":(result),"preSeg":"1IEG19O890","outlet":"1IEG1AGNM0"}
	segs["OnMessage"]=OnMessage={
		"exec":OnMessage_exec,
		"name":"OnMessage",
		"jaxId":"1IEG19O890",
		"url":"OnMessage@"+agentURL
	}
	
	async def OnLogout_exec(input):#//:1IEG1APHA0
		result=input
		##{1IEG1APHA0Code#
		##}1IEG1APHA0Code#
		return {"result":result}
	segs["OnLogout"]=OnLogout={
		"exec":OnLogout_exec,
		"name":"OnLogout",
		"jaxId":"1IEG1APHA0",
		"url":"OnLogout@"+agentURL
	}
	
	async def OnQRCode_exec(input):#//:1IEG1BSNG0
		result=input
		##{1IEG1BSNG0Code#
		##}1IEG1BSNG0Code#
		return {"result":result}
	segs["OnQRCode"]=OnQRCode={
		"exec":OnQRCode_exec,
		"name":"OnQRCode",
		"jaxId":"1IEG1BSNG0",
		"url":"OnQRCode@"+agentURL
	}
	
	async def CheckGroup_exec(input):#//:1IEGULP3I0
		if input.is_group:
			return {"seg":HandleGroup,"result":(input),"preSeg":"1IEGULP3I0","outlet":"1IEGUOM510"}
		#default/else:
		return {"seg":CheckFrom,"result":(input),"preSeg":"1IEGULP3I0","outlet":"1IEGUOM520"}
	segs["CheckGroup"]=CheckGroup={
		"exec":CheckGroup_exec,
		"name":"CheckGroup",
		"jaxId":"1IEGULP3I0",
		"url":"CheckGroup@"+agentURL
	}
	
	async def HandleGroup_exec(input):#//:1IEGUNNSL0
		result=input
		##{1IEGUNNSL0Code#
		##}1IEGUNNSL0Code#
		return {"result":result}
	segs["HandleGroup"]=HandleGroup={
		"exec":HandleGroup_exec,
		"name":"HandleGroup",
		"jaxId":"1IEGUNNSL0",
		"url":"HandleGroup@"+agentURL
	}
	
	async def CheckFrom_exec(input):#//:1IEGUO61N0
		if input.from_user_nickname==selfId:
			output=input
			return {"seg":IgnoreSelf,"result":(output),"preSeg":"1IEGUO61N0","outlet":"1IEGUOM522"}
		if input.from_user_nickname==masterNickname or input.from_user_id==masterId:
			output=input
			return {"seg":HandleMaster,"result":(output),"preSeg":"1IEGUO61N0","outlet":"1IEGV0HDH0"}
		#default/else:
		return {"seg":HandleOthers,"result":(input),"preSeg":"1IEGUO61N0","outlet":"1IEGUOM523"}
	segs["CheckFrom"]=CheckFrom={
		"exec":CheckFrom_exec,
		"name":"CheckFrom",
		"jaxId":"1IEGUO61N0",
		"url":"CheckFrom@"+agentURL
	}
	
	async def IgnoreSelf_exec(input):#//:1IEGV3MUR0
		result=input
		##{1IEGV3MUR0Code#
		##}1IEGV3MUR0Code#
		return {"result":result}
	segs["IgnoreSelf"]=IgnoreSelf={
		"exec":IgnoreSelf_exec,
		"name":"IgnoreSelf",
		"jaxId":"1IEGV3MUR0",
		"url":"IgnoreSelf@"+agentURL
	}
	
	async def HandleMaster_exec(input):#//:1IEGV43DU0
		result=input
		##{1IEGV43DU0Code#
		nonlocal masterId
		if not masterId:
			masterId=input.from_user_id
			config["masterId"]=masterId
			await bot.saveConfig()
		result={"agent":"master.py","input":input}
		result={"agent":"others.py","input":input}
		##}1IEGV43DU0Code#
		return {"result":result}
	segs["HandleMaster"]=HandleMaster={
		"exec":HandleMaster_exec,
		"name":"HandleMaster",
		"jaxId":"1IEGV43DU0",
		"url":"HandleMaster@"+agentURL
	}
	
	async def Echo_exec(input):#//:1IEH4S48Q0
		result=input
		role="assistant"
		content=f"[{input.content}]"
		await session.addChatText(role,content,{})
		return {"result":result}
	segs["Echo"]=Echo={
		"exec":Echo_exec,
		"name":"Echo",
		"jaxId":"1IEH4S48Q0",
		"url":"Echo@"+agentURL
	}
	
	async def HandleOthers_exec(input):#//:1IFGSMIR90
		result=input
		##{1IFGSMIR90Code#
		result={"agent":"others.py","input":input}
		##}1IFGSMIR90Code#
		return {"result":result}
	segs["HandleOthers"]=HandleOthers={
		"exec":HandleOthers_exec,
		"name":"HandleOthers",
		"jaxId":"1IFGSMIR90",
		"url":"HandleOthers@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1HIRHBGQ60PreEntry#
		##}1HIRHBGQ60PreEntry#
		result = {"seg":OnStart,"input":input}
		##{1HIRHBGQ60PostEntry#
		##}1HIRHBGQ60PostEntry#
		return result
	agent = {
		"isAIAgent": true,
		"session": session,
		"name": "agent",
		"url": agentURL,
		"baseDir": basePath,
		"autoStart": true,
		"jaxId": "1HIRHBGQ60",
		"context": context,
		"livingSeg": None,
		"execChat": execAgent,
		##{1HIRHBGQ60MoreAgentAttrs#
		"segs":segs
		##}1HIRHBGQ60MoreAgentAttrs#
	}
	##{1HIRHBGQ60PostAgent#
	##}1HIRHBGQ60PostAgent#
	return agent
##{1HIRHBGQ60ExCodes#
##}1HIRHBGQ60ExCodes#

ChatAPI=[{
	"def":{
		"name": "agent",
		"description": "这是一个AI代理。",
		"parameters":{
			"type": "object",
			"properties":{
			}
		}
	},
	"agent": agent
}]

default=agent
__all__=["default","agent","ChatAPI"]
""">>>CodyExport
let ChatAPI,Exports;
ChatAPI=[{
	def:{
		name: "agent",
		description: "这是一个AI代理。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	agent: true
}];

return {api:ChatAPI,export:Exports};
>>>CodyExport"""
#Cody Project Doc
#{
#	"type": "docfile",
#	"def": "DocAIAgent",
#	"jaxId": "1HIRHBGQ60",
#	"attrs": {
#		"editObjs": {
#			"jaxId": "1HIRHBM1Q0",
#			"attrs": {}
#		},
#		"agent": {
#			"jaxId": "1HIRHBM1R0",
#			"attrs": {}
#		},
#		"entry": "GetInput",
#		"autoStart": "true",
#		"inBrowser": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1HIRHBM1R4",
#			"attrs": {}
#		},
#		"localVars": {
#			"jaxId": "1HIRHBM1R1",
#			"attrs": {
#				"config": {
#					"type": "auto",
#					"valText": "#None"
#				},
#				"bot": {
#					"type": "auto",
#					"valText": "#None"
#				},
#				"chatChannel": {
#					"type": "auto",
#					"valText": "#None"
#				},
#				"masterNickname": {
#					"type": "string",
#					"valText": ""
#				},
#				"masterId": {
#					"type": "string",
#					"valText": ""
#				},
#				"selfId": {
#					"type": "string",
#					"valText": ""
#				}
#			}
#		},
#		"context": {
#			"jaxId": "1HIRHBM1R2",
#			"attrs": {}
#		},
#		"globalMockup": {
#			"jaxId": "1HIRHBM1R3",
#			"attrs": {}
#		},
#		"segs": {
#			"attrs": [
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEG1DIP70",
#					"attrs": {
#						"id": "OnStart",
#						"viewName": "",
#						"label": "",
#						"x": "95",
#						"y": "90",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEG1EF7J4",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEG1EF7J5",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEG1EF7H2",
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
#					"jaxId": "1IEG190QI0",
#					"attrs": {
#						"id": "OnLogin",
#						"viewName": "",
#						"label": "",
#						"x": "95",
#						"y": "200",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEG1AGNO0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEG1AGNO1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEG1AGNL0",
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
#					"jaxId": "1IEG19O890",
#					"attrs": {
#						"id": "OnMessage",
#						"viewName": "",
#						"label": "",
#						"x": "95",
#						"y": "430",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEG1AGNO2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEG1AGNO3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEG1AGNM0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEGULP3I0"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEG1APHA0",
#					"attrs": {
#						"id": "OnLogout",
#						"viewName": "",
#						"label": "",
#						"x": "95",
#						"y": "315",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEG1EF7J0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEG1EF7J1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEG1EF7H0",
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
#					"jaxId": "1IEG1BSNG0",
#					"attrs": {
#						"id": "OnQRCode",
#						"viewName": "",
#						"label": "",
#						"x": "95",
#						"y": "550",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEG1EF7J2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEG1EF7J3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEG1EF7H1",
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
#					"def": "brunch",
#					"jaxId": "1IEGULP3I0",
#					"attrs": {
#						"id": "CheckGroup",
#						"viewName": "",
#						"label": "",
#						"x": "335",
#						"y": "430",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEGUOUIF0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEGUOUIF1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEGUOM520",
#							"attrs": {
#								"id": "Default",
#								"desc": "输出节点。",
#								"output": "#input"
#							},
#							"linkedSeg": "1IEGUO61N0"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IEGUOM510",
#									"attrs": {
#										"id": "IsGroup",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEGUOUIF2",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEGUOUIF3",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#input.is_group"
#									},
#									"linkedSeg": "1IEGUNNSL0"
#								}
#							]
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEGUNNSL0",
#					"attrs": {
#						"id": "HandleGroup",
#						"viewName": "",
#						"label": "",
#						"x": "580",
#						"y": "335",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEGUOUIF4",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEGUOUIF5",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEGUOM521",
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
#					"def": "brunch",
#					"jaxId": "1IEGUO61N0",
#					"attrs": {
#						"id": "CheckFrom",
#						"viewName": "",
#						"label": "",
#						"x": "580",
#						"y": "510",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEGUOUIF6",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEGUOUIF7",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEGUOM523",
#							"attrs": {
#								"id": "Default",
#								"desc": "输出节点。",
#								"output": ""
#							},
#							"linkedSeg": "1IFGSMIR90"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IEGUOM522",
#									"attrs": {
#										"id": "FromSelf",
#										"desc": "输出节点。",
#										"output": "#input",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEGUOUIF8",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEGUOUIF9",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#input.from_user_nickname==selfId"
#									},
#									"linkedSeg": "1IEGV3MUR0"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IEGV0HDH0",
#									"attrs": {
#										"id": "FromMaster",
#										"desc": "输出节点。",
#										"output": "#input",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEGV6SBB0",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEGV6SBB1",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#input.from_user_nickname==masterNickname or input.from_user_id==masterId"
#									},
#									"linkedSeg": "1IEGV43DU0"
#								}
#							]
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IEGV3MUR0",
#					"attrs": {
#						"id": "IgnoreSelf",
#						"viewName": "",
#						"label": "",
#						"x": "840",
#						"y": "390",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEGV6SBB2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEGV6SBB3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEGV5LGQ0",
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
#					"jaxId": "1IEGV43DU0",
#					"attrs": {
#						"id": "HandleMaster",
#						"viewName": "",
#						"label": "",
#						"x": "840",
#						"y": "510",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEGV6SBB4",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEGV6SBB5",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEGV5LGQ1",
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
#					"def": "output",
#					"jaxId": "1IEH4S48Q0",
#					"attrs": {
#						"id": "Echo",
#						"viewName": "",
#						"label": "",
#						"x": "1080",
#						"y": "510",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEH4TNRF0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEH4TNRF1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#f\"[{input.content}]\"",
#						"outlet": {
#							"jaxId": "1IEH4TNRA0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IFGSMIR90",
#					"attrs": {
#						"id": "HandleOthers",
#						"viewName": "",
#						"label": "",
#						"x": "840",
#						"y": "630",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IFGSO3360",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IFGSO3361",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IFGSO3330",
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
#		"desc": "这是一个AI代理。",
#		"exportAPI": "true",
#		"exportAddOn": "false",
#		"addOnOpts": ""
#	}
#}