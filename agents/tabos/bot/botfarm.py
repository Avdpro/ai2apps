import asyncio
import os
import json
from bot.bot import AgentBot

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
		return {}
	except json.JSONDecodeError as e:
		print(f"JSON {file_path} parse error: {e}")
		return {}
	except Exception as e:
		print(f"发生错误: {e}")
	finally:
		if file and (not file.closed):  # 确保文件被关闭
			file.close()


class BotFarm(object):
	def __init__(self,agentNode):
		config=readJSON(pathLib.join(agentNode.path,"config.json"))
		self.agentNode=agentNode
		self.config =config
		path=config.get("botPath")
		if path[:1]!="/":
			path=pathLib.join(agentNode.path,path)
			path=pathLib.normpath(path)
		self.path=path
		self.bots=None

	async def start(self):
		bots=self.bots=[]
		try:
			items=os.listdir(self.path)
			dirs=[name for name in os.listdir(self.path) if os.path.isdir(pathLib.join(self.path, name))]
			for dir in dirs:
				path=pathLib.join(self.path,dir)
				bot=AgentBot(path,self)
				bots.append(bot)
				asyncio.create_task(bot.startUp())
		except Exception as e:
			print(f"Start BotFarm error: {e}. At: {getErrorLocation(e)}")
