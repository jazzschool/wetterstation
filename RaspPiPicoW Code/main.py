# main.py - Raspberry Pi Pico WH Weather Station with MQTT and Email
# ====================================================================

import machine
import time
import network
import json
import umail
from bme680 import BME680_I2C
import os

from config import *

# Try importing MQTT
try:
    from umqtt.simple import MQTTClient
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    if DEBUG:
        print("⚠️ umqtt.simple not found - MQTT disabled")

# --- GLOBAL VARIABLES ---
wlan = None
mqtt_client = None
readings_since_last_email = 0

# --- STARTUP ---
print("\n" + "="*50)
print("🚀 Wetterstation startet...")
print("="*50)

# --- INITIALIZE SENSOR ---
def init_sensor():
    """Initialize BME680 sensor on I2C bus."""
    try:
        i2c = machine.I2C(0, scl=machine.Pin(SENSOR_I2C_SCL), 
                         sda=machine.Pin(SENSOR_I2C_SDA), freq=100000)
        sensor = BME680_I2C(i2c=i2c, address=0x77)
        print("✅ Sensor: BME680 on address 0x77")
        return sensor
    except Exception as e:
        if DEBUG:
            print(f"⚠️ Address 0x77 failed: {e}")
        try:
            i2c = machine.I2C(0, scl=machine.Pin(SENSOR_I2C_SCL), 
                             sda=machine.Pin(SENSOR_I2C_SDA), freq=100000)
            sensor = BME680_I2C(i2c=i2c, address=0x76)
            print("✅ Sensor: BME680 on address 0x76")
            return sensor
        except Exception as e2:
            print(f"❌ Sensor Error: {e2}")
            return None

# --- INITIALIZE WLAN ---
def wifi_ok():
    return wlan is not None and wlan.isconnected()

def init_wlan():
    """Initialize WiFi connection."""
    global wlan
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if DEBUG:
        print(f"📡 WiFi: Initializing...")
    return wlan

# --- WIFI CONNECTION ---
def connect_wifi():
    """Connect to WiFi network."""
    if wlan.isconnected():
        if DEBUG:
            print("✅ WiFi: Already connected")
        return True
    
    print(f"📡 WiFi: Connecting to {WIFI_SSID}...")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    
    for attempt in range(20):
        if wlan.isconnected():
            ip_info = wlan.ifconfig()
            print(f"✅ WiFi: Connected!")
            print(f"   IP: {ip_info[0]}")
            return True
        time.sleep(0.5)
    
    print("❌ WiFi: Connection failed")
    return False

# --- MQTT INITIALIZATION ---
def init_mqtt():
    """Initialize and connect to MQTT broker."""
    global mqtt_client
    
    if not MQTT_ENABLE or not MQTT_AVAILABLE:
        return None
    
    if not wlan.isconnected():
        if DEBUG:
            print("⚠️ MQTT: WiFi not connected, skipping")
        return None
    
    try:
        print("🔌 MQTT: Connecting to broker...")
        mqtt_client = MQTTClient(
            client_id=MQTT_CLIENT_ID,
            server=MQTT_SERVER,
            port=MQTT_PORT,
            user=MQTT_USER,
            password=MQTT_PASSWORD,
            keepalive=MQTT_KEEPALIVE,
            ssl=MQTT_SSL
        )
        mqtt_client.connect()
        print(f"✅ MQTT: Connected to {MQTT_SERVER.decode()}")
        return mqtt_client
    except Exception as e:
        print(f"❌ MQTT Error: {e}")
        return None

# --- MQTT PUBLISH ---
def publish_mqtt(topic, payload):
    """Publish message to MQTT broker."""
    global mqtt_client
    
    if not MQTT_ENABLE or mqtt_client is None:
        return False
    
    try:
        # Construct full topic
        full_topic = MQTT_TOPIC_PREFIX + b"/" + topic.encode() if isinstance(topic, str) else MQTT_TOPIC_PREFIX + b"/" + topic
        
        # Ensure payload is bytes
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload).encode()
        elif isinstance(payload, str):
            payload = payload.encode()
        
        mqtt_client.publish(full_topic, payload)
        if DEBUG:
            print(f"📤 MQTT: Published to {full_topic.decode()}")
        return True
    except Exception as e:
        print(f"❌ MQTT Publish Error: {e}")
        return False

# --- MQTT RECONNECT ---
def reconnect_mqtt():
    """Attempt to reconnect to MQTT broker if disconnected."""
    global mqtt_client
    
    if not MQTT_ENABLE or not MQTT_AVAILABLE:
        return False
    
    if mqtt_client is None:
        return init_mqtt() is not None
    
    try:
        mqtt_client.ping()
        return True
    except Exception:
        if DEBUG:
            print("⚠️ MQTT: Connection lost, reconnecting...")
        mqtt_client = None
        return init_mqtt() is not None

# --- EMAIL SENDING (INDEPENDENT) ---

def save_email_locally(subject, body, data):
    """Save unsent email as JSON file on the Pico."""
    try:
        # Make sure base folder exists
        base_dir = "unsent"
        if base_dir not in os.listdir():
            os.mkdir(base_dir)

        # Use timestamp from data if available, else current time
        ts = data.get("timestamp", None)
        if ts is None:
            t = time.localtime()
            ts = "{:04d}-{:02d}-{:02d}_{:02d}-{:02d}-{:02d}".format(
                t[0], t[1], t[2], t[3], t[4], t[5]
            )
        else:
            # convert "DD.MM.YYYY HH:MM:SS" -> "YYYY-MM-DD_HH-MM-SS"
            # safe minimal conversion so filename has no spaces/colons
            try:
                day, month, year_time = ts.split(".")
                year, time_part = year_time.split(" ", 1)
                time_part = time_part.replace(":", "-")
                ts = "{}-{}-{}_{}".format(year, month, day, time_part)
            except:
                ts = ts.replace(" ", "_").replace(":", "-")

        # Unique filename: mid + timestamp
        fname = "unsent_{}_{}.json".format(MID, ts)
        path = "{}/{}".format(base_dir, fname)

        payload = {
            "subject": subject,
            "body": body,
            "data": data,
        }

        # Write JSON string to file
        json_str = json.dumps(payload)
        with open(path, "w") as f:
            f.write(json_str)

        if DEBUG:
            print("💾 Saved unsent email to", path)
        return True
    except Exception as e:
        print("❌ Failed to save email locally:", e)
        return False

def send_email(subject, body, data):
    """Send email via Gmail SMTP.

    Tries all EMAIL_RECIPIENTS in order until one works.
    If WiFi/server not reachable, save to local file.
    """
    if not EMAIL_ENABLE:
        return False

    # No WiFi? Save locally immediately.
    if not wifi_ok():
        if DEBUG:
            print("❌ No WiFi, saving email locally instead of sending")
        save_email_locally(subject, body, data)
        return False

    # Make sure we have a list of recipients
    try:
        recipients = EMAIL_RECIPIENTS
    except NameError:
        # Backwards compatibility: single EMAIL_TO
        recipients = [EMAIL_TO]

    last_error = None
    sent_ok = False

    for addr in recipients:
        try:
            if DEBUG:
                print("📧 Email: Attempting to send to", addr, "...")

            smtp = umail.SMTP(SMTP_SERVER, SMTP_PORT, ssl=False)
            smtp.cmd("STARTTLS")
            smtp.login(SMTP_USER, SMTP_PASS)

            smtp.to(addr)
            smtp.write("From: " + SMTP_FROM + "\r\n")
            smtp.write("To: " + addr + "\r\n")
            smtp.write("Subject: " + subject + "\r\n")
            smtp.write("Content-Type: text/plain; charset=utf-8\r\n\r\n")
            smtp.write(body)

            smtp.send()
            smtp.quit()

            print("✅ Email: Sent successfully to", addr)
            sent_ok = True
            break  # stop after first success

        except Exception as e:
            last_error = e
            print("❌ Email Error to", addr, ":", e)
            # Try next address in the list

    if not sent_ok:
        # All recipients failed despite WiFi being up → save locally
        if DEBUG:
            print("⚠️ All email recipients failed, saving locally")
        save_email_locally(subject, body, data)
        return False

    return True


# --- SENSOR READING ---
def read_sensor(sensor):
    """Read data from BME680 sensor and return as JSON dict."""
    if sensor is None:
        return None
    
    try:
        # READ ACTUAL VALUES FROM SENSOR
        temp = sensor.temperature
        hum = sensor.humidity
        press = sensor.pressure
        gas = sensor.gas  # Gas resistance in Ohms
        
        # Get current time
        t = time.localtime()
        timestamp_str = "{:02d}.{:02d}.{:04d} {:02d}:{:02d}:{:02d}".format(
            t[2], t[1], t[0], t[3], t[4], t[5]
        )
        
        # Print to console
        if DEBUG:
            print("="*50)
            print(f"Temperatur: {temp:.1f} °C")
            print(f"Feuchte:    {hum:.1f} %")
            print(f"Druck:      {press:.1f} hPa")
            print(f"Gas:        {gas} Ohms")
            print(f"Zeit:       {timestamp_str}")
            print("="*50)
        
        # Calculate air quality from gas resistance
        # Lower ohms = worse air quality
        if gas > 100000:
            quality = "Excellent"
        elif gas > 50000:
            quality = "Good"
        elif gas > 25000:
            quality = "Moderate"
        elif gas > 10000:
            quality = "Poor"
        else:
            quality = "Very Poor"
        
        # Create data dictionary with ACTUAL sensor values
        data = {
            "mid": MID,
            "temperatur": "{:.1f}".format(temp).replace(".", ","),
            "feuchte": "{:.1f}".format(hum).replace(".", ","),
            "druck": "{:.1f}".format(press).replace(".", ","),
            "qualitaet": quality,
            "gas_resistance": gas,
            "timestamp": timestamp_str
        }
        
        return data
    except Exception as e:
        print(f"❌ Sensor Error: {e}")
        return None

# --- FORMAT EMAIL BODY (JSON) ---
def format_email_body(data):
    """Format sensor data as JSON in email body."""
    # MicroPython json.dumps doesn't support indent parameter
    json_body = json.dumps(data)
    
    body = json_body
    
    return body

# --- MAIN EXECUTION ---
def main():
    """Main application loop."""
    global readings_since_last_email, mqtt_client
    
    # Initialize hardware
    sensor = init_sensor()
    if sensor is None:
        print("❌ Cannot continue without sensor!")
        return
    
    wlan_obj = init_wlan()
    
    # Connect to WiFi
    if not connect_wifi():
        print("❌ Cannot continue without WiFi!")
        return
    
    # Initialize MQTT (optional - doesn't block startup)
    if MQTT_ENABLE:
        mqtt_client = init_mqtt()
        if mqtt_client is None and DEBUG:
            print("⚠️ MQTT not available, but email will still work!")
    
    print("\n" + "="*50)
    print("✅ System ready - starting measurements")
    print("="*50 + "\n")
    
    # Main loop
    loop_count = 0
    
    try:
        while True:
            loop_count += 1
            
            # Read sensor with ACTUAL VALUES
            data = read_sensor(sensor)
            if data is None:
                print("⚠️ Sensor read failed, retrying...")
                time.sleep(READ_INTERVAL)
                continue
            
            # --- MQTT Publishing (OPTIONAL) ---
            # MQTT failures do NOT block email sending
            mqtt_published = False
            if MQTT_ENABLE and MQTT_AVAILABLE:
                # Try reconnect every 10 readings
                if loop_count % 10 == 0:
                    if mqtt_client is None:
                        reconnect_mqtt()
                
                # Publish individual readings
                if mqtt_client is not None:
                    try:
                        publish_mqtt("temperature", data['temperatur'])
                        publish_mqtt("humidity", data['feuchte'])
                        publish_mqtt("pressure", data['druck'])
                        publish_mqtt("quality", data['qualitaet'])
                        publish_mqtt("gas_resistance", str(data['gas_resistance']))
                        
                        # Publish complete JSON
                        publish_mqtt("data", data)
                        mqtt_published = True
                    except Exception as e:
                        if DEBUG:
                            print(f"⚠️ MQTT publish error: {e}")
                        mqtt_client = None
            
            # --- EMAIL Sending (INDEPENDENT) ---
            # Emails are sent REGARDLESS of MQTT status
            readings_since_last_email += 1
            
            if EMAIL_ENABLE and readings_since_last_email >= EMAIL_INTERVAL:
                if DEBUG:
                    print(f"📧 Email: Sending (every {EMAIL_INTERVAL} readings)...")
                subject = f"Wetterstation Update {data['timestamp']}"
                body = format_email_body(data)
                email_sent = send_email(subject, body, data)

                
                # Only reset counter if email succeeded
                if email_sent:
                    readings_since_last_email = 0
                else:
                    # Keep trying - will retry on next cycle
                    if DEBUG:
                        print("⚠️ Email failed, will retry next cycle")
            
            # Wait before next reading
            if DEBUG:
                print(f"⏳ Next reading in {READ_INTERVAL}s (Loop #{loop_count})")
                if MQTT_ENABLE and mqtt_client is None:
                    print("   ⚠️ MQTT: Not connected (email still working)")
                print()
            
            time.sleep(READ_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n⏹️ Stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import sys
        sys.print_exception(e)
    finally:
        if mqtt_client is not None:
            try:
                mqtt_client.disconnect()
            except:
                pass
        print("\n👋 Shutdown complete")

# --- RUN ---
if __name__ == "__main__":
    main()
