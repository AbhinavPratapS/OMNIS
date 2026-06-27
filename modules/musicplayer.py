
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from fuzzywuzzy import process
import google.generativeai as genai
import config

genai.configure(api_key=config.GEMINI_API_KEY)

sp = None
try:
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=config.SPOTIFY_CLIENT_ID,
        client_secret=config.SPOTIFY_CLIENT_SECRET,
        redirect_uri=config.SPOTIFY_REDIRECT_URI,
        scope="user-read-playback-state user-modify-playback-state"
    ))
except Exception as e:
    print(f"[musicplayer] Spotify init failed: {e}. Music features disabled.")

def correct_song_details(song_query):
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f'''
    Correct the spelling of this Spotify search query:
    "{song_query}"

    Return only the corrected song and artist names.
    '''

    response = model.generate_content(prompt)

    return response.text.strip() if response.text else song_query

def search_best_match(query):
    if sp is None:
        return None
    try:
        results = sp.search(q=query, type='track', limit=10)

        track_names = {
            track["name"]: track["uri"]
            for track in results["tracks"]["items"]
        }

        best_match = process.extractOne(query, track_names.keys())

        if best_match and best_match[1] > 70:
            return track_names[best_match[0]]

        return None
    except SpotifyException as e:
        print(f"[musicplayer] Spotify search error: {e.msg}")
        return None

def play_song(song_name, artist_name=None):
    if sp is None:
        return "Spotify is not configured. Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET."

    query = f"{song_name} {artist_name}" if artist_name else song_name

    track_uri = search_best_match(query)

    if not track_uri:
        corrected_query = correct_song_details(query)
        track_uri = search_best_match(corrected_query)

    if track_uri:
        try:
            devices = sp.devices()

            if not devices["devices"]:
                return "No active Spotify device found. Open Spotify on your phone or PC first."

            device_id = devices["devices"][0]["id"]

            sp.start_playback(device_id=device_id, uris=[track_uri])

            return f"Now playing {song_name}."
        except SpotifyException as e:
            return f"Spotify error: {e.msg}"
    else:
        return "I couldn't find that song."

def pause_song():
    if sp is None:
        return "Spotify is not configured."
    try:
        sp.pause_playback()
        return "Paused playback."
    except SpotifyException as e:
        return f"Could not pause: {e.msg}"
    except Exception as e:
        return f"Pause failed: {e}"

def resume_song():
    if sp is None:
        return "Spotify is not configured."
    try:
        sp.start_playback()
        return "Resumed playback."
    except SpotifyException as e:
        return f"Could not resume: {e.msg}"
    except Exception as e:
        return f"Resume failed: {e}"

def skip_song():
    if sp is None:
        return "Spotify is not configured."
    try:
        sp.next_track()
        return "Skipped to next song."
    except SpotifyException as e:
        return f"Could not skip: {e.msg}"
    except Exception as e:
        return f"Skip failed: {e}"

def get_current_song():
    if sp is None:
        return "Spotify is not configured."
    try:
        current = sp.current_playback()

        if current and current["is_playing"]:
            track = current["item"]["name"]
            artist = current["item"]["artists"][0]["name"]
            return f"Currently playing {track} by {artist}."

        return "Nothing is currently playing."
    except SpotifyException as e:
        return f"Could not get song info: {e.msg}"
    except Exception as e:
        return f"Song info failed: {e}"
