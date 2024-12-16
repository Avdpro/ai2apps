import asyncio
import queue

"""
社交媒体登录账号渠道抽象基类，使用异步方式
"""

class SnsChannel(object):
	channel_type = ""

	def __init__(self,bot):
		self.type= None
		self.name = None  # 登录的用户名
		self.user_id = None  # 登录的用户id
		self.bot=bot
		self.agentNode=bot.agentNode
		self.config=bot.config
		self.getMessages=queue.Queue(maxsize=20)
		self.putMessages=queue.Queue(maxsize=20)
		self.alive=False
		self.connected=False

	async def startup(self):
		"""
		init channel
		"""
		raise NotImplementedError

	async def handle_message(self, msg):
		"""
		process received msg
		:param msg: message object
		"""
		raise NotImplementedError

	# 统一的发送函数，每个Channel自行实现，根据reply的type字段发送不同类型的消息
	async def send(self, msg):
		"""
		send message to user
		:param msg: message content
		:param receiver: receiver channel account
		:return:
		"""
		raise NotImplementedError


_channelRegs={}

def registerChannel(name,cls):
	_channelRegs[name]=cls

async def createChannel(chType,bot):
	chType=chType.lower()
	cls=_channelRegs.get(chType)
	if cls:
		chn=cls(bot)
		task=asyncio.create_task(asyncio.to_thread(chn.startup))
		return chn
	return None
