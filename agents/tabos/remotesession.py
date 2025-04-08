import asyncio
import json
import websockets

class RemoteSession:
	def __init__(self, local_session, sessionId):
		self.session = local_session
		self.agentNode = local_session.agentNode
		self.sessionId = sessionId
		self.ws = None
		self.isAlive=False
		self.is_connected = False
		self.execPms = None
		self.startPms=None
		self.wsTask=None
		self.msgTask=None
		self.messages=[]
		self.upperAgent = None
		self.askUpwardSeg = None
		self.fromAgent = None

	@staticmethod
	async def exec(session, node_name, agent, input_data, options=None):
		if options:
			startNodeOpts={"checkUpdate":options.get("checkUpdate",True)}
			callAgentOpts = {"fromAgent": options.get("fromAgent",None), "askUpwardSeg":options.get("askUpwardSeg",None)}
		else:
			startNodeOpts = {"checkUpdate": True}
			callAgentOpts = {}

		res = await session.callHub("StartAgentNode",{
			"name": node_name,
			"path": options.get("nodeEntry"),
			"options": startNodeOpts
		})
		if not res or res["code"] != 200:
			raise Exception(f"Start AgentNode error: {res.get('info', 'Unknown error')}")

		res= await session.callHub("AhCreateSession",{"node": node_name,"language":session.language})
		if not res or res["code"] != 200:
			raise Exception(f"Create Session error: {res.get('info', 'Unknown error')}")

		sessionId = res["sessionId"]
		remote_session = RemoteSession(session, sessionId)
		await remote_session.connect()
		await remote_session.start()
		return await remote_session.exec_agent(agent, input_data, callAgentOpts)

	# -----------------------------------------------------------------------
	async def connect(self):
		session=self.session
		ws = await websockets.connect(session.agentNode.host,max_size=10 * 1024 * 1024)
		self.ws = ws
		self.isAlive = True

	# -----------------------------------------------------------------------
	async def start(self):
		async def on_open():
			await self.ws.send(json.dumps({"msg": "CONNECT", "selector": self.sessionId}))
			print("Remote session WS connected.")

		self.startPms=asyncio.Future()
		try:
			self.wsTask=asyncio.create_task(self.runWS())
			self.msgTask = asyncio.create_task(self.runMsg())
			await on_open()
			await self.startPms
			# await asyncio.gather(on_open(), self.startPms)
		except Exception as e:
			print("RemoteSession start failed:", e)
			raise

	# -----------------------------------------------------------------------
	async def runMsg(self):
		async def on_message(msg):
			msg_vo = json.loads(msg)
			msg_code = msg_vo.get("msg")
			log=f"Message from remote session: {msg_vo}"
			if len(log)>2048:
				log=log[:2048]
			print(log)
			if not self.is_connected and msg_code == "CONNECTED":
				self.is_connected = True
				self.execPms = None
				self.startPms.set_result(True)
				self.startPms=None
				print("Remote session ready.")
			else:
				handler = getattr(self, f"WSMSG_{msg_code}", None)
				if handler:
					await handler(msg_vo)

		while self.isAlive:
			if len(self.messages)>0:
				msg=self.messages.pop(0)
				await on_message(msg)
			await asyncio.sleep(0.1)

	# -----------------------------------------------------------------------
	async def runWS(self):
		async def on_close():
			if self.is_connected:
				self.is_connected = False
				self.isAlive=False
				if self.execPms:
					self.execPms.set_exception(Exception("Session end."))
			else:
				if self.execPms:
					self.execPms.set_exception(Exception("Session start failed."))
			self.ws = None
			self.sessionId = None

		try:
			while self.isAlive:
				message = await self.ws.recv()
				if message:
					self.messages.append(message)
				await asyncio.sleep(0.1)
		except websockets.ConnectionClosed as e:
			print(f"Connection lost{e}")
			if self.isAlive and self.is_connected:
				await on_close()
		finally:
			if self.ws:
				await self.ws.close()

	async def endExec(self,result):
		self.isAlive=False
		self.is_connected=False
		await self.ws.close()
		await asyncio.gather(self.wsTask,self.msgTask)
		self.wsTask=None
		self.msgTask=None
		return result

	async def exec_agent(self, agent, prompt, opts):
		opts=opts or {}
		if not self.ws:
			raise Exception("RemoteSession missing websocket to execAgent")
		self.upperAgent = self.fromAgent = opts.get("fromAgent",None)
		self.askUpwardSeg = opts.get("askUpwardSeg",None)

		self.execPms = asyncio.Future()

		await self.ws.send(json.dumps({
			"msg": "ExecAgent",
			"sessionId": self.sessionId,
			"agent": agent,
			"prompt": prompt or ""
		}))

		try:
			result = await self.execPms
			print("RemoteSession execute result: ", result)
			await self.endExec(result)
			return result
		except Exception as e:
			print("Execution error:", e)
			raise e

	async def WSMSG_Message(self, msg):
		msg_code = msg["message"]["msg"]
		msg_vo = msg["message"]["vo"]
		session = self.session
		if msg_code == "ChatBlock":
			opts={}
			if msg_vo.get("image"):
				opts["image"] =msg_vo.get("image")
			if msg_vo.get("audio"):
				opts["audio"] =msg_vo.get("audio")
			role=msg_vo.get("role","assistant")
			await session.addChatText(role, msg_vo.get("text",""),opts)
		else:
			await session.sendToClient(msg_code, msg_vo)

	async def WSMSG_Call(self, msg):
		callId = msg.get("callId")
		msg_code = msg["message"]["msg"]
		msg_vo = msg["message"]["vo"]
		session = self.session
		try:
			if msg_code=="AskChatInput":
				result=await session.askChatInput(msg_vo)
			elif msg_code=="AskUpward":
				fakeAgent = {"upperAgent": self.fromAgent, "askUpwardSeg": self.askUpwardSeg}
				result = await session.askUpward(fakeAgent, msg_vo.get("prompt",None))
			elif msg_code=="AddWaitBlock":
				result=await session.showWait(msg_vo.get("text"))
			else:
				result=await session.callClient(msg_code, msg_vo)
			res={"msg": "CallResult", "sessionId": self.sessionId, "callId": callId, "result": result}
			await self.ws.send(json.dumps(res))
			return
		except Exception as e:
			errMsg={"msg": "CallResult", "sessionId": self.sessionId, "callId": callId, "error": f"{e}"}
			await self.ws.send(json.dumps(errMsg))

	async def WSMSG_ExecAgentEnd(self, msg):
		result = msg.get("result")
		error = msg.get("error")

		if error:
			if self.execPms:
				self.execPms.set_exception(Exception(error))
				self.execPms = None
		else:
			if self.execPms:
				self.execPms.set_result(result)
				self.execPms = None
