"""WebSocket fan-out. Payloads carry NO patient data -- clients refetch over REST."""
import asyncio
from collections import defaultdict

from fastapi import WebSocket


class Hub:
    def __init__(self):
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None

    async def join(self, room: str, ws: WebSocket):
        await ws.accept()
        self.rooms[room].add(ws)

    def leave(self, room: str, ws: WebSocket):
        self.rooms[room].discard(ws)

    async def _send(self, room: str, message: dict):
        for ws in list(self.rooms.get(room, ())):
            try:
                await ws.send_json(message)
            except Exception:
                self.rooms[room].discard(ws)

    def broadcast(self, room: str, message: dict):
        """Thread-safe: endpoints are sync (threadpool), sockets are async."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._send(room, message), self.loop)


hub = Hub()
