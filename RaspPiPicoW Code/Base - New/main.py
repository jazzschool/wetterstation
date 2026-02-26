import time
import json
import network
from machine import Pin, I2C
from bme680 import BME680_I2C
from umail import SMTP

# ===============================
# WLAN
# ===============================
WIFI_SSID = "dd-wrt"
WIFI_PASSWORD = "54tzck23"

# ===============================
# Sensor-ID
# ===============================
SENSOR_MID = 1  # eindeutige ID des Sensors

# ===============================
# E-Mail
# ===============================
EMAIL_ENABLED = True
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_SENDER_EMAIL = "jazz.kiewicz@gmail.com"
SMTP_APP_PASSWORD = "muurnoakhmehjhuj"
EMAIL_RECIPIENT = "wetter.station.2026@fds-limburg.schule"
EMAIL_SUBJECT = "🌡 Wetterstation BME680 JSON"

# ===============================
# Cache
# ===============================
CACHE_FILE = "cache.json"

# ===============================
# WLAN verbinden
# ===============================
def connect_wlan():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("📡 WLAN verbinden...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
    if wlan.isconnected():
        print("✅ WLAN verbunden:", wlan.ifconfig())
        return True
    else:
        print("⚠ WLAN nicht verbunden, Offline-Modus")
        return False

# ===============================
# E-Mail senden
# ===============================
def send_email(data_list):
    try:
        smtp = SMTP(
            SMTP_SERVER,
            SMTP_PORT,
            username=SMTP_SENDER_EMAIL,
            password=SMTP_APP_PASSWORD,
            ssl=True
        )
        payload = json.dumps(data_list)
        msg = (
            "Subject: {}\r\n"
            "To: {}\r\n"
            "From: {}\r\n"
            "Content-Type: application/json\r\n\r\n{}"
        ).format(
            EMAIL_SUBJECT,
            EMAIL_RECIPIENT,
            SMTP_SENDER_EMAIL,
            payload
        )
        smtp.to(EMAIL_RECIPIENT, mail_from=SMTP_SENDER_EMAIL)
        smtp.send(msg.encode("utf-8"))
        smtp.quit()
        print("📧 E-Mail gesendet:", payload)

        # Cache nach Versand leeren
        with open(CACHE_FILE, "w") as f:
            f.write("[]")

    except Exception as e:
        print("❌ Fehler beim Senden, speichere in Cache:", e)
        # Cache speichern
        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
        except:
            cache = []
        cache += data_list
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)

# ===============================
# Sensor initialisieren
# ===============================
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)
sensor = BME680_I2C(i2c)

# ===============================
# Start
# ===============================
internet = connect_wlan()
print("▶ Wetterstation gestartet")

# ===============================
# Hauptschleife
# ===============================
while True:
    # Timestamp im MySQL-kompatiblen Format
    t = time.localtime()
    timestamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        t[0], t[1], t[2], t[3], t[4], t[5]
    )

    # Aktuelle Messung
    data = {
        "mid": SENSOR_MID,
        "temperatur": float(sensor.temperature),
        "feuchte": float(sensor.humidity),
        "druck": float(sensor.pressure),
        "qualitaet": float(sensor.gas),
        "timestamp": timestamp
    }

    if internet and EMAIL_ENABLED:
        # Internet da → direkt senden
        send_email([data])
    else:
        # Offline → Cache speichern
        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
        except:
            cache = []
        cache.append(data)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
        print("⚠ Keine Internetverbindung, Messung in Cache gespeichert")

    # Messintervall
    time.sleep(60)
