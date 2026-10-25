"""Rotinas de pixel compiladas com o emissor viper.

Os quadros chegam em RGB565 big-endian, como a câmera entrega. Todos os buffers
usam a mesma grade de análise de 80x60. O modelo de fundo guarda cada canal RGB
em ponto fixo (valor << 4) para aprender de forma suave.
"""

import micropython
from micropython import const

W = const(80)
H = const(60)
N = const(4800)
MAX_BLOBS = const(32)
STRIDE = const(7)


@micropython.viper
def sample(src: ptr8, px: ptr16, width: int, step: int):
    col = step << 1
    row = width * col
    line = ((step >> 1) * width + (step >> 1)) << 1
    i = 0
    y = 0
    while y < H:
        p = line
        x = 0
        while x < W:
            px[i] = (src[p] << 8) | src[p + 1]
            p += col
            i += 1
            x += 1
        line += row
        y += 1


@micropython.viper
def seed(px: ptr16, bg: ptr16):
    i = 0
    j = 0
    while i < N:
        v = px[i]
        bg[j] = (v >> 4) & 0xF80
        bg[j + 1] = (v << 1) & 0xFC0
        bg[j + 2] = (v << 7) & 0xF80
        i += 1
        j += 3


@micropython.viper
def drift(px: ptr16, bg: ptr16) -> int:
    total = 0
    i = 0
    j = 0
    while i < N:
        v = px[i]
        total += ((v >> 4) & 0xF80) + ((v << 1) & 0xFC0) + ((v << 7) & 0xF80) - bg[j] - bg[j + 1] - bg[j + 2]
        i += 1
        j += 3
    return total


@micropython.viper
def foreground(px: ptr16, bg: ptr16, mask: ptr8, params: ptr32) -> int:
    threshold = params[0]
    offset = params[1]
    fast = params[2]
    slow = params[3]
    count = 0
    i = 0
    j = 0
    while i < N:
        v = px[i]
        r = (v >> 4) & 0xF80
        g = (v << 1) & 0xFC0
        b = (v << 7) & 0xF80
        br = bg[j]
        bgg = bg[j + 1]
        bb = bg[j + 2]
        d = r - br - offset
        if d < 0:
            d = -d
        e = g - bgg - offset
        if e < 0:
            e = -e
        if e > d:
            d = e
        e = b - bb - offset
        if e < 0:
            e = -e
        if e > d:
            d = e
        shift = fast
        if d > threshold:
            mask[i] = 1
            count += 1
            shift = slow
        else:
            mask[i] = 0
        bg[j] = br + ((r - br) >> shift)
        bg[j + 1] = bgg + ((g - bgg) >> shift)
        bg[j + 2] = bb + ((b - bb) >> shift)
        i += 1
        j += 3
    return count


@micropython.viper
def denoise(mask: ptr8, tmp: ptr8):
    i = 0
    while i < N:
        tmp[i] = 0
        i += 1
    y = 1
    while y < H - 1:
        x = 1
        while x < W - 1:
            p = y * W + x
            n = (mask[p - W - 1] + mask[p - W] + mask[p - W + 1] + mask[p - 1]
                 + mask[p + 1] + mask[p + W - 1] + mask[p + W] + mask[p + W + 1])
            if (mask[p] != 0 and n >= 3) or n >= 6:
                tmp[p] = 1
            x += 1
        y += 1
    i = 0
    while i < N:
        mask[i] = tmp[i]
        i += 1


@micropython.viper
def label(mask: ptr8, labels: ptr8, stack: ptr16, stats: ptr32) -> int:
    i = 0
    while i < N:
        labels[i] = 0
        i += 1
    n = 0
    start = 0
    while start < N and n < MAX_BLOBS:
        if mask[start] != 0 and labels[start] == 0:
            n += 1
            labels[start] = n
            sy = 0
            sx = start
            while sx >= W:
                sx -= W
                sy += 1
            stack[0] = sx
            stack[1] = sy
            top = 2
            x0 = W
            y0 = H
            x1 = 0
            y1 = 0
            area = 0
            sum_x = 0
            sum_y = 0
            while top > 0:
                top -= 2
                x = stack[top]
                y = stack[top + 1]
                p = y * W + x
                area += 1
                sum_x += x
                sum_y += y
                if x < x0:
                    x0 = x
                if x > x1:
                    x1 = x
                if y < y0:
                    y0 = y
                if y > y1:
                    y1 = y
                if x > 0 and mask[p - 1] != 0 and labels[p - 1] == 0:
                    labels[p - 1] = n
                    stack[top] = x - 1
                    stack[top + 1] = y
                    top += 2
                if x < W - 1 and mask[p + 1] != 0 and labels[p + 1] == 0:
                    labels[p + 1] = n
                    stack[top] = x + 1
                    stack[top + 1] = y
                    top += 2
                if y > 0 and mask[p - W] != 0 and labels[p - W] == 0:
                    labels[p - W] = n
                    stack[top] = x
                    stack[top + 1] = y - 1
                    top += 2
                if y < H - 1 and mask[p + W] != 0 and labels[p + W] == 0:
                    labels[p + W] = n
                    stack[top] = x
                    stack[top + 1] = y + 1
                    top += 2
            s = (n - 1) * STRIDE
            stats[s] = x0
            stats[s + 1] = y0
            stats[s + 2] = x1
            stats[s + 3] = y1
            stats[s + 4] = area
            stats[s + 5] = sum_x
            stats[s + 6] = sum_y
        start += 1
    return n


@micropython.viper
def colors(px: ptr16, labels: ptr8, sums: ptr32, n: int):
    i = 0
    while i < n * 3:
        sums[i] = 0
        i += 1
    i = 0
    while i < N:
        k = labels[i]
        if k != 0:
            v = px[i]
            j = (k - 1) * 3
            sums[j] = sums[j] + ((v >> 8) & 0xF8)
            sums[j + 1] = sums[j + 1] + ((v >> 3) & 0xFC)
            sums[j + 2] = sums[j + 2] + ((v << 3) & 0xF8)
        i += 1


@micropython.viper
def render(mask: ptr8, out: ptr8):
    i = 0
    while i < N >> 3:
        out[i] = 0
        i += 1
    i = 0
    while i < N:
        if mask[i] != 0:
            out[i >> 3] = out[i >> 3] | (0x80 >> (i & 7))
        i += 1
