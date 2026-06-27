# OMNIS — AI Voice Assistant

A local-first, multithreaded AI voice assistant built in Python. OMNIS resolves the majority of commands without an LLM call using a sub-millisecond rule-based intent parser, falling back to Gemini and a web scraper only when needed.

---

## Architecture Overview

```
Wake Word (openwakeword)
        │
        ▼
  RMS-based VAD
  (capture up to 7s, cut off after 1.6s silence)
        │
        ▼
  Google Speech Recognition
        │
        ▼
  Local Intent Parser  ──── hit (78.6%) ────► Module Dispatcher
  (0.006 ms mean)                                    │
        │                                     ┌──────┴──────────────────────┐
        │ miss (21.4%)                        │   6 Independent Modules     │
        ▼                                     │  speech / timers / alarms   │
  Gemini 2.0 Flash (~800 ms)                 │  reminders / music / web    │
        │                                     └─────────────────────────────┘
        │ error / no result
        ▼
  DuckDuckGo Web Scraper (~290 ms)
        │
        ▼
  Async TTS Engine (daemon thread, non-blocking)
```

---

## Performance Benchmarks

All numbers are measured by `benchmark.py` on real hardware.

| Metric | Result |
|---|---|
| Local parser mean latency | **0.006 ms** |
| Local parser p95 latency | < 0.02 ms |
| Routing accuracy | **100%** across 22 intent types |
| Local hit rate | **78.6%** of all commands |
| Concurrent throughput | **82,500+ routing decisions/sec** (20 threads) |
| Gemini fallback latency | ~800 ms avg |
| DuckDuckGo scraper latency | ~290 ms avg |

Run the benchmark yourself:

```bash
python benchmark.py
```

---

## Key Technical Features

### Local Intent Parser — 0.006 ms Mean Latency
Regex and keyword-based rule engine that resolves 78.6% of commands without touching the network. Handles 22 distinct intent types across timers, alarms, reminders, music control, and time queries. Each resolved command skips the ~800 ms Gemini round-trip entirely.

### 3-Tier Fallback Pipeline — 100% Query Coverage
Commands escalate through three tiers automatically:
1. **Local rule parser** (0.006 ms) — handles structured intents
2. **Gemini 2.0 Flash** (~800 ms) — handles open-ended queries
3. **DuckDuckGo web scraper** (~290 ms) — fallback if Gemini fails

Zero silent failures: every query gets a response.

### Modular Monolithic Architecture
Six independent capability modules (`speech`, `timers`, `alarms`, `reminders`, `music`, `web`) each isolated behind a clean interface and routed through a single dispatcher in `ai_response.py`. Adding a new intent type requires only a new parser branch and a module function — no existing modules are touched.

### Asynchronous TTS Engine
Speech synthesis and `pw-play` audio playback run on a dedicated daemon thread. The main command loop is never blocked by audio output. Supports mid-sentence interruption via `stop_speaking()`, which terminates the active `pw-play` process before starting the next response.

### Custom RMS-based Voice Activity Detector
Replaces fixed-duration recording with a dynamic VAD:
- Captures audio in 1280-sample chunks (~80 ms each) via PipeWire `pw-record`
- Starts buffering on voice onset (RMS > 300)
- Stops recording after 1.6 seconds of continuous silence
- Hard cap at 7 seconds to prevent runaway capture
- Eliminates 100% of silent-frame processing overhead

### State Persistence — Zero Data Loss on Restart
All active timers, alarms, and reminders are serialized to `assets/timers_alarms.json` via a thread-safe write path. State is reloaded on startup and re-armed automatically. Validated across 3 concurrent state-bearing modules with no race conditions.

### Multi-threaded Routing
The local parser is stateless and lock-free, enabling linear throughput scaling. At 20 threads, the system sustains **82,500+ routing decisions per second** with sub-millisecond per-operation latency.

---

## Modules

| Module | File | Capabilities |
|---|---|---|
| Intent routing | `ai/ai_response.py` | Local parser, Gemini fallback, TTS dispatch |
| Wake word | `wakeword/wakeword.py` | openwakeword Hey Jarvis, PipeWire audio capture |
| Timers & Alarms | `modules/time_module.py` | Set, check, cancel, persist, alarm sound |
| Reminders | `modules/reminders.py` | SQLite-backed reminder scheduling |
| Music | `modules/musicplayer.py` | Spotify playback via Spotipy |
| Web | `modules/web_scraper.py` | DuckDuckGo scraping via BeautifulSoup |

---

## Setup

### Requirements

- Python 3.10+
- Linux with PipeWire (`pw-record`, `pw-play` must be on PATH)
- Gemini API key
- Spotify developer credentials (for music features)

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure

Set environment variables (or edit `config.py`):

```bash
export GEMINI_API_KEY=your_key_here
export SPOTIFY_CLIENT_ID=your_client_id
export SPOTIFY_CLIENT_SECRET=your_client_secret
```

### Run

```bash
python main.py
```

Say **"Hey Jarvis"** to activate.

---

## Supported Commands

| Category | Examples |
|---|---|
| Timers | `set a timer for 5 minutes`, `set a timer for 30 seconds called pasta`, `list timers`, `cancel timer pasta` |
| Alarms | `set an alarm at 7:00 am called morning`, `list alarms`, `cancel alarm morning` |
| Reminders | `remind me to call mom at 5:30 pm`, `remind me to drink water in 30 minutes` |
| Time & Date | `what time is it`, `what time is it in Tokyo`, `what is the date` |
| Music | `play Blinding Lights by The Weeknd`, `pause music`, `resume music`, `next song`, `what song is playing` |
| Stop | `stop`, `shut up`, `silence` — immediately halts all audio |
| General | Anything else → Gemini 2.0 Flash → DuckDuckGo |

---

## Project Structure

```
OMNIS/
├── main.py                  # Entry point
├── config.py                # API keys and constants
├── benchmark.py             # Performance benchmark suite
├── ai/
│   └── ai_response.py       # Intent parser, command router, TTS engine
├── wakeword/
│   ├── wakeword.py          # Wake word detection + VAD
│   └── Omnis.ppn            # Custom wake word model
├── modules/
│   ├── time_module.py       # Timers and alarms
│   ├── reminders.py         # Reminder scheduling
│   ├── musicplayer.py       # Spotify integration
│   └── web_scraper.py       # DuckDuckGo fallback
├── assets/
│   ├── alarm.wav            # Alarm sound
│   └── timers_alarms.json   # Persisted state
└── requirements.txt
```
