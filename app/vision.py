from array import array

from app import kernels as k

GRID = (k.W, k.H)

_FAST, _SLOW, _WARMUP_FAST = 5, 9, 2
_WARMUP_FRAMES = 12


class Blob:
    def __init__(self, x0, y0, x1, y1, area, cx, cy, rgb):
        self.box = (x0, y0, x1 - x0 + 1, y1 - y0 + 1)
        self.area = area
        self.cx = cx
        self.cy = cy
        self.rgb = rgb


def color_name(rgb):
    r, g, b = rgb
    hi, lo = max(rgb), min(rgb)
    if hi < 48:
        return "preto"
    if (hi - lo) * 100 < hi * 22:
        return "branco" if hi > 170 else "cinza"
    span = hi - lo
    if hi == r:
        hue = 60 * (g - b) / span
    elif hi == g:
        hue = 60 * (b - r) / span + 120
    else:
        hue = 60 * (r - g) / span + 240
    hue %= 360
    for limit, name in ((15, "vermelho"), (40, "laranja"), (70, "amarelo"), (165, "verde"),
                        (255, "azul"), (290, "roxo"), (335, "rosa")):
        if hue < limit:
            return name
    return "vermelho"


def hex_color(rgb):
    return "#%02x%02x%02x" % rgb


class Vision:
    """Encontra objetos em movimento com modelo de fundo adaptativo e rotulagem de blobs."""

    def __init__(self, width, height, sensitivity=28, min_area=30):
        self._width = width
        self._step = min(width // k.W, height // k.H)
        if self._step < 1:
            raise ValueError("frame smaller than the analysis grid")
        self.sensitivity = sensitivity
        self.min_area = min_area
        self.coverage = 0.0
        self._px = bytearray(k.N * 2)
        self._bg = bytearray(k.N * 6)
        self.mask = bytearray(k.N)
        self._tmp = bytearray(k.N)
        self._labels = bytearray(k.N)
        self._stack = bytearray(k.N * 4)
        self._stats = array("i", (0,) * (k.MAX_BLOBS * k.STRIDE))
        self._sums = array("i", (0,) * (k.MAX_BLOBS * 3))
        self._params = array("i", (0, 0, 0, 0))
        self._warmup = _WARMUP_FRAMES

    def recalibrate(self):
        self._warmup = _WARMUP_FRAMES

    def process(self, frame):
        k.sample(frame, self._px, self._width, self._step)

        if self._warmup == _WARMUP_FRAMES:
            k.seed(self._px, self._bg)
        p = self._params
        p[0] = self.sensitivity << 4
        p[1] = k.drift(self._px, self._bg) // (3 * k.N)
        p[2] = _WARMUP_FAST if self._warmup else _FAST
        p[3] = _WARMUP_FAST if self._warmup else _SLOW
        count = k.foreground(self._px, self._bg, self.mask, p)
        if self._warmup:
            self._warmup -= 1
            self.coverage = 0.0
            return []

        self.coverage = count / k.N
        k.denoise(self.mask, self._tmp)
        n = k.label(self.mask, self._labels, self._stack, self._stats)
        k.colors(self._px, self._labels, self._sums, n)
        return self._blobs(n)

    def _blobs(self, n):
        stats, sums = self._stats, self._sums
        blobs = []
        for i in range(n):
            s = i * k.STRIDE
            area = stats[s + 4]
            if area < self.min_area:
                continue
            c = i * 3
            rgb = (sums[c] // area, sums[c + 1] // area, sums[c + 2] // area)
            blobs.append(Blob(stats[s], stats[s + 1], stats[s + 2], stats[s + 3], area,
                              stats[s + 5] / area, stats[s + 6] / area, rgb))
        return blobs

    def render_mask(self, out):
        k.render(self.mask, out)
