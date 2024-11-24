import os
from io import BytesIO
from types import SimpleNamespace
import base64
import json
import asyncio
import httpx
import importlib
import importlib.util
from PIL import Image
from openai import OpenAI
from playsound import playsound
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import traceback
import inspect
import re

pathLib = os.path

openAI = None
def setupOpenAI(session):
	global openAI
	if openAI:
		return openAI
	key=session.agentNode.hubJSON.get("key_OpenAI")
	if key:
		openAI=OpenAI(api_key=key)
		return openAI
	return None

def trimJSON(input_string):
	try:
		start_idx = input_string.index('{')
	except ValueError:
		return None
	decoder = json.JSONDecoder()
	while start_idx < len(input_string):
		try:
			obj, end = decoder.raw_decode(input_string[start_idx:])
			return obj
		except json.JSONDecodeError:
			try:
				start_idx = input_string.index('{', start_idx + 1)
			except ValueError:
				break
	return None


def import_module_from_file(file_path):
	name = pathLib.basename(file_path)
	if name.endswith(".py"):
		name = name[:-3]
	spec = importlib.util.spec_from_file_location(name, file_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class AISession:
	basePath = None
	curAgent = None
	curPath = None
	agentDict = {}
	globalContext = {}

	def __init__(self, basePath, node=None, sessionId=None):
		self.basePath = basePath
		self.curPath = None
		self.agentNode = node
		self.sessionId = sessionId
		self.nextCallId = 0
		self.callMap = {}
		self.version = "0.0.2"
		self.curAgent = None

	# -------------------------------------------------------------------------
	# Show version:
	def showVersion(self):
		print("AIChatSession 0.02")

	# -------------------------------------------------------------------------
	async def sendToClient(self, msg, vo):
		message = {
			"msg": "MessageToClient",
			"sessionId": self.sessionId,
			"message":{
				"msg": msg,
				"vo": vo
			}
		}
		message = json.dumps(message)
		await self.agentNode.websocket.send(message)

	# -------------------------------------------------------------------------
	async def callClient(self, msg, vo):
		callId = str(self.nextCallId)
		self.nextCallId += 1
		pms=asyncio.Future()
		stub = {"callId": callId, "pms": pms}
		self.callMap[callId] = stub
		message = {
			"msg": "CallClient",
			"sessionId": self.sessionId,
			"callId": callId,
			"message": {"msg": msg, "vo": vo}
		}
		message = json.dumps(message)
		await self.agentNode.websocket.send(message)
		return await pms

	# -------------------------------------------------------------------------
	async def clientCallResult(self, callId, result):
		stub = self.callMap.get(callId, None)
		if not stub:
			return
		self.callMap.pop(callId, None)
		stub["pms"].set_result(result)

	# -------------------------------------------------------------------------
	async def clientCallError(self, callId, error):
		stub = self.callMap.get(callId)
		if not stub:
			return
		self.callMap.pop(callId, None)
		stub["pms"].set_exception(Exception(error))

	# -------------------------------------------------------------------------
	# Load agent from file:
	async def loadAgent(self, fromAgent, path):
		agent = None
		agentDict = self.agentDict
		if not path.startswith("/"):
			if not fromAgent:
				path = pathLib.join(self.basePath, path)
			else:
				path = pathLib.join(fromAgent.get("baseDir") or self.basePath, path)
			path = pathLib.abspath(path)
		if path in agentDict:
			agent = agentDict[path]
		if agent:
			return agent
		entryPath=path
		if entryPath.startswith("/@"):
			entryPath = "../"+entryPath[2:]
			if not fromAgent:
				entryPath = pathLib.join(self.basePath, entryPath)
			else:
				entryPath = pathLib.join(fromAgent.get("baseDir") or self.basePath, entryPath)
			entryPath = pathLib.abspath(entryPath)
		try:
			module = import_module_from_file(entryPath)
			agent = getattr(module, "default")
			self.agentDict[path] = agent
			return agent
		except Exception as e:
			print(f"Failed to load agent from {path}: {e}")
			raise e

	async def runSeg(self, agent, segVO):
		result = None
		catchSeg = None
		input = ""
		if "input" in segVO:
			input = segVO["input"]
		elif "result" in segVO:
			input = segVO["result"]
		seg = segVO["seg"]
		if "catchSeg" in segVO:
			catchSeg = segVO["catchSeg"]
		try:
			while seg:
				segAct=await self.logSegStart(agent,result or segVO)
				result = await seg["exec"](input)
				await self.logSegEnd(agent,segAct,result)
				if "result" in result:
					input = result["result"]
				if "seg" in result:
					seg = result["seg"]
				else:
					seg = None
					result = input
				if seg and ("catchSeg" in result):
					return await self.runSeg(agent,result)
		except Exception as e:
			print(f"Caught error: {e}")
			print(f"Exception type: {type(e).__name__}")
			print(f"Exception message: {e}")
			print("Traceback (most recent call last):")
			traceback.print_tb(e.__traceback__)  # 打印详细堆栈信息
			if catchSeg:
				catchSegVO = {"input": e, "seg": catchSeg}
				result = await self.runSeg(agent,catchSegVO)
			else:
				raise e
		return result

	# -------------------------------------------------------------------------
	# Execute an agent:
	async def execAgent(self,agentPath, input):
		fromAgent=self.curAgent
		if callable(agentPath):
			agent = agentPath
		else:
			agent = await self.loadAgent(fromAgent, agentPath)
		agent = await agent(self)
		await self.logAgentStart(agent)
		entry = await agent["execChat"](input)
		result = await self.runSeg(agent,entry)
		self.curAgent = fromAgent
		return result

	# -------------------------------------------------------------------------
	# Execute an agent-seg-flow:
	async def execAISeg(self, agent, seg, input):
		execVO = {"seg": seg, "input": input}
		return await self.runSeg(agent,execVO)

	# -------------------------------------------------------------------------
	async def logAgentStart(self,agent):
		if not self.agentNode:
			return
		log={
			"type":"StartAgent",
			"agent":agent.get("jaxId")
		}
		await self.sendToClient("DebugLog", log)

	# -------------------------------------------------------------------------
	async def logAgentEnd(self,agent):
		if not self.agentNode:
			return
		log={
			"type":"StarEnd",
			"agent":agent.get("jaxId")
		}
		await self.sendToClient("DebugLog", log)

	# -------------------------------------------------------------------------
	async def logSegStart(self,agent,segVO):
		if not self.agentNode:
			return
		seg=segVO.get("seg",None)
		if not seg:
			return
		segAct={
			"agent":agent.get("jaxId"),
			"name": seg.get("name", "seg"),
			"url": seg.get("url", ""),
			"jaxId": seg.get("jaxId", ""),
			"input": segVO.get("input",None) or segVO.get("result",None),
			"fromSeg": segVO.get("preSeg", None),
			"fromOutlet": segVO.get("outlet", None)
		}
		segAct["id"]=id(segAct)
		log={
			"type":"StartSeg",
			"session":self.sessionId,
			"seg":segAct
		}
		await self.sendToClient("DebugLog", log)
		return segAct

	# -------------------------------------------------------------------------
	async def logSegEnd(self,agent,segAct,result):
		if not self.agentNode:
			return
		segAct["result"] = result.get("result",None)
		log={
			"type":"EndSeg",
			"session":self.sessionId,
			"seg":segAct
		}
		await self.sendToClient("DebugLog", log)

	# -------------------------------------------------------------------------
	# APIs for agent to call:
	# -------------------------------------------------------------------------
	# import file:
	async def importFile(self, path):
		return import_module_from_file(path)

	# -------------------------------------------------------------------------
	async def loadAPIFromFile(self, path):
		if not path.startswith("/"):
			path = pathLib.join(self.basePath, path)
			path = pathLib.abspath(path)
		try:
			module = import_module_from_file(path)
			apis = getattr(module, "ChatAPI")
			return apis
		except Exception as e:
			print(f"Failed to load agent from {path}: {e}")
			return None

	# -------------------------------------------------------------------------
	# load APIs
	async def loadAISegAPIs(self, list):
		allApis = []
		n = len(list)
		for i in range(n):
			path = list[i]
			print("---loadAPI: " + path)
			sub = await self.loadAPIFromFile(path)
			if (sub):
				allApis += sub
		return allApis

	# -------------------------------------------------------------------------
	async def readFile(self, path, outputFormat):
		if not path.startswith("/"):
			path = pathLib.join(self.basePath, path)
			path = pathLib.abspath(path)
		file = open(path, "rb")
		content = file.read()
		file.close()
		if outputFormat == "text":
			return content.decode("utf-8")
		return content

	# -------------------------------------------------------------------------
	async def writeFile(self, path, content, outputFormat):
		if not path.startswith("/"):
			path = pathLib.join(self.basePath, path)
			path = pathLib.abspath(path)
		if outputFormat == "text":
			file = open(path, "w", encoding='utf-8')
		else:
			file = open(path, "wb")
		file.write(content)
		file.close()

	# -------------------------------------------------------------------------
	# output text/image to user
	async def addChatText(self, role, content, opts):
		if self.agentNode:
			blockVO = {
				"role": role,
				"text": content,
			}
			if role!="user" and role!="log":
				blockVO["txtHeader"]=self.agentNode.name
			if opts:
				if "image" in opts:
					blockVO.image = opts["image"]
				if "audio" in opts:
					blockVO.audio = opts["audio"]
			await self.sendToClient("ChatBlock", blockVO)
		elif (opts):
			print(f"[{role}]: {content}")
			if "image" in opts:
				dataURL = opts["image"]
				image_data = dataURL.split(",")[1]
				# 将base64编码的图像数据解码
				image_bytes = base64.b64decode(image_data)
				# 将图像数据转换为PIL Image对象
				image = Image.open(BytesIO(image_bytes))
				# 显示图片
				image.show()
			if "audio" in opts:
				tempPath = pathLib.abspath(pathLib.join(self.basePath, "_temp_audio.mp3"))
				mp3_data = base64.b64decode(opts["audio"])
				file = open(tempPath, "wb")
				file.write(mp3_data)
				file.close()
				try:
					playsound(tempPath)
					os.remove(tempPath)
				except Exception as e:
					print(f"Error in playsound: {e}")
					print(f"The temp audio file is: {tempPath}")

	# -----------------------------------------------------------------------
	async def resizeImage(self, data_url, maxSize, imgFormat):
		# 从dataURL中提取图片数据
		image_data = base64.b64decode(data_url.split(',')[1])

		# 使用Pillow打开图片
		image = Image.open(BytesIO(image_data))

		# 原始尺寸
		orgW, orgH = image.size
		newW = orgW
		newH = orgH
		if orgW <= maxSize and orgH <= maxSize:
			return data_url
		if orgW > maxSize:
			newH = int(orgH * maxSize / orgW)
			newW = maxSize
		if newH > maxSize:
			newW = int(newW * maxSize / newH)
			newH = maxSize
		# 缩放图片
		resized_image = image.resize((newW, newH))
		# 将缩放后的图片转换为dataURL
		image_buffer = BytesIO()
		resized_image.save(image_buffer, format=(imgFormat or 'JPEG'))
		image_data = image_buffer.getvalue()
		image_base64 = base64.b64encode(image_data).decode()
		if imgFormat == "PNG":
			data_url_resized = f"data:image/png;base64,{image_base64}"
		else:
			data_url_resized = f"data:image/jpeg;base64,{image_base64}"
		return data_url_resized

	# -----------------------------------------------------------------------
	# input from user
	async def askChatInput(self, vo):
		if self.agentNode:
			askVO = {
				"role": vo.get("role", "assistant"),
				"prompt": vo.get("prompt") or "Please input",
				"initText": vo.get("initText", "")
			}
			return await self.callClient("AskChatInput", askVO)
		elif "prompt" in vo:
			prompt = vo["prompt"] or "Please input: "
		else:
			prompt = "Please input: "
		return input(prompt)

	# -----------------------------------------------------------------------
	async def callHub(self,msg,vo):
		return await self.agentNode.callHub(msg,vo,self)

	# -----------------------------------------------------------------------
	async def callHubLLM(self,opts,messages,waitBlk):
		callVO={
			"platform":opts.get("platform","OpenAI"),
			"model":opts.get("mode","gpt-4o"),
			"temperature":opts.get("temperature",0),
			"max_tokens":opts.get("maxToken",4096),
			"messages":messages,
			"top_p":opts.get("topP",1),
			"presence_penalty":opts.get("prcP",0),
			"frequency_penalty":opts.get("fqcP",0),
			"response_format":opts.get("responseFormat","text")
		}

		seed=opts.get("seed",None)
		if seed:
			callVO.seed=seed

		apis=opts.get("apis",None)
		if apis:
			callVO["functions"]=apis.get("functions")
			if opts.get("parallelFunction"):
				callVO.parallelFunction=True
		res = await self.callHub("AICallStream", callVO)
		if res.get("code") !=200:
			raise Exception(f"AIStreamCall failed:{res.get('code')}:{res.get('info')}")
		streamId = res.get("streamId")
		streamObj={}
		while not res.get("closed",False):
			res=await self.callHub("readAIChatStream",{"streamId":streamId})
			if res.get("code")!=200:
				break
			pmt=res.get("message","")
			streamObj["content"]=pmt
			if res.get("functionCall"):
				streamObj["functionCall"]=res.get("functionCall")
			if res.get("toolCalls"):
				streamObj["toolCalls"]=res.get("toolCalls")
			if res.get("inputTokens")>=0:
				streamObj["inputTokens"]=res.get("inputTokens")
			if res.get("outputTokens")>=0:
				streamObj["outputTokens"]=res.get("outputTokens")
			await self.sendToClient("SetWaitBlockText", {"block": waitBlk, "text": pmt})

		content=streamObj["content"]
		functionCall = streamObj.get("functionCall")
		toolCalls = streamObj.get("toolCalls")

		if functionCall:
			name = functionCall.get("name")
			stub = opts["apis"]["stubs"].get("name")
			if not stub:
				raise Exception(f"API Function: {name} not found.")
			func = stub["func"]
			args = functionCall["arguments"]
			if func:
				args = functionCall.get("arguments")
				params = inspect.signature(func).parameters.keys()
				filteredArgs = {key: args[key] for key in params if key in args}
				callResult = await func(session=self, **filteredArgs)
			else:
				raise Exception(f"Can't find function {name}")
			messages = messages[:]
			messages.push({"role": "assistant", "content": "", "function_call": functionCall});
			messages.push({"role": "function", "name": name, "content": callResult});
			result = await self.callHubLLM(opts, messages)
		elif toolCalls:
			messages = messages[:]
			n=len(toolCalls)
			for i in range(n):
				toolCall = toolCalls[i]
				functionCall = toolCall.get("function")
				name= functionCall.get("name")
				stub = opts["apis"]["stubs"].get(name)
				if not stub:
					raise Exception(f"API Function: {name} not found.")
				func = stub.get("func")
				if func:
					args = functionCall.get("arguments")
					params = inspect.signature(func).parameters.keys()
					filteredArgs = {key: args[key] for key in params if key in args}
					callResult = await func(session=self, **filteredArgs)
					messages.append({"tool_call_id": toolCall.get("id"), "role": "tool", "name": "name", "content": callResult})
				else:
					messages.append({"tool_call_id": toolCall.get("id"), "role": "tool", "name": "name", "content": "Can't find function"})
			result = await self.callHubLLM(opts, messages)
		else:
			result = content
		return result

	# -----------------------------------------------------------------------
	# Call LLM:
	async def callSegLLM(self, codeURL, opts, messages, fromSeg):
		platform, model, completion = None, None, None
		waitBlk=0
		apiHash = None
		model2Platform = {
			"gpt-4o": "OpenAI",
			"gpt-4o-mini": "OpenAI",
			"gpt-3.5-turbo": "OpenAI",
			"gpt-3.5-turbo-16k": "OpenAI",
			"gpt-3.5-turbo-1106": "OpenAI",
			"gpt-4": "OpenAI",
			"gpt-4-32k": "OpenAI",
			"gpt-4-1106-preview": "OpenAI",
		}
		if "model" in opts:
			model = opts["model"]
		elif "mode" in opts:
			model = opts["mode"]
		else:
			model = "gpt-4o-minio"
		platform = model2Platform.get(model) or opts.get("platform")
		if self.agentNode:
			waitBlk = await self.callClient("AddWaitBlock", {"text":"..."})
		try:
			if platform == "OpenAI":
				openAI=setupOpenAI(self)
				if not openAI:
					return await self.callHubLLM(opts,messages,waitBlk)
				useStream=opts.get("stream",True)
				temperature = opts.get("temperature",1)
				# Add function/tool support:
				if "apis" in opts:
					apis = opts["apis"]
					apiHash = {}
					if "parallelFunction" in opts and opts["parallelFunction"]:
						tools = []
						for stub in apis:
							print(stub)
							toolDef = stub["def"]
							tools.append({
								"type": "function",
								"function": toolDef
							})
							apiHash[toolDef["name"]] = stub
						completion = openAI.chat.completions.create(
							model=model,
							temperature=temperature,
							messages=messages,
							tools=tools,
							tool_choice="auto",
							response_format={ "type": "json_object" } if opts.get("responseFormat")=="json_object" else { "type": "text" },
							stream=useStream
						)
					else:
						stub = None
						apiList = []
						for stub in apis:
							toolDef = stub["def"]
							apiList.append(toolDef)
							apiHash[toolDef["name"]] = stub
						completion = openAI.chat.completions.create(
							model=model,
							temperature=temperature,
							messages=messages,
							functions=apiList,
							function_call="auto",
							response_format={ "type": "json_object" } if opts.get("responseFormat")=="json_object" else { "type": "text" },
							stream=useStream
						)
				else:
					completion = openAI.chat.completions.create(
						model=model,
						temperature=temperature,
						messages=messages,
						response_format={ "type": "json_object" } if opts.get("responseFormat")=="json_object" else { "type": "text" },
						stream=useStream
					)
				if useStream :
					def readContent():
						content=""
						tool=""
						funcCall=""
						for chunk in completion:
							delta=chunk.choices[0].delta
							if delta.content:
								content+=delta.content
							if delta.tool_calls:
								tool+=delta.tool_calls
							if delta.function_call:
								funcCall+=delta.function_call
							if self.agentNode:
								waitText=tool if tool else (funcCall if funcCall else content)
								asyncio.run(self.sendToClient("SetWaitBlockText", {"block": waitBlk, "text": waitText}))

						if tool:
							ret= {"content":content,"tool_calls":json.loads(tool),"function_call":None}
						elif funcCall:
							ret= {"content": content, "function_call": json.loads(funcCall),"tool_calls": None}
						else:
							ret={"content": content, "function_call": None, "tool_calls":None}
						return SimpleNamespace(**ret)
					loop = asyncio.get_running_loop()
					with ThreadPoolExecutor() as pool:
						result = await loop.run_in_executor(pool, readContent)
				else:
					result = completion.choices[0].message
				# print("Chat result:")
				# print(result)
				if result.tool_calls:
					toolCalls = result.tool_calls
					# print("Will call tools")
					# print(toolCalls)
					messages = messages[:]
					messages.append(result)
					for toolCall in toolCalls:
						callStub = toolCall.function
						callName = callStub.name
						apiStub = apiHash[callName]
						apiFunc = apiStub["func"]
						callArgs = json.loads(callStub.arguments)
						callArgs["session"] = self
						callResult = await apiFunc(**callArgs)
						# print(f"Call {callName} result:")
						# print(callResult)
						messages.append({
							"tool_call_id": toolCall.id,
							"role": "tool",
							"name": callName,
							"content": callResult,
						})
					return await self.callSegLLM(codeURL, opts, messages, False)
				if result.function_call:
					functionCall = result.function_call
					# print("Will call function")
					# print(functionCall)
					messages = messages[:]
					messages.append({"role": "assistant", "content": "", "function_call": functionCall})
					callName = functionCall.name
					apiStub = apiHash[callName]
					apiFunc = apiStub["func"]
					callArgs = json.loads(functionCall.arguments)
					callArgs["session"] = self
					callResult = await apiFunc(**callArgs)
					# print(f"Call {callName} result:")
					# print(callResult)
					messages.append({
						"role": "function", "name": callName, "content": callResult
					})
					return await self.callSegLLM(codeURL, opts, messages, False)
				return result.content
			else:
				return await self.callHubLLM(opts, messages, waitBlk)
				# raise Exception(f"Unknown platform: {platform}, model: {model}")
		finally:
			if self.agentNode:
				await self.sendToClient("RemoveWaitBlock", {"block":waitBlk})

	# -------------------------------------------------------------------------
	# Call AI to draw something:
	async def callAIDraw(self, vo):
		model2Platform = {
			"dall-e-3": "OpenAI",
			"dall-e-2": "OpenAI",
		}
		if "model" in vo:
			model = vo["model"]
		elif "mode" in vo:
			model = vo["mode"]
		else:
			model = "dall-e-3"
		platform = model2Platform.get(model, "OpenAI")
		if platform == "OpenAI":
			prompt = vo["prompt"]
			size = vo["size"]
			response = openAI.images.generate(
				model=model,
				prompt=prompt,
				n=1,
				size=size,
				response_format="b64_json"
			)
			img = response.data[0].b64_json
			return {"code": 200, "img": img}
		else:
			return {"code": 400, "info": f"Unknown model: {model}"}

	def genMp3Name(self):
		now = datetime.now()
		now = now.strftime("%Y_%m_%d_%H_%M_%S")
		return "speech" + now + ".mp3"

	# -------------------------------------------------------------------------
	async def callAITTS(self, vo):
		tempPath = pathLib.abspath(pathLib.join(self.basePath, self.genMp3Name()))
		model2Platform = {
			"tts-1": "OpenAI",
			"tts-1-hd": "OpenAI",
		}
		if "model" in vo:
			model = vo["model"]
		elif "mode" in vo:
			model = vo["mode"]
		else:
			model = "tts-1"
		platform = model2Platform.get(model, "OpenAI")
		if platform == "OpenAI":
			input = vo["input"]
			voice = vo["voice"]
			response = openAI.audio.speech.create(
				model=model,
				input=input,
				voice=voice
			)
			response.stream_to_file(tempPath)
			file = open(tempPath, "rb")
			content = file.read()
			file.close()
			content = base64.b64encode(content).decode()
			print("TTS output into:" + tempPath)
			return {"code": 200, "mp3": content}
		return {"code": 400, "info": f"Unknown model: {model}"}

	# -------------------------------------------------------------------------
	async def pipeChat(self, path, input, hideInter):
		return await self.execAgent(path, input)

	# -------------------------------------------------------------------------
	async def webCall(self, vo, fromAgent, timeout):
		url = vo.url
		method = vo["method"] if ("method" in vo) else "GET"
		headers = vo["headers"] if ("headers" in vo) else {}
		argMode = vo["argMode"] if ("argMode" in vo) else None

		if argMode == "JSON":
			headers["Content-Type"] = "application/json"
			with httpx.Client() as client:
				response = client.request(method, url, headers=headers, json=vo["json"])
		elif argMode == "TEXT":
			headers["Content-Type"] = "text/plain"
			with httpx.Client() as client:
				response = client.request(method, url, headers=headers, data=vo["text"])
		elif argMode == "DATA":
			headers["Content-Type"] = "application/octet-stream"
			with httpx.Client() as client:
				response = client.request(method, url, headers=headers, data=vo["data"])
		else:
			with httpx.Client() as client:
				response = client.request(method, url, headers=headers)
		if response.status_code == httpx.codes.OK:
			return {"code": 200, "data": response.text}
		else:
			return {"code": response.status_code, "info": response.text}

	# -------------------------------------------------------------------------
	# Show command line menu and get select:
	def showMenu(self, prompt, items):
		idx = None
		print(prompt)
		n = len(items)
		for i in range(n):
			print(f"[{i + 1}]: ")
			print("    " + items[i]["text"])
		while (True):
			idx = input("Input a index of your choice: ")
			try:
				idx = int(idx)
			except Exception as e:
				idx = -1
			idx = idx - 1
			if 0 <= idx < n:
				break
		return items[idx]

	# -------------------------------------------------------------------------
	# Show confirm buttons, menu...
	async def askUserRaw(self, vo):
		if self.agentNode:
			return await self.callClient("AskUserRaw", vo)
		else:
			askType = vo["type"]
			# --Button confirm:
			if askType == "confirm":
				items = []
				if vo["button1"]:
					items.append({"text": vo["button1"], "code": 1})
				else:
					items.append({"text": "OK", "code": 1})
				if vo["button2"]:
					items.append({"text": vo["button2"], "code": 0})
				else:
					items.append({"text": "Cancel", "code": 0})
				if vo["button3"]:
					items.append({"text": vo["button3"], "code": 2})
				item = self.showMenu(vo["prompt"], items)
				return [item["text"], item["code"]]
			# --Menu selections:
			if askType == "menu":
				items = vo["items"]
				item = self.showMenu(vo["prompt"], items)
				return [item["text"], item]
			# --Input:
			if askType == "input":
				# --File:
				if "path" in vo:
					if "prompt" in vo:
						prompt = vo["prompt"] or "Please input: "
					else:
						prompt = "Please input: "
					inputPath = path = input(prompt)
					if not path.startswith("/"):
						path = pathLib.join(self.basePath, path)
						path = pathLib.abspath(path)
					return [inputPath, path]


# Exports:
__all__ = ["AISession","trimJSON"]
