WIFI_SSID = "VUPT - RL"
WIFI_PASSWORD = "ughtdoti"
HOSTNAME = "esteira"

# Usado quando a conexão com a rede Wi-Fi não está configurada ou falha.
AP_SSID = "Esteira-IA"
AP_PASSWORD = "esteira123"

HTTP_PORT = 80
MAX_STREAMS = 3

# O conector da câmera tem pinos fixos (padrão ESP32-S3-EYE / Freenove).
CAMERA_PINS = {
    "data_pins": [11, 9, 8, 10, 12, 18, 17, 16],
    "vsync_pin": 6,
    "href_pin": 7,
    "sda_pin": 4,
    "scl_pin": 5,
    "pclk_pin": 13,
    "xclk_pin": 15,
    "powerdown_pin": -1,
    "reset_pin": -1,
}
CAMERA_FRAME_SIZE = "QVGA"
CAMERA_QUALITY = 75

SONAR_TRIG = 47
SONAR_ECHO = 21

OLED_SCL = 39
OLED_SDA = 38

# GPIO7 e GPIO15 do esquemático original pertencem à câmera,
# então o buzzer e o servo foram movidos para pinos livres.
BUZZER = 46
SERVO = 14

RGB_RED = 1
RGB_GREEN = 2
RGB_BLUE = 42

BUTTON_ESTOP = 40
BUTTON_AUX = 41
