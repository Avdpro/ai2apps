#Auto genterated by Cody
import os
import json
import base64
import urllib.parse
import importlib
##{1IDQ0PSHI0MoreImports#
from PIL import Image
from io import BytesIO
import asyncio
import threading
from diffusers import AutoPipelineForText2Image
import torch
##}1IDQ0PSHI0MoreImports#

true=True
false=False
undefined=None
pathLib= os.path
agentURL= pathLib.abspath(__file__)
basePath=pathLib.dirname(agentURL)

argsTemplate={
	"properties":{
		"drawPrompt":{
			"name":"drawPrompt","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"",
		},
		"model":{
			"name":"model","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"",
		},
		"device":{
			"name":"device","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"",
		}
	},
	##{1IDQ0PSHI0ArgsView#
	##}1IDQ0PSHI0ArgsView#
}

##{1IDQ0PSHI0StartDoc#
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

##}1IDQ0PSHI0StartDoc#
##----------------------------------------------------------------------------
async def DrawSD(session):
	drawPrompt=None
	model=None
	device=None
	
	context, globalContext = None, None
	self = None
	__Ln = session.language or "CN"
	CheckPipeline, TipStart, StartSD, TipReady, CheckTask, WaitTask, Draw = None, None, None, None, None, None, None
	##{1IDQ0PSHI0LocalVals#
	pipeline=None
	waitTaskBlk=None
	##}1IDQ0PSHI0LocalVals#
	
	
	def parseAgentArgs(input):
		nonlocal drawPrompt,model,device
		if isinstance(input, dict):
			drawPrompt=input.get("drawPrompt")
			model=input.get("model")
			device=input.get("device")
		else:
			drawPrompt=None
			model=None
			device=None
		##{1IDQ0PSHI0ParseArgs#
		if not model:
			model="runwayml/stable-diffusion-v1-5"
		if not device:
			device="mps"
		##}1IDQ0PSHI0ParseArgs#
	
	##{1IDQ0PSHI0PreContext#
	##}1IDQ0PSHI0PreContext#
	globalContext = session.globalContext
	context = {}
	##{1IDQ0PSHI0PostContext#
	##}1IDQ0PSHI0PostContext#
	agent,segs = None, {}
	
	async def CheckPipeline_exec(input):#//:1IDQ0QPNM0
		##{1IDQ0QPNM0Start#
		global pipelineMap
		nonlocal pipeline
		pipeline=pipelineMap.get(model,None)
		##}1IDQ0QPNM0Start#
		if pipeline:
			return {"seg":CheckTask,"result":(input),"preSeg":"1IDQ0QPNM0","outlet":"1IDQ0QPNN0"}
		##{1IDQ0QPNM0Post#
		##}1IDQ0QPNM0Post#
		#default/else:
		return {"seg":TipStart,"result":(input),"preSeg":"1IDQ0QPNM0","outlet":"1IDQ0QPNM3"}
	segs["CheckPipeline"]=CheckPipeline={
		"exec":CheckPipeline_exec,
		"name":"CheckPipeline",
		"jaxId":"1IDQ0QPNM0",
		"url":"CheckPipeline@"+agentURL
	}
	
	async def TipStart_exec(input):#//:1IDQ0RHEM0
		result=input
		role="log"
		content="Starting pipeline..."
		await session.addChatText(role,content,{})
		return {"seg":StartSD,"result":(result),"preSeg":"1IDQ0RHEM0","outlet":"1IDQ0RHEM3"}
	segs["TipStart"]=TipStart={
		"exec":TipStart_exec,
		"name":"TipStart",
		"jaxId":"1IDQ0RHEM0",
		"url":"TipStart@"+agentURL
	}
	
	async def StartSD_exec(input):#//:1IDQ0RSEH0
		result=input
		##{1IDQ0RSEH0Code#
		global pipelineMap
		nonlocal pipeline,device
		pipeline = AutoPipelineForText2Image.from_pretrained(model).to(device)
		pipelineMap[model]=pipeline
		##}1IDQ0RSEH0Code#
		return {"seg":TipReady,"result":(result),"preSeg":"1IDQ0RSEH0","outlet":"1IDQ0RSEH3"}
	segs["StartSD"]=StartSD={
		"exec":StartSD_exec,
		"name":"StartSD",
		"jaxId":"1IDQ0RSEH0",
		"url":"StartSD@"+agentURL
	}
	
	async def TipReady_exec(input):#//:1IDQ0SC460
		result=input
		role="log"
		content="Pipeline ready"
		await session.addChatText(role,content,{})
		return {"seg":CheckTask,"result":(result),"preSeg":"1IDQ0SC460","outlet":"1IDQ0SC463"}
	segs["TipReady"]=TipReady={
		"exec":TipReady_exec,
		"name":"TipReady",
		"jaxId":"1IDQ0SC460",
		"url":"TipReady@"+agentURL
	}
	
	async def CheckTask_exec(input):#//:1IDQ0SR900
		##{1IDQ0SR900Start#
		global curTask
		##}1IDQ0SR900Start#
		if curTask:
			return {"seg":WaitTask,"result":(input),"preSeg":"1IDQ0SR900","outlet":"1IDQ0SR904"}
		##{1IDQ0SR900Post#
		##}1IDQ0SR900Post#
		#default/else:
		return {"seg":Draw,"result":(input),"preSeg":"1IDQ0SR900","outlet":"1IDQ0SR903"}
	segs["CheckTask"]=CheckTask={
		"exec":CheckTask_exec,
		"name":"CheckTask",
		"jaxId":"1IDQ0SR900",
		"url":"CheckTask@"+agentURL
	}
	
	async def WaitTask_exec(input):#//:1IDQ0TE9D0
		result=input
		##{1IDQ0TE9D0Code#
		global waitTaskBlks
		nonlocal waitTaskBlk
		waitTaskBlk=await session.showWait(f"Wait other task(s) finish: {len(waitTaskBlks)+1}")
		waitTaskBlk={
			"session":session,
			"blk":waitTaskBlk
		}
		waitTaskBlks.append(waitTaskBlk)
		##}1IDQ0TE9D0Code#
		return {"seg":Draw,"result":(result),"preSeg":"1IDQ0TE9D0","outlet":"1IDQ0TE9D3"}
	segs["WaitTask"]=WaitTask={
		"exec":WaitTask_exec,
		"name":"WaitTask",
		"jaxId":"1IDQ0TE9D0",
		"url":"WaitTask@"+agentURL
	}
	
	async def Draw_exec(input):#//:1IDQ0TQ8A0
		result=input
		##{1IDQ0TQ8A0Code#
		global curTask,curDrawSession,curDrawWait,curDrawSteps,drawResult
		nonlocal pipeline,waitTaskBlk,device
		pms=asyncio.Future()
		task=curTask
		curTask=pms
		if task:
			await task;
			#TODO: Show wait block:
		if waitTaskBlk:
			await session.removeWait(waitTaskBlk["blk"])
			await execTaskBlk(waitTaskBlk)
			waitTaskBlk=None
		curDrawSession=session
		curDrawWait=await session.showWait("Drawing...")
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
		await session.removeWait(curDrawWait)
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
		##}1IDQ0TQ8A0Code#
		return {"result":result}
	segs["Draw"]=Draw={
		"exec":Draw_exec,
		"name":"Draw",
		"jaxId":"1IDQ0TQ8A0",
		"url":"Draw@"+agentURL
	}
	
	async def execAgent(input):
		result = None
		parseAgentArgs(input)
		##{1IDQ0PSHI0PreEntry#
		##}1IDQ0PSHI0PreEntry#
		result = {"seg":CheckPipeline,"input":input}
		##{1IDQ0PSHI0PostEntry#
		##}1IDQ0PSHI0PostEntry#
		return result
	agent = {
		"isAIAgent": true,
		"session": session,
		"name": "DrawSD",
		"url": agentURL,
		"baseDir": basePath,
		"autoStart": true,
		"jaxId": "1IDQ0PSHI0",
		"context": context,
		"livingSeg": None,
		"execChat": execAgent,
		##{1IDQ0PSHI0MoreAgentAttrs#
		##}1IDQ0PSHI0MoreAgentAttrs#
	}
	##{1IDQ0PSHI0PostAgent#
	##}1IDQ0PSHI0PostAgent#
	return agent
##{1IDQ0PSHI0ExCodes#
##}1IDQ0PSHI0ExCodes#

ChatAPI=[{
	"def":{
		"name": "DrawSD",
		"description": "这是一个AI智能体。",
		"parameters":{
			"type": "object",
			"properties":{
				"drawPrompt":{"type":"string","description":""},
				"model":{"type":"string","description":""},
				"device":{"type":"string","description":""}
			}
		}
	},
	"agent": DrawSD
}]

default=DrawSD
__all__=["default","DrawSD","ChatAPI"]
""">>>CodyExport
let ChatAPI,Exports;
ChatAPI=[{
	def:{
		name: "DrawSD",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				drawPrompt:{type:"string",description:""},
				model:{type:"string",description:""},
				device:{type:"string",description:""}
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
		name:"DrawSD",showName:"DrawSD",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"drawPrompt":{name:"drawPrompt",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"model":{name:"model",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"device":{name:"device",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","drawPrompt","model","device","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocPyAgentExporter.segTypeExporters["DrawSD"]=
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
			coder.packText("args['drawPrompt']=");this.genAttrStatement(seg.getAttr("drawPrompt"));coder.newLine();
			coder.packText("args['model']=");this.genAttrStatement(seg.getAttr("model"));coder.newLine();
			coder.packText("args['device']=");this.genAttrStatement(seg.getAttr("device"));coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("DrawSD.py",args,false)`);coder.newLine();
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
#	"jaxId": "1IDQ0PSHI0",
#	"attrs": {
#		"editObjs": {
#			"jaxId": "1IDQ0PSHI1",
#			"attrs": {
#				"DrawSD": {
#					"type": "objclass",
#					"def": "ObjClass",
#					"jaxId": "1IDQ0PSHI7",
#					"attrs": {
#						"exportType": "UI Data Template",
#						"constructArgs": {
#							"jaxId": "1IDQ0PSHI8",
#							"attrs": {}
#						},
#						"superClass": "",
#						"properties": {
#							"jaxId": "1IDQ0PSHI9",
#							"attrs": {}
#						},
#						"functions": {
#							"jaxId": "1IDQ0PSHI10",
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
#			"jaxId": "1IDQ0PSHI2",
#			"attrs": {}
#		},
#		"entry": "",
#		"autoStart": "true",
#		"debug": "true",
#		"apiArgs": {
#			"jaxId": "1IDQ0PSHI3",
#			"attrs": {
#				"drawPrompt": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IDQ157DH2",
#					"attrs": {
#						"type": "String",
#						"mockup": "\"\"",
#						"desc": "",
#						"required": "true"
#					}
#				},
#				"model": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IDQ157DH0",
#					"attrs": {
#						"type": "String",
#						"mockup": "\"\"",
#						"desc": "",
#						"required": "false"
#					}
#				},
#				"device": {
#					"type": "object",
#					"def": "AgentCallArgument",
#					"jaxId": "1IDQ157DH1",
#					"attrs": {
#						"type": "String",
#						"mockup": "\"\"",
#						"desc": "",
#						"required": "false"
#					}
#				}
#			}
#		},
#		"localVars": {
#			"jaxId": "1IDQ0PSHI4",
#			"attrs": {}
#		},
#		"context": {
#			"jaxId": "1IDQ0PSHI5",
#			"attrs": {}
#		},
#		"globalMockup": {
#			"jaxId": "1IDQ0PSHI6",
#			"attrs": {}
#		},
#		"segs": {
#			"attrs": [
#				{
#					"type": "aiseg",
#					"def": "brunch",
#					"jaxId": "1IDQ0QPNM0",
#					"attrs": {
#						"id": "CheckPipeline",
#						"viewName": "",
#						"label": "",
#						"x": "80",
#						"y": "210",
#						"desc": "这是一个AISeg。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDQ0QPNM1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDQ0QPNM2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDQ0QPNM3",
#							"attrs": {
#								"id": "Default",
#								"desc": "输出节点。",
#								"output": ""
#							},
#							"linkedSeg": "1IDQ0RHEM0"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IDQ0QPNN0",
#									"attrs": {
#										"id": "Ready",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IDQ0QPNN1",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IDQ0QPNN2",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#pipeline"
#									},
#									"linkedSeg": "1IDQ0SR900"
#								}
#							]
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IDQ0RHEM0",
#					"attrs": {
#						"id": "TipStart",
#						"viewName": "",
#						"label": "",
#						"x": "365",
#						"y": "365",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDQ0RHEM1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDQ0RHEM2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "log",
#						"text": "Starting pipeline...",
#						"outlet": {
#							"jaxId": "1IDQ0RHEM3",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDQ0RSEH0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IDQ0RSEH0",
#					"attrs": {
#						"id": "StartSD",
#						"viewName": "",
#						"label": "",
#						"x": "585",
#						"y": "365",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDQ0RSEH1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDQ0RSEH2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDQ0RSEH3",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDQ0SC460"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "output",
#					"jaxId": "1IDQ0SC460",
#					"attrs": {
#						"id": "TipReady",
#						"viewName": "",
#						"label": "",
#						"x": "795",
#						"y": "365",
#						"desc": "这是一个AISeg。",
#						"codes": "false",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDQ0SC461",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDQ0SC462",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"role": "log",
#						"text": "Pipeline ready",
#						"outlet": {
#							"jaxId": "1IDQ0SC463",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDQ0V44A0"
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "brunch",
#					"jaxId": "1IDQ0SR900",
#					"attrs": {
#						"id": "CheckTask",
#						"viewName": "",
#						"label": "",
#						"x": "365",
#						"y": "195",
#						"desc": "这是一个AISeg。",
#						"codes": "true",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDQ0SR901",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDQ0SR902",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDQ0SR903",
#							"attrs": {
#								"id": "Default",
#								"desc": "输出节点。",
#								"output": ""
#							},
#							"linkedSeg": "1IDQ0TQ8A0"
#						},
#						"outlets": {
#							"attrs": [
#								{
#									"type": "aioutlet",
#									"def": "AIConditionOutlet",
#									"jaxId": "1IDQ0SR904",
#									"attrs": {
#										"id": "Wait",
#										"desc": "输出节点。",
#										"output": "",
#										"codes": "false",
#										"context": {
#											"jaxId": "1IDQ0SR905",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"global": {
#											"jaxId": "1IDQ0SR906",
#											"attrs": {
#												"cast": ""
#											}
#										},
#										"condition": "#curTask"
#									},
#									"linkedSeg": "1IDQ0TE9D0"
#								}
#							]
#						}
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IDQ0TE9D0",
#					"attrs": {
#						"id": "WaitTask",
#						"viewName": "",
#						"label": "",
#						"x": "585",
#						"y": "180",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "None",
#						"context": {
#							"jaxId": "1IDQ0TE9D1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDQ0TE9D2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDQ0TE9D3",
#							"attrs": {
#								"id": "Result",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDQ0TQ8A0"
#						},
#						"result": "#input"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "code",
#					"jaxId": "1IDQ0TQ8A0",
#					"attrs": {
#						"id": "Draw",
#						"viewName": "绘制",
#						"label": "",
#						"x": "795",
#						"y": "210",
#						"desc": "这是一个AISeg。",
#						"mkpInput": "$$input$$",
#						"segMark": "flag.svg",
#						"context": {
#							"jaxId": "1IDQ0TQ8A1",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"global": {
#							"jaxId": "1IDQ0TQ8A2",
#							"attrs": {
#								"cast": ""
#							}
#						},
#						"outlet": {
#							"jaxId": "1IDQ0TQ8A3",
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
#					"jaxId": "1IDQ0V44A0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "930",
#						"y": "285",
#						"outlet": {
#							"jaxId": "1IDQ11EH20",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDQ0V7DQ0"
#						},
#						"dir": "R2L"
#					}
#				},
#				{
#					"type": "aiseg",
#					"def": "connector",
#					"jaxId": "1IDQ0V7DQ0",
#					"attrs": {
#						"id": "",
#						"label": "New AI Seg",
#						"x": "390",
#						"y": "285",
#						"outlet": {
#							"jaxId": "1IDQ11EH21",
#							"attrs": {
#								"id": "Outlet",
#								"desc": "输出节点。"
#							},
#							"linkedSeg": "1IDQ0SR900"
#						},
#						"dir": "R2L"
#					}
#				}
#			]
#		},
#		"desc": "这是一个AI智能体。",
#		"exportAPI": "true",
#		"exportAddOn": "true",
#		"addOnOpts": ""
#	}
#}