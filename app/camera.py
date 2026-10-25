import asyncio
import time

import jpeg
from camera import Camera, FrameSize, GrabMode, PixelFormat


class FrameSource:
    """Captura quadros RGB565, avisa cada novo quadro e só codifica JPEG quando pedido.

    O OV5640 não inicia no modo JPEG com este driver, então os quadros ficam crus:
    a visão os lê diretamente e o vídeo só paga a compressão enquanto alguém assiste.
    """

    def __init__(self, pins, frame_size="QVGA", quality=75, xclk_mhz=20, vflip=False, hmirror=False):
        self._pins = pins
        self._frame_size = getattr(FrameSize, frame_size)
        self._cam = self._open(xclk_mhz)
        self.xclk_mhz = xclk_mhz
        self.flip = (vflip, hmirror)
        self.sensor = self._cam.sensor_name
        self.width = self._cam.pixel_width
        self.height = self._cam.pixel_height
        self.raw = bytearray(self.width * self.height * 2)
        self.frames = 0
        self.fps = 0.0
        self.fresh = asyncio.Event()
        self._encoder = jpeg.Encoder(width=self.width, height=self.height,
                                     pixel_format="RGB565_BE", quality=quality)
        self._jpeg = (-1, b"")

    def _open(self, xclk_mhz):
        return Camera(
            **self._pins,
            xclk_freq=xclk_mhz * 1_000_000,
            pixel_format=PixelFormat.RGB565,
            frame_size=self._frame_size,
            fb_count=2,
            grab_mode=GrabMode.LATEST,
        )

    def set_xclk(self, mhz):
        flip = self.flip
        self._cam.deinit()
        try:
            self._cam = self._open(mhz)
        except OSError:
            self._cam = self._open(self.xclk_mhz)
            self.flip = flip
            raise
        self.xclk_mhz = mhz
        self.flip = flip

    def close(self):
        self._cam.deinit()

    @property
    def flip(self):
        return self._cam.vflip, self._cam.hmirror

    @flip.setter
    def flip(self, value):
        self._cam.vflip, self._cam.hmirror = value

    def jpeg(self):
        frame, data = self._jpeg
        if frame != self.frames:
            data = self._encoder.encode(self.raw)
            self._jpeg = (self.frames, data)
        return data

    async def next_frame(self):
        await self.fresh.wait()

    async def run(self):
        size = len(self.raw)
        last = time.ticks_ms()
        while True:
            for _ in range(40):
                if self._cam.frame_available():
                    break
                await asyncio.sleep_ms(5)
            cam = self._cam
            try:
                data = cam.capture()
            except Exception:
                await asyncio.sleep_ms(100)
                continue
            if data is None or len(data) != size:
                cam.free_buffer()
                await asyncio.sleep_ms(10)
                continue
            self.raw[:] = data
            cam.free_buffer()

            now = time.ticks_ms()
            self.fps = 0.9 * self.fps + 100 / max(1, time.ticks_diff(now, last))
            last = now
            self.frames += 1

            self.fresh.set()
            self.fresh.clear()
            await asyncio.sleep_ms(0)
