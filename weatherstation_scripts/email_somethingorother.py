import paho.mqtt.clients as mqtt
import json
import smtplib
from email.mime.text import MIMEText

# MQTT
MQTT_BROKER = "localhost"
MQTT_PORT = 1884
MQTT_TOPIC = "weatherstation/bme60"
MQTT_USER = "weatheruser"
MQTT_PASSWORD = "54tzck23"

# Email Config
SMTP_SERVER = 'smtp.mailgun.org'
SMTP_PORT = 587
SMTP_USER = 'Admin@sandboxac032464eaf545eab70dbad9b2bdd6f6.mailgun.org'
SMTP_PASS = '54tzck23'
EMAIL_TO = 'account_dumdum@protonmail.com'

def send_email(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] =
    
    try:
        smtp_server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        smtp_server.starttls()
        smtp_server.login(SMTP_USER, SMTP_PASS)
        smtp_server.send_message(msg)
        smtp_server.quit()
        print('Email sent')
    except Exception as e:
        print('failed to send email:', e)
        
def on_connect(cient, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        print("Recieved data for email:", data)
        subject = "Wetterstationsdaten Update"
        body = f"Temperatur: {data['temperatur']} °C\nLuftdruck: {data['luftdruck_hpa']} hPa\nFeuchtigkeit; {data['feuchtigkeit_percent']} %"
        send_email(subject, body)
    except Exception as e:
        print("Error processing message:", e)
        
client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_forever()
