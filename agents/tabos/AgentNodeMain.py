import os
import sys
import asyncio
from AgentNode import AgentNode

pathLib = os.path

getArrayItem = lambda arr, index: arr[index] if 0 <= index < len(arr) else None

# Get current path:
current_path = pathLib.dirname(pathLib.realpath(__file__))
print("Run path:", current_path)

# argv[1]: agentPath, argv[2]: host address, argv[3]: host name
agentPath=getArrayItem(sys.argv,1)
host=getArrayItem(sys.argv,2)
name=getArrayItem(sys.argv,3)
agentNode = AgentNode(agentPath, host , name)

# Set up an async looper for async calls:
loop = asyncio.get_event_loop()

loop.run_until_complete(agentNode.start())
