import asyncio
import json
import websockets

class RemoteSession:
    def __init__(self, local_session, session_id):
        self.session = local_session
        self.agentNode = local_session.agentNode
        self.session_id = session_id
        self.ws = None
        self.is_connected = False
        self.exec_callback = None
        self.exec_error_callback = None

    @staticmethod
    async def exec(session, node_name, agent, input_data, options=None):
        if options is None:
            options = {}

        res = await tabNT.make_call("StartAgentNode", {
            "name": node_name,
            "path": options.get("nodeEntry"),
            "options": options
        })
        if not res or res["code"] != 200:
            raise Exception(f"Start AgentNode error: {res.get('info', 'Unknown error')}")

        res = await tabNT.make_call("AhCreateSession", {"node": node_name})
        if not res or res["code"] != 200:
            raise Exception(f"Create Session error: {res.get('info', 'Unknown error')}")

        session_id = res["sessionId"]
        remote_session = RemoteSession(session, session_id)
        await remote_session.start()
        return await remote_session.exec_agent(agent, input_data)

    async def start(self):
        async def on_open():
            await self.ws.send(json.dumps({"msg": "CONNECT", "selector": self.session_id}))
            print("Remote session WS connected.")

        async def on_message(message):
            msg_vo = json.loads(message)
            msg_code = msg_vo.get("msg")
            print(f"Message from remote session: {msg_vo}")

            if not self.is_connected and msg_code == "CONNECTED":
                self.is_connected = True
                if self.exec_callback:
                    self.exec_callback()
                    self.exec_callback = None
                    self.exec_error_callback = None
                print("Remote session ready.")
            else:
                handler = getattr(self, f"WSMSG_{msg_code}", None)
                if handler:
                    await handler(msg_vo)

        async def on_close():
            if self.is_connected:
                self.is_connected = False
                if self.exec_error_callback:
                    self.exec_error_callback("Session end.")
            else:
                if self.exec_error_callback:
                    self.exec_error_callback("Session start failed.")
            self.ws = None
            self.session_id = None

        try:
            async with websockets.connect(f"ws://{document.location.host}") as ws:
                self.ws = ws
                await asyncio.gather(on_open(), self.wait_ready())
        except Exception as e:
            print("RemoteSession start failed:", e)
            raise

    async def wait_ready(self):
        while not self.is_connected:
            await asyncio.sleep(0.1)

    async def exec_agent(self, agent, prompt):
        if not self.ws:
            raise Exception("RemoteSession missing websocket to execAgent")

        self.exec_callback = asyncio.Future()
        self.exec_error_callback = asyncio.Future()

        await self.ws.send(json.dumps({
            "msg": "ExecAgent",
            "sessionId": self.session_id,
            "agent": agent,
            "prompt": prompt
        }))

        try:
            result = await self.exec_callback
            print("RemoteSession execute result: ", result)
            return result
        except Exception as e:
            print("Execution error:", e)
            raise e

    async def WSMSG_Message(self, msg):
        msg_code = msg["message"]["msg"]
        msg_vo = msg["message"]["vo"]
        session = self.session

        if msg_code == "ChatBlock":
            session.add_chat_block(msg_vo)
        elif msg_code == "SetWaitBlockText":
            await session.set_wait_block_text(msg_vo.get("block") or msg_vo.get("blockId"), msg_vo["text"])
        elif msg_code == "RemoveWaitBlock":
            await session.remove_wait_block(msg_vo["block"])
        elif msg_code == "DebugLog":
            await session.on_remote_debug_log(msg_vo)
        else:
            handler = getattr(session, f"WSCall_{msg_code}", None) or getattr(self, f"WSCall_{msg_code}", None)
            if not handler:
                raise Exception(f"No call-handler for msg: {msg_code}")
            await handler(msg_vo)

    async def WSMSG_ExecAgentEnd(self, msg):
        result = msg.get("result")
        error = msg.get("error")

        await self.ws.close()

        if error:
            if self.exec_error_callback:
                self.exec_error_callback.set_result(error)
                self.exec_error_callback = None
                self.exec_callback = None
        else:
            if self.exec_callback:
                self.exec_callback.set_result(result)
                self.exec_callback = None
                self.exec_error_callback = None