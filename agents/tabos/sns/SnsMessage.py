import os
from enum import Enum
import asyncio
import aiofiles
from concurrent.futures import ThreadPoolExecutor

pathLib = os.path

"""
本类表示聊天消息，用于对itchat和wechaty的消息进行统一的封装。

填好必填项(群聊6个，非群聊8个)，即可接入ChatChannel，并支持插件，参考TerminalChannel

ChatMessage
msg_id: 消息id (必填)
create_time: 消息创建时间

ctype: 消息类型 : ContextType (必填)
content: 消息内容, 如果是声音/图片，这里是文件路径 (必填)

from_user_id: 发送者id (必填)
from_user_nickname: 发送者昵称
to_user_id: 接收者id (必填)
to_user_nickname: 接收者昵称

other_user_id: 对方的id，如果你是发送者，那这个就是接收者id，如果你是接收者，那这个就是发送者id，如果是群消息，那这一直是群id (必填)
other_user_nickname: 同上

is_group: 是否是群消息 (群聊必填)
is_at: 是否被at

- (群消息时，一般会存在实际发送者，是群内某个成员的id和昵称，下列项仅在群消息时存在)
actual_user_id: 实际发送者id (群聊必填)
actual_user_nickname：实际发送者昵称
self_display_name: 自身的展示名，设置群昵称时，该字段表示群昵称

_prepare_fn: 准备函数，用于准备消息的内容，比如下载图片等,
_prepared: 是否已经调用过准备函数
_rawmsg: 原始消息对象

"""

_file_threads = ThreadPoolExecutor()


class SnsChatMessage(object):
	msg_id = None
	create_time = None

	ctype = None
	content = None

	from_user_id = None
	from_user_nickname = None
	to_user_id = None
	to_user_nickname = None
	other_user_id = None
	other_user_nickname = None
	my_msg = False
	self_display_name = None

	is_group = False
	is_at = False
	actual_user_id = None
	actual_user_nickname = None
	at_list = None

	_prepare_fn = None
	_prepared = False
	_hubURL =None
	_rawmsg = None
	agentNode =None

	def __init__(self, _rawmsg, agentNode):
		self._rawmsg = _rawmsg
		self.agentNode=agentNode

	def prepare(self):
		if self._prepare_fn and not self._prepared:
			self._prepared = True
			self._prepare_fn()

	async def hubURL(self):
		def loadFile():
			self._prepared = True
			self._prepare_fn()

		if self._hubURL:
			return self._hubURL
		if self._prepare_fn and not self._prepared:
			fileName=pathLib.basename(self.content)
			loop = asyncio.get_running_loop()
			await loop.run_in_executor(_file_threads, loadFile)
			async with aiofiles.open(self.content, mode='rb') as file:
				content = await file.read()  # 异步读取文件内容
			hubFileName=await self.agentNode.saveHubFile(fileName,content)
			self._hubURL="hub://"+hubFileName
			return self._hubURL
		else:
			return None


	def __str__(self):
		return "ChatMessage: id={}, create_time={}, ctype={}, content={}, from_user_id={}, from_user_nickname={}, to_user_id={}, to_user_nickname={}, other_user_id={}, other_user_nickname={}, is_group={}, is_at={}, actual_user_id={}, actual_user_nickname={}, at_list={}".format(
			self.msg_id,
			self.create_time,
			self.ctype,
			self.content,
			self.from_user_id,
			self.from_user_nickname,
			self.to_user_id,
			self.to_user_nickname,
			self.other_user_id,
			self.other_user_nickname,
			self.is_group,
			self.is_at,
			self.actual_user_id,
			self.actual_user_nickname,
			self.at_list
		)

class SnsMessageType(Enum):
	TEXT = "text"  # 文本消息
	VOICE = "voice"  # 音频消息
	IMAGE = "image"  # 图片消息
	FILE = "file"  # 文件信息
	VIDEO = "video"  # 视频信息
	URL = "url"  # 分享信息

	#Wechat message:
	WX_ACCEPT_FRIEND = "wx_accept_friend" # 同意好友请求
	WX_JOIN_GROUP = "wx_join_group"  # 加入群聊
	WX_PATPAT = "wx_patpat"  # 拍了拍
	WX_EXIT_GROUP = "wx_exit_group" #退出

	def __str__(self):
		return self.name
