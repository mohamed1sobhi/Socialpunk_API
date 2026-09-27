import asyncio
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect, status


HEARTBEAT_INTERVAL_SECONDS = 30
HEARTBEAT_TIMEOUT_SECONDS = 90


@dataclass(eq=False)
class ManagedConnection:
    user_id: UUID
    websocket: WebSocket
    last_pong: datetime = field(default_factory=lambda: datetime.now(UTC))
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    heartbeat_task: asyncio.Task[None] | None = None


class InMemoryConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[ManagedConnection]] = defaultdict(set)
        self._by_websocket: dict[WebSocket, ManagedConnection] = {}
        self._lock = asyncio.Lock()

    async def handle_connection(self, user_id: UUID, websocket: WebSocket) -> None:
        connection = await self._accept_and_register(user_id, websocket)
        connection.heartbeat_task = asyncio.create_task(self._heartbeat(connection))

        try:
            # The receive loop is the authoritative lifetime of the connection.
            await self._receive_loop(connection)
        except WebSocketDisconnect:
            pass
        except Exception:
            await self._close_connection(connection, status.WS_1011_INTERNAL_ERROR)
        finally:
            # Cleanup runs once per connection lifetime and is safe if repeated.
            await self.disconnect(user_id, websocket)

    async def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        """Remove a connection safely, even if it was already removed."""
        async with self._lock:
            connection = self._by_websocket.pop(websocket, None)
            if connection is None:
                return
            connections = self._connections.get(user_id)
            if connections is not None:
                connections.discard(connection)
                if not connections:
                    self._connections.pop(user_id, None)

        task = connection.heartbeat_task
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def send_to_user(self, user_id: UUID, payload: dict) -> bool:
        delivered = False
        async with self._lock:
            connections = tuple(self._connections.get(user_id, set()))

        for connection in connections:
            if await self._send(connection, payload):
                delivered = True
        return delivered

    async def send_personal_message(self, user_id: UUID, payload: dict) -> None:
        await self.send_to_user(user_id, payload)

    async def broadcast(self, payload: dict) -> None:
        async with self._lock:
            connections = tuple(
                connection
                for sockets in self._connections.values()
                for connection in sockets
            )

        for connection in connections:
            await self._send(connection, payload)

    async def _accept_and_register(self, user_id: UUID, websocket: WebSocket) -> ManagedConnection:
        await websocket.accept()
        connection = ManagedConnection(user_id=user_id, websocket=websocket)
        async with self._lock:
            self._connections[user_id].add(connection)
            self._by_websocket[websocket] = connection
        return connection

    async def _receive_loop(self, connection: ManagedConnection) -> None:
        while True:
            message = await connection.websocket.receive_json()
            await self._handle_message(connection, message)

    async def _handle_message(self, connection: ManagedConnection, message: object) -> None:
        message_type = message.get("type") if isinstance(message, dict) else None
        if message_type == "pong":
            connection.last_pong = datetime.now(UTC)
            return
        if message_type == "ack":
            return
        await self._send(
            connection,
            {
                "type": "error",
                "payload": {"message": "Unsupported message type"},
            },
        )

    async def _heartbeat(self, connection: ManagedConnection) -> None:
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                if datetime.now(UTC) - connection.last_pong >= timedelta(
                    seconds=HEARTBEAT_TIMEOUT_SECONDS,
                ):
                    # The server is the heartbeat authority; stale sockets are closed and removed here.
                    await self._close_and_disconnect(connection, status.WS_1001_GOING_AWAY)
                    return
                if not await self._send(connection, {"type": "ping"}):
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            await self._close_and_disconnect(connection, status.WS_1011_INTERNAL_ERROR)

    async def _send(self, connection: ManagedConnection, payload: dict) -> bool:
        try:
            async with connection.send_lock:
                await connection.websocket.send_json(payload)
        except Exception:
            await self._close_and_disconnect(connection, status.WS_1001_GOING_AWAY)
            return False
        return True

    async def _close_and_disconnect(self, connection: ManagedConnection, code: int) -> None:
        await self._close_connection(connection, code)
        await self.disconnect(connection.user_id, connection.websocket)

    async def _close_connection(self, connection: ManagedConnection, code: int) -> None:
        with suppress(Exception):
            await connection.websocket.close(code=code)


connection_manager = InMemoryConnectionManager()

__all__ = ["connection_manager"]
