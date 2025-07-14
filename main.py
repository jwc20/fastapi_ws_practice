import anyio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# origins = [
#     "http://localhost.tiangolo.com",
#     "https://localhost.tiangolo.com",
#     "http://localhost",
#     "http://localhost:8080",
# ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def main():
    return {"message": "Hello World"}

from broadcaster import Broadcast

broadcast = Broadcast("redis://localhost:6379")

app = FastAPI(on_startup=[broadcast.connect], on_shutdown=[broadcast.disconnect])


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        await broadcast.publish(channel="chat", message=message)

    async def broadcast_to_local_connections(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@app.get("/")
async def get():
    return FileResponse("templates/lobby.html")

@app.post("/create-room")
async def create_room():
    print("create-room")

@app.get("/rooms")
async def get_rooms():
    return ["1", "2"]


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)

    async def redis_listener():
        async with broadcast.subscribe(channel="chat") as subscriber:
            async for event in subscriber:
                await manager.broadcast_to_local_connections(event.message)

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(redis_listener)
        try:
            while True:
                data = await websocket.receive_text()
                await manager.send_personal_message(f"You wrote: {data}", websocket)
                await manager.broadcast(f"Client #{client_id} says {data}")

        except WebSocketDisconnect:
            manager.disconnect(websocket)
            await manager.broadcast(f"Client #{client_id} left the chat")
