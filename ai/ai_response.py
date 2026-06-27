
import threading
import pyttsx3
import google.generativeai as genai
import config
import os
import re
import datetime
import subprocess

from modules.web_scraper import search_bing
from modules.time_module import *
from modules.musicplayer import *
from modules.reminders import *

# Gemini API setup
genai.configure(api_key=config.GEMINI_API_KEY)

# PipeWire Asynchronous TTS Playback Engine
tts_process = None
tts_lock = threading.Lock()

def speak(text):
    global tts_process
    
    def _speak():
        global tts_process
        speech_file = "assets/speech.wav"
        os.makedirs(os.path.dirname(speech_file), exist_ok=True)
        
        # Stop any active speaking before starting new
        stop_speaking()
        
        with tts_lock:
            try:
                # Initialize a local pyttsx3 engine in this thread to avoid cross-thread access bugs
                local_engine = pyttsx3.init()
                local_engine.setProperty('rate', 150)
                local_engine.save_to_file(text, speech_file)
                local_engine.runAndWait()
                
                # Asynchronously play the spoken text WAV file via native PipeWire pw-play
                tts_process = subprocess.Popen(
                    ["pw-play", speech_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception as e:
                print(f"Error in speech synthesis/playback: {e}")
                
    threading.Thread(target=_speak, daemon=True).start()

def stop_speaking():
    global tts_process
    with tts_lock:
        if tts_process is not None:
            try:
                tts_process.terminate()
                tts_process.wait(timeout=0.5)
            except Exception:
                pass
            tts_process = None

# Local Parser Helpers
def text_to_number(text):
    words = text.lower().replace("-", " ").strip().split()
    
    num_dict = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
        "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
        "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
        "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
        "ninety": 90, "hundred": 100, "thousand": 1000
    }

    total = 0
    current = 0
    for w in words:
        if w in num_dict:
            val = num_dict[w]
            if val == 100:
                current = (current if current != 0 else 1) * 100
            elif val == 1000:
                total += (current if current != 0 else 1) * 1000
                current = 0
            else:
                current += val
        elif w == "and":
            continue
        else:
            try:
                current += int(w)
            except ValueError:
                pass
    total += current
    return total if total > 0 else None

def parse_duration_to_seconds(duration_str):
    duration_str = duration_str.lower().strip()
    
    if "half an hour" in duration_str:
        return 1800
    if "an hour" in duration_str or "one hour" in duration_str:
        return 3600
        
    pattern = r"([\w\s\.]+)\s*(second|minute|hour)s?"
    matches = re.findall(pattern, duration_str)
    
    if not matches:
        # Check if they just said a bare number like "timer for 10" (default to minutes)
        val = text_to_number(duration_str)
        if val is not None:
            return val * 60
        return None
        
    total_seconds = 0
    for val_str, unit in matches:
        val_str = val_str.strip()
        val = None
        try:
            val = float(val_str)
        except ValueError:
            val = text_to_number(val_str)
            
        if val is None:
            continue
            
        if "second" in unit:
            total_seconds += val
        elif "minute" in unit:
            total_seconds += val * 60
        elif "hour" in unit:
            total_seconds += val * 3600
            
    return int(total_seconds) if total_seconds > 0 else None

def parse_reminder_time(time_str):
    time_str = time_str.lower().strip()
    now = datetime.datetime.now()
    
    # 1. Check relative duration "in X"
    if time_str.startswith("in "):
        duration_str = time_str[3:]
        seconds = parse_duration_to_seconds(duration_str)
        if seconds:
            reminder_time = now + datetime.timedelta(seconds=seconds)
            return reminder_time.strftime("%Y-%m-%d %H:%M")
            
    # 2. Check absolute time "at HH:MM [AM/PM]"
    if time_str.startswith("at "):
        time_part = time_str[3:]
        match = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)?", time_part)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            meridiem = match.group(3)
            
            if meridiem:
                if meridiem == "pm" and hour < 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0
            
            reminder_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if reminder_time < now:
                reminder_time += datetime.timedelta(days=1)
                
            return reminder_time.strftime("%Y-%m-%d %H:%M")
            
    return None

# Local Logic intent parser
def parse_command_locally(command):
    command_lower = command.lower().strip()
    
    # 1. STOP intent (immediate abort of all playing audios/alarms/tts)
    stop_keywords = ["stop", "shut up", "silence", "stop audio", "abort", "cancel", "dismiss"]
    if any(keyword == command_lower for keyword in stop_keywords) or command_lower == "stop":
        return ("STOP", {})
        
    # 2. TIMERS
    if "cancel all timers" in command_lower or "clear all timers" in command_lower:
        return ("CANCEL_ALL_TIMERS", {})
        
    cancel_timer_match = re.search(r"(?:cancel|delete|stop)\s+timer\s+(.+)", command_lower)
    if cancel_timer_match:
        return ("CANCEL_TIMER", {"name": cancel_timer_match.group(1).strip()})
        
    check_timer_match = re.search(r"(?:how much time is left on|check timer)\s+(.+)", command_lower)
    if check_timer_match:
        return ("CHECK_TIMER", {"name": check_timer_match.group(1).strip()})
        
    if "list timers" in command_lower or "show timers" in command_lower or "what timers" in command_lower:
        return ("LIST_TIMERS", {})
        
    set_timer_match = re.search(r"(?:set|start)?\s*(?:a)?\s*timer\s*for\s*(.+?)(?:\s*(?:called|named)\s+(.+))?$", command_lower)
    if set_timer_match:
        duration_str = set_timer_match.group(1).strip()
        timer_name = set_timer_match.group(2).strip() if set_timer_match.group(2) else "default"
        duration_seconds = parse_duration_to_seconds(duration_str)
        if duration_seconds:
            return ("SET_TIMER", {"duration": duration_seconds, "name": timer_name})
            
    # 3. REMINDERS
    reminder_match = re.search(r"(?:set|add)?\s*(?:a)?\s*reminder\s*(?:to|for)?\s*(.+?)\s+(?:at|in|on)\s+(.+)$", command_lower)
    if reminder_match:
        message = reminder_match.group(1).strip()
        time_str = reminder_match.group(2).strip()
        preposition = "in " if "in " in command_lower else "at "
        parsed_time = parse_reminder_time(preposition + time_str)
        if parsed_time:
            return ("SET_REMINDER", {"message": message, "time": parsed_time})
            
    # 4. ALARMS
    cancel_alarm_match = re.search(
        r"(?:cancel|delete|remove)\s+(?:the\s+)?alarm\s+(?:(?:called|named|labelled)\s+)?(.+)?$",
        command_lower
    )
    if cancel_alarm_match:
        label = cancel_alarm_match.group(1).strip() if cancel_alarm_match.group(1) else "alarm"
        return ("CANCEL_ALARM", {"label": label})

    if "list alarms" in command_lower or "show alarms" in command_lower or "what alarms" in command_lower:
        return ("LIST_ALARMS", {})

    set_alarm_match = re.search(
        r"(?:set|add)?\s*(?:an?\s*)?alarm\s+(?:for\s+)?"
        r"((?:at|in)\s+[\w\s:]+?)"
        r"(?:\s+(?:called|named|labelled)\s+(.+))?$",
        command_lower
    )
    if set_alarm_match:
        time_phrase = set_alarm_match.group(1).strip()
        label = set_alarm_match.group(2).strip() if set_alarm_match.group(2) else "alarm"
        parsed_time = parse_reminder_time(time_phrase)
        if parsed_time:
            return ("SET_ALARM", {"time": parsed_time, "label": label})

    # 5. TIME & DATE
    if "date" in command_lower:
        return ("GET_DATE", {})
    if "time" in command_lower:
        city_match = re.search(r"time\s+in\s+(.+)", command_lower)
        city = city_match.group(1).strip() if city_match else config.DEFAULT_CITY
        return ("GET_TIME", {"city": city})
        
    # 6. MUSIC
    if "pause music" in command_lower or "pause playback" in command_lower:
        return ("PAUSE_MUSIC", {})
    if "resume music" in command_lower or "resume playback" in command_lower:
        return ("RESUME_MUSIC", {})
    if "skip song" in command_lower or "next song" in command_lower:
        return ("SKIP_SONG", {})
    if "song details" in command_lower or "what song" in command_lower:
        return ("SONG_DETAILS", {})
        
    if command_lower.startswith("play "):
        song_query = command_lower[5:].replace("on spotify", "").replace("spotify", "").strip()
        artist_name = None
        if " by " in song_query:
            song_name, artist_name = song_query.split(" by ", 1)
        else:
            song_name = song_query
        return ("PLAY_MUSIC", {"song_name": song_name, "artist_name": artist_name})
        
    return None

def handle_command(command):
    command = command.strip()
    if not command:
        return ""
        
    print(f"You: {command}")
    
    # Try parsing locally first
    parsed = parse_command_locally(command)
    response_text = None
    
    if parsed:
        intent, args = parsed
        
        if intent == "STOP":
            stop_speaking()
            stop_timer_sound()
            response_text = "Stopped all audio."
            
        elif intent == "SET_TIMER":
            response_text = set_timer(args["name"], args["duration"])
            
        elif intent == "CHECK_TIMER":
            response_text = check_timer(args["name"])
            
        elif intent == "LIST_TIMERS":
            response_text = list_timers()
            
        elif intent == "CANCEL_TIMER":
            response_text = cancel_timer(args["name"])
            
        elif intent == "CANCEL_ALL_TIMERS":
            response_text = cancel_all_timers()
            
        elif intent == "GET_TIME":
            response_text = get_current_time(args["city"])
            
        elif intent == "GET_DATE":
            response_text = get_current_date()
            
        elif intent == "PLAY_MUSIC":
            response_text = play_song(args["song_name"], args["artist_name"])
            
        elif intent == "PAUSE_MUSIC":
            response_text = pause_song()
            
        elif intent == "RESUME_MUSIC":
            response_text = resume_song()
            
        elif intent == "SKIP_SONG":
            response_text = skip_song()
            
        elif intent == "SONG_DETAILS":
            response_text = get_current_song()
            
        elif intent == "SET_REMINDER":
            add_reminder(args["message"], args["time"])
            response_text = f"Reminder set: '{args['message']}' for {args['time']}."

        elif intent == "SET_ALARM":
            response_text = set_alarm(args["time"], args["label"])

        elif intent == "CANCEL_ALARM":
            response_text = cancel_alarm(args["label"])

        elif intent == "LIST_ALARMS":
            response_text = list_alarms()

    # Fallback to Gemini if no local intent matches
    if response_text is None:
        try:
            model = genai.GenerativeModel("gemini-2.0-flash")
            prompt = f"Keep responses concise and conversational: {command}"
            response = model.generate_content(prompt)
            response_text = response.text
        except Exception as e:
            print(f"Gemini API fallback failed: {e}. Searching Bing...")
            response_text = search_bing(command)
            
    print(f"AI: {response_text}")
    speak(response_text)
    return response_text

