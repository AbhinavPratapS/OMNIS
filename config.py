
import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

DEFAULT_CITY = "Mumbai"
WAKE_WORD = "jarvis"

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "YOUR_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"

PERSISTENCE_FILE = "assets/timers_alarms.json"

ALARM_SOUND = "assets/alarm.wav"

