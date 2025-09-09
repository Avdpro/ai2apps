#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
from session import trimJSON
##{1HIRHBGQ60MoreImports#
from aalgorithm.agents.autoapi.agent import create_project_api_manager,create_project_api_server
from aalgorithm.llm import LLMProvider
import asyncio
from loguru import logger
import dotenv
import time
import pprint
##}1HIRHBGQ60MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

argsTemplate={
	"properties":{
		"host":{
			"name":"host","type":"auto",
			"defaultValue":"127.0.0.1",
			"desc":"",
		},
		"port":{
			"name":"port","type":"auto",
			"defaultValue":8082,
			"desc":"",
		},
		"repository_root":{
			"name":"repository_root","type":"auto",
			"defaultValue":"repository_root",
			"desc":"",
		}
	},
	##{1HIRHBGQ60ArgsView#
	##}1HIRHBGQ60ArgsView#
}

##{1HIRHBGQ60StartDoc#
##}1HIRHBGQ60StartDoc#
##----------------------------------------------------------------------------
async def agent(session):
	host=None
	port=None
	repository_root=None
	
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	start_server, atmoic_llm, process_llm, direct_llm_call = None, None, None, None
	##{1HIRHBGQ60LocalVals#
	def process_output_exec_sync(input):
		asyncio.run(process_llm_exec(input))
	
	# 添加自定义logger handler，使用enqueue=True避免死锁
	logger.add(process_output_exec_sync, level='DEBUG',
			format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
			enqueue=True)
	##}1HIRHBGQ60LocalVals#
	
	
	def parseAgentArgs(input):
		nonlocal host,port,repository_root
		if isinstance(input, dict):
			host=input.get("host")
			port=input.get("port")
			repository_root=input.get("repository_root")
		else:
			host=None
			port=None
			repository_root=None
		##{1HIRHBGQ60ParseArgs#
		##}1HIRHBGQ60ParseArgs#
	
	##{1HIRHBGQ60PreContext#
	##}1HIRHBGQ60PreContext#
	globalContext = session.globalContext
	context = {}
	##{1HIRHBGQ60PostContext#
	##}1HIRHBGQ60PostContext#
	_agent,agent,segs = None, None, {}
	
	async def start_server_exec(input):#//:1J47V914E0
		nonlocal segs
		result=input
		##{1J47V914E0Code#
		dotenv.load_dotenv(dotenv.find_dotenv())
		host=input.get("host","127.0.0.1")
		port=input.get("port",8082)
		repository_root=input.get("repository_root",".")
		
		def inner_autoapi_server():
			llm_provider = LLMProvider(call_llm=direct_llm_call_exec)
			manager = create_project_api_manager(
				llm_provider=llm_provider,
				repository_root=repository_root
			)
			server = create_project_api_server(manager, host, port)
			server.run(debug=False,loop='asyncio')
			# server.run(debug=False)
		# 启动服务器
		from threading import Thread
		Thread(target=inner_autoapi_server,daemon=True).start()
		# server.run(debug=False,loop='asyncio')
		time.sleep(3)
		result={"status":"started","host":host,"port":port,"repository_root":repository_root}
		##}1J47V914E0Code#
		return {"result":result}
	segs["start_server"]=start_server={
		"exec":start_server_exec,
		"name":"start_server",
		"jaxId":"1J47V914E0",
		"url":"start_server@"+agentURL
	}
	
	async def atmoic_llm_exec(input):#//:1J47V9L6Q0
		prompt=None
		result=None
		##{1J47V9L6Q0Input#
		##}1J47V9L6Q0Input#
		
		opts={
			"platform":"Claude",
			"mode":"claude-3-7-sonnet-latest",
			"maxToken":2000,
			"temperature":0,
			"topP":1,
			"fqcP":0,
			"prcP":0,
			"secret":false,
			"responseFormat":"text"
		}
		chatMem=atmoic_llm.get("messages",[])
		seed=""
		if(seed):
			opts.seed=seed
		messages=[
			{"role":"system","content":"You are a smart assistant."},
		]
		##{1J47V9L6Q0PrePrompt#
		##}1J47V9L6Q0PrePrompt#
		prompt=input
		if(prompt):
			if not isinstance(prompt,str):
				prompt=json.dumps(prompt,indent=4)
			messages.append({"role":"user","content":prompt})
		##{1J47V9L6Q0PreCall#
		messages = input.get("messages", messages)
		opts['mode'] = input.get("model", opts['mode'])
		opts['maxToken'] = input.get("max_tokens", opts['maxToken'])
		opts['temperature'] = input.get("temperature", opts['temperature'])
		opts['responseFormat'] = input.get("response_format", {}).get("type", "text")
		##}1J47V9L6Q0PreCall#
		result=(await session.makeAICall("atmoic_llm@"+agentURL,opts,messages,true)) if (not result) else result
		##{1J47V9L6Q0PostCall#
		if not opts['responseFormat']=="text":
			result = trimJSON(result)
		print(pprint.pformat(result))
		##}1J47V9L6Q0PostCall#
		return {"result":result}
	segs["atmoic_llm"]=atmoic_llm={
		"exec":atmoic_llm_exec,
		"name":"atmoic_llm",
		"jaxId":"1J47V9L6Q0",
		"url":"atmoic_llm@"+agentURL
	}
	
	async def process_llm_exec(input):#//:1J49A0FKV0
		result=input
		channel="Process"
		opts={"txtHeader":_agent.get("name",_agent.get("showName",None)),"channel":channel}
		role="assistant"
		content=input
		await session.addChatText(role,content,opts)
		return {"result":result}
	segs["process_llm"]=process_llm={
		"exec":process_llm_exec,
		"name":"process_llm",
		"jaxId":"1J49A0FKV0",
		"url":"process_llm@"+agentURL
	}
	
	async def direct_llm_call_exec(input):#//:1J4CPEQUG0
		nonlocal segs
		result=input
		##{1J4CPEQUG0Code#
		opts = {
			"mode": "claude-3-7-sonnet-latest",
			"maxToken": 2000,
			"temperature": 0,
			"topP": 1,
			"fqcP": 0,
			"prcP": 0,
			"secret": false,
			"responseFormat": "text"
		}
		messages = input.get("messages")
		# opts['mode'] = input.get("model", opts['mode'])
		opts['maxToken'] = input.get("max_tokens", opts['maxToken'])
		opts['temperature'] = input.get("temperature", opts['temperature'])
		opts['responseFormat'] = input.get("response_format", {}).get("type", "text")
		def get_platform(model_name):
			platform_mapping = {
				'claude': 'Claude',
				'gpt': 'OpenAI'
			}
		
			for key in platform_mapping:
				if key in model_name.lower():
					return platform_mapping[key]
		opts['platform'] =  get_platform(opts['mode'])
		result = await session.agentNode.callHubAI(opts,messages,opts['mode'])
		if not opts['responseFormat']=="text":
			result = trimJSON(result)
		##}1J4CPEQUG0Code#
		return {"result":result}
	segs["direct_llm_call"]=direct_llm_call={
		"exec":direct_llm_call_exec,
		"name":"direct_llm_call",
		"jaxId":"1J4CPEQUG0",
		"url":"direct_llm_call@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1HIRHBGQ60PreEntry#
		##}1HIRHBGQ60PreEntry#
		result = {"seg":start_server,"input":input}
		##{1HIRHBGQ60PostEntry#
		##}1HIRHBGQ60PostEntry#
		return result
	_agent = agent = {
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
				"host":{"type":"auto","description":""},
				"port":{"type":"auto","description":""},
				"repository_root":{"type":"auto","description":""}
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
				host:{type:"auto",description:""},
				port:{type:"auto",description:""},
				repository_root:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true,
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
#		"showName": "",
#		"entry": "start_server",
#		"autoStart": "true",
#		"inBrowser": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1HIRHBM1R4",
#			"attrs": {
#				"host": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1J47VMIU40",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "\"127.0.0.1\"",
#						"desc": ""
#					}
#				},
#				"port": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1J47VMIU41",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "8082",
#						"desc": ""
#					}
#				},
#				"repository_root": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1J47VMIU42",
#					"attrs": {
#						"type": "Auto",
#						"mockup": "\"repository_root\"",
#						"desc": ""
#					}
#				}
#			}
#		},
#		"localVars": {
#			"jaxId": "1HIRHBM1R1",
#			"attrs": {}
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
#					"jaxId": "1J47V914E0",
#					"attrs": {
#						"id": "start_server",
#						"viewName": "",
#						"label": "",
#						"x": "185",
#						"y": "290",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1J47VA2BE0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1J47VA2BE1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1J47VA2BC0",
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
#					"def": "callLLM",
#					"jaxId": "1J47V9L6Q0",
#					"attrs": {
#						"id": "atmoic_llm",
#						"viewName": "",
#						"label": "",
#						"x": "200",
#						"y": "480",
#						"desc": "执行一次LLM调用。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1J47VA2BE2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1J47VA2BE3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"platform": "Claude",
#						"mode": "claude-3-7-sonnet-latest",
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
#							"jaxId": "1J47VA2BD0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						},
#						"stream": "false",
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
#						"responseFormat": "text",
#						"formatDef": "null"
#					},
#					"icon": "llm.svg"
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1J49A0FKV0",
#					"attrs": {
#						"id": "process_llm",
#						"viewName": "",
#						"label": "",
#						"x": "475",
#						"y": "480",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1J49A1MTB0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1J49A1MTB1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "Assistant",
#						"channel": "Process",
#						"text": "#input",
#						"outlet": {
#							"jaxId": "1J49A1MT30",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							}
#						}
#					},
#					"icon": "hudtxt.svg"
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1J4CPEQUG0",
#					"attrs": {
#						"id": "direct_llm_call",
#						"viewName": "",
#						"label": "",
#						"x": "195",
#						"y": "570",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1J4CPF4UQ0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1J4CPF4UQ1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1J4CPF4UK0",
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
#				}
#			]
#		},
#		"desc": "这是一个AI代理。",
#		"exportAPI": "true",
#		"exportAddOn": "false",
#		"addOnOpts": ""
#	}
#}