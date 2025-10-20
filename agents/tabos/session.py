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
# from playsound import playsound
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import traceback
import inspect
import sys
from remotesession import RemoteSession

pathLib = os.path
openAI = None


# *****************************************************************************
def setupOpenAI(session):
	global openAI
	if openAI:
		return openAI
	key=session.agentNode.hubJSON.get("key_OpenAI")
	if key:
		openAI=OpenAI(api_key=key)
		return openAI
	return None

# *****************************************************************************
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


# *****************************************************************************
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


# *****************************************************************************
def getErrorLocation(e):
	tb = e.__traceback__
	while tb.tb_next is not None:
		tb = tb.tb_next  # 获取最后一层堆栈信息

	file_name = tb.tb_frame.f_code.co_filename
	line_number = tb.tb_lineno
	function_name = tb.tb_frame.f_code.co_name
	return f"File: {file_name}, Line: {line_number}, Function: {function_name}"


# *****************************************************************************
def to_dict(obj, max_depth=3, _visited=None, _current_depth=0):
	"""
	将对象递归转化为字典，支持最大递归深度和循环引用检测。

	:param obj: 要转化的对象
	:param max_depth: 最大递归深度
	:param _visited: 内部使用，用于记录已经处理过的对象，避免循环引用
	:param _current_depth: 当前递归深度
	:return: 转化后的字典
	"""
	# 初始化 visited 集合，记录已访问的对象
	if _visited is None:
		_visited = set()

	# 如果超过最大递归深度，返回字符串表示
	if _current_depth > max_depth:
		return f"<Max depth reached: {type(obj).__name__}>"

	# 如果对象是 None、基本类型或可以直接 JSON 序列化，直接返回
	if obj is None or isinstance(obj, (str, int, float, bool)):
		return obj

	# 如果是字典，递归处理其键值
	if isinstance(obj, dict):
		return {to_dict(k, max_depth, _visited, _current_depth + 1):
				to_dict(v, max_depth, _visited, _current_depth + 1)
				for k, v in obj.items()}

	# 如果是列表或元组，递归处理其元素
	if isinstance(obj, (list, tuple)):
		return [to_dict(item, max_depth, _visited, _current_depth + 1) for item in obj]

	# 检查对象是否已经访问过，防止循环引用
	obj_id = id(obj)
	if obj_id in _visited:
		return f"<Circular reference: {type(obj).__name__}>"
	_visited.add(obj_id)

	# 尝试将对象的属性转化为字典
	result = {}
	if hasattr(obj, "__dict__"):  # 处理有 __dict__ 属性的对象
		result = {key: to_dict(value, max_depth, _visited, _current_depth + 1)
				  for key, value in vars(obj).items()}
	elif hasattr(obj, "__slots__"):  # 处理有 __slots__ 的对象
		result = {key: to_dict(getattr(obj, key), max_depth, _visited, _current_depth + 1)
				  for key in obj.__slots__ if hasattr(obj, key)}
	else:
		result = f"<Unsupported object type: {type(obj).__name__}>"

	# 从 _visited 中移除对象，允许其在其他上下文中再次被处理
	_visited.remove(obj_id)
	return result

frameSeqId=0

class AISession:
	basePath = None
	curAgent = None
	curPath = None
	agentDict = {}
	globalContext = {}

	def __init__(self, basePath, node=None, sessionId=None,options=None):
		self.basePath = basePath
		self.curPath = None
		self.agentNode = node
		self.sessionId = sessionId
		self.nextCallId = 0
		self.callMap = {}
		self.version = "0.0.2"
		self.curAgent = None
		self.options = options or {}
		self.language = self.options.get('language') or "CN"
		self.snsBot=options.get("snsBot", None)
		self.snsChatUserId = None
		self.debugStarted=False
		self.debugConnected=False
		self.keepAlive=False;
		self.callHandlers={}

		nodeJSON=node.hubJSON
		if nodeJSON:
			nodeGlobal=nodeJSON.get("globalContext")
			if nodeGlobal:
				self.globalContext.update(nodeGlobal)
		nodeJSON=node.nodeJSON
		if nodeJSON:
			nodeGlobal=nodeJSON.get("globalContext")
			if nodeGlobal:
				self.globalContext.update(nodeGlobal)
		nodeGlobal=self.options.get("globalContext")
		if nodeGlobal:
			self.globalContext.update(nodeGlobal)
		self.callClientFromAgent=None
		self.callClientAskSeg=None

		

	# -------------------------------------------------------------------------
	# Show version:
	def showVersion(self):
		print("AIChatSession 0.02")

	# -------------------------------------------------------------------------
	async def indentMore(self):
		await self.callClient("IdentMore",{})

	# -------------------------------------------------------------------------
	async def indentLess(self):
		await self.callClient("IdentLess",{})

	# -------------------------------------------------------------------------
	# Network APIs:
	# -------------------------------------------------------------------------
	async def startDebug(self,agentURL,entryDef):
		self.debugStarted=True
		try:
			await self.callClient("ConnectAgentDebug",{"address":self.agentNode.address,"port":self.agentNode.debugPort,"entryURL":agentURL,"entryAgent":entryDef})
			print("Debug client connected")
		except Exception as e:
			return False
		self.debugConnected=True

	async def sendToClient(self, msg, vo):
		if not self.agentNode.websocket:
			return
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
		if not self.agentNode.websocket:
			return
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

	# -----------------------------------------------------------------------
	async def callHub(self,msg,vo):
		return await self.agentNode.callHub(msg,vo,self)

	# -------------------------------------------------------------------------
	async def webCall(self, vo, fromAgent, timeout):
		url = vo.get("url")
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
	# Load/ run agent
	# -------------------------------------------------------------------------
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

			# TODO: Read source def:
			codes=""
			try:
				# 打开文件并读取内容
				with open(entryPath, 'r', encoding='utf-8') as file:
					codes = file.read()
					if codes:
						mark = "#Cody Project Doc"
						pos = codes.find(mark)
						if pos > 0:
							codes = codes[pos + len(mark):]
							codes = codes.replace("\n#", "\n")
							agent.sourceDef = json.loads(codes)
			except Exception as e:
				print(f"Read sourceDef error：{e}")
				agent.sourceDef=None
			return agent
		except Exception as e:
			print(f"Failed to load agent from {path}: {e}")
			raise e

	# -------------------------------------------------------------------------
	# Call an agent, client, node, or local
	# -------------------------------------------------------------------------
	async def callAgent(self, agentNode,agentPath,input,opts):
		opts=opts or {}
		if agentNode:
			if agentNode=="$client":
				result=None
				oldFromAgent=self.callClientFromAgent
				oldAskSeg=self.callClientAskSeg
				self.callClientFromAgent=opts.get("fromAgent",None) or opts.get("upperAgent",None)
				self.callClientAskSeg=opts.get("askUpwardSeg",None)
				try:
					result=await self.callClient("CallAgent",{"agent":agentPath,"arg":input})
				finally:
					self.callClientFromAgent=oldFromAgent
					self.callClientAskSeg=oldAskSeg
				return result
			return await RemoteSession.exec(self,agentNode,agentPath,input,opts);
		else:
			result=self.execAgent(agentPath, input,opts)
		return result

	# -------------------------------------------------------------------------
	async def pipeChat(self, path, input, hideInter=False):
		return await self.execAgent(path, input)

	# -------------------------------------------------------------------------
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
			print(f"Caught error: [{type(e).__name__}]: {e}")
			print("Traceback (most recent call last):")
			traceback.print_tb(e.__traceback__)  # 打印详细堆栈信息
			info=f"Caught error: {e} at {getErrorLocation(e)}"
			if catchSeg:
				await self.logCatchError(agent,info)
				catchSegVO = {"input": info, "seg": catchSeg}
				result = await self.runSeg(agent,catchSegVO)
			else:
				raise e
		return result

	# -------------------------------------------------------------------------
	# Create a new agent, but not execute it:
	async def createAgent(self,agentPath):
		global frameSeqId
		fromAgent=self.curAgent
		if callable(agentPath):
			agent = agentPath
		else:
			agent = await self.loadAgent(fromAgent, agentPath)
		agent = await agent(self)
		agent["agentFrameId"]=frameSeqId
		frameSeqId+=1
		await self.logAgentStart(agent)
		return agent

	# -------------------------------------------------------------------------
	# Execute an agent:
	async def execAgent(self,agentPath, input, opts=None):
		global frameSeqId
		fromAgent=self.curAgent
		opts=opts or {}

		if callable(agentPath):
			agent = agentPath
		else:
			agent = await self.loadAgent(fromAgent, agentPath)
		try:
			sourceDef=agent.sourceDef
			agent = await agent(self)
			# sourceDef = agent.get("sourceDef")
			agent["sourceDef"] = sourceDef
			agent["agentFrameId"] = frameSeqId
			agent["upperAgent"]=opts.get("fromAgent",None)
			agent["askUpwardSeg"]=opts.get("askUpwardSeg",None)

			frameSeqId += 1

			if not self.debugStarted:
				await self.startDebug(agent.get("url"), sourceDef)

			self.curAgent = agent
			await self.logAgentStart(agent)
			entry = await agent["execChat"](input)
			result = await self.runSeg(agent,entry)
			await self.logAgentEnd(agent,result)
		finally:
			self.curAgent = fromAgent
		return result

	# -------------------------------------------------------------------------
	# Execute an agent-seg-flow:
	async def execAISeg(self, agent, seg, input):
		execVO = {"seg": seg, "input": input}
		return await self.runSeg(agent,execVO)

	# -------------------------------------------------------------------------
	# Ask upward:
	# -------------------------------------------------------------------------
	async def askUpward(self,agent,prompt):
		askUpwardSeg=None
		askAgent=agent
		agentName=agent.get("name",None)
		if agentName:
			showOpts={"txtHeader":agent.get("showName",None) or agent.get("name",None),"icon":"/~/-tabos/shared/assets/ask.svg","iconSize":24,"fontSize":12}
			await self.addChatText("assistant",prompt,showOpts)

		while askAgent :
			askUpwardSeg=askAgent.get("askUpwardSeg",None)
			askAgent=askAgent.get("upperAgent",None)
			if askAgent and askUpwardSeg:
				break
		if askUpwardSeg and askAgent:
			if askAgent=="$client":
				result=await self.callClient("AskUpward",{"prompt":prompt})
			elif askAgent=="$remote":
				remoteSession = askUpwardSeg
				result=await remoteSession.callRemote("AskUpward",{"prompt":prompt})
			else:
				result=await self.execAISeg(askAgent,askUpwardSeg,prompt)
		else:
			result=await self.askChatInput({"type":"input","text":"","allowFile":True})
			if isinstance (result,str):
				await self.addChatText("user",result)
			elif result.get("assets",None) and  result.get("prompt",None):
				await self.addChatText("user",f"{result.get('prompt')}{chr(10)}- - -{chr(10)}{(chr(10)+'- - -'+chr(10)).join(result.get('assets',None))}",{"render":True})
			else:
				await self.addChatText("user",result.get("text",None) or result.get("prompt",None) or result)
		if not isinstance(result, str):
			result = json.dumps(result)
		return result

	# -------------------------------------------------------------------------
	# Make logs
	# -------------------------------------------------------------------------
	async def logAgentStart(self,agent,arg=""):
		if not self.agentNode:
			return
		log={
			"type":"StartAgent",
			"agent":agent.get("jaxId"),
			"name":agent.get("name"),
			"url":agent.get("url"),
			"input":arg,
			"frameId":agent.get("agentFrameId"),
			"sourceDef":agent.get("sourceDef")
		}
		if await self.agentNode.sendDebugLog(log):
			return
		# await self.sendToClient("DebugLog", log)

	# -------------------------------------------------------------------------
	async def logAgentEnd(self,agent,result=""):
		if not self.agentNode:
			return
		log={
			"type":"EndAgent",
			"agent":agent.get("jaxId"),
			"name": agent.get("name"),
			"frameId":agent.get("agentFrameId"),
			"result": result,
		}
		if await self.agentNode.sendDebugLog(log):
			return
		# await self.sendToClient("DebugLog", log)

	# -------------------------------------------------------------------------
	async def logSegStart(self,agent,segVO):
		if not self.agentNode:
			return
		seg=segVO.get("seg",None)
		if not seg:
			return
		inputVO = segVO.get("input", None) or segVO.get("result", None)
		try:
			inputJSON=json.dumps(inputVO)
		except Exception as e:
			try:
				inputVO = to_dict(inputVO,3)
			except Exception as e:
				inputVO = "[Object]"
		segAct={
			"agent":agent.get("jaxId"),
			"name": seg.get("name", "seg"),
			"url": seg.get("url", ""),
			"jaxId": seg.get("jaxId", ""),
			"input": inputVO,
			"fromSeg": segVO.get("preSeg", None),
			"fromOutlet": segVO.get("outlet", None)
		}
		segAct["id"]=id(segAct)
		log={
			"type":"StartSeg",
			"session":self.sessionId,
			"seg":segAct
		}
		if await self.agentNode.sendDebugLog(log):
			return segAct
		# await self.sendToClient("DebugLog", log)
		return segAct

	# -------------------------------------------------------------------------
	async def logSegEnd(self,agent,segAct,result):
		if not self.agentNode:
			return
		if result:
			result = result.get("result", None)
			try:
				resultJSON=json.dumps(result)
			except Exception as e:
				try:
					result=to_dict(result)
				except Exception as e:
					result ="[Object]"
		segAct["result"] =result
		log={
			"type":"EndSeg",
			"session":self.sessionId,
			"seg":segAct
		}
		if await self.agentNode.sendDebugLog(log):
			return
		# await self.sendToClient("DebugLog", log)

	# -------------------------------------------------------------------------
	async def logCatchError(self,agent,error):
		if not self.agentNode:
			return
		log={
			"type":"CatchError",
			"agent":agent.get("jaxId"),
			"frameId":agent.get("agentFrameId"),
			"error":f"{error}",
		}
		await self.agentNode.sendDebugLog(log)

	# -------------------------------------------------------------------------
	async def logLlmCall(self,codeURL,opts,messages):
		if not self.agentNode:
			return
		log={
			"type":"LlmCall",
			"session":self.sessionId,
			"code":codeURL,
			"options":opts,
			"messages":messages
		}
		if await self.agentNode.sendDebugLog(log):
			return
		# await self.sendToClient("DebugLog", log)

	# -------------------------------------------------------------------------
	async def logLlmResult(self,codeURL,opts,messages,result):
		if not self.agentNode:
			return
		log={
			"type":"LlmResult",
			"session":self.sessionId,
			"code":codeURL,
			"options":opts,
			"messages":messages,
			"result": result
		}
		if await self.agentNode.sendDebugLog(log):
			return
		# await self.sendToClient("DebugLog", log)

	# -------------------------------------------------------------------------
	# APIs for agent to call-tool or I/O with AgentHub:
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
		content=None
		orgPath=path
		if not path.startswith("/"):
			path = pathLib.join(self.basePath, path)
			path = pathLib.abspath(path)
		try:
			with open(path, 'rb') as file:
				content = file.read()
		except Exception as e:
			try:
				content=base64.b64decode(orgPath)
			except Exception as e:
				content=None
		if not content:
			return None
		if outputFormat == "text":
			return content.decode("utf-8")
		if outputFormat == "base64":
			return base64.b64encode(content).decode('utf-8')
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
	async def saveHubTextFile(self, fileName, text):
		content = base64.b64encode(text)
		content = content.decode("utf-8")
		return await self.saveHubFile(fileName, content)

	# -------------------------------------------------------------------------
	async def saveHubFile(self, fileName, content):
		if isinstance(content, str):
			if content.startswith("data:"):
				pos = content.find(",")  # 找到逗号的索引
				content = content[pos + 1:]  # 从逗号后的位置开始截取			content = content.encode("utf-8")
		elif isinstance(content, (bytes, bytearray)):
			content = base64.b64encode(content)
			content = content.decode("utf-8")
		else:
			try:
				content = json.dumps(content)
			except Exception as e:
				content = ""+content
			content = content.encode("utf-8")
			content = base64.b64encode(content)
			content = content.decode("utf-8")
		res=await self.callHub("AhFileSave",{"fileName":fileName,"data":content})
		#TODO: DebugLog file:
		if res and res.get("code")==200:
			await self.callClient("NewHubFile",res.get('fileName'))
			return res.get('fileName')
		if res:
			raise Exception(f"Save hub file ${fileName} failed {res.get('code')}: {res.get('info')}")
		raise Exception(f"Save hub file ${fileName} failed.")

	# -------------------------------------------------------------------------
	async def loadHubFile(self, fileName, outputFormat="utf-8"):
		outputFormat=outputFormat.lower()
		res=await self.callHub("AhFileLoad",{"fileName":fileName})
		if (not res) or (res.get("code")!=200):
			if res:
				raise Exception(f"Load hub file ${fileName} failed {res.get('code')}: {res.get('info')}")
			else:
				raise Exception(f"Load hub file ${fileName} failed.")
		if outputFormat=="utf-8" or outputFormat=="text" or outputFormat=="utf8":
			decoded_bytes = base64.b64decode(res.get('data'))
			return decoded_bytes.decode('utf-8')
		elif outputFormat=="json":
			decoded_bytes = base64.b64decode(res.get('data'))
			text=decoded_bytes.decode('utf-8')
			return json.loads(text)
		elif outputFormat=="data" or outputFormat=="bytes":
			return base64.b64decode(res.get('data'))
		elif outputFormat=="dataurl":
			ext=pathLib.splitext(fileName)[1]
			if ext==".json":
				return "data:application/json;base64,"+res.get('data')
			if ext==".jpg" or ext==".jpeg":
				return "data:image/jpeg;base64,"+res.get('data')
			if ext==".png":
				return "data:image/png;base64,"+res.get('data')
			if ext==".txt":
				return "data:text/plain;base64,"+res.get('data')
			if ext==".mp3":
				return "data:audio/mpeg;base64,"+res.get('data')
			if ext==".js":
				return "data:application/javascript;base64,"+res.get('data')
			if ext==".md":
				return "data:text/markdown;base64,"+res.get('data')
			return "data:application/octet-stream;base64,"+res.get('data')
		return res.get('data')

	# -------------------------------------------------------------------------
	async def normURL(self,url):
		if url.startswith("hub://"):
			fileName=url.split("hub://")[1]
			return self.loadHubFile(fileName,"dataurl")
		return url

	# -----------------------------------------------------------------------
	# Interactive with user:
	# -----------------------------------------------------------------------
	# input from user
	async def askChatInput(self, vo):
		if self.agentNode:
			askVO = {
				"role": vo.get("role", "assistant"),
				"prompt": vo.get("prompt") or "Please input",
				"initText": vo.get("initText", "")
			}
			askVO.update(vo)
			if self.snsBot:
				return await self.snsBot.agentAskUserChat(askVO,self.snsChatUserId or None)
			return await self.callClient("AskChatInput", askVO)
		elif "prompt" in vo:
			prompt = vo["prompt"] or "Please input: "
		else:
			prompt = "Please input: "
		return input(prompt)

	# -------------------------------------------------------------------------
	# output text/image to user
	async def addChatText(self, role, content, opts={}):
		if self.agentNode:
			blockVO = {
				"role": role,
				"text": content,
				"txtHeader":opts.get("txtHeader",None),
				"channel":opts.get("channel",None),
			}
			if role!="user" and role!="log":
				blockVO["txtHeader"]=self.agentNode.name
			if opts:
				if "image" in opts:
					blockVO["image"] = opts["image"]
				if "audio" in opts:
					blockVO["audio"] = opts["audio"]
			if self.snsBot:
				if role!="user":
					await self.snsBot.agentSendUserChat(blockVO,self.snsChatUserId or None,opts)
				return
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
					# playsound(tempPath)
					os.remove(tempPath)
				except Exception as e:
					# print(f"Error in playsound: {e}")
					print(f"The temp audio file is: {tempPath}")

	# -----------------------------------------------------------------------
	async def resizeImage(self, data_url, maxSize, imgFormat):
		if data_url[:6]=="hub://":
			image_data=await self.loadHubFile(data_url[6:],"data")
		else:# 从dataURL中提取图片数据
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
			if self.snsBot:
				return await self.snsBot.agentAskUserRaw(vo,self.snsChatUserId or None)
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


	# -----------------------------------------------------------------------
	# Call AI without stream:
	# -----------------------------------------------------------------------
	async def callHubAI(self,opts,messages,waitBlk):
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
		models=self.globalContext.get("models") or {}
		name=callVO.get("model")
		if name[:1]=="$":
			name=name[1:]
			vo=models.get(name)
			if not vo:
				raise Exception(f"Can't find platform shortcut: {name}")
			callVO["platform"]=vo["platform"]
			callVO["model"]=vo["model"]
		seed=opts.get("seed",None)
		if seed:
			callVO.seed=seed

		apis=opts.get("apis",None)
		if apis:
			callVO["functions"]=apis.get("functions")
			if opts.get("parallelFunction"):
				callVO.parallelFunction=True
		res = await self.callHub("AICall", callVO)
		if res.get("code") !=200:
			raise Exception(f"AIStreamCall failed:{res.get('code')}:{res.get('info')}")
		result = res.get("message")
		return result

	# -----------------------------------------------------------------------
	# Call LLM and other AI features with stream:
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
		models=self.globalContext.get("models") or {}
		name=callVO.get("model")
		if name[:1]=="$":
			name=name[1:]
			vo=models.get(name)
			if not vo:
				raise Exception(f"Can't find platform shortcut: {name}")
			callVO["platform"]=vo["platform"]
			callVO["model"]=vo["model"]
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
			if res.get("inputTokens"):
				streamObj["inputTokens"]=res.get("inputTokens")
			if res.get("outputTokens"):
				streamObj["outputTokens"]=res.get("outputTokens")
			if waitBlk:
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
	async def makeAICall(self,codeURL,opts,messages,fromSeg):
		platform, model, completion = None, None, None
		await self.logLlmCall(codeURL,opts, messages)
		waitBlk=None
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

		result=await self.callHubAI(opts, messages, waitBlk)
		await self.logLlmResult(codeURL, opts, messages, result)
		return result

	# -----------------------------------------------------------------------
	async def callSegLLM(self, codeURL, opts, messages, fromSeg):
		platform, model, completion = None, None, None
		await self.logLlmCall(codeURL,opts, messages)
		waitBlk=None
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
		if self.snsBot:
			waitBlk=None
		elif self.agentNode:
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
							if (waitBlk is not None) and self.agentNode:
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
					result=await self.callSegLLM(codeURL, opts, messages, False)
					await self.logLlmResult(codeURL, opts, messages,result)
					return result
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
					result=await self.callSegLLM(codeURL, opts, messages, False)
					await self.logLlmResult(codeURL, opts, messages, result.content)
					return result
				await self.logLlmResult(codeURL, opts, messages, result.content)
				return result.content
			else:
				result=await self.callHubLLM(opts, messages, waitBlk)
				await self.logLlmResult(codeURL, opts, messages, result)
				return result
				# raise Exception(f"Unknown platform: {platform}, model: {model}")
		finally:
			if (waitBlk is not None) and self.agentNode:
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
	# Wait util API
	# -------------------------------------------------------------------------
	async def showWait(self,text):
		if self.snsBot:
			blockVO = {
				"role": "assistant",
				"text": text,
			}
			await self.snsBot.agentSendUserChat(blockVO, self.snsChatUserId or None, {})
			return 1
		return await self.callClient("AddWaitBlock", {"text": text or "..."})

	# -------------------------------------------------------------------------
	async def setWaitText(self,waitBlk,text):
		if self.snsBot:
			#TODO: Code this?
			return
		await self.sendToClient("SetWaitBlockText", {"block": waitBlk, "text": text})

	# -------------------------------------------------------------------------
	async def removeWait(self,waitBlk):
		if self.snsBot:
			#TODO: Code this?
			return
		await self.sendToClient("RemoveWaitBlock", {"block": waitBlk})

	# -------------------------------------------------------------------------
	async def handleCall(self,msg,vo):
		if msg=="AskUpward":
			fromAgent = self.callClientFromAgent
			askSeg = self.callClientAskSeg
			fakeAgent = {"upperAgent": fromAgent,"askUpwardSeg": askSeg}
			return await self.askUpward(fakeAgent, vo.prompt)
		handler=self.callHandlers.get(msg)
		if not handler:
			raise Exception(f"No call handler for '{msg}'.")
		return await handler(self,msg,vo)

# Exports:
__all__ = ["AISession","trimJSON"]
