# email_to_db.py - Gmail → XAMPP MySQL Sync for Wetterstation
# ============================================================
# Reads sensor data from Gmail and stores it in XAMPP MySQL database

import imaplib
import email
import json
import mysql.connector
import time
import re
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================

# Gmail IMAP Settings
GMAIL_USER = "[INSERT GMAIL ADDRESS]"
GMAIL_PASS = "[INSERT GMAIL APP PASSWORD]"      # ← Use Gmail App Password, NOT your regular password
GMAIL_IMAP = "imap.gmail.com"
GMAIL_IMAP_PORT = 993

# XAMPP MySQL Settings
DB_HOST = "[INSERT DB IP ADDRESS]"
DB_USER = "[ISERT DB USER]"
DB_PASS = "[ISERT DB PASSWORD]"
DB_NAME = "[ISERT DB NAME]"
DB_TABLE = "[ISERT DB TABLE NAME]"

# Check for email interval (seconds)
CHECK_INTERVAL = 60

# Email search criteria
EMAIL_SEARCH = '(UNSEEN SUBJECT "wetterstation daten")'


# ============================================================
# FUNCTIONS
# ============================================================

def connect_imap():
    """Connect to Gmail IMAP server."""
    try:
        imap = imaplib.IMAP4_SSL(GMAIL_IMAP, GMAIL_IMAP_PORT)
        imap.login(GMAIL_USER, GMAIL_PASS)
        print(f"✅ IMAP Connected as {GMAIL_USER}")
        return imap
    except Exception as e:
        print(f"❌ IMAP Connection Error: {e}")
        return None

def connect_mysql():
    """Connect to XAMPP MySQL database."""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME
        )
        print(f"✅ MySQL Connected to {DB_HOST}/{DB_NAME}")
        return conn
    except Exception as e:
        print(f"❌ MySQL Connection Error: {e}")
        return None

def parse_email_body(body):
    """Extract JSON from email body (first JSON object found)."""
    try:
        # Find JSON pattern: { ... }
        match = re.search(r'\{.*\}', body, re.DOTALL)
        if match:
            json_str = match.group(0)
            data = json.loads(json_str)
            return data
    except Exception as e:
        print(f"⚠️ JSON Parse Error: {e}")
    return None

def format_timestamp(ts_str):
    """
    Convert timestamp from Pico format (DD.MM.YYYY HH:MM:SS)
    to MySQL format (YYYY-MM-DD HH:MM:SS)
    """
    try:
        # Parse: "28.01.2026 10:14:30" -> datetime object
        dt = datetime.strptime(ts_str, "%d.%m.%Y %H:%M:%S")
        # Format: "2026-01-28 10:14:30"
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"⚠️ Timestamp Format Error: {e}")
        return None

def parse_decimal(value_str):
    """
    Convert German decimal format (comma) to float.
    Example: "22,5" -> 22.5
    """
    try:
        if isinstance(value_str, str):
            return float(value_str.replace(",", "."))
        return float(value_str)
    except:
        return None

def insert_measurement(conn, data):
    """
    Insert measurement into messwert table.
    
    Expected data dict from Pico:
    {
        "mid": 1,
        "temperatur": "22,5",
        "feuchte": "45,3",
        "druck": "1013,2",
        "qualitaet": "Good",
        "gas_resistance": 50000,
        "timestamp": "28.01.2026 10:14:30"
    }
    """
    try:
        cursor = conn.cursor()
        
        # Extract and convert values
        mid = data.get("mid")
        temperatur = parse_decimal(data.get("temperatur"))
        feuchtigkeit = int(float(parse_decimal(data.get("feuchte"))))
        luftdruck = int(float(parse_decimal(data.get("druck"))))
        zeitpunkt = format_timestamp(data.get("timestamp"))
        
        # Validate required fields
        if not all([mid, temperatur is not None, feuchtigkeit, luftdruck, zeitpunkt]):
            print(f"⚠️ Missing required fields in data: {data}")
            return False
        
        # SQL Insert
        sql = f"""
            INSERT INTO {DB_TABLE} (mid, zeitpunkt, temperatur, feuchtigkeit, luftdruck)
            VALUES (%s, %s, %s, %s, %s)
        """
        
        values = (mid, zeitpunkt, temperatur, feuchtigkeit, luftdruck)
        cursor.execute(sql, values)
        conn.commit()
        
        print(f"   ✅ Stored: {zeitpunkt} - MID:{mid}, Temp: {temperatur}°C, Humidity: {feuchtigkeit}%, Pressure: {luftdruck}hPa")
        cursor.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Database Insert Error: {e}")
        return False

def check_and_sync():
    """Check Gmail for new sensor emails and sync to database."""
    print("\n" + "="*60)
    print("🌡️  Weather Station Email to MySQL Sync")
    print("="*60)
    print(f"Email: {GMAIL_USER}")
    print(f"Database: {DB_HOST}/{DB_NAME}")
    print(f"Check interval: {CHECK_INTERVAL}s")
    print("="*60)
    
    # Connect to MySQL first
    mysql_conn = connect_mysql()
    if not mysql_conn:
        print("⚠️ Cannot continue without MySQL connection")
        return False
    
    # Main loop
    try:
        while True:
            # Connect to IMAP
            imap = connect_imap()
            if not imap:
                print("⏳ Retrying in 30s...")
                time.sleep(30)
                continue
            
            try:
                # Select Gmail label as mailbox instead of INBOX
                status, _ = imap.select("wetterstation")

                # Search for unseen emails in that label
                status, email_ids = imap.search(None, "UNSEEN")

                
                # Initialize email_list to avoid undefined variable error
                email_list = []
                if status == 'OK' and email_ids[0]:
                    email_list = email_ids[0].split()
                
                if email_list:
                    print(f"\n📬 Found {len(email_list)} new email(s)")
                    print("-" * 60)
                    
                    for email_id in email_list:
                        # Fetch email
                        status, msg_data = imap.fetch(email_id, "(RFC822)")
                        
                        if status == 'OK':
                            msg = email.message_from_bytes(msg_data[0][1])
                            
                            # Extract subject
                            subject = msg.get("Subject", "No Subject")
                            print(f"\n📧 Email from: {msg.get('From', 'Unknown')}")
                            print(f"   Subject: {subject}")
                            
                            # Extract body
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/plain":
                                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                        break
                            else:
                                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                            
                            # Parse JSON from body
                            data = parse_email_body(body)
                            if data:
                                print(f"   ✅ JSON extracted")
                                
                                # Insert into database
                                if insert_measurement(mysql_conn, data):
                                    # Mark as read
                                    imap.store(email_id, '+FLAGS', '\\Seen')
                                else:
                                    print(f"   ⚠️ Failed to store in database")
                            else:
                                print(f"   ❌ No valid JSON found in email")
                else:
                    print(f"✅ No new emails (all caught up)")
                
                imap.close()
                
            except Exception as e:
                print(f"❌ IMAP Error: {e}")
                try:
                    imap.logout()
                except:
                    pass
            
            # Wait before next check
            print(f"\n⏳ Next check in {CHECK_INTERVAL}s...")
            time.sleep(CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
    finally:
        if mysql_conn.is_connected():
            mysql_conn.close()
            print("👋 MySQL connection closed")

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    check_and_sync()
