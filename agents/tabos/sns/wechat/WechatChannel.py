import io
import json
import os
import asyncio
import queue
import threading
import time
import requests
from enum import Enum
from pyee import EventEmitter
from sns.SnsChannle import SnsChannel,registerChannel
from sns.wechat.WechatMessage import WechatMessage
from common.log import logger
from config import conf, get_appdata_dir
import itchat
from itchat.content import *
pathLib = os.path


# Make QRCode:
def qrCallback(uuid, status, qrcode):
	# logger.debug("qrCallback: {} {}".format(uuid,status))
	if status == "0":
		try:
			from PIL import Image
			img = Image.open(io.BytesIO(qrcode))
			_thread = threading.Thread(target=img.show, args=("QRCode",))
			_thread.setDaemon(True)
			_thread.start()
		except Exception as e:
			pass

		import qrcode
		url = f"https://login.weixin.qq.com/l/{uuid}"
		qr = qrcode.QRCode(border=1)
		qr.make(fit=True)
		try:
			qr.print_ascii(invert=True)
		except UnicodeEncodeError:
			print("ASCII QR code printing failed due to encoding issues.")

class WechatChannel(SnsChannel):
	def __init__(self,bot):
		super().__init__(bot)
		self.itchat=None
		self.alive=True
		self.connected=False
		self.loginTime=0
		self.loginInfoDumpTime=0

	def startup(self):
		cfg=self.config
		self.itchat = itchat.load_sync_itchat()
		self.itchat.receivingRetryCount=600
		hotReload = cfg.get("hot_reload", False)
		status_path = cfg.get("status_path", "itchat.pkl")
		status_path = pathLib.join(self.bot.path,status_path)

		# ItChat 1-on-1 message handler:
		@self.itchat.msg_register([TEXT, VOICE, PICTURE, NOTE, ATTACHMENT, SHARING])
		def handler_single_msg(msg):
			try:
				cmsg = WechatMessage(msg, self.agentNode,False)
			except NotImplementedError as e:
				logger.debug("[WX]single message {} skipped: {}".format(msg["MsgId"], e))
				return None
			self.handleSingle(cmsg)
			return None

		# ItChat group message handler:
		@self.itchat.msg_register([TEXT, VOICE, PICTURE, NOTE, ATTACHMENT, SHARING], isGroupChat=True)
		def handler_group_msg(msg):
			try:
				cmsg = WechatMessage(msg, self.agentNode,True)
			except NotImplementedError as e:
				logger.debug("[WX]group message {} skipped: {}".format(msg["MsgId"], e))
				return None
			self.handleGroup(cmsg)
			return None

		self.itchat.auto_login(
			enableCmdQR=2,
			hotReload=hotReload,
			statusStorageDir=status_path,
			qrCallback=qrCallback,
			exitCallback=self.exitCallback,
			loginCallback=self.loginCallback
		)
		self.user_id = self.itchat.storageClass.userName
		self.name = self.itchat.storageClass.nickName
		logger.info("Wechat login success, user_id: {}, nickname: {}".format(self.user_id, self.name))
		# start message listener
		self.itchat.run()

	def loginCallback(self):
		self.connected=True
		self.loginInfoDumpTime=self.loginTime=time.time()
		self.getMessages.put({"type":"login"})
		self.runSend()
		return self.itchat #TODO: Code this:

	def exitCallback(self):
		if self.connected:
			self.getMessages.put({"type": "logoff"})
			self.connected=False
			self.alive=False

	def handleSingle(self, cmsg):
		self.getMessages.put({"type":"message","message":cmsg})
		return self.itchat #TODO: Code this:

	def handleGroup(self, cmsg):
		self.getMessages.put({"type":"message","message":cmsg})
		return self.itchat #TODO: Code this:

	def runSend(self):
		itChat=self.itchat
		messages=self.putMessages

		def proc():
			while self.connected:
				try:
					message=messages.get()
					msgType=message.get("type")
					if msgType=="text" or msgType=="message":
						content=message.get("content")
						if isinstance(content,dict):
							content=json.dumps(content)
						else:
							content=str(content)
						itChat.send(content,toUserName=message.get("userName"))
					elif msgType == "image":
						itChat.send_image(file_=message.get("file"),toUserName=message.get("userName"))
					elif msgType == "voice":
						continue # TODO: Code this
					elif msgType == "url":
						continue  # TODO: Code this
					elif msgType == "file":
						continue  # TODO: Code this
					# TODO: More actions like accept invite:
				finally:
					messages.task_done()

		sendThread = threading.Thread(target=proc,daemon=True)
		sendThread.start()

	def readMessage(self):
		messages=self.getMessages
		message=None
		if not messages.empty():
			try:
				# 非阻塞取消息
				message = messages.get_nowait()
				print(f"Consumed: {message}")
				# 标记任务完成
				messages.task_done()
			except queue.Empty:
				# 防止意外条件下队列变空
				print("Queue unexpectedly empty!")
		now=time.time()
		if now-self.loginInfoDumpTime>60:
			self.itchat.dump_login_status()
		return message

registerChannel("wx",WechatChannel)
registerChannel("wechat",WechatChannel)