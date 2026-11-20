import framebuf
from machine import Pin, SoftI2C

from app.vision import PREVIEW_GRID
from ssd1306 import SSD1306_I2C

_FOLD = {"á": "a", "à": "a", "â": "a", "ã": "a", "é": "e", "ê": "e", "í": "i",
         "ó": "o", "ô": "o", "õ": "o", "ú": "u", "ç": "c"}
_FOLD.update({ch.upper(): plain.upper() for ch, plain in _FOLD.items()})
_WIDTH, _HEIGHT = 128, 32
_TEXT_COLS = _WIDTH // 8
_PREVIEW_W, _PREVIEW_H = PREVIEW_GRID

PAGES = ("painel", "visao", "rede")


def fold(text):
    return "".join(ch if " " <= ch <= "~" else _FOLD.get(ch, "?") for ch in str(text))


class Display:
    def __init__(self, scl, sda):
        self.oled = SSD1306_I2C(_WIDTH, _HEIGHT, SoftI2C(scl=Pin(scl), sda=Pin(sda), freq=400_000))
        self.page = 0
        self._glyph = framebuf.FrameBuffer(bytearray(8), 8, 8, framebuf.MONO_HLSB)
        self._mask = bytearray(_PREVIEW_W * _PREVIEW_H // 8)
        self._mask_fb = framebuf.FrameBuffer(self._mask, _PREVIEW_W, _PREVIEW_H, framebuf.MONO_HLSB)
        self._tick = 0

    def next_page(self):
        self.page = (self.page + 1) % len(PAGES)

    def message(self, title, *lines):
        fb = self.oled
        fb.fill(0)
        fb.fill_rect(0, 0, _WIDTH, 10, 1)
        fb.text(fold(title)[:_TEXT_COLS], 0, 1, 0)
        for i, line in enumerate(lines[:2]):
            fb.text(fold(line)[:_TEXT_COLS], 0, 12 + i * 10, 1)
        fb.show()

    def render(self, app):
        self._tick += 1
        if app.estop:
            self._emergency()
        else:
            (self._dashboard, self._vision, self._network)[self.page](app)
        self.oled.show()

    def _big(self, text, x, y, size, color=1):
        fb, glyph = self.oled, self._glyph
        edges = [i * size // 8 for i in range(9)]
        for ch in text:
            glyph.fill(0)
            glyph.text(ch, 0, 0, 1)
            for gy in range(8):
                for gx in range(8):
                    if glyph.pixel(gx, gy):
                        fb.fill_rect(x + edges[gx], y + edges[gy], edges[gx + 1] - edges[gx],
                                     edges[gy + 1] - edges[gy], color)
            x += size

    def _right(self, text, y):
        self.oled.text(text, _WIDTH - 8 * len(text), y, 1)

    def _dashboard(self, app):
        fb = self.oled
        fb.fill(0)
        total, rate, rejected = "%03d" % app.total, "%d/m" % app.rate, "x%d" % app.rejected
        count_width = _WIDTH - 8 * max(len(rate), len(rejected)) - 4
        self._big(total, 0, 0, min(16, count_width // len(total)))
        self._right(rate, 0)
        self._right(rejected, 8)
        label = fold(app.last["label"]) if app.last else "aguardando..."
        fb.text(label[:_TEXT_COLS], 0, 16, 1)
        sonar = app.sonar
        if sonar is not None and sonar.distance is not None:
            height = sonar.height
            fb.text("%.1fcm" % height, 0, 24, 1)
            fb.rect(64, 24, 64, 7, 1)
            fb.fill_rect(66, 26, min(60, int(height * 6)), 3, 1)

    def _vision(self, app):
        fb = self.oled
        fb.fill(0)
        if app.vision is None:
            fb.text("sem camera", 24, 12, 1)
            return
        app.vision.render_mask(self._mask)
        fb.blit(self._mask_fb, 1, 1)
        fb.rect(0, 0, _PREVIEW_W + 2, _PREVIEW_H + 2, 1)
        line = 1 + int(app.settings.line * _PREVIEW_W)
        for y in range(1, _PREVIEW_H, 4):
            fb.vline(line, y, 2, 1)
        for track in app.tracks:
            x, y, w, h = track.box
            left, top = x // 2, y // 2
            right, bottom = (x + w - 1) // 2, (y + h - 1) // 2
            fb.rect(left + 1, top + 1, right - left + 1, bottom - top + 1, 1)
        fb.text("%d fps" % int(app.camera.fps), 48, 1, 1)
        fb.text("%d obj" % len(app.tracks), 48, 12, 1)
        fb.text("%d%% area" % int(app.vision.coverage * 100), 48, 23, 1)

    def _network(self, app):
        fb = self.oled
        fb.fill(0)
        net = app.network
        prefix = "AP " if net["mode"] == "ap" else ""
        fb.text((prefix + fold(net["ssid"]))[:_TEXT_COLS], 0, 0, 1)
        fb.text(net["ip"], 0, 8, 1)
        fb.text((net["host"] + ".local")[:_TEXT_COLS], 0, 16, 1)
        fb.text("clientes %d" % app.clients, 0, 24, 1)

    def _emergency(self):
        fb = self.oled
        on = self._tick & 1
        fb.fill(on)
        fb.rect(1, 1, _WIDTH - 2, _HEIGHT - 2, 1 - on)
        self._big("STOP", 32, 3, 16, 1 - on)
        fb.text("EMERGENCIA", 24, 21, 1 - on)
