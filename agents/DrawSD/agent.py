#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
##{1HIRHBGQ60MoreImports#
from PIL import Image
from io import BytesIO
import asyncio
import threading
from diffusers import AutoPipelineForText2Image
import torch
##}1HIRHBGQ60MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

argsTemplate={
	"properties":{
		"model":{
			"name":"model","type":"string",
			"defaultValue":"",
			"desc":"",
		},
		"device":{
			"name":"device","type":"string",
			"defaultValue":"cpu",
			"desc":"",
		}
	},
	##{1HIRHBGQ60ArgsView#
	##}1HIRHBGQ60ArgsView#
}

##{1HIRHBGQ60StartDoc#
pipelineMap={}
pipeline=None
curTask=None
curDrawSession=None
curDrawWait=None
curDrawSteps=50
waitTaskBlks=[]
drawResult=None

async def execTaskBlk(blk):
	global waitTaskBlks
	if blk!=waitTaskBlks[0]:
		raise Exception(f"Task order error")
	waitTaskBlks.pop(0)
	for i in range(len(waitTaskBlks)):
		await waitTaskBlks[i]["session"].setWaitText(waitTaskBlks[i]["blk"],f"Waiting other task(s) to finish: {i+1}")

async def showStep(step,latents,opts):
	global curDrawSession,curDrawWait,curDrawSteps
	await curDrawSession.setWaitText(curDrawWait, f"Draw step: {step}/{curDrawSteps}")
		
# Render-step-callback
def stepCallback(step, latents, opts):
	global curDrawSession,curDrawWait
	if curDrawWait:
		asyncio.run(showStep(step, latents, opts))
		
def image2DataURL(image):
	buffered = BytesIO()
	image.save(buffered, format="PNG")
	img_bytes = buffered.getvalue()
	img_base64 = base64.b64encode(img_bytes).decode("utf-8")
	data_url = f"data:image/png;base64,{img_base64}"
	return data_url

async def drawWithSD(pipeline,prompt,device,seed,pms):
	global drawResult
	generator = torch.Generator(device)
	if seed:
		generator=generator.manual_seed(seed)
	image = pipeline(f"{prompt}", generator=generator, num_inference_steps=curDrawSteps,callback=stepCallback,callback_steps=5).images[0]
	drawResult=image
	#pms.set_result(image)
	
def drawThreadProc(pipeline,prompt,device,seed,pms):
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)  # 将新循环绑定到当前线程
	loop.run_until_complete(drawWithSD(pipeline,prompt,device,seed,pms))
	loop.close()

def drawInThread(pipeline,prompt,device,seed,pms):
	global drawResult
	drawResult=None
	thread = threading.Thread(target=drawThreadProc,args=(pipeline,prompt,device,seed,pms),kwargs={})
	thread.start()

##}1HIRHBGQ60StartDoc#
##----------------------------------------------------------------------------
async def agent(session):
	model=None
	device=None
	
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	CheckPipeline, TipStart, StartSD, TipReady, Ask, CheckTask, WaitTask, Draw, ShowImage = None, None, None, None, None, None, None, None, None
	##{1HIRHBGQ60LocalVals#
	pipeline=None
	waitTaskBlk=None
	##}1HIRHBGQ60LocalVals#
	
	
	def parseAgentArgs(input):
		nonlocal model,device
		if isinstance(input, dict):
			model=input.get("model")
			device=input.get("device")
		else:
			model=None
			device=None
		##{1HIRHBGQ60ParseArgs#
		if not model:
			model="runwayml/stable-diffusion-v1-5"
		if not device:
			device="mps"
		##}1HIRHBGQ60ParseArgs#
	
	##{1HIRHBGQ60PreContext#
	##}1HIRHBGQ60PreContext#
	globalContext = session.globalContext
	context = {}
	##{1HIRHBGQ60PostContext#
	##}1HIRHBGQ60PostContext#
	agent,segs = None, {}
	
	async def CheckPipeline_exec(input):#//:1IDI79MEI0
		##{1IDI79MEI0Start#
		global pipelineMap
		nonlocal pipeline
		pipeline=pipelineMap.get(model,None)
		##}1IDI79MEI0Start#
		if pipeline:
			return {"seg":Ask,"result":(input),"preSeg":"1IDI79MEI0","outlet":"1IDI7AN350"}
		##{1IDI79MEI0Post#
		##}1IDI79MEI0Post#
		#default/else:
		return {"seg":TipStart,"result":(input),"preSeg":"1IDI79MEI0","outlet":"1IDI7AN351"}
	segs["CheckPipeline"]=CheckPipeline={
		"exec":CheckPipeline_exec,
		"name":"CheckPipeline",
		"jaxId":"1IDI79MEI0",
		"url":"CheckPipeline@"+agentURL
	}
	
	async def TipStart_exec(input):#//:1IDI7D5SS0
		result=input
		role="log"
		content="Starting pipeline..."
		await session.addChatText(role,content,{})
		return {"seg":StartSD,"result":(result),"preSeg":"1IDI7D5SS0","outlet":"1IDI7GSUB0"}
	segs["TipStart"]=TipStart={
		"exec":TipStart_exec,
		"name":"TipStart",
		"jaxId":"1IDI7D5SS0",
		"url":"TipStart@"+agentURL
	}
	
	async def StartSD_exec(input):#//:1IDAJNF9E0
		result=input
		##{1IDAJNF9E0Code#
		global pipelineMap
		nonlocal pipeline,device
		pipeline = AutoPipelineForText2Image.from_pretrained(model).to(device)
		pipelineMap[model]=pipeline
		##}1IDAJNF9E0Code#
		return {"seg":TipReady,"result":(result),"preSeg":"1IDAJNF9E0","outlet":"1IDAJNF9F0"}
	segs["StartSD"]=StartSD={
		"exec":StartSD_exec,
		"name":"StartSD",
		"jaxId":"1IDAJNF9E0",
		"url":"StartSD@"+agentURL
	}
	
	async def TipReady_exec(input):#//:1IDI7FQK40
		result=input
		role="log"
		content="Pipeline ready"
		await session.addChatText(role,content,{})
		return {"seg":Ask,"result":(result),"preSeg":"1IDI7FQK40","outlet":"1IDI7GSUB1"}
	segs["TipReady"]=TipReady={
		"exec":TipReady_exec,
		"name":"TipReady",
		"jaxId":"1IDI7FQK40",
		"url":"TipReady@"+agentURL
	}
	
	async def Ask_exec(input):#//:1IDAJSJCR0
		tip=(("你想画什么？") if(__Ln=="CN") else ("What do you want to draw?"))
		tipRole="assistant"
		prompt=undefined
		placeholder=""
		text=""
		result=""
		if tip:
			await session.addChatText(tipRole,tip,{})
		result=await session.askChatInput({"type":"input","prompt":prompt,"placeholder":placeholder,"text":text})
		await session.addChatText("user",result,{})
		return {"seg":CheckTask,"result":(result),"preSeg":"1IDAJSJCR0","outlet":"1IDAJUL2H0"}
	segs["Ask"]=Ask={
		"exec":Ask_exec,
		"name":"Ask",
		"jaxId":"1IDAJSJCR0",
		"url":"Ask@"+agentURL
	}
	
	async def CheckTask_exec(input):#//:1IDIALT4C0
		##{1IDIALT4C0Start#
		global curTask
		##}1IDIALT4C0Start#
		if curTask:
			return {"seg":WaitTask,"result":(input),"preSeg":"1IDIALT4C0","outlet":"1IDIAOPG10"}
		##{1IDIALT4C0Post#
		##}1IDIALT4C0Post#
		#default/else:
		return {"seg":Draw,"result":(input),"preSeg":"1IDIALT4C0","outlet":"1IDIAOPG11"}
	segs["CheckTask"]=CheckTask={
		"exec":CheckTask_exec,
		"name":"CheckTask",
		"jaxId":"1IDIALT4C0",
		"url":"CheckTask@"+agentURL
	}
	
	async def WaitTask_exec(input):#//:1IDIANDS30
		result=input
		##{1IDIANDS30Code#
		global waitTaskBlks
		nonlocal waitTaskBlk
		waitTaskBlk=await session.showWait(f"Wait other task(s) finish: {len(waitTaskBlks)+1}")
		waitTaskBlk={
			"session":session,
			"blk":waitTaskBlk
		}
		waitTaskBlks.append(waitTaskBlk)
		##}1IDIANDS30Code#
		return {"seg":Draw,"result":(result),"preSeg":"1IDIANDS30","outlet":"1IDIAOPG12"}
	segs["WaitTask"]=WaitTask={
		"exec":WaitTask_exec,
		"name":"WaitTask",
		"jaxId":"1IDIANDS30",
		"url":"WaitTask@"+agentURL
	}
	
	async def Draw_exec(input):#//:1IDAK0Q9G0
		result=input
		##{1IDAK0Q9G0Code#
		global curTask,curDrawSession,curDrawWait,curDrawSteps,drawResult
		nonlocal pipeline,waitTaskBlk,device
		pms=asyncio.Future()
		task=curTask
		curTask=pms;
		if task:
			await task;
			#TODO: Show wait block:
		if waitTaskBlk:
			await session.removeWait(waitTaskBlk["blk"])
			await execTaskBlk(waitTaskBlk)
			waitTaskBlk=None
		curDrawSession=session
		curDrawWait=await session.showWait("Drawing...");
		curDrawSteps=30
		
		drawInThread(pipeline,input,device,False,pms)
		"""
		generator = torch.Generator(device).manual_seed(131)
		image = pipeline(f"{input}", generator=generator, num_inference_steps=curDrawSteps,callback=stepCallback,callback_steps=5).images[0]
		image.show()
		"""
		result=None
		while not drawResult:
			await asyncio.sleep(0.05)
		image=drawResult
		result=image2DataURL(image)
		await session.removeWait(curDrawWait);
		curDrawWait=None
		curDrawSession=None
		curTask=None
		pms.set_result(result)
		"""
		result=image2DataURL(image)
		await session.removeWait(curDrawWait);
		curDrawWait=None
		curDrawSession=None
		pms.set_result(True)
		"""
		##}1IDAK0Q9G0Code#
		return {"seg":ShowImage,"result":(result),"preSeg":"1IDAK0Q9G0","outlet":"1IDAK1IR10"}
	segs["Draw"]=Draw={
		"exec":Draw_exec,
		"name":"Draw",
		"jaxId":"1IDAK0Q9G0",
		"url":"Draw@"+agentURL
	}
	
	async def ShowImage_exec(input):#//:1IDJDRPJV0
		result=input
		role="assistant"
		content="图片:"
		result=await session.resizeImage(result,512,"PNG")
		await session.addChatText(role,content,{"image":result})
		return {"seg":Ask,"result":(result),"preSeg":"1IDJDRPJV0","outlet":"1IDJDSNTB0"}
	segs["ShowImage"]=ShowImage={
		"exec":ShowImage_exec,
		"name":"ShowImage",
		"jaxId":"1IDJDRPJV0",
		"url":"ShowImage@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1HIRHBGQ60PreEntry#
		##}1HIRHBGQ60PreEntry#
		result = {"seg":CheckPipeline,"input":input}
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
		"description": "这是通过Diffuser绘制的智能体。",
		"parameters":{
			"type": "object",
			"properties":{
				"model":{"type":"string","description":""},
				"device":{"type":"string","description":""}
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
		description: "这是通过Diffuser绘制的智能体。",
		parameters:{
			type: "object",
			properties:{
				model:{type:"string",description:""},
				device:{type:"string",description:""}
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
#		"entry": "CheckPipeline",
#		"autoStart": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1HIRHBM1R4",
#			"attrs": {
#				"model": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IDI8RCIP0",
#					"attrs": {
#						"type": "String",
#						"mockup": "\"\"",
#						"desc": ""
#					}
#				},
#				"device": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IDI8SMD70",
#					"attrs": {
#						"type": "String",
#						"mockup": "cpu",
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
#					"def": "brunch",
#					"jaxId": "1IDI79MEI0",
#					"attrs": {
#						"id": "CheckPipeline",
#						"viewName": "",
#						"label": "",
#						"x": "80",
#						"y": "285",
#						"desc": "这是一个AISeg。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDI7BAL30",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDI7BAL31",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDI7AN351",
#							"attrs": {
#								"id": "Default",
#								"desc": "输出节点。",
#								"output": ""
#							},
#							"linkedSeg": "1IDI7D5SS0"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IDI7AN350",
#									"attrs": {
#										"id": "Ready",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IDI7BAL32",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IDI7BAL33",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#pipeline"
#									},
#									"linkedSeg": "1IDAJSJCR0"
#								}
#							]
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IDI7D5SS0",
#					"attrs": {
#						"id": "TipStart",
#						"viewName": "",
#						"label": "",
#						"x": "330",
#						"y": "420",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDI7GSUF0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDI7GSUF1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "log",
#						"text": "Starting pipeline...",
#						"outlet": {
#							"jaxId": "1IDI7GSUB0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDAJNF9E0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IDAJNF9E0",
#					"attrs": {
#						"id": "StartSD",
#						"viewName": "",
#						"label": "",
#						"x": "545",
#						"y": "420",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDAJNF9H0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDAJNF9I0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDAJNF9F0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDI7FQK40"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IDI7FQK40",
#					"attrs": {
#						"id": "TipReady",
#						"viewName": "",
#						"label": "",
#						"x": "745",
#						"y": "420",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDI7GSUG2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDI7GSUG3",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "log",
#						"text": "Pipeline ready",
#						"outlet": {
#							"jaxId": "1IDI7GSUB1",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDI7EHJG0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "askChat",
#					"jaxId": "1IDAJSJCR0",
#					"attrs": {
#						"id": "Ask",
#						"viewName": "",
#						"label": "",
#						"x": "385",
#						"y": "270",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDAJUL2N0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDAJUL2N1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"tip": {
#							"type": "string",
#							"valText": "What do you want to draw?",
#							"localize": {
#								"EN": "What do you want to draw?",
#								"CN": "你想画什么？"
#							},
#							"localizable": true
#						},
#						"tipRole": "Assistant",
#						"placeholder": "",
#						"text": "",
#						"file": "false",
#						"showText": "true",
#						"outlet": {
#							"jaxId": "1IDAJUL2H0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDIALT4C0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "brunch",
#					"jaxId": "1IDIALT4C0",
#					"attrs": {
#						"id": "CheckTask",
#						"viewName": "",
#						"label": "",
#						"x": "580",
#						"y": "270",
#						"desc": "这是一个AISeg。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDIAOPG80",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDIAOPG81",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDIAOPG11",
#							"attrs": {
#								"id": "Default",
#								"desc": "输出节点。",
#								"output": ""
#							},
#							"linkedSeg": "1IDAK0Q9G0"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IDIAOPG10",
#									"attrs": {
#										"id": "Wait",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IDIAOPG82",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IDIAOPG83",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#curTask"
#									},
#									"linkedSeg": "1IDIANDS30"
#								}
#							]
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IDIANDS30",
#					"attrs": {
#						"id": "WaitTask",
#						"viewName": "",
#						"label": "",
#						"x": "800",
#						"y": "255",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDIAOPG84",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDIAOPG85",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDIAOPG12",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDAK0Q9G0"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IDAK0Q9G0",
#					"attrs": {
#						"id": "Draw",
#						"viewName": "绘制",
#						"label": "",
#						"x": "1000",
#						"y": "285",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDAK2D980",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDAK2D981",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDAK1IR10",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDJDRPJV0"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "image",
#					"jaxId": "1IDJDRPJV0",
#					"attrs": {
#						"id": "ShowImage",
#						"viewName": "",
#						"label": "",
#						"x": "1185",
#						"y": "285",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDJDSNTJ0",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDJDSNTJ1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"text": "图片:",
#						"image": "#input",
#						"role": "Assistant",
#						"sizeLimit": "512",
#						"format": "PNG",
#						"outlet": {
#							"jaxId": "1IDJDSNTB0",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDAKHMHP0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IDAKHMHP0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "1335",
#						"y": "200",
#						"outlet": {
#							"jaxId": "1IDAKHVRE0",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDAKHPE10"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IDAKHPE10",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "410",
#						"y": "200",
#						"outlet": {
#							"jaxId": "1IDAKHVRE1",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDAJSJCR0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IDI7EHJG0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "880",
#						"y": "345",
#						"outlet": {
#							"jaxId": "1IDI7GSUG0",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDI7EO4I0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IDI7EO4I0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "410",
#						"y": "345",
#						"outlet": {
#							"jaxId": "1IDI7GSUG1",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDAJSJCR0"
#						},
#						"dir": "R2L"
#					}
#				}
#			]
#		},
#		"desc": "这是通过Diffuser绘制的智能体。",
#		"exportAPI": "true",
#		"exportAddOn": "false",
#		"addOnOpts": ""
#	}
#}