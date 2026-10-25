import asyncio
import time

from machine import PWM, Pin

TUNES = {
    "boot": ((523, 80), (659, 80), (784, 80), (1047, 180)),
    "ready": ((1319, 60), (0, 40), (1760, 90)),
    "count": ((1568, 35),),
    "reject": ((440, 110), (0, 40), (330, 220)),
    "alarm": ((1760, 160), (1175, 160)) * 4,
    "rearm": ((784, 70), (1047, 70), (1568, 120)),
    "click": ((2093, 15),),
}


def reserve_camera_clock(pin):
    # O driver da câmera gera o XCLK no canal LEDC 0 / timer 3 sem o MicroPython saber.
    # Reservar o canal 0 no pino do XCLK primeiro (dividindo o timer do RGB) afasta os outros
    # PWMs desse canal e limita o MicroPython aos timers 0-2. Deve rodar antes da câmera.
    return PWM(Pin(pin), freq=RgbLed.FREQ, duty_u16=0)


class RgbLed:
    FREQ = 5000

    def __init__(self, red, green, blue):
        self._channels = [PWM(Pin(p), freq=self.FREQ, duty_u16=0) for p in (red, green, blue)]
        self.rgb = (0, 0, 0)

    def set(self, rgb):
        rgb = tuple(max(0, min(255, int(c))) for c in rgb)
        if rgb == self.rgb:
            return
        self.rgb = rgb
        for channel, value in zip(self._channels, rgb):
            channel.duty_u16(value * value * 65535 // 65025)

    @property
    def hex(self):
        return "#%02x%02x%02x" % self.rgb


class Buzzer:
    def __init__(self, pin, volume=0.25):
        self._pwm = PWM(Pin(pin), freq=2000, duty_u16=0)
        self._duty = int(32768 * volume)
        self._task = None
        self.muted = False

    def play(self, name, force=False):
        if self.muted and not force:
            return
        if self._task is not None:
            self._task.cancel()
        self._task = asyncio.create_task(self._play(TUNES[name]))

    async def _play(self, notes):
        try:
            for freq, ms in notes:
                if freq:
                    self._pwm.freq(freq)
                    self._pwm.duty_u16(self._duty)
                else:
                    self._pwm.duty_u16(0)
                await asyncio.sleep_ms(ms)
        finally:
            self._pwm.duty_u16(0)


class Servo:
    def __init__(self, pin, angle=0):
        self._pwm = PWM(Pin(pin), freq=50)
        self.angle = None
        self.move(angle)

    def move(self, angle):
        angle = max(0, min(180, int(angle)))
        if angle != self.angle:
            self.angle = angle
            self._pwm.duty_ns(500_000 + angle * 2_000_000 // 180)


class Button:
    """Botão ativo em nível baixo, com debounce e detecção de toque longo."""

    def __init__(self, pin, on_press=None, on_long=None, long_ms=1200):
        self._pin = Pin(pin, Pin.IN, Pin.PULL_UP)
        self._on_press = on_press
        self._on_long = on_long
        self._long_ms = long_ms

    @property
    def pressed(self):
        return self._pin.value() == 0

    async def run(self):
        while True:
            while not self.pressed:
                await asyncio.sleep_ms(20)
            start = time.ticks_ms()
            fired = False
            while self.pressed:
                if not fired and self._on_long and time.ticks_diff(time.ticks_ms(), start) >= self._long_ms:
                    fired = True
                    self._on_long()
                await asyncio.sleep_ms(20)
            if not fired and time.ticks_diff(time.ticks_ms(), start) >= 30 and self._on_press:
                self._on_press()


class EmergencyStop:
    """E-STOP com trava: a interrupção acorda a tarefa de tratamento imediatamente."""

    def __init__(self, pin, on_trip):
        self._pin = Pin(pin, Pin.IN, Pin.PULL_UP)
        self._flag = asyncio.ThreadSafeFlag()
        self._on_trip = on_trip
        self._pin.irq(lambda _: self._flag.set(), Pin.IRQ_FALLING)

    @property
    def pressed(self):
        return self._pin.value() == 0

    async def run(self):
        if self.pressed:
            self._on_trip()
        while True:
            await self._flag.wait()
            await asyncio.sleep_ms(15)
            if self.pressed:
                self._on_trip()
