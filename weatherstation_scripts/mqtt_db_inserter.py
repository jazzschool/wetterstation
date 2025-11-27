import paho.mqtt.client as mqtt
import json
import mysql.connector
import time

# MariaDB config
db_config = {
    'user': 'admin'
    'password': '54tzck23'
    'host': 'localhost',
    'database': 'weather'
}

# MQTT config
MQTT_BROKER = "localhost"
MQTT_PORT = 1884
MQTT_TOPIC = "weatherstation/bme60"
MQTT_USER = "weatheruser"
MQTT_PASSWORD = "54tzck23"

def insert_data(data):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = ("INSERT INTO sensor_data "
                 "(timestamp, temperature_c, pressure_hpa, humidity_percent) "
                 "VALUES (%s, %s, %s, %s)")
        vals = (data['zeitpunkt'], data['temperatur'], data['luftdruck_hpa'], data['luftfeuchtigkeit_percent'])
        cursor.execute(query, vals)
        conn.commit()
        cursor.close()
        conn.close()
        print("Data inserted into MariaDB.")
    except Exception as e:
        print("Failed to insert data:" e)
        
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    client.subscribe(MQTT_TOPIC)
    
def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        print("Recieved data:", data)
        insert_data(data)
    except Exception as e:
        print("Error processing message:" e)
        
client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_forever()