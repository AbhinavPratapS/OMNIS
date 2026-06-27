
import datetime
import threading
import time
import json
import os
import wave
import math
import struct
import subprocess
import config
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CITY_TIMEZONES = {
    # India
    "mumbai": "Asia/Kolkata",
    "delhi": "Asia/Kolkata",
    "new delhi": "Asia/Kolkata",
    "kolkata": "Asia/Kolkata",
    "chennai": "Asia/Kolkata",
    "bangalore": "Asia/Kolkata",
    "bengaluru": "Asia/Kolkata",
    "hyderabad": "Asia/Kolkata",
    "pune": "Asia/Kolkata",
    "ahmedabad": "Asia/Kolkata",
    "jaipur": "Asia/Kolkata",
    "surat": "Asia/Kolkata",
    # USA
    "new york": "America/New_York",
    "boston": "America/New_York",
    "miami": "America/New_York",
    "atlanta": "America/New_York",
    "washington": "America/New_York",
    "chicago": "America/Chicago",
    "houston": "America/Chicago",
    "dallas": "America/Chicago",
    "denver": "America/Denver",
    "phoenix": "America/Phoenix",
    "los angeles": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles",
    "seattle": "America/Los_Angeles",
    "las vegas": "America/Los_Angeles",
    # Canada
    "toronto": "America/Toronto",
    "vancouver": "America/Vancouver",
    # Latin America
    "mexico city": "America/Mexico_City",
    "sao paulo": "America/Sao_Paulo",
    "buenos aires": "America/Argentina/Buenos_Aires",
    # Europe
    "london": "Europe/London",
    "paris": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "amsterdam": "Europe/Amsterdam",
    "rome": "Europe/Rome",
    "madrid": "Europe/Madrid",
    "moscow": "Europe/Moscow",
    "istanbul": "Europe/Istanbul",
    # Middle East / Africa / South Asia
    "dubai": "Asia/Dubai",
    "riyadh": "Asia/Riyadh",
    "tehran": "Asia/Tehran",
    "karachi": "Asia/Karachi",
    "islamabad": "Asia/Karachi",
    "lahore": "Asia/Karachi",
    "cairo": "Africa/Cairo",
    "nairobi": "Africa/Nairobi",
    "johannesburg": "Africa/Johannesburg",
    "dhaka": "Asia/Dhaka",
    # Asia-Pacific
    "tokyo": "Asia/Tokyo",
    "seoul": "Asia/Seoul",
    "beijing": "Asia/Shanghai",
    "shanghai": "Asia/Shanghai",
    "hong kong": "Asia/Hong_Kong",
    "taipei": "Asia/Taipei",
    "singapore": "Asia/Singapore",
    "kuala lumpur": "Asia/Kuala_Lumpur",
    "jakarta": "Asia/Jakarta",
    "bangkok": "Asia/Bangkok",
    "sydney": "Australia/Sydney",
    "melbourne": "Australia/Melbourne",
    "auckland": "Pacific/Auckland",
}

timers = {}
alarms = {}
alarm_process = None
alarm_lock = threading.Lock()


def save_data():
    data = {
        "timers": timers,
        "alarms": alarms
    }

    with open(config.PERSISTENCE_FILE, "w") as file:
        json.dump(data, file, indent=4)

def load_timers_and_alarms():
    global timers, alarms

    if not os.path.exists(config.PERSISTENCE_FILE):
        save_data()

    try:
        with open(config.PERSISTENCE_FILE, "r") as file:
            content = file.read().strip()

            if not content:
                save_data()
                return

            data = json.loads(content)

            timers = data.get("timers", {})
            alarms = data.get("alarms", {})

    except (json.JSONDecodeError, KeyError, TypeError):
        save_data()

def set_timer(name, duration):
    end_time = time.time() + duration

    timers[name] = {
        "duration": duration,
        "end_time": end_time
    }

    save_data()

    return f"Timer '{name}' set for {duration} seconds."

def check_timer(name):
    if name not in timers:
        return "Timer not found."

    remaining = int(timers[name]["end_time"] - time.time())

    return f"{remaining} seconds remaining on timer '{name}'."

def list_timers():
    if not timers:
        return "No active timers."

    return ", ".join(timers.keys())

def cancel_timer(name):
    if name in timers:
        del timers[name]
        save_data()
        return f"Cancelled timer '{name}'."

    return "Timer not found."

def cancel_all_timers():
    timers.clear()
    save_data()
    return "All timers cancelled."

def set_alarm(time_str, label="alarm"):
    alarms[label] = {"time": time_str}
    save_data()
    try:
        friendly = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M").strftime("%I:%M %p")
    except ValueError:
        friendly = time_str
    return f"Alarm '{label}' set for {friendly}."

def cancel_alarm(label="alarm"):
    if label in alarms:
        del alarms[label]
        save_data()
        return f"Alarm '{label}' cancelled."
    return f"No alarm named '{label}' found."

def list_alarms():
    if not alarms:
        return "No active alarms."
    parts = [f"'{lbl}' at {data['time']}" for lbl, data in alarms.items()]
    return "Active alarms: " + ", ".join(parts) + "."

def ensure_alarm_sound_exists():
    filepath = config.ALARM_SOUND
    if os.path.exists(filepath):
        return

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    sample_rate = 44100.0
    freq = 600.0
    duration = 1.5

    try:
        with wave.open(filepath, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(int(sample_rate))

            num_samples = int(duration * sample_rate)
            for i in range(num_samples):
                ms = (i / sample_rate) * 1000.0
                cycle_time = ms % 350.0

                if cycle_time < 250.0:
                    amp = 1.0
                    if cycle_time < 20.0:
                        amp = cycle_time / 20.0
                    elif cycle_time > 230.0:
                        amp = (250.0 - cycle_time) / 20.0

                    val = math.sin(2.0 * math.pi * freq * (i / sample_rate))
                    val += 0.4 * math.sin(2.0 * math.pi * (freq * 2.0) * (i / sample_rate))
                    val = max(-1.0, min(1.0, val * amp))

                    packed_val = struct.pack('<h', int(val * 16384.0))
                else:
                    packed_val = struct.pack('<h', 0)
                wav_file.writeframesraw(packed_val)
    except Exception as e:
        print(f"Error generating alarm sound: {e}")

def play_alarm_sound():
    global alarm_process
    ensure_alarm_sound_exists()

    with alarm_lock:
        if alarm_process is not None:
            return

        try:
            def loop_alarm():
                global alarm_process
                while alarm_process is not None:
                    p = subprocess.Popen(["pw-play", config.ALARM_SOUND], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    # Wait for completion or break if stopped
                    p.wait()
                    time.sleep(0.5)

            alarm_process = "ACTIVE"
            threading.Thread(target=loop_alarm, daemon=True).start()

        except Exception as e:
            print(f"Failed to play alarm via PipeWire: {e}")

def stop_timer_sound():
    global alarm_process
    with alarm_lock:
        if alarm_process is not None:
            alarm_process = None
            try:
                subprocess.run(["pkill", "-f", f"pw-play {config.ALARM_SOUND}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error stopping alarm process: {e}")


def timer_checker():
    while True:
        current_time = time.time()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # Check timers
        expired_timers = []
        for name, timer_data in list(timers.items()):
            if current_time >= timer_data["end_time"]:
                print(f"Timer '{name}' finished.")
                play_alarm_sound()
                expired_timers.append(name)
        for name in expired_timers:
            del timers[name]
        if expired_timers:
            save_data()

        # Check alarms
        expired_alarms = []
        for label, alarm_data in list(alarms.items()):
            if alarm_data["time"] == now_str:
                print(f"Alarm '{label}' triggered.")
                from ai.ai_response import speak
                speak(f"Alarm: {label}")
                play_alarm_sound()
                expired_alarms.append(label)
        for label in expired_alarms:
            del alarms[label]
        if expired_alarms:
            save_data()

        time.sleep(1)

def get_current_time(city="Mumbai"):
    tz_name = CITY_TIMEZONES.get(city.lower().strip())
    try:
        now = datetime.datetime.now(ZoneInfo(tz_name)) if tz_name else datetime.datetime.now()
    except ZoneInfoNotFoundError:
        now = datetime.datetime.now()
    return now.strftime(f"The time in {city} is %I:%M %p.")

def get_current_date():
    now = datetime.datetime.now()
    return now.strftime("Today's date is %A, %d %B %Y.")

def start_scheduler():
    ensure_alarm_sound_exists()
    load_timers_and_alarms()

    from modules.reminders import init_db, start_reminder_checker
    init_db()
    start_reminder_checker()

    threading.Thread(
        target=timer_checker,
        daemon=True
    ).start()
