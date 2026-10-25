import framebuf
from machine import Pin, SoftI2C

from ssd1306 import SSD1306_I2C

_FOLD = {"á": "a", "à": "a", "â": "a", "ã": "a", "é": "e", "ê": "e", "í": "i",
         "ó": "o", "ô": "o", "õ": "o", "ú": "u", "ç": "c"}

PAGES = ("painel", "visao", "rede")


def fold(text):
    return "".join(_FOLD.get(ch, ch) for ch in str(text).lower())


class Display:
    def __init__(self, scl, sda):
        self.oled = SSD1306_I2C(128, 64, SoftI2C(scl=Pin(scl), sda=Pin(sda), freq=400_000))
        self.page = 0
        self._glyph = framebuf.FrameBuffer(bytearray(8), 8, 8, framebuf.MONO_HLSB)
        self._mask = bytearray(600)
        self._mask_fb = framebuf.FrameBuffer(self._mask, 80, 60, framebuf.MONO_HLSB)
        self._tick = 0

    def next_page(self):
        self.page = (self.page + 1) % len(PAGES)

    def message(self, title, *lines):
        fb = self.oled
        fb.fill(0)
        fb.fill_rect(0, 0, 128, 12, 1)
        fb.text(fold(title)[:16], 2, 2, 0)
        for i, line in enumerate(lines):
            fb.text(fold(line)[:16], 0, 18 + i * 11, 1)
        fb.show()

    def render(self, app):
        self._tick += 1
        if app.estop:
            self._emergency()
        else:
            (self._dashboard, self._vision, self._network)[self.page](app)
        self.oled.show()

    def _big(self, text, x, y, size=24, color=1):
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
        self.oled.text(text, 128 - 8 * len(text), y, 1)

    def _header(self, title, app):
        fb = self.oled
        fb.fill(0)
        fb.text(title, 0, 0, 1)
        if self._tick & 2:
            fb.fill_rect(123, 1, 4, 4, 1)
        fb.hline(0, 10, 128, 1)

    def _dashboard(self, app):
        fb = self.oled
        self._header("ESTEIRA IA", app)
        self._big("%03d" % (app.total % 1000), 0, 17, 20)
        self._right("%d/m" % app.rate, 16)
        self._right("x%d" % app.rejected, 28)
        fb.text(fold(app.last["label"])[:16] if app.last else "aguardando...", 0, 43, 1)
        sonar = app.sonar
        if sonar is not None and sonar.distance is not None:
            fb.text("%.1fcm" % sonar.height, 0, 55, 1)
            fb.rect(64, 55, 64, 7, 1)
            fb.fill_rect(66, 57, min(60, int(sonar.height * 6)), 3, 1)

    def _vision(self, app):
        fb = self.oled
        fb.fill(0)
        if app.vision is None:
            fb.text("sem camera", 24, 28, 1)
            return
        app.vision.render_mask(self._mask)
        fb.blit(self._mask_fb, 0, 2)
        fb.rect(0, 2, 80, 60, 1)
        line = int(app.settings.line * 80)
        for y in range(2, 62, 4):
            fb.vline(line, y, 2, 1)
        for track in app.tracks:
            x, y, w, h = track.box
            fb.rect(x, y + 2, w, h, 1)
        self._right("%dfps" % int(app.camera.fps), 4)
        self._right("%d obj" % len(app.tracks), 20)
        self._right("%d%%" % int(app.vision.coverage * 100), 36)

    def _network(self, app):
        fb = self.oled
        self._header("REDE", app)
        net = app.network
        fb.text(("AP " if net["mode"] == "ap" else "") + net["ssid"][:13], 0, 16, 1)
        fb.text(net["ip"], 0, 28, 1)
        fb.text((net["host"] + ".local")[:16], 0, 40, 1)
        fb.text("clientes %d" % app.clients, 0, 54, 1)

    def _emergency(self):
        fb = self.oled
        on = self._tick & 1
        fb.fill(on)
        fb.rect(2, 2, 124, 60, 1 - on)
        self._big("STOP", 16, 10, 24, 1 - on)
        fb.text("EMERGENCIA", 24, 44, 1 - on)
