"""Roda o controlador, o rastreador, a API e o servidor web reais no CPython, com hardware simulado.

    uv run --with pillow python tools/simulator.py   ->  http://localhost:8765
"""
import asyncio
import builtins
import io
import math
import os
import sys
import tempfile
import time
import types

sys.dont_write_bytecode = True
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)

# ---- Adaptações do MicroPython ----
_t0 = time.monotonic()
time.ticks_ms = lambda: int((time.monotonic() - _t0) * 1000)
time.ticks_diff = lambda a, b: a - b
time.ticks_add = lambda a, b: a + b
time.sleep_us = lambda us: None
asyncio.sleep_ms = lambda ms: asyncio.sleep(ms / 1000)
asyncio.wait_for_ms = lambda aw, ms: asyncio.wait_for(aw, ms / 1000)
asyncio.ThreadSafeFlag = asyncio.Event
import gc
gc.mem_free = lambda: 7_900_000
for name in ("ptr8", "ptr16", "ptr32"):
    setattr(builtins, name, object)

mp = types.ModuleType("micropython")
mp.const = lambda x: x
mp.viper = lambda f: f
sys.modules["micropython"] = mp


class Pin:
    IN, OUT, PULL_UP, IRQ_FALLING = 0, 1, 2, 4

    def __init__(self, *a, **k):
        self._v = 1

    def value(self, v=None):
        return self._v if v is None else None

    def irq(self, *a, **k):
        pass


class PWM:
    def __init__(self, *a, **k):
        pass

    def duty_u16(self, *a):
        pass

    def duty_ns(self, *a):
        pass

    def freq(self, *a):
        pass


machine = types.ModuleType("machine")
machine.Pin, machine.PWM = Pin, PWM
machine.time_pulse_us = lambda *a: -1
machine.SoftI2C = object
sys.modules["machine"] = machine
network = types.ModuleType("network")
sys.modules["network"] = network

from PIL import Image, ImageDraw  # noqa: E402

from app import api  # noqa: E402
from app.controller import App  # noqa: E402
from app.hardware import Buzzer, RgbLed, Servo  # noqa: E402
from app.settings import Settings  # noqa: E402
from app.vision import Blob  # noqa: E402

W, H = 320, 240
OBJECTS = [((230, 50, 50), 50, 40), ((40, 120, 230), 40, 40), ((240, 200, 40), 60, 34), ((40, 190, 90), 36, 50)]


def scene(t):
    period = 4.5
    out = []
    for i, (rgb, w, h) in enumerate(OBJECTS):
        phase = (t / period + i / len(OBJECTS)) % 1.0
        x = -60 + phase * (W + 120)
        y = 95 + 25 * math.sin(i * 1.7)
        out.append((rgb, x, y, w, h))
    return out


class FakeCamera:
    sensor, width, height = "OV5640", W, H
    flip = (True, False)
    xclk_mhz = 20

    def set_xclk(self, mhz):
        self.xclk_mhz = mhz

    def __init__(self):
        self.frame = b""
        self.fps = 0.0
        self.fresh = asyncio.Event()

    def jpeg(self):
        return self.frame

    async def next_frame(self):
        await self.fresh.wait()

    async def run(self):
        while True:
            t = time.monotonic()
            img = Image.new("RGB", (W, H), (38, 42, 48))
            d = ImageDraw.Draw(img)
            d.rectangle((0, 80, W, 170), fill=(58, 62, 66))
            for x in range(-40, W, 40):
                xx = x + (t * 60) % 40
                d.line((xx, 80, xx, 170), fill=(70, 74, 78), width=2)
            for rgb, x, y, w, h in scene(t):
                d.rounded_rectangle((x, y, x + w, y + h), 6, fill=rgb)
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=80)
            self.frame = buf.getvalue()
            self.fps = 0.9 * self.fps + 0.1 * 10
            self.fresh.set()
            self.fresh.clear()
            await asyncio.sleep(0.1)


class FakeVision:
    sensitivity, min_area, coverage = 28, 30, 0.0

    def recalibrate(self):
        pass

    def process(self, frame):
        blobs = []
        cover = 0
        for rgb, x, y, w, h in scene(time.monotonic()):
            x0, x1 = max(0, x), min(W - 1, x + w)
            if x1 - x0 < 8:
                continue
            g = [int(v / 4) for v in (x0, y, x1, y + h)]
            area = (g[2] - g[0] + 1) * (g[3] - g[1] + 1)
            cover += area
            blobs.append(Blob(g[0], g[1], g[2], g[3], area, (g[0] + g[2]) / 2, (g[1] + g[3]) / 2, rgb))
        self.coverage = cover / 4800
        return blobs


class FakeSonar:
    min_height = 1.2
    baseline = 18.0

    @property
    def distance(self):
        for _, x, _, w, _ in scene(time.monotonic()):
            if x < W / 2 < x + w:
                return 18.0 - w / 12
        return 18.0 + 0.1 * math.sin(time.monotonic() * 7)

    @property
    def height(self):
        return max(0.0, self.baseline - self.distance)

    @property
    def present(self):
        return self.height >= self.min_height

    def recent_peak(self, window_ms=1500):
        return self.height or 3.5

    def recalibrate(self):
        pass


async def main():
    settings = Settings(os.path.join(tempfile.gettempdir(), "esteira_sim_settings.json"))
    camera = FakeCamera()
    app = App(settings, rgb=RgbLed(1, 2, 3), buzzer=Buzzer(4),
              servo=Servo(5), camera=camera, vision=FakeVision(), sonar=FakeSonar(),
              network={"mode": "sta", "ssid": "Simulador", "ip": "127.0.0.1", "host": "esteira",
                       "wlan": types.SimpleNamespace(status=lambda key: -58)})
    server = api.build(app, 3)
    server._static = PROJECT + "/www"
    await server.start(int(os.environ.get("PORT", "8765")))
    for job in (camera.run(), app.run_vision(), app.run_indicators()):
        asyncio.create_task(job)
    app.log("Simulador pronto")
    print("Simulador em http://localhost:%s" % os.environ.get("PORT", "8765"))
    await asyncio.Event().wait()


asyncio.run(main())
