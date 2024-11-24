import json
import asyncio
import websockets
import os
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
		self.path = path
		self.hubPath = hubPath
		self.name = name or None
		self.host = host
		self.connected = False
		self.websocket = None
		self.agent = None
		self.sessionMap = {}
		self.nodeJSON = None
		self.hubJSON=hubConfig
		self.callMap={}
		self.nextCallId=0


	# -------------------------------------------------------------------------
	# Create a websocket connect to host
	async def start(self):
		# Read config json:
		jsonPath = pathLib.join(self.hubPath,self.path, 'agent.json')
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

		self.websocket = await websockets.connect(self.host)
		await self.onOpen()
		try:
			while True:
				message = await self.websocket.recv()
				await self.onMessage(message)
		except websockets.ConnectionClosed:
			await self.onClose()
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

		print(f"Got websocket message: {message}")

		# check if connected, if not, check if message is "CONNECTED", then call onConnected
		if not self.connected:
			msgCode = message.get("msg", None)
			if msgCode == 'CONNECTED':
				await self.onConnect()
		else:
			msg = message.get("msg", None)
			if msg == 'CreateSession':
				await self.createSession(message.get("sessionId"))
			elif msg == 'ExecAgent':
				sessionId=message.get("sessionId")

				async def callback(task):
					try:
						result = task.result()  # 获取任务的返回值
						print(f"Task result: {result}")
						await self.websocket.send(json.dumps({"msg": "EndExecAgent", "session":sessionId, "result": result}))
					except Exception as e:
						print(f"Task raised an exception: {e}")
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
	async def createSession(self, sessionId):
		if not self.connected:
			return False
		ssn = AISession(self.path, self, sessionId)
		self.sessionMap[sessionId] = ssn
		await self.websocket.send(json.dumps({"msg": "SessionReady", "session": sessionId}))

	# -------------------------------------------------------------------------
	async def execAgent(self, sessionId, path, prompt):
		ssn = self.sessionMap.get(sessionId, None)
		if not ssn:
			return False
		result = await ssn.execAgent(path, prompt)
		self.sessionMap.pop(sessionId, None)
		await self.websocket.send(json.dumps({"msg": "EndSession", "session": sessionId}))
		return result

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
	async def callHub(self,msg,vo,session):
		callId = str(self.nextCallId)
		self.nextCallId += 1
		pms=asyncio.Future()
		stub = {"callId": callId, "pms":pms}
		self.callMap[callId] = stub
		message={
			"msg": "CallHub",
			"callId": callId,
			"session": session.sessionId,
			"message": {"msg": msg, "vo": vo}
		}
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
