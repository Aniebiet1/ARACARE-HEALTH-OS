"""WebSocket fan-out. Payloads carry NO patient data -- clients refetch over REST.

A socket can sit in several rooms (AraPulse: `staff:<id>` for personal pushes and `fac:<facility_id>` for
channel traffic); the queue screens use the single "queue" room."""
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

    def add(self, ws: WebSocket, *rooms: str):
        """Put an already-accepted socket into more rooms."""
        for room in rooms:
            self.rooms[room].add(ws)

    def leave(self, room: str, ws: WebSocket):
        self.rooms[room].discard(ws)
        if not self.rooms.get(room, True):
            self.rooms.pop(room, None)          # per-person rooms would otherwise pile up

    def leave_all(self, ws: WebSocket):
        for room in [r for r, members in self.rooms.items() if ws in members]:
            self.leave(room, ws)

    async def _send(self, room: str, message: dict):
        for ws in list(self.rooms.get(room, ())):
            try:
                await ws.send_json(message)
            except Exception:
                self.leave_all(ws)

    def broadcast(self, room: str, message: dict):
        """Thread-safe: endpoints are sync (threadpool), sockets are async."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._send(room, message), self.loop)


hub = Hub()
