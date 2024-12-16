import asyncio
import aiofiles
from io import BytesIO
import json
import os
import uuid
import time
import base64
import queue
from sns.SnsChannle import createChannel
from sns.wechat.WechatChannel import WechatMessage
pathLib = os.path

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
		return None
	except json.JSONDecodeError as e:
		print(f"JSON {file_path} parse error: {e}")
		return {}
	except Exception as e:
		print(f"发生错误: {e}")
	finally:
		if file and (not file.closed):  # 确保文件被关闭
			file.close()


# *****************************************************************************
async def writeJSON(file_path,data):
	if not isinstance(data, dict):
		raise ValueError("data 参数必须是字典类型")
	try:
		json_data = json.dumps(data, ensure_ascii=False, indent=4)
		async with aiofiles.open(file_path, 'w', encoding='utf-8') as file:
			await file.write(json_data)
		print(f"字典成功异步写入到 {file_path}")
	except Exception as e:
		return


# *****************************************************************************
# *****************************************************************************
class AgentBot:
	def __init__(self,path,botFarm):
		self.path= path
		self.botFarm = botFarm
		self.name= pathLib.basename(path)
		self.id=self.name
		self.snsChannels={}
		self.chatChannel=None
		self.config=None
		self.agentNode=botFarm.agentNode
		self.sessionId=str(uuid.uuid4())
		self.session=None
		self.chatAgent=None
		self.postAgent=None
		self.askPmsMap={}
		self.chatTasks={}
		self.handlingMsg=None
		self.freeSessions=[]
		self.lastConfigTime=0

	async def startUp(self):
		cfg=self.config=readJSON(pathLib.join(self.path,"config.json"))
		self.lastConfigTime=0
		if cfg is None:
			return
		self.name=cfg.get("name") or self.name
		self.id=cfg.get("id") or self.id

		session=self.session = await self.agentNode.createSession(self.sessionId, {"snsBot": self,"allowOffline":True})
		chatAgent = cfg.get("chatEntry")
		if chatAgent:
			chatAgent= self.chatAgent = await self.session.createAgent(chatAgent)
			seg = chatAgent.get("segs").get("OnStart")
			if seg:
				await session.runSeg(chatAgent, {"seg": seg, "input": self})

		channels=cfg.get("channels") or []
		for chnName in channels:
			print(f"Creating channel {chnName} for Bot: {self.name}")
			chn=await createChannel(chnName,self)
			self.snsChannels[chnName]=chn
			print(f"Channel {chnName} for Bot: {self.name} started.")
		chnName = cfg.get("chatChannel")
		if chnName:
			self.chatChannel=self.snsChannels.get(chnName)
		if self.chatChannel:
			newMessageTime=cfg.get('readMessageTime',0)
			while self.chatChannel.alive is True:
				if self.chatChannel.connected:
					message=self.chatChannel.readMessage()
					if message and chatAgent:
						msgType=message.get("type")
						if msgType=="login":
							seg = chatAgent.get("segs").get("OnLogin")
							if seg:
								await session.runSeg(chatAgent, {"seg": seg, "input": {}})
						elif msgType=="message":
							cmsg = message.get("message")
							fromId=cmsg.from_user_id
							if cmsg.create_time>newMessageTime:
								askPms=self.askPmsMap.get(fromId,None)
								if askPms:
									self.askPmsMap.pop(fromId,None)
									askPms.set_result(cmsg.content)
								else:
									seg = chatAgent.get("segs").get("OnMessage")
									if seg:
										self.handlingMsg = cmsg
										session.globalContext["botHandlingMsg"] = cmsg
										result=None
										try:
											result=await session.runSeg(chatAgent, {"seg": seg, "input": {"message": cmsg}})
										except Exception as e:
											print(f"Error while handling message: {e} at {getErrorLocation(e)}")
											res=None
										session.globalContext["botHandlingMsg"] = None
										self.handlingMsg = None
										if isinstance(result,dict):
											agent=result.get("agent")
											if isinstance(agent,str):
												await self.initChatTask(cmsg.from_user_id,agent,result.get("input") or result.get("prompt"))
								cfg['readMessageTime']=newMessageTime=cmsg.create_time
								if not self.lastConfigTime:
									self.lastConfigTime=time.time()
				#auto save config if changed, make a 1s delay to avoid too many saves:
				if self.lastConfigTime>0 and time.time()-self.lastConfigTime>1:
					await self.saveConfig()
					self.lastConfigTime=0
				# take a good nap:
				await asyncio.sleep(0.1)


	async def saveConfig(self):
		path=pathLib.join(self.path,"config.json")
		await writeJSON(path,self.config)

	async def allocSession(self):
		freeList=self.freeSessions
		if len(freeList)>0:
			session=freeList.pop(0)
		else:
			sessionId = str(uuid.uuid4())
			session=await self.agentNode.createSession(sessionId, {"snsBot": self,"allowOffline":True})
			session.globalContext["bot"]=self
		return session

	async def freeSession(self,sn):
		# TODO: Maybe clear session
		self.freeSessions.append(sn)

	# Init a micro-chat-session with user fromId
	async def initChatTask(self,userId,agentPath,prompt):
		async def taskProc(path,preTask):
			if preTask:
				await preTask
			subSession=await self.allocSession()
			subSession.snsChatUserId=userId
			try:
				await subSession.execAgent(path,prompt)
			except Exception as e:
				print(f"Error while chat task: {e} at {getErrorLocation(e)}")
			finally:
				await self.freeSession(subSession)
		if agentPath[:1]!="/":
			agentPath=pathLib.join(self.chatAgent.get("baseDir"),agentPath)
			agentPath=pathLib.normpath(agentPath)
		elif agentPath[:2]=="/@":
			agentPath=pathLib.join(self.agentNode.hubPath,agentPath)
			agentPath = pathLib.normpath(agentPath)
		curTask=self.chatTasks.get(userId,None)
		self.chatTasks[userId]=asyncio.create_task(taskProc(agentPath,curTask))

	# 发送Agent产生的对话文本/图片等消息，主要是与用户聊天的
	async def agentSendUserChat(self,msg,userId=None,opts=None):
		opts=opts or {}
		chatChannel = self.chatChannel
		if not chatChannel:
			return
		if userId is None:
			handlingMsg=self.handlingMsg
			if not handlingMsg:
				raise Exception("Missing handling channel message")
			userId=handlingMsg.from_user_id
		chatChannel.putMessages.put({"type":"message","content":msg.get("text"),"userName":userId})
		image=opts.get("image","")
		if image:
			if image[:6]=="hub://":
				imageData=await self.agentNode.loadHubImage(image,"data")
			else:
				imageData= base64.b64decode(image.split(',')[1])
			memFile=BytesIO(imageData)
			chatChannel.putMessages.put({"type":"image","file":memFile,"userName":userId})

	# 发送Agent产生的询问用户消息
	async def agentAskUserChat(self,msg,userId=None):
		chatChannel = self.chatChannel
		if userId is None:
			handlingMsg=self.handlingMsg
			if not handlingMsg:
				raise Exception("Missing handling channel message")
			userId=handlingMsg.from_user_id
		askPms=self.askPmsMap.get(userId)
		if askPms:
			raise Exception("Already in an ask")
		askPms=asyncio.Future()
		self.askPmsMap[userId]=askPms
		# chatChannel.putMessages.put({"type":"message","content":msg.get("prompt"),"userName":userId})
		# Apply time out of 120s
		try:
			async with asyncio.timeout(2 * 60):
				result = await askPms
		except asyncio.TimeoutError:
			await self.agentSendUserChat({"text": "Timeout, task aborted."}, userId)
			self.askPmsMap[userId] = None
			raise asyncio.TimeoutError
		return result

	async def agentAskUserRaw(self,msg,userId=None):
		chatChannel = self.chatChannel
		if userId is None:
			handlingMsg=self.handlingMsg
			if not handlingMsg:
				raise Exception("Missing handling channel message")
			userId=handlingMsg.from_user_id
		askType=msg.get("type")
		#Button choices:
		if askType=="confirm":
			chatChannel.putMessages.put({"type": "message", "content": msg.get("prompt"), "userName": userId})
			button1=msg.get("button1")
			button2=msg.get("button2")
			button3=msg.get("button3")
			text="Please choose:"
			if button1:
				text+=f"\n[1: {button1}]"
			if button2:
				text+=f"\n[2: {button2}]"
			if button3:
				text+=f"\n[3: {button3}]"
			text+=f"\nPlease input the index number of your choice."
			chatChannel.putMessages.put({"type": "message", "content": text, "userName": userId})
			# Create task to wait
			askPms=self.askPmsMap.get(userId)
			if askPms:
				raise Exception("Already in an ask")
			retry=0
			while True:
				askPms=asyncio.Future()
				self.askPmsMap[userId]=askPms
				#Apply time out of 120s
				try:
					async with asyncio.timeout(2*60):
						result=await askPms
				except asyncio.TimeoutError:
					await self.agentSendUserChat({"text":"Timeout, task aborted."},userId)
					self.askPmsMap[userId] = None
					raise asyncio.TimeoutError
				try:
					idx = int(result)
				except ValueError:
					idx = None
				if idx and idx>0:
					result= msg.get(f"button{idx}")
					if result is not None:
						if idx==1:
							return result,1
						if idx==2:
							return result,0
						if idx==3:
							return result,2
				retry+=1
				if retry>3:
					raise Exception("User input error, abort chat.")
				#input error:
				chatChannel.putMessages.put({"type": "message", "content": "Choice not found, please input index number of your choice", "userName": userId})
		#Menu choices:
		elif askType=="menu":
			chatChannel.putMessages.put({"type": "message", "content": msg.get("prompt"), "userName": userId})
			items=msg.get("items")
			text="Please choose from:"
			idx=1
			for item in items:
				text+=f"\n[{idx}: {item.get('text')}]"
				idx+=1
			if msg.get("multiSelect"):
				text+=f"\nPlease input the index numbers of your choice(s), separate with coma(',')."
			else:
				text+=f"\nPlease input the index number of your choice."
			chatChannel.putMessages.put({"type": "message", "content": text, "userName": userId})

			# Create task to wait
			askPms=self.askPmsMap.get(userId)
			if askPms:
				raise Exception("Already in an ask")
			retry=0
			while True:
				askPms=asyncio.Future()
				self.askPmsMap[userId]=askPms
				#Apply time out of 120s
				try:
					async with asyncio.timeout(2*60):
						result=await askPms
				except asyncio.TimeoutError:
					await self.agentSendUserChat({"text":"Timeout, task aborted."},userId)
					self.askPmsMap[userId] = None
					raise asyncio.TimeoutError
				if not msg.get("multiSelect"):
					try:
						idx = int(result)
					except ValueError:
						# TODO: Add support for chat input:
						idx = None
					if idx and 0 < idx <= len(items):
						result= items[idx-1]
						if result:
							return result.get("text"),result
					retry+=1
					if retry>3:
						raise Exception("User input error, abort chat.")
					#input error:
					chatChannel.putMessages.put({"type": "message", "content": "Choice not found, please input index number of your choice", "userName": userId})
				else:
					try:
						numbers = list(map(int, result.split(",")))
						for i in range(0,len(numbers)):
							numbers[i]=items(numbers[i])
						return numbers, numbers
					except Exception as e:
						# TODO: Add support for chat input:
						retry += 1
						if retry > 3:
							raise Exception("User input error, abort chat.")
					chatChannel.putMessages.put({"type": "message", "content": "Choice not found, please input index number of your choice, separate with coma(',')", "userName": userId})

