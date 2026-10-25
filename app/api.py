import asyncio
import json

from app.vision import GRID
from app.web import HttpError, Response, Server


def _event(kind, payload):
    return b"event: " + kind.encode() + b"\ndata: " + payload.encode() + b"\n\n"


class MjpegStream(Response):
    active = 0

    def __init__(self, app):
        super().__init__(content_type="multipart/x-mixed-replace; boundary=frame",
                         headers={"Cache-Control": "no-store"})
        self.app = app

    async def send(self, writer):
        app = self.app
        MjpegStream.active += 1
        app.clients += 1
        try:
            writer.write(self.head())
            while True:
                await app.camera.next_frame()
                frame = app.camera.jpeg()
                writer.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(frame))
                writer.write(frame)
                writer.write(b"\r\n")
                await writer.drain()
        finally:
            MjpegStream.active -= 1
            app.clients -= 1


class EventStream(Response):
    def __init__(self, app):
        super().__init__(content_type="text/event-stream", headers={"Cache-Control": "no-store"})
        self.app = app

    async def send(self, writer):
        app = self.app
        queue = app.subscribe()
        app.clients += 1
        try:
            writer.write(self.head() + b"retry: 2000\n\n")
            writer.write(_event("hello", json.dumps({"history": app.history})))
            while True:
                while queue:
                    kind, data = queue.pop(0)
                    writer.write(_event(kind, json.dumps(data)))
                writer.write(_event("state", app.snapshot()))
                await writer.drain()
                await asyncio.sleep_ms(200)
        finally:
            app.clients -= 1
            app.unsubscribe(queue)


def build(app, max_streams):
    server = Server("/www")

    def need_camera():
        if app.camera is None:
            raise HttpError(503, "câmera indisponível")

    @server.get("/stream")
    async def stream(req):
        need_camera()
        if MjpegStream.active >= max_streams:
            raise HttpError(503, "limite de streams atingido")
        return MjpegStream(app)

    @server.get("/snapshot.jpg")
    async def snapshot(req):
        need_camera()
        await app.camera.next_frame()
        return Response(app.camera.jpeg(), content_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @server.get("/events")
    async def events(req):
        return EventStream(app)

    @server.get("/api/state")
    async def state(req):
        return Response(app.snapshot(), content_type="application/json")

    @server.get("/api/settings")
    async def get_settings(req):
        cam = app.camera
        return {
            "settings": app.settings.as_dict(),
            "grid": GRID,
            "camera": {"sensor": cam.sensor, "width": cam.width, "height": cam.height} if cam else None,
            "network": {k: app.network[k] for k in ("mode", "ssid", "ip", "host")} if app.network else None,
        }

    @server.post("/api/settings")
    async def set_settings(req):
        return {"applied": app.apply_settings(req.json())}

    @server.post("/api/estop")
    async def estop(req):
        if req.json().get("active", True):
            app.emergency("web")
        elif not app.rearm():
            raise HttpError(409, "solte o botão de emergência antes de rearmar")
        return {"estop": app.estop}

    @server.post("/api/reset")
    async def reset(req):
        app.reset_counts()

    @server.post("/api/calibrate")
    async def calibrate(req):
        app.recalibrate()

    @server.post("/api/ai")
    async def ai(req):
        app.ai_update(req.json().get("detections", []))

    @server.post("/api/test")
    async def test(req):
        if app.estop:
            raise HttpError(409, "sistema em emergência")
        device = req.json().get("device")
        if device == "servo":
            asyncio.create_task(app.push())
        elif device == "buzzer":
            app.buzzer.play("ready", force=True)
        elif device == "count":
            app.count()
        else:
            raise HttpError(400, "dispositivo desconhecido")

    return server
