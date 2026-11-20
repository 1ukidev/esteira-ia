import asyncio
import gc
import json
import time

from app import net
from app.tracker import Tracker
from app.vision import GRID, color_name, hex_color

_AI_TTL_MS = 1500


class App:
    """Cérebro da esteira: combina visão, sonar e IA do navegador e comanda as saídas."""

    def __init__(self, settings, *, rgb, buzzer, servo, camera=None, vision=None,
                 sonar=None, display=None, network=None):
        self.settings = settings
        self.rgb = rgb
        self.buzzer = buzzer
        self.servo = servo
        self.camera = camera
        self.vision = vision
        self.sonar = sonar
        self.display = display
        self.network = network
        self.estop_switch = None

        self.tracker = Tracker()
        self.tracks = []
        self.estop = False
        self.total = 0
        self.rejected = 0
        self.counts = {}
        self.last = None
        self.history = []
        self.ai = []
        self.clients = 0
        self.vision_fps = 0.0

        self._started = time.ticks_ms()
        self._ai_at = 0
        self._stamps = []
        self._subscribers = []
        self._reject_until = 0
        self._glow = ((0, 0, 0), 0)
        self._push_task = None
        self._snapshot = (0, "{}")
        self.apply_settings({})

    @property
    def uptime(self):
        return time.ticks_diff(time.ticks_ms(), self._started) // 1000

    @property
    def rate(self):
        now = time.ticks_ms()
        self._stamps = [t for t in self._stamps if time.ticks_diff(now, t) < 60_000]
        return len(self._stamps)

    def subscribe(self):
        queue = []
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue):
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def publish(self, kind, data):
        for queue in self._subscribers:
            if len(queue) < 32:
                queue.append((kind, data))

    def log(self, text, level="info"):
        print("[%s] %s" % (level, text))
        self.publish("log", {"text": text, "level": level, "t": self.uptime})

    def apply_settings(self, changes):
        applied = self.settings.update(changes) if changes else {}
        s = self.settings
        if self.vision is not None:
            self.vision.sensitivity = s.sensitivity
            self.vision.min_area = s.min_area
        if self.camera is not None and "xclk_mhz" in applied:
            self._restart_camera(applied)
        if self.camera is not None and ("vflip" in applied or "hmirror" in applied or not changes):
            self.camera.flip = (s.vflip, s.hmirror)
            if self.vision is not None:
                self.vision.recalibrate()
        self.buzzer.muted = not s.sound
        if self._push_task is None:
            self.servo.set_pulse(s.servo_neutral_us)
        return applied

    def _restart_camera(self, applied):
        mhz = self.settings.xclk_mhz
        try:
            self.camera.set_xclk(mhz)
            self.log("Câmera reiniciada com XCLK de %d MHz" % mhz)
        except OSError as e:
            restored = self.camera.xclk_mhz
            applied["xclk_mhz"] = self.settings.update({"xclk_mhz": restored})["xclk_mhz"]
            self.log("XCLK de %d MHz falhou (%s); mantido em %d MHz" % (mhz, e, restored), "warn")
        if self.vision is not None:
            self.vision.recalibrate()

    def emergency(self, source="botão"):
        if self.estop:
            return
        self.estop = True
        self.servo.set_pulse(self.settings.servo_neutral_us)
        if self._push_task is not None:
            self._push_task.cancel()
            self._push_task = None
        self.tracker.clear()
        self.tracks = []
        self.buzzer.play("alarm", force=True)
        self.publish("estop", {"active": True, "source": source})
        self.log("Parada de emergência acionada (%s)" % source, "alert")

    def rearm(self):
        if not self.estop:
            return True
        if self.estop_switch is not None and self.estop_switch.pressed:
            return False
        self.estop = False
        if self.vision is not None:
            self.vision.recalibrate()
        self.buzzer.play("rearm", force=True)
        self.publish("estop", {"active": False})
        self.log("Sistema rearmado")
        return True

    def reset_counts(self):
        self.total = self.rejected = 0
        self.counts = {}
        self.last = None
        self.history = []
        self._stamps = []
        self.log("Contadores zerados")

    def recalibrate(self):
        if self.vision is not None:
            self.vision.recalibrate()
        if self.sonar is not None:
            self.sonar.recalibrate()
        self.tracker.clear()
        self.log("Fundo e sensor recalibrados")

    def ai_update(self, detections):
        width, height = GRID
        clean = []
        for det in detections[:16]:
            x, y, w, h = (float(v) for v in det["box"])
            label, score = str(det["label"])[:32], float(det.get("score", 0.5))
            clean.append({"label": label, "score": round(score, 2), "box": [x, y, w, h]})
            for track in self.tracks:
                cx, cy = track.cx / width, track.cy / height
                if x - 0.05 <= cx <= x + w + 0.05 and y - 0.05 <= cy <= y + h + 0.05:
                    track.vote(label, score)
        self.ai = clean
        self._ai_at = time.ticks_ms()

    def count(self, track=None):
        now = time.ticks_ms()
        s = self.settings
        rgb = track.rgb if track else (160, 160, 160)
        color = color_name(rgb) if track else "objeto"
        label = (track.label if track else None) or color
        height = self.sonar.recent_peak() if self.sonar else 0.0
        reject = s.sorter and (label in s.reject or color in s.reject)

        self.total += 1
        self.counts[label] = self.counts.get(label, 0) + 1
        self._stamps.append(now)
        self._glow = (rgb, now)
        if reject:
            self.rejected += 1
            self._reject_until = time.ticks_add(now, 700)
            if not self.request_push():
                self.log("Desviador ocupado; não acionado para a peça %d" % self.total, "warn")
        self.buzzer.play("reject" if reject else "count")

        event = {
            "n": self.total,
            "label": label,
            "color": color,
            "rgb": hex_color(rgb),
            "height": round(height, 1),
            "reject": reject,
            "t": self.uptime,
            "box": list(track.box) if track else None,
        }
        self.last = event
        self.history = (self.history + [event])[-12:]
        self.publish("count", event)

    def request_push(self):
        if self.estop or self._push_task is not None:
            return False
        self._push_task = asyncio.create_task(self._push())
        return True

    async def _push(self):
        s = self.settings
        try:
            if s.push_delay:
                await asyncio.sleep_ms(s.push_delay)
            neutral, drive = s.servo_neutral_us, s.servo_drive_us
            advance_ms, return_ms = s.servo_advance_ms, s.servo_return_ms
            self.servo.set_pulse(neutral + drive)
            await asyncio.sleep_ms(advance_ms)
            self.servo.set_pulse(neutral - drive)
            await asyncio.sleep_ms(return_ms)
        finally:
            # Um ciclo cancelado pode terminar depois do rearme e de um novo acionamento.
            if self._push_task is asyncio.current_task():
                self._push_task = None
                self.servo.set_pulse(s.servo_neutral_us)

    def snapshot(self):
        stamp, cached = self._snapshot
        now = time.ticks_ms()
        if time.ticks_diff(now, stamp) < 150:
            return cached
        sonar = self.sonar
        fresh_ai = time.ticks_diff(now, self._ai_at) < _AI_TTL_MS
        state = {
            "up": self.uptime,
            "estop": self.estop,
            "fps": round(self.camera.fps, 1) if self.camera else 0,
            "vfps": round(self.vision_fps, 1),
            "coverage": round(self.vision.coverage, 3) if self.vision else 0,
            "tracks": [[t.id] + list(t.box) + [hex_color(t.rgb), t.label or color_name(t.rgb)]
                       for t in self.tracks],
            "ai": self.ai if fresh_ai else [],
            "total": self.total,
            "rejected": self.rejected,
            "rate": self.rate,
            "counts": self.counts,
            "sonar": None if sonar is None or sonar.distance is None else {
                "cm": round(sonar.distance, 1),
                "base": round(sonar.baseline, 1),
                "h": round(sonar.height, 1),
            },
            "io": {
                "rgb": self.rgb.hex,
                "servo": self.servo.pulse_us,
            },
            "clients": self.clients,
            "mem": gc.mem_free(),
            "rssi": net.rssi(self.network) if self.network else None,
        }
        cached = json.dumps(state)
        self._snapshot = (now, cached)
        return cached

    async def run_vision(self):
        cam, vision = self.camera, self.vision
        last = time.ticks_ms()
        while True:
            await cam.next_frame()
            if self.estop:
                continue
            try:
                blobs = vision.process(cam.raw)
            except Exception as e:
                self.log("Falha na visão: %r" % e, "warn")
                await asyncio.sleep_ms(500)
                continue
            s = self.settings
            for track in self.tracker.update(blobs, s.line * GRID[0], s.direction):
                self.count(track)
            self.tracks = [t for t in self.tracker.tracks if t.missed == 0]

            now = time.ticks_ms()
            self.vision_fps = 0.85 * self.vision_fps + 150 / max(1, time.ticks_diff(now, last))
            last = now
            await asyncio.sleep_ms(0)

    async def run_sonar_counter(self):
        was_present = False
        while True:
            present = self.sonar.present and not self.estop
            if present and not was_present:
                self.count()
            was_present = present
            await asyncio.sleep_ms(60)

    def _indicator_color(self, now):
        if self.estop:
            return (255 * abs((now % 800) - 400) / 400, 0, 0)
        if time.ticks_diff(self._reject_until, now) > 0:
            return (255, 0, 0) if (now // 90) & 1 else (0, 0, 0)
        rgb, since = self._glow
        age = time.ticks_diff(now, since)
        if self.last is not None and age < 2500:
            return tuple(c * (1 - age / 2500) for c in rgb)
        breath = abs((now % 2000) - 1000) / 1000
        if self.tracks or (self.sonar is not None and self.sonar.present):
            return (40 + 160 * breath, 20 + 80 * breath, 0)
        return (0, 6 + 18 * breath, 8 + 25 * breath)

    async def run_indicators(self):
        while True:
            self.rgb.set(self._indicator_color(time.ticks_ms()))
            await asyncio.sleep_ms(40)

    async def run_display(self):
        failures = 0
        while failures < 5:
            try:
                self.display.render(self)
                failures = 0
            except OSError:
                failures += 1
            await asyncio.sleep_ms(250 if self.display.page == 1 else 400)
        self.log("Display OLED não responde; desativado", "warn")
