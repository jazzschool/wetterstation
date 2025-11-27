import machine
import time
import network
from umqtt.simple import MQTTClient
from bme680 import BME680_I2C # Benötigt bme680.py
from config import *

# To Publish on Linux Terminal:
# mosquitto_sub -h localhost -p 1884 -t "weatherstation/bme680" -u weatheruser -P 54tzck23 -v


# --- STARTUP ---

# 1 - Initialisiere I2C Bus und Sensor
try:
    i2c = machine.I2C(0, scl=machine.Pin(SENSOR_I2C_SCL), sda=machine.Pin(SENSOR_I2C_SDA), freq=100000)
    sensor = BME680_I2C(i2c=i2c, address=0x77)  # Versuche 0x77 zuerst
    print(f"BME680 auf I2C initialisiert (SCL=GP{SENSOR_I2C_SCL}, SDA=GP{SENSOR_I2C_SDA}).")
except Exception as e:
    print(f"Fehler bei Initialisierung BME680 auf 0x77: {e}")
    print("Versuche alternative I2C-Adresse 0x76...")
    try:
        sensor = BME680_I2C(i2c=i2c, address=0x76)
        print("BME680 auf Adresse 0x76 initialisiert")
    except Exception as e2:
        print(f"Fehler bei beiden Adressen: {e2}")


# 2 - Initialisiere Netzwerk-Schnittstelle
wlan = network.WLAN(network.STA_IF)
wlan.active(True)




# --- FUNKTIONEN ---

def connect_to_wifi():
    """Verbindet mit dem angegebenen WLAN."""
    if wlan.isconnected():
        status = wlan.ifconfig()
        print("Bereits mit WLAN verbunden.")
        print("Pico W IP-Adresse:", status[0])
        return True

    print(f"Verbinde mit WLAN: {WIFI_SSID}")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    max_wait = 20
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        time.sleep(0.4)
        max_wait -= 1

    if wlan.status() != 3:
        print("WLAN-Verbindung fehlgeschlagen oder Zeitüberschreitung.")
        return False

    status = wlan.ifconfig()
    print(f"Verbindung erfolgreich! IP-Adresse: {status[0]}")
    return True

def connect_and_publish(client, data_json):
    """Verbindet zum MQTT Broker und sendet die Daten."""
    try:
        client.connect()
        print(f"Verbunden mit MQTT Broker: {MQTT_SERVER}\n")
        
        print(f"Veröffentliche auf Thema '{MQTT_TOPIC}': \n{data_json} \n")
        client.publish(MQTT_TOPIC, data_json)
        print("Veröffentlichung erfolgreich.")
        
        client.disconnect()

    except OSError as e:
        print(f"MQTT Verbindung oder Veröffentlichung fehlgeschlagen: {e}")
    except Exception as e:
        print(f"Unerwarteter Fehler bei MQTT: {e}")

def read_bme680_data():
    """Liest Temperatur, Druck und Luftfeuchtigkeit vom BME680 Sensor."""
    try:
        temp = sensor.temperature
        press = sensor.pressure
        hum = sensor.humidity
        
        print()
        print("========================================")
        print(f"- Temperatur: {temp:.2f} °C")
        print(f"- Luftdruck: {press:.2f} hPa")
        print(f"- feuchtigkeit: {hum:.2f} %")
        print("========================================")
        print()

        data = {
            "zeitpunkt": time.time(),
            "temperatur": round(temp, 2),
            "luftdruck_hpa": round(press, 2),
            "feuchtigkeit_percent": round(hum, 2)
        }
        import json
        return json.dumps(data)

    except Exception as e:
        print(f"Fehler beim Lesen der Sensordaten: {e}")
        return None




# --- HAUPTSCHLEIFE ---

if connect_to_wifi():
    try:
        mqtt_client = MQTTClient(
            client_id=MQTT_CLIENT_ID,
            server=MQTT_SERVER,
            port=1884,  # Port 1884 verwenden (nicht Standard 1883)
            user=MQTT_USER,
            password=MQTT_PASSWORD,
            keepalive=60
        )
        print("MQTT Client initialisiert.")
    except Exception as e:
        print(f"Initialisierung des MQTTClient fehlgeschlagen: {e}")
        mqtt_client = None
else:
    mqtt_client = None

while True:
    try:
        data_json = read_bme680_data()

        if mqtt_client and data_json:
            connect_and_publish(mqtt_client, data_json)
        else:
            print("⚠ Kein MQTT Client oder keine Daten verfügbar. Überspringe Veröffentlichung.")

    except Exception as e:
        print(f"Kritischer Fehler in der Hauptschleife: {e}. Versuche WLAN-Verbindung neu.")
        if not connect_to_wifi():
            print("Verbindung fehlgeschlagen. Warte 10 Sekunden...")
            time.sleep(10)
            continue

    print(f"{READ_INTERVAL} Sekunden bis zur nächsten Messung...")
    time.sleep(READ_INTERVAL)
