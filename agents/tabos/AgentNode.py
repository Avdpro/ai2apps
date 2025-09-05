import json
import asyncio
import base64
import websockets
import os
import sys
import signal
from session import AISession

pathLib = os.path

current_path = pathLib.dirname(pathLib.realpath(__file__))


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
def readJSON(file_path):
	file=None
	try:
		file = open(file_path, "r", encoding="utf-8")
		data = json.load(file)
		file.close()  # 显式关闭文件
		return data
	except FileNotFoundError:
		print(f"File {file_path} not found")
		return {}
	except json.JSONDecodeError as e:
		print(f"JSON {file_path} parse error: {e}")
		return {}
	except Exception as e:
		print(f"发生错误: {e}")
	finally:
		if file and (not file.closed):  # 确保文件被关闭
			file.close()

# *****************************************************************************

def wrap_async_callback(async_callback):
	def callback(task):
		asyncio.create_task(async_callback(task))  # 调度异步回调

	return callback


hubPath=pathLib.join(current_path,"../")
hubConfig=readJSON(pathLib.join(current_path,"../agenthub.json"))


# *****************************************************************************
class AgentNode:
	def __init__(self, path, host, name):
		if not path.startswith("/"):
			path=pathLib.join(hubPath,path)

		if path not in sys.path:
			sys.path.insert(0, path)  # Make sure we are in path.

		path = pathLib.normpath(path)
		if path.endswith(".json"):
			jsonPath=path
			path=pathLib.dirname(jsonPath)
		else:
			jsonPath=pathLib.join(path,"agent.json")

		self.path=path
		self.hubPath = hubPath
		self.name = name or None
		self.host = host
		self.address = None
		self.connected = False
		self.websocket = None
		self.agent = None
		self.sessionMap = {}
		self.nodeJSON = None
		self.hubJSON=hubConfig
		self.callMap={}
		self.nextCallId=0
		self.callHandlers={}
		self.workload=0
		# debugs:
		self.slowMo=False
		self.debugServer=None
		self.wsDebug=None
		self.debugSockets=[]
		self.debugConnected=False
		self.debugStepRun=False
		self.debugStepTask=None
		self.debugPort=5001

		# Read config json:
		try:
			file = open(jsonPath, "r", encoding="utf-8")
			nodeJSON = json.load(file)  # 解析 JSON 内容为 Python 对象
			nodeJSON["path"]=nodeJSON.get("path",self.path)
			print("JSON 数据:", nodeJSON)
		except:
			nodeJSON = {
				"name": self.name or self.path,
				"path": self.path,
				"description": "Agent node"
			}
		self.nodeJSON = nodeJSON
		if not self.name:
			self.name = nodeJSON.get("name", self.name)
		if not self.host:
			self.host = hubConfig.get("host", self.host)
		if not self.address:
			self.host = hubConfig.get("address", self.host)
		self.devKey=nodeJSON.get("devKey", None) or hubConfig.get("devKey", None)

	# -------------------------------------------------------------------------
	# Create a websocket connect to host
	async def start(self,run=True):
		if self.nodeJSON.get("debug")is not False:
			task=asyncio.create_task(self.startDebug())
		self.websocket = await websockets.connect(self.host,max_size=10485760)
		await self.onOpen()
		if run:
			await self.run()

	# -------------------------------------------------------------------------
	async def run(self):
		try:
			while True:
				message = await self.websocket.recv()
				await self.onMessage(message)
		except websockets.ConnectionClosed as e:
			print(f"Websocket connection closed: {e}")
			await self.onClose()
		except Exception as e:
			print(f"Websocket exception: {e}")
		finally:
			# Make sure close:
			await self.websocket.close()

	# -------------------------------------------------------------------------
	# Create a websocket connect to host
	async def onOpen(self):
		message = {
			"msg": "CONNECT",
			"name": self.name,
			"selector": "RegisterAgentNode",
			"info": self.nodeJSON
		}
		message = json.dumps(message)
		await self.websocket.send(message)

	# -------------------------------------------------------------------------
	async def onMessage(self, message):
		if isinstance(message, str):
			try:
				message = json.loads(message)
			except:
				print(f"Parse message error, message: {message}")
				return

		msgCode=message.get("msg",None)
		if msgCode!="State":
			log=f"Got websocket message: {message}"
			if(len(log)<1024*10):
				print(log)
			else:
				shortLog=log[:1024*5]+"..."+log[-1024*5:]
				print(shortLog)

		# check if connected, if not, check if message is "CONNECTED", then call onConnected
		if not self.connected:
			if msgCode == 'CONNECTED':
				await self.onConnect()
		else:
			msg = msgCode
			if msg == 'CreateSession':
				await self.createSession(message.get("sessionId"),message.get("options")or{})

			elif msg == 'State':
				await self.websocket.send(json.dumps({"msg": "State","workload":self.workload}))

			elif msg == 'StopNode':
				await self.websocket.close(1000)
				sys.exit()

			elif msg == 'RestartNode':
				await self.websocket.close(1000)
				python = sys.executable
				os.execv(python, [python] + sys.argv)

			elif msg == 'Call':
				sessionId=message.get("session") or message.get("sessionId")
				callData=message.get("message")
				callId=message.get("callId")
				if callData and callId:
					callError=None
					callResult=None
					try:
						callResult=await self.handleCall(message)
					except Exception as e:
						callError=f"Error: {e}"
					res={
						"msg": "CallResult",
						"session": sessionId,
						"callId": callId,
					}
					if callError :
						res["error"]=callError
					else:
						res["result"]=callResult
					await self.websocket.send(json.dumps(res))
						
			elif msg == 'ExecAgent':
				sessionId=message.get("sessionId")

				async def callback(task):
					try:
						result = task.result()  # 获取任务的返回值
						print(f"Task result: {result}")
						await self.websocket.send(json.dumps({"msg": "EndExecAgent", "session":sessionId, "result": result}))
					except Exception as e:
						print(f"Task raised an exception: {e}. At: {getErrorLocation(e)}")
						await self.websocket.send(json.dumps({"msg": "EndExecAgent", "session":sessionId, "error": f"Error: {e} \nAt: {getErrorLocation(e)}"}))
				agentPath=message.get("agent", None)
				if agentPath:
					ext=pathLib.splitext(agentPath)[1]
					if ext!=".py":
						agentPath=agentPath+".py"
					task=asyncio.create_task(self.execAgent(sessionId, agentPath, message.get("prompt", "")))
					task.add_done_callback(wrap_async_callback(callback))
				else:
					await self.websocket.send(json.dumps({"msg": "EndExecAgent", "session": sessionId, "error": f"Error: missing agent name/path"}))

			elif msg == "CallResult":
				def callback(task):
					try:
						result = task.result()  # 获取任务的返回值
						print(f"CallResult task result: {result}")
					except Exception as e:
						print(f"CallResult task raised an exception: {e}")
				task=asyncio.create_task(self.callResult(message))
				task.add_done_callback(callback)

	# -------------------------------------------------------------------------
	async def onConnect(self):
		if self.connected:
			return
		self.connected = True

	# -------------------------------------------------------------------------
	async def onClose(self):
		self.connected = False
		print("Will close agent.")
		return True

	# -------------------------------------------------------------------------
	# Create a session for execute agent:
	async def createSession(self, sessionId,options):
		options=options or {}
		if (not self.connected) and (not options.get("allowOffline")):
			return False
		ssn = AISession(self.path, self, sessionId, options)
		self.sessionMap[sessionId] = ssn
		if self.connected:
			await self.websocket.send(json.dumps({"msg": "SessionReady", "session": sessionId}))
		return ssn

	# -------------------------------------------------------------------------
	async def execAgent(self, sessionId, path, prompt):
		cwd = os.getcwd()  # pathLib.dirname(pathLib.realpath(__file__))
		print("Agent run path:", cwd)

		ssn = self.sessionMap.get(sessionId, None)
		if not ssn:
			return False
		result = await ssn.execAgent(path, prompt,{"fromAgent":"$client","askUpwardSeg":True})
		self.sessionMap.pop(sessionId, None)
		await self.websocket.send(json.dumps({"msg": "EndSession", "session": sessionId}))
		return result

	# -------------------------------------------------------------------------
	async def handleCall(self,message):
		sessionId = message.get("session",None) or message.get("sessionId",None)
		callData = message.get("message")
		callMsg = callData.get("msg")
		callVO = callData.get("vo")

		if sessionId:
			session=self.sessionMap.get(sessionId,None)
			if not session:
				raise Exception(f"Session {sessionId} not found.")
			return await session.handleCall(callMsg,callVO)

		if callMsg=="State":
			return {"workload": self.workload}
		if hasattr(self, f"HandleCall_{callMsg}"):
			method= getattr(self,f"HandleCall_{callMsg}")
			return await method(callMsg,callVO)
		handler=self.callHandlers.get(callMsg)
		if not handler:
			raise Exception(f"No call handler for '{callMsg}'.")
		return await handler(self,callMsg,callVO)
	
	# -------------------------------------------------------------------------
	async def callResult(self, message):
		sessionId = message.get("session")
		if not sessionId:
			if "error" in message:
				await self.hubCallReject(message.get("callId"), message.get("error"))
			else:
				await self.hubCallResult(message.get("callId"), message.get("result"))
		ssn = self.sessionMap.get(sessionId)
		if not ssn:
			return
		if "error" in message:
			await ssn.clientCallError(message.get("callId"), message.get("error"))
		else:
			await ssn.clientCallResult(message.get("callId"), message.get("result"))

	# -------------------------------------------------------------------------
	async def callHub(self,msg,vo,session=None):
		callId = str(self.nextCallId)
		self.nextCallId += 1
		pms=asyncio.Future()
		stub = {"callId": callId, "pms":pms}
		self.callMap[callId] = stub
		message={
			"msg": "CallHub",
			"callId": callId,
			"message": {"msg": msg, "vo": vo},
		}
		if self.devKey:
			message["devKey"] = self.devKey
		if session:
			message["session"] = session.sessionId
		message = json.dumps(message)
		await self.websocket.send(message)
		return await pms

	# -------------------------------------------------------------------------
	async def hubCallResult(self, callId, result):
		stub = self.callMap.get(callId, None)
		if not stub:
			return
		self.callMap.pop(callId, None)
		stub["pms"].set_result(result)

	# -------------------------------------------------------------------------
	async def hubCallReject(self,callId,err):
		stub=self.callMap.get(callId,None)
		if not stub:
			return
		self.callMap.pop(callId, None)
		stub["pms"].set_exception(err)

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
		if res and res.get("code")==200:
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
			return "data:application/octet-stream;base64,"+res.get('data')
		return res.get('data')

	# -------------------------------------------------------------------------
	async def normURL(self,url):
		if url.startswith("hub://"):
			fileName=url.split("hub://")[1]
			return self.loadHubFile(fileName,"dataurl")
		return url

	# -------------------------------------------------------------------------
	async def callHubAI(self,opts,messages,models):
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
		models=models or {}
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

	# -------------------------------------------------------------------------
	async def startDebug(self):
		self.debugStepRun=False
		async def shutdown(server):
			server.close()
			await server.wait_closed()
			print("Debug Server closed.")

		async def handler(websocket):
			print("Debug client connected")
			"""
			curWebSocket = self.wsDebug
			if curWebSocket:
				print("New client connected, close old connection")
				self.wsDebug=None
				self.debugConnected=False
				await curWebSocket.close()
			if self.debugStepTask:
				self.debugStepTask.set_result(True)
				self.debugStepTask=None
			self.wsDebug=websocket
			"""
			self.debugSockets.append(websocket)
			self.debugConnected=True
			try:
				async for message in websocket: # client should not send message to here?
					print(f"Debug port received: {message}")
					message = json.loads(message)
					cmd=message['cmd']
					if cmd=="StepRunOn":
						self.debugStepRun=True
						await self.sendDebugLog({"type":"StepRunOn"})
					elif cmd=="StepRunOff":
						self.debugStepRun=False
						await self.sendDebugLog({"type":"StepRunOff"})
					elif cmd=="RunStep":
						if self.debugStepTask:
							self.debugStepTask.set_result(True)
							self.debugStepTask = None
					elif cmd=="SlowMo":
						self.slowMo=message.get("enable",False)
				# await websocket.send(f"Echo: {message}")
				print("Websocket for end")
				try:
					self.debugSockets.remove(websocket)
					if len(self.debugSockets) == 0:
						self.debugConnected = False
				except ValueError:
					print("Could not find websocket on close")
			except Exception as e:
				try:
					self.debugSockets.remove(websocket)
					if len(self.debugSockets) == 0:
						self.debugConnected = False
				except ValueError:
					print("Could not find websocket on close")

		self.debugPort=self.nodeJSON.get("debugPort",5001)
		while True:
			try:
				server = await websockets.serve(handler, "localhost",self.debugPort, max_size=None)
				print(f"Debug server started at port: {self.debugPort}")
				break
			except OSError as e:
				self.debugPort+=1
		self.debugServer = server
		loop = asyncio.get_running_loop()
		loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown(server)))

		print("Debug webSocket server started")
		await server.wait_closed()

	async def sendDebugLog(self,log):
		try:
			"""
			if not self.wsDebug:
				return False
			"""
			logType=log.get("type")
			try:
				log=json.dumps(log)
			except Exception as e:
				return False

			for ws in self.debugSockets:
				try:
					await ws.send(log)
				except Exception as e:
					print("Error sending debug log",e)
			if logType=="StartSeg" and self.debugStepRun:
				for ws in self.debugSockets:
					try:
						await ws.send(json.dumps({"type":"StepPaused"}))
					except Exception as e:
						print("Error sending debug log",e)
				loop = asyncio.get_event_loop()
				self.debugStepTask=loop.create_future()
				await self.debugStepTask
			return True
		except Exception as e:
			print("SendDebugLog error",e)
			return False
