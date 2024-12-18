#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
##{1IEHE15JV0MoreImports#
##}1IEHE15JV0MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

##{1IEHE15JV0StartDoc#
##}1IEHE15JV0StartDoc#
##----------------------------------------------------------------------------
async def master(session):
	execInput=None
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	CheckHi, ReplyHi, AskChat, ReplyChat, AskButtons, ReplyLo, ReplyYo, AskMenu, ReplyRepeat, ReadImage, ReplyImage, CallNodeChat, AskCmd, CallNode, NodeChatResult = None, None, None, None, None, None, None, None, None, None, None, None, None, None, None
	##{1IEHE15JV0LocalVals#
	##}1IEHE15JV0LocalVals#
	
	
	def parseAgentArgs(input):
		execInput=input
		##{1IEHE15JV0ParseArgs#
		##}1IEHE15JV0ParseArgs#
	
	##{1IEHE15JV0PreContext#
	##}1IEHE15JV0PreContext#
	globalContext = session.globalContext
	context = {}
	##{1IEHE15JV0PostContext#
	##}1IEHE15JV0PostContext#
	agent,segs = None, {}
	
	async def CheckHi_exec(input):#//:1IEHE28IF0
		if input.content=="x" or input.content=="X":
			return {"seg":AskMenu,"result":(input),"preSeg":"1IEHE28IF0","outlet":"1IEJT4CPM0"}
		if input.ctype.value=="image":
			output=input
			return {"seg":ReadImage,"result":(output),"preSeg":"1IEHE28IF0","outlet":"1IEIKM4B00"}
		if input.content=="hi":
			return {"seg":AskCmd,"result":(input),"preSeg":"1IEHE28IF0","outlet":"1IEHE5KDD0"}
		if input.content=="o" or input.content=="O":
			return {"seg":CallNode,"result":(input),"preSeg":"1IEHE28IF0","outlet":"1IF443OAJ0"}
		#default/else:
		return {"result":input}
	segs["CheckHi"]=CheckHi={
		"exec":CheckHi_exec,
		"name":"CheckHi",
		"jaxId":"1IEHE28IF0",
		"url":"CheckHi@"+agentURL
	}
	
	async def ReplyHi_exec(input):#//:1IEHE3FT60
		result=input
		role="assistant"
		content="Hi"
		await session.addChatText(role,content,{})
		return {"result":result}
	segs["ReplyHi"]=ReplyHi={
		"exec":ReplyHi_exec,
		"name":"ReplyHi",
		"jaxId":"1IEHE3FT60",
		"url":"ReplyHi@"+agentURL
	}
	
	async def AskChat_exec(input):#//:1IEHI8RA20
		tip="What is your command, My master?"
		tipRole="assistant"
		prompt=undefined
		placeholder=""
		text=""
		result=""
		if tip:
			await session.addChatText(tipRole,tip,{})
		result=await session.askChatInput({"type":"input","prompt":prompt,"placeholder":placeholder,"text":text})
		return {"seg":ReplyChat,"result":(result),"preSeg":"1IEHI8RA20","outlet":"1IEHIA0LC0"}
	segs["AskChat"]=AskChat={
		"exec":AskChat_exec,
		"name":"AskChat",
		"jaxId":"1IEHI8RA20",
		"url":"AskChat@"+agentURL
	}
	
	async def ReplyChat_exec(input):#//:1IEHI96A90
		result=input
		role="assistant"
		content=f"[{input}]"
		await session.addChatText(role,content,{})
		return {"result":result}
	segs["ReplyChat"]=ReplyChat={
		"exec":ReplyChat_exec,
		"name":"ReplyChat",
		"jaxId":"1IEHI96A90",
		"url":"ReplyChat@"+agentURL
	}
	
	async def AskButtons_exec(input):#//:1IEHJ6RUT0
		prompt=("Please confirm") or input
		button1=("Say Hi") or "OK"
		button2=("Say Lo") or "Cancel"
		button3=("Say Yo") or ""
		result="";
		value=0;
		result,value=await session.askUserRaw({"type":"confirm","prompt":prompt,"button1":button1,"button2":button2,"button3":button3})
		if(value==1):
			result=("") or result
			return {"seg":ReplyHi,"result":(result),"preSeg":"1IEHJ6RUT0","outlet":"1IEHJ6RU70"}
		if(value==2):
			result=("") or result
			return {"seg":ReplyYo,"result":(result),"preSeg":"1IEHJ6RUT0","outlet":"1IEHJ6RU72"}
		result=("") or result
		return {"seg":ReplyLo,"result":(result),"preSeg":"1IEHJ6RUT0","outlet":"1IEHJ6RU71"}
	
	segs["AskButtons"]=AskButtons={
		"exec":AskButtons_exec,
		"name":"AskButtons",
		"jaxId":"1IEHJ6RUT0",
		"url":"AskButtons@"+agentURL
	}
	
	async def ReplyLo_exec(input):#//:1IEHJRELR0
		result=input
		role="assistant"
		content="Lo"
		await session.addChatText(role,content,{})
		return {"result":result}
	segs["ReplyLo"]=ReplyLo={
		"exec":ReplyLo_exec,
		"name":"ReplyLo",
		"jaxId":"1IEHJRELR0",
		"url":"ReplyLo@"+agentURL
	}
	
	async def ReplyYo_exec(input):#//:1IEHJRRT00
		result=input
		role="assistant"
		content="Yo"
		await session.addChatText(role,content,{})
		return {"result":result}
	segs["ReplyYo"]=ReplyYo={
		"exec":ReplyYo_exec,
		"name":"ReplyYo",
		"jaxId":"1IEHJRRT00",
		"url":"ReplyYo@"+agentURL
	}
	
	async def AskMenu_exec(input):#//:1IEHMCM410
		prompt=("Please confirm") or input
		items=[
			{"icon":"/~/-tabos/shared/assets/hudbox.svg","text":"Say Hi","code":0},
			{"icon":"/~/-tabos/shared/assets/hudbox.svg","text":"Say Lo","code":1},
			{"icon":"/~/-tabos/shared/assets/hudbox.svg","text":"Say Yo","code":2},
		]
		result=""
		item=None
		multi=false
		
		result,item=await session.askUserRaw({"type":"menu","prompt":prompt,"multiSelect":multi,"items":items})
		if(multi):
			return {"seg":ReplyHi,"result":(result),"preSeg":"1IEHMCM410","outlet":"1IEHMCM380"}
		
		if(item["code"]==0):
			return {"seg":ReplyHi,"result":(result),"preSeg":"1IEHMCM410","outlet":"1IEHMCM380"}
		if(item["code"]==1):
			return {"seg":ReplyLo,"result":(result),"preSeg":"1IEHMCM410","outlet":"1IEHMCM381"}
		if(item["code"]==2):
			return {"seg":ReplyYo,"result":(result),"preSeg":"1IEHMCM410","outlet":"1IEHMCM382"}
		return {"result":result}
	segs["AskMenu"]=AskMenu={
		"exec":AskMenu_exec,
		"name":"AskMenu",
		"jaxId":"1IEHMCM410",
		"url":"AskMenu@"+agentURL
	}
	
	async def ReplyRepeat_exec(input):#//:1IEHMDLKD0
		result=input
		role="assistant"
		content=f"[{input}]"
		await session.addChatText(role,content,{})
		return {"result":result}
	segs["ReplyRepeat"]=ReplyRepeat={
		"exec":ReplyRepeat_exec,
		"name":"ReplyRepeat",
		"jaxId":"1IEHMDLKD0",
		"url":"ReplyRepeat@"+agentURL
	}
	
	async def ReadImage_exec(input):#//:1IEIKN6T30
		result=input
		##{1IEIKN6T30Code#
		result=await input.hubURL()
		##}1IEIKN6T30Code#
		return {"seg":ReplyImage,"result":(result),"preSeg":"1IEIKN6T30","outlet":"1IEINDT9M0"}
	segs["ReadImage"]=ReadImage={
		"exec":ReadImage_exec,
		"name":"ReadImage",
		"jaxId":"1IEIKN6T30",
		"url":"ReadImage@"+agentURL
	}
	
	async def ReplyImage_exec(input):#//:1IEINLLKK0
		result=input
		role="assistant"
		content="图片:"
		result=await session.resizeImage(result,256,"JPEG")
		await session.addChatText(role,content,{"image":result})
		return {"result":result}
	segs["ReplyImage"]=ReplyImage={
		"exec":ReplyImage_exec,
		"name":"ReplyImage",
		"jaxId":"1IEINLLKK0",
		"url":"ReplyImage@"+agentURL
	}
	
	async def CallNodeChat_exec(input):#//:1IEJT4L950
		result=None
		sourcePath=pathLib.join(basePath,"/@tabos/NodeChat.py")
		arg=input
		result= await session.pipeChat(sourcePath,arg,false)
		return {"seg":NodeChatResult,"result":(result),"preSeg":"1IEJT4L950","outlet":"1IEJT7FVE0"}
	segs["CallNodeChat"]=CallNodeChat={
		"exec":CallNodeChat_exec,
		"name":"CallNodeChat",
		"jaxId":"1IEJT4L950",
		"url":"CallNodeChat@"+agentURL
	}
	
	async def AskCmd_exec(input):#//:1IEJT66A30
		tip="What do you like to ask"
		tipRole="assistant"
		prompt=undefined
		placeholder=""
		text=""
		result=""
		if tip:
			await session.addChatText(tipRole,tip,{})
		result=await session.askChatInput({"type":"input","prompt":prompt,"placeholder":placeholder,"text":text})
		await session.addChatText("user",result,{})
		return {"seg":CallNodeChat,"result":(result),"preSeg":"1IEJT66A30","outlet":"1IEJT7FVE1"}
	segs["AskCmd"]=AskCmd={
		"exec":AskCmd_exec,
		"name":"AskCmd",
		"jaxId":"1IEJT66A30",
		"url":"AskCmd@"+agentURL
	}
	
	async def CallNode_exec(input):#//:1IF43UGLC0
		result=None
		args={}
		args['nodeName']="DrawSD"
		args['callAgent']="ChatDraw.py"
		args['callArg']=undefined
		args['checkUpdate']=true
		result= await session.pipeChat("/@tabos/RemoteChat.py",args,false)
		return {"result":result}
	segs["CallNode"]=CallNode={
		"name":"CallNode",
		"exec":CallNode_exec,
		"jaxId":"1IF43UGLC0",
		"url":"CallNode@"+agentURL
	}
	
	async def NodeChatResult_exec(input):#//:1IF93MDVS0
		result=input
		role="assistant"
		content=input.get("result")
		await session.addChatText(role,content,{})
		return {"result":result}
	segs["NodeChatResult"]=NodeChatResult={
		"exec":NodeChatResult_exec,
		"name":"NodeChatResult",
		"jaxId":"1IF93MDVS0",
		"url":"NodeChatResult@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1IEHE15JV0PreEntry#
		##}1IEHE15JV0PreEntry#
		result = {"seg":CheckHi,"input":input}
		##{1IEHE15JV0PostEntry#
		##}1IEHE15JV0PostEntry#
		return result
	agent = {
		"isAIAgent": true,
		"session": session,
		"name": "master",
		"url": agentURL,
		"baseDir": basePath,
		"autoStart": true,
		"jaxId": "1IEHE15JV0",
		"context": context,
		"livingSeg": None,
		"execChat": execAgent,
		##{1IEHE15JV0MoreAgentAttrs#
		##}1IEHE15JV0MoreAgentAttrs#
	}
	##{1IEHE15JV0PostAgent#
	##}1IEHE15JV0PostAgent#
	return agent
##{1IEHE15JV0ExCodes#
##}1IEHE15JV0ExCodes#

ChatAPI=None

default=master
__all__=["default","master","ChatAPI"]
""">>>CodyExport
let ChatAPI,Exports;

return {api:ChatAPI,export:Exports};
>>>CodyExport"""
#Cody Project Doc
#{
#	"type": "docfile",
#	"def": "DocAIAgent",
#	"jaxId": "1IEHE15JV0",
#	"attrs": {
#		"editObjs": {
#			"jaxId": "1IEHE15JV1",
#			"attrs": {
#				"master": {
#					"type": "objclass",
#					"def": "ObjClass",
#					"jaxId": "1IEHE15JV7",
#					"attrs": {
#						"exportType": "UI Data Template",
#						"constructArgs": {
#							"jaxId": "1IEHE15K00",
#							"attrs": {}
#						},
#						"superClass": "",
#						"properties": {
#							"jaxId": "1IEHE15K01",
#							"attrs": {}
#						},
#						"functions": {
#							"jaxId": "1IEHE15K02",
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
#			"jaxId": "1IEHE15JV2",
#			"attrs": {}
#		},
#		"entry": "",
#		"autoStart": "true",
#		"inBrowser": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1IEHE15JV3",
#			"attrs": {}
#		},
#		"localVars": {
#			"jaxId": "1IEHE15JV4",
#			"attrs": {}
#		},
#		"context": {
#			"jaxId": "1IEHE15JV5",
#			"attrs": {}
#		},
#		"globalMockup": {
#			"jaxId": "1IEHE15JV6",
#			"attrs": {}
#		},
#		"segs": {
#			"attrs": [
#				{
#					"type": "aiseg",
#					"def": "brunch",
#					"jaxId": "1IEHE28IF0",
#					"attrs": {
#						"id": "CheckHi",
#						"viewName": "",
#						"label": "",
#						"x": "30",
#						"y": "710",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEHE5KDF0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEHE5KDF1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEHE5KDD1",
#							"attrs": {
#								"id": "Default",
#								"desc": "输出节点。",
#								"output": ""
#							}
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IEJT4CPM0",
#									"attrs": {
#										"id": "IsX",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEJT4CPP0",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEJT4CPP1",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#input.content==\"x\" or input.content==\"X\""
#									},
#									"linkedSeg": "1IEHMCM410"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IEIKM4B00",
#									"attrs": {
#										"id": "IsImage",
#										"desc": "输出节点。",
#										"output": "#input",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEINDT9R0",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEINDT9R1",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#input.ctype.value==\"image\""
#									},
#									"linkedSeg": "1IEIKN6T30"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IEHE5KDD0",
#									"attrs": {
#										"id": "IsHi",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEHE5KDF2",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEHE5KDF3",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#input.content==\"hi\""
#									},
#									"linkedSeg": "1IEJT66A30"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IF443OAJ0",
#									"attrs": {
#										"id": "IsO",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IF443OAO0",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IF443OAO1",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#input.content==\"o\" or input.content==\"O\""
#									},
#									"linkedSeg": "1IF43UGLC0"
#								}
#							]
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IEHE3FT60",
#					"attrs": {
#						"id": "ReplyHi",
#						"viewName": "",
#						"label": "",
#						"x": "560",
#						"y": "230",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEHE5KDF4",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEHE5KDF5",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "Hi",
#						"outlet": {
#							"jaxId": "1IEHE5KDD2",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "askChat",
#					"jaxId": "1IEHI8RA20",
#					"attrs": {
#						"id": "AskChat",
#						"viewName": "",
#						"label": "",
#						"x": "300",
#						"y": "80",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEHIA0LH0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEHIA0LH1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"tip": "What is your command, My master?",
#						"tipRole": "Assistant",
#						"placeholder": "",
#						"text": "",
#						"file": "false",
#						"showText": "false",
#						"outlet": {
#							"jaxId": "1IEHIA0LC0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEHI96A90"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IEHI96A90",
#					"attrs": {
#						"id": "ReplyChat",
#						"viewName": "",
#						"label": "",
#						"x": "560",
#						"y": "80",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEHIA0LH2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEHIA0LH3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#f\"[{input}]\"",
#						"outlet": {
#							"jaxId": "1IEHIA0LC1",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "askConfirm",
#					"jaxId": "1IEHJ6RUT0",
#					"attrs": {
#						"id": "AskButtons",
#						"viewName": "",
#						"label": "",
#						"x": "300",
#						"y": "310",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"prompt": "Please confirm",
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIButtonOutlet",
#									"jaxId": "1IEHJ6RU70",
#									"attrs": {
#										"id": "Hi",
#										"desc": "输出节点。",
#										"text": "Say Hi",
#										"result": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEHJ74S00",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEHJ74S01",
#											"attrs": {
#												"cast": ""
#											}
#										}
#									},
#									"linkedSeg": "1IEHE3FT60"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIButtonOutlet",
#									"jaxId": "1IEHJ6RU71",
#									"attrs": {
#										"id": "Lo",
#										"desc": "输出节点。",
#										"text": "Say Lo",
#										"result": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEHJ74S02",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEHJ74S03",
#											"attrs": {
#												"cast": ""
#											}
#										}
#									},
#									"linkedSeg": "1IEHJRELR0"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIButtonOutlet",
#									"jaxId": "1IEHJ6RU72",
#									"attrs": {
#										"id": "Yo",
#										"desc": "输出节点。",
#										"text": "Say Yo",
#										"result": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEHJ74S04",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEHJ74S05",
#											"attrs": {
#												"cast": ""
#											}
#										}
#									},
#									"linkedSeg": "1IEHJRRT00"
#								}
#							]
#						},
#						"silent": "false"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IEHJRELR0",
#					"attrs": {
#						"id": "ReplyLo",
#						"viewName": "",
#						"label": "",
#						"x": "560",
#						"y": "310",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEHJS4BV0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEHJS4BV1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "Lo",
#						"outlet": {
#							"jaxId": "1IEHJS4BS0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IEHJRRT00",
#					"attrs": {
#						"id": "ReplyYo",
#						"viewName": "",
#						"label": "",
#						"x": "560",
#						"y": "395",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEHJS4BV2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEHJS4BV3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "Yo",
#						"outlet": {
#							"jaxId": "1IEHJS4BS1",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "askMenu",
#					"jaxId": "1IEHMCM410",
#					"attrs": {
#						"id": "AskMenu",
#						"viewName": "",
#						"label": "",
#						"x": "300",
#						"y": "545",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"prompt": "Please confirm",
#						"multi": "false",
#						"withChat": "true",
#						"outlet": {
#							"jaxId": "1IEHMERV20",
#							"attrs": {
#								"id": "ChatInput",
#								"desc": "输出节点。",
#								"codes": "false"
#							},
#							"linkedSeg": "1IEHMDLKD0"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIButtonOutlet",
#									"jaxId": "1IEHMCM380",
#									"attrs": {
#										"id": "Hi",
#										"desc": "输出节点。",
#										"text": "Say Hi",
#										"result": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEHMERV21",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEHMERV22",
#											"attrs": {
#												"cast": ""
#											}
#										}
#									},
#									"linkedSeg": "1IEHE3FT60"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIButtonOutlet",
#									"jaxId": "1IEHMCM381",
#									"attrs": {
#										"id": "Lo",
#										"desc": "输出节点。",
#										"text": "Say Lo",
#										"result": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEHMERV23",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEHMERV24",
#											"attrs": {
#												"cast": ""
#											}
#										}
#									},
#									"linkedSeg": "1IEHJRELR0"
#								},
#								{
#									"type": "aioutlet",
#									"def": "AIButtonOutlet",
#									"jaxId": "1IEHMCM382",
#									"attrs": {
#										"id": "Yo",
#										"desc": "输出节点。",
#										"text": "Say Yo",
#										"result": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IEHMERV25",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IEHMERV26",
#											"attrs": {
#												"cast": ""
#											}
#										}
#									},
#									"linkedSeg": "1IEHJRRT00"
#								}
#							]
#						},
#						"silent": "false"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IEHMDLKD0",
#					"attrs": {
#						"id": "ReplyRepeat",
#						"viewName": "",
#						"label": "",
#						"x": "560",
#						"y": "590",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEHMERV27",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEHMERV28",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#f\"[{input}]\"",
#						"outlet": {
#							"jaxId": "1IEHMERUR0",
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
#					"jaxId": "1IEIKN6T30",
#					"attrs": {
#						"id": "ReadImage",
#						"viewName": "",
#						"label": "",
#						"x": "300",
#						"y": "680",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEINDT9S0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEINDT9S1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IEINDT9M0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEINLLKK0"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "image",
#					"jaxId": "1IEINLLKK0",
#					"attrs": {
#						"id": "ReplyImage",
#						"viewName": "",
#						"label": "",
#						"x": "560",
#						"y": "680",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEINNPS80",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEINNPS81",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"text": "图片:",
#						"image": "#input",
#						"role": "Assistant",
#						"sizeLimit": "256",
#						"format": "JEPG",
#						"outlet": {
#							"jaxId": "1IEINNPS50",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "aiBot",
#					"jaxId": "1IEJT4L950",
#					"attrs": {
#						"id": "CallNodeChat",
#						"viewName": "",
#						"label": "",
#						"x": "560",
#						"y": "750",
#						"desc": "调用其它AI Agent，把调用的结果作为输出",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJT7FVG0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJT7FVG1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"source": "/@tabos/NodeChat.py",
#						"argument": "#{}#>input",
#						"secret": "false",
#						"outlet": {
#							"jaxId": "1IEJT7FVE0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IF93MDVS0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "askChat",
#					"jaxId": "1IEJT66A30",
#					"attrs": {
#						"id": "AskCmd",
#						"viewName": "",
#						"label": "",
#						"x": "300",
#						"y": "750",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IEJT7FVG2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IEJT7FVG3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"tip": "What do you like to ask",
#						"tipRole": "Assistant",
#						"placeholder": "",
#						"text": "",
#						"file": "false",
#						"showText": "true",
#						"outlet": {
#							"jaxId": "1IEJT7FVE1",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IEJT4L950"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "RemoteChat",
#					"jaxId": "1IF43UGLC0",
#					"attrs": {
#						"id": "CallNode",
#						"viewName": "",
#						"label": "",
#						"x": "300",
#						"y": "825",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IF443OAP0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IF443OAP1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"nodeName": "DrawSD",
#						"callAgent": "ChatDraw.py",
#						"callArg": "",
#						"checkUpdate": "true",
#						"outlet": {
#							"jaxId": "1IF443OAL0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IF93MDVS0",
#					"attrs": {
#						"id": "NodeChatResult",
#						"viewName": "",
#						"label": "",
#						"x": "805",
#						"y": "750",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IF93MSQ20",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IF93MSQ21",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"text": "#input.get(\"result\")",
#						"outlet": {
#							"jaxId": "1IF93MSPR0",
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