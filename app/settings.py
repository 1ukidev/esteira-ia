import json

DEFAULTS = {
    "sensitivity": 28,
    "min_area": 30,
    "line": 0.5,
    "direction": 0,
    "sorter": True,
    "reject": ["vermelho"],
    "servo_rest": 15,
    "servo_push": 105,
    "push_delay": 0,
    "push_ms": 600,
    "sound": True,
    "xclk_mhz": 20,
    "vflip": True,
    "hmirror": False,
}

_LIMITS = {
    "sensitivity": (4, 120),
    "min_area": (4, 1200),
    "line": (0.05, 0.95),
    "direction": (-1, 1),
    "servo_rest": (0, 180),
    "servo_push": (0, 180),
    "push_delay": (0, 5000),
    "push_ms": (150, 3000),
    "xclk_mhz": (8, 24),
}


class Settings:
    def __init__(self, path="settings.json"):
        self._path = path
        self._data = dict(DEFAULTS)
        try:
            with open(path) as f:
                self.update(json.load(f), save=False)
        except (OSError, ValueError):
            pass

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name)

    def as_dict(self):
        return dict(self._data)

    def update(self, changes, save=True):
        applied = {}
        for key, value in changes.items():
            if key not in DEFAULTS:
                continue
            default = DEFAULTS[key]
            if isinstance(default, bool):
                value = bool(value)
            elif isinstance(default, list):
                if not isinstance(value, list):
                    continue
                value = [str(v)[:32] for v in value][:24]
            elif isinstance(default, (int, float)):
                value = type(default)(value)
                low, high = _LIMITS[key]
                value = max(low, min(high, value))
            self._data[key] = applied[key] = value
        if save and applied:
            with open(self._path, "w") as f:
                json.dump(self._data, f)
        return applied
