class Track:
    def __init__(self, tid, blob):
        self.id = tid
        self.hits = 0
        self.missed = 0
        self.counted = False
        self.vx = 0.0
        self.vy = 0.0
        self.votes = {}
        self.cx = blob.cx
        self.cy = blob.cy
        self.rgb = blob.rgb
        self.absorb(blob)

    def absorb(self, blob):
        self.prev_cx = self.cx
        self.vx = 0.6 * self.vx + 0.4 * (blob.cx - self.cx)
        self.vy = 0.6 * self.vy + 0.4 * (blob.cy - self.cy)
        self.cx, self.cy = blob.cx, blob.cy
        self.box = blob.box
        self.area = blob.area
        self.rgb = tuple((3 * old + new) // 4 for old, new in zip(self.rgb, blob.rgb))
        self.hits += 1
        self.missed = 0

    def predicted(self):
        return self.cx + self.vx, self.cy + self.vy

    def vote(self, label, weight):
        self.votes[label] = self.votes.get(label, 0) + weight

    @property
    def label(self):
        best, score = None, 0
        for name, value in self.votes.items():
            if value > score:
                best, score = name, value
        return best


class Tracker:
    """Rastreador guloso por vizinho mais próximo, com predição de velocidade constante."""

    def __init__(self, max_jump=16, patience=5):
        self.tracks = []
        self._max_jump2 = max_jump * max_jump
        self._patience = patience
        self._next_id = 1

    def clear(self):
        self.tracks = []

    def update(self, blobs, line_x, direction):
        pairs = []
        for ti, track in enumerate(self.tracks):
            px, py = track.predicted()
            for bi, blob in enumerate(blobs):
                d2 = (blob.cx - px) ** 2 + (blob.cy - py) ** 2
                if d2 <= self._max_jump2:
                    pairs.append((d2, ti, bi))
        pairs.sort()

        matched_tracks, matched_blobs = set(), set()
        for _, ti, bi in pairs:
            if ti in matched_tracks or bi in matched_blobs:
                continue
            matched_tracks.add(ti)
            matched_blobs.add(bi)
            self.tracks[ti].absorb(blobs[bi])

        crossed = []
        survivors = []
        for ti, track in enumerate(self.tracks):
            if ti in matched_tracks:
                if self._crossed(track, line_x, direction):
                    track.counted = True
                    crossed.append(track)
            else:
                track.missed += 1
            if track.missed <= self._patience:
                survivors.append(track)

        for bi, blob in enumerate(blobs):
            if bi not in matched_blobs:
                survivors.append(Track(self._next_id, blob))
                self._next_id += 1

        self.tracks = survivors
        return crossed

    @staticmethod
    def _crossed(track, line_x, direction):
        if track.counted or track.hits < 2:
            return False
        before, after = track.prev_cx - line_x, track.cx - line_x
        if direction >= 0 and before < 0 <= after:
            return True
        return direction <= 0 and before > 0 >= after
