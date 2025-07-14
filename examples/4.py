"""
Broadcaster helps you develop realtime streaming functionality by providing a simple broadcast API onto a number of different backend services.

It currently supports Redis PUB/SUB, Redis Streams, Apache Kafka, and Postgres LISTEN/NOTIFY, plus a simple in-memory backend, that you can use for local development or during testing.
"""

import anyio  # what is this for?
from broadcaster import Broadcast
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute
from starlette.templating import Jinja2Templates


broadcast = Broadcast("redis://localhost:6379")
templates = Jinja2Templates("templates")


async def homepage(request):
    template = "index.html"
    context = {"request": request}
    return templates.TemplateResponse(template, context)


async def chatroom_ws(websocket):
    await websocket.accept()

    async with anyio.create_task_group() as task_group:  # what is task_group for?
        # run until first is complete
        async def run_chatroom_ws_receiver() -> None:
            await chatroom_ws_receiver(websocket=websocket)
            task_group.cancel_scope.cancel()  # what is this for

        task_group.start_soon(run_chatroom_ws_receiver)
        await chatroom_ws_sender(websocket)


async def chatroom_ws_receiver(websocket):
    async for message in websocket.iter_text():  # iter_text() what is this method?
        await broadcast.publish(channel="chatroom", message=message)


async def chatroom_ws_sender(websocket):
    async with broadcast.subscribe(channel="chatroom") as subscriber:
        async for event in subscriber:
            await websocket.send_text(event.message)


routes = [
    Route("/", homepage),
    WebSocketRoute("/", chatroom_ws, name="chatroom_ws"),
]

app = Starlette(
    routes=routes, on_startup=[broadcast.connect], on_shutdown=[broadcast.disconnect]
)
