
import sqlite3
import datetime
import threading
import time
import os

DB_NAME = "assets/reminders.db"

def init_db():
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT,
        time TEXT
    )
    ''')

    conn.commit()
    conn.close()

def add_reminder(message, reminder_time):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO reminders (message, time) VALUES (?, ?)",
        (message, reminder_time)
    )

    conn.commit()
    conn.close()

def get_reminders():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM reminders")

    reminders = cursor.fetchall()

    conn.close()

    return reminders

def check_reminders():
    while True:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM reminders WHERE time=?",
            (now,)
        )

        due = cursor.fetchall()

        if due:
            # Local import to avoid circular dependency
            from ai.ai_response import speak
            for reminder in due:
                msg = f"Reminder: {reminder[1]}"
                print(msg)
                speak(msg)
                
                # Delete reminder so it only triggers once
                cursor.execute("DELETE FROM reminders WHERE id=?", (reminder[0],))
            conn.commit()

        conn.close()

        # Check every 30 seconds
        time.sleep(30)

def start_reminder_checker():
    threading.Thread(target=check_reminders, daemon=True).start()


