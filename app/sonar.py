import asyncio
import time

from machine import Pin, time_pulse_us

_US_PER_CM = 58.3
_TIMEOUT_US = 25_000


class Sonar:
    """HC-SR04P que aprende a distância da esteira vazia e informa a altura do objeto."""

    def __init__(self, trig, echo, min_height=1.2):
        self._trig = Pin(trig, Pin.OUT, value=0)
        self._echo = Pin(echo, Pin.IN)
        self.min_height = min_height
        self.distance = None
        self.baseline = None
        self._window = []
        self._peak = (0.0, 0)

    @property
    def height(self):
        if self.distance is None or self.baseline is None:
            return 0.0
        return max(0.0, self.baseline - self.distance)

    @property
    def present(self):
        return self.height >= self.min_height

    def recent_peak(self, window_ms=1500):
        height, at = self._peak
        return height if time.ticks_diff(time.ticks_ms(), at) <= window_ms else self.height

    def recalibrate(self):
        self.baseline = self.distance

    def _ping(self):
        self._trig.value(1)
        time.sleep_us(10)
        self._trig.value(0)
        us = time_pulse_us(self._echo, 1, _TIMEOUT_US)
        return us / _US_PER_CM if us > 0 else None

    async def run(self, period_ms=70):
        while True:
            reading = self._ping()
            if reading is not None and 2 <= reading <= 400:
                self._window = (self._window + [reading])[-5:]
                self.distance = sorted(self._window)[len(self._window) // 2]
                self._learn()
            await asyncio.sleep_ms(period_ms)

    def _learn(self):
        d = self.distance
        if self.baseline is None or d > self.baseline:
            self.baseline = d
        elif self.baseline - d < self.min_height:
            self.baseline += (d - self.baseline) * 0.02
        h = self.height
        now = time.ticks_ms()
        if h >= self._peak[0] or time.ticks_diff(now, self._peak[1]) > 1500:
            self._peak = (h, now)
