import json
from typing import Any, Callable, Dict
import websockets


class WebSocketServer:
    def __init__(
        self,
        handler: Callable,
        host="localhost",
        port=8080,
    ):
        self.host = host
        self.port = port
        self.handler = handler
        self.server = None

    async def serve(self):
        """启动WebSocket服务器"""
        self.server = await websockets.serve(self.handler, self.host, self.port)
        print(f"WebSocket server started at ws://{self.host}:{self.port}")
        await self.server.wait_closed()


async def websocket_send(
    websocket: Any,
    header: Dict,
    data: Any,
):
    """发送数据"""
    await websocket.send(json.dumps(header))
    await websocket.send(data)
