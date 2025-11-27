# configuration variables for Pico W weather station

# WLAN
WIFI_SSID = "dd-wrt"
WIFI_PASSWORD = "54tzck23"

# MQTT
MQTT_SERVER = "192.168.1.119"
MQTT_CLIENT_ID = "Jasmin"
MQTT_TOPIC = "weatherstation/bme680"
MQTT_USER = "weatheruser"
MQTT_PASSWORD = "54tzck23"

# Sensors & Reading Interval
SENSOR_I2C_SDA = 4
SENSOR_I2C_SCL = 5
READ_INTERVAL = 60
