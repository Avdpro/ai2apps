from enum import Enum

class SnsUserType(Enum):
	SNSUSER= "SnsUser"	# 普通社交用户
	COPILOT = "Copilot"  # 个人助理
	AGENTBOT = "AgentBot"  # 代理机器人
	AGENTKOL = "AgentKOL"  # 代理大V
	AGENTCS = "AgentCS"  # 代理客服

	def __str__(self):
		return self.name


class SnsUser:
	def __init__(self):
		self.snsType=SnsUserType.SNSUSER
		self.snsChannel="wechat"
		self.userName=""
		self.userId=""
		self.description=""
		self.gender=0
		self.groups=[]
		self.contacts=[]

