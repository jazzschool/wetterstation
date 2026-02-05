# config.py - Wetterstation Configuration
# ============================================

# --- WLAN ---
WIFI_SSID = "dd-wrt"
WIFI_PASSWORD = "54tzck23"



# --- SENSOR ---
SENSOR_I2C_SDA = 4
SENSOR_I2C_SCL = 5
READ_INTERVAL = 60  # seconds between readings



# --- MQTT Configuration ---
MQTT_ENABLE = True
MQTT_SERVER = b"192.168.1.119"         # Your MQTT broker IP
MQTT_PORT = 1883
MQTT_USER = b"weatheruser"             # MQTT broker username
MQTT_PASSWORD = b"54tzck23"            # MQTT broker password
MQTT_CLIENT_ID = b"pico-weatherstation-1"
MQTT_SSL = False
MQTT_KEEPALIVE = 60
MQTT_TOPIC_PREFIX = b"weatherstation"  # Base topic



# --- EMAIL Configuration ---
EMAIL_ENABLE = True

# List of recipients to try in order
EMAIL_RECIPIENTS = [
    "[INSERT EMAIL RECIPIENTS]",
]

EMAIL_INTERVAL = 5  # Send email every N readings


# --- GMAIL SMTP ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "[INSERT GMAIL ADDRESS]"
SMTP_PASS = "[INSERT GMAIL APP PASSWORD]"
SMTP_FROM = "[INSERT GMAIL READING ADDRESS"



# --- DEVICE ID ---
MID = 1  # Measurement/Device ID



# --- DEBUG ---
DEBUG = True  # Print debug messages



# --- SENSOR QUALITY ---
# Dynamically calculated from sensor.gas in main.py
# These are just defaults if calculation fails
SENSOR_QUALITY_GOOD = 0
SENSOR_QUALITY_MODERATE = 50
SENSOR_QUALITY_UNHEALTHY = 200
