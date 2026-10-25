import asyncio
import gc

import esp

import config
from app import api, net
from app.controller import App
from app.hardware import Buzzer, Button, EmergencyStop, RgbLed, Servo, reserve_camera_clock
from app.settings import Settings
from app.sonar import Sonar

# Desligar a câmera na saída impede que o driver inunde o REPL depois do Ctrl-C.
on_exit = []


def optional(name, factory):
    try:
        return factory()
    except Exception as e:
        print("[warn] %s indisponível: %r" % (name, e))
        return None


def start_display():
    from app.display import Display

    return Display(config.OLED_SCL, config.OLED_SDA)


def start_camera(settings):
    from app.camera import FrameSource
    from app.settings import DEFAULTS
    from app.vision import Vision

    def open_camera():
        return FrameSource(config.CAMERA_PINS, config.CAMERA_FRAME_SIZE, config.CAMERA_QUALITY,
                           settings.xclk_mhz, settings.vflip, settings.hmirror)

    try:
        camera = open_camera()
    except OSError:
        if settings.xclk_mhz == DEFAULTS["xclk_mhz"]:
            raise
        settings.update({"xclk_mhz": DEFAULTS["xclk_mhz"]})
        camera = open_camera()
    return camera, Vision(camera.width, camera.height, settings.sensitivity, settings.min_area)


def wheel(hue):
    x = 255 * (60 - abs(hue % 120 - 60)) // 60
    return ((255, x, 0), (x, 255, 0), (0, 255, x), (0, x, 255), (x, 0, 255), (255, 0, x))[hue // 60 % 6]


async def rainbow(rgb):
    hue = 0
    while True:
        rgb.set(c // 3 for c in wheel(hue))
        hue = (hue + 5) % 360
        await asyncio.sleep_ms(25)


async def main():
    esp.osdebug(None)
    settings = Settings()
    xclk = reserve_camera_clock(config.CAMERA_PINS["xclk_pin"])
    rgb = RgbLed(config.RGB_RED, config.RGB_GREEN, config.RGB_BLUE)
    buzzer = Buzzer(config.BUZZER)
    servo = Servo(config.SERVO, settings.servo_rest)
    display = optional("display OLED", start_display)

    buzzer.play("boot", force=True)
    intro = asyncio.create_task(rainbow(rgb))
    if display:
        display.message("Esteira IA", "conectando wifi", config.WIFI_SSID or config.AP_SSID)
    network = await net.connect(config.WIFI_SSID, config.WIFI_PASSWORD, config.HOSTNAME,
                                config.AP_SSID, config.AP_PASSWORD)
    if display:
        display.message("Esteira IA", "iniciando camera", network["ip"])
    camera, vision = optional("câmera", lambda: start_camera(settings)) or (None, None)
    if camera:
        on_exit.append(camera.close)
    sonar = Sonar(config.SONAR_TRIG, config.SONAR_ECHO)
    intro.cancel()

    app = App(settings, rgb=rgb, buzzer=buzzer, servo=servo, camera=camera,
              vision=vision, sonar=sonar, display=display, network=network)
    app.estop_switch = EmergencyStop(config.BUTTON_ESTOP, lambda: app.emergency("botão"))

    def aux_press():
        buzzer.play("click")
        if display:
            display.next_page()

    def aux_hold():
        if app.estop:
            if not app.rearm():
                buzzer.play("reject", force=True)
        else:
            app.recalibrate()
            buzzer.play("ready", force=True)

    aux = Button(config.BUTTON_AUX, on_press=aux_press, on_long=aux_hold)

    await api.build(app, config.MAX_STREAMS).start(config.HTTP_PORT)

    jobs = [app.estop_switch.run(), aux.run(), app.run_indicators(), sonar.run()]
    if camera:
        jobs += [camera.run(), app.run_vision()]
    else:
        jobs.append(app.run_sonar_counter())
    if display:
        jobs.append(app.run_display())
    for job in jobs:
        asyncio.create_task(job)

    buzzer.play("ready", force=True)
    app.log("Pronto em http://%s (%s.local)" % (network["ip"], config.HOSTNAME))
    while True:
        await asyncio.sleep(5)
        gc.collect()


try:
    asyncio.run(main())
finally:
    for close in on_exit:
        close()
