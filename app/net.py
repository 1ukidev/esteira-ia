import asyncio

import network


async def connect(ssid, password, hostname, ap_ssid, ap_password, timeout_ms=15_000):
    network.hostname(hostname)
    sta = network.WLAN(network.WLAN.IF_STA)
    if ssid:
        sta.active(True)
        sta.config(pm=sta.PM_NONE)
        sta.connect(ssid, password)
        for _ in range(timeout_ms // 250):
            if sta.isconnected():
                return {"mode": "sta", "ssid": ssid, "ip": sta.ifconfig()[0], "host": hostname, "wlan": sta}
            await asyncio.sleep_ms(250)
        sta.active(False)

    ap = network.WLAN(network.WLAN.IF_AP)
    ap.active(True)
    ap.config(essid=ap_ssid, password=ap_password, authmode=network.AUTH_WPA2_PSK)
    return {"mode": "ap", "ssid": ap_ssid, "ip": ap.ifconfig()[0], "host": hostname, "wlan": ap}


def rssi(net):
    if net["mode"] != "sta":
        return None
    try:
        return net["wlan"].status("rssi")
    except OSError:
        return None
