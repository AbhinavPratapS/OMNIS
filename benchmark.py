"""
OMNIS Benchmark Suite
Measures: local parser latency, routing accuracy, thread concurrency throughput,
Gemini fallback latency, and web scraper latency.
"""

import time
import threading
import statistics
import sys
import os

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Patch config before importing anything that reads it
import config
if config.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
    print("[WARN] GEMINI_API_KEY not set — Gemini benchmark will be skipped.")
    GEMINI_AVAILABLE = False
else:
    GEMINI_AVAILABLE = True

from ai.ai_response import parse_command_locally

# ---------------------------------------------------------------------------
# Test corpus: (command_text, expected_intent)
# ---------------------------------------------------------------------------
LOCAL_COMMANDS = [
    ("set a timer for 5 minutes", "SET_TIMER"),
    ("set a timer for thirty seconds called pasta", "SET_TIMER"),
    ("set a timer for 2 hours", "SET_TIMER"),
    ("list timers", "LIST_TIMERS"),
    ("cancel timer default", "CANCEL_TIMER"),
    ("cancel all timers", "CANCEL_ALL_TIMERS"),
    ("how much time is left on pasta", "CHECK_TIMER"),
    ("what time is it", "GET_TIME"),
    ("what is the time in Tokyo", "GET_TIME"),
    ("what is the date", "GET_DATE"),
    ("set a reminder to call mom at 5:30 pm", "SET_REMINDER"),
    ("set a reminder to drink water in 30 minutes", "SET_REMINDER"),
    ("set an alarm at 7:00 am called morning", "SET_ALARM"),
    ("cancel alarm morning", "CANCEL_ALARM"),
    ("list alarms", "LIST_ALARMS"),
    ("play Blinding Lights by The Weeknd", "PLAY_MUSIC"),
    ("pause music", "PAUSE_MUSIC"),
    ("resume music", "RESUME_MUSIC"),
    ("next song", "SKIP_SONG"),
    ("what song is playing", "SONG_DETAILS"),
    ("stop", "STOP"),
    ("shut up", "STOP"),
]

GEMINI_FALLBACK_COMMANDS = [
    "What is the capital of Australia?",
    "Explain black holes in one sentence.",
    "Who wrote Pride and Prejudice?",
]

WEB_SCRAPER_QUERIES = [
    "latest news in technology",
    "Python programming language",
    "weather forecast today",
]


# ---------------------------------------------------------------------------
# 1. Local Parser Latency + Routing Accuracy
# ---------------------------------------------------------------------------
def benchmark_local_parser(runs=200):
    print("\n" + "="*60)
    print("BENCHMARK 1: Local Intent Parser (Latency + Accuracy)")
    print("="*60)

    latencies = []
    correct = 0
    incorrect = []

    for _ in range(runs):
        for cmd, expected in LOCAL_COMMANDS:
            t0 = time.perf_counter()
            result = parse_command_locally(cmd)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000)  # ms

            actual_intent = result[0] if result else None
            if actual_intent == expected:
                correct += 1
            else:
                if _ == 0:  # only log mismatches on first pass
                    incorrect.append((cmd, expected, actual_intent))

    total_tests = runs * len(LOCAL_COMMANDS)
    accuracy = (correct / total_tests) * 100

    print(f"  Runs:            {runs}x {len(LOCAL_COMMANDS)} commands = {total_tests} total")
    print(f"  Accuracy:        {accuracy:.1f}% ({correct}/{total_tests} correct)")
    print(f"  Latency (mean):  {statistics.mean(latencies):.3f} ms")
    print(f"  Latency (p50):   {statistics.median(latencies):.3f} ms")
    print(f"  Latency (p95):   {statistics.quantiles(latencies, n=20)[18]:.3f} ms")
    print(f"  Latency (max):   {max(latencies):.3f} ms")

    if incorrect:
        print(f"\n  Routing mismatches ({len(incorrect)}):")
        for cmd, exp, got in incorrect:
            print(f"    '{cmd}' → expected {exp}, got {got}")

    return {
        "accuracy_pct": accuracy,
        "mean_ms": statistics.mean(latencies),
        "p95_ms": statistics.quantiles(latencies, n=20)[18],
    }


# ---------------------------------------------------------------------------
# 2. Concurrent Throughput (Multi-threading)
# ---------------------------------------------------------------------------
def benchmark_concurrency(num_threads=20, commands_per_thread=50):
    print("\n" + "="*60)
    print("BENCHMARK 2: Multi-threaded Concurrent Routing Throughput")
    print("="*60)

    results = []
    lock = threading.Lock()

    def worker(tid):
        local_latencies = []
        for i in range(commands_per_thread):
            cmd, _ = LOCAL_COMMANDS[i % len(LOCAL_COMMANDS)]
            t0 = time.perf_counter()
            parse_command_locally(cmd)
            t1 = time.perf_counter()
            local_latencies.append((t1 - t0) * 1000)
        with lock:
            results.extend(local_latencies)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]

    t_start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    t_end = time.perf_counter()

    total_ops = num_threads * commands_per_thread
    elapsed = t_end - t_start
    throughput = total_ops / elapsed

    print(f"  Threads:         {num_threads}")
    print(f"  Ops/thread:      {commands_per_thread}")
    print(f"  Total ops:       {total_ops}")
    print(f"  Wall time:       {elapsed:.3f} s")
    print(f"  Throughput:      {throughput:.0f} routing decisions/sec")
    print(f"  Latency (mean):  {statistics.mean(results):.3f} ms")
    print(f"  Latency (p95):   {statistics.quantiles(results, n=20)[18]:.3f} ms")

    return {"throughput_ops_per_sec": throughput, "thread_count": num_threads}


# ---------------------------------------------------------------------------
# 3. Routing Decision: Local vs Gemini split
# ---------------------------------------------------------------------------
def benchmark_routing_split():
    print("\n" + "="*60)
    print("BENCHMARK 3: Routing Decision Split (Local vs LLM Fallback)")
    print("="*60)

    all_commands = [cmd for cmd, _ in LOCAL_COMMANDS] + GEMINI_FALLBACK_COMMANDS + WEB_SCRAPER_QUERIES
    local_hits = 0
    llm_fallback = 0

    for cmd in all_commands:
        result = parse_command_locally(cmd)
        if result:
            local_hits += 1
        else:
            llm_fallback += 1

    total = len(all_commands)
    print(f"  Total commands tested: {total}")
    print(f"  Local parser resolved: {local_hits} ({local_hits/total*100:.1f}%)")
    print(f"  Fell back to LLM/web:  {llm_fallback} ({llm_fallback/total*100:.1f}%)")
    print(f"  (Local hits avoid ~avg 800ms+ Gemini API round-trip)")

    return {"local_hit_rate_pct": local_hits / total * 100}


# ---------------------------------------------------------------------------
# 4. Gemini API Latency (only if key set)
# ---------------------------------------------------------------------------
def benchmark_gemini(runs=3):
    if not GEMINI_AVAILABLE:
        print("\n[SKIP] Gemini benchmark — API key not configured.")
        return None

    print("\n" + "="*60)
    print("BENCHMARK 4: Gemini API Fallback Latency")
    print("="*60)

    import google.generativeai as genai
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
    latencies = []

    for q in GEMINI_FALLBACK_COMMANDS[:runs]:
        t0 = time.perf_counter()
        try:
            resp = model.generate_content(f"Keep responses concise and conversational: {q}")
            _ = resp.text
        except Exception as e:
            print(f"  [ERROR] {e}")
            continue
        t1 = time.perf_counter()
        ms = (t1 - t0) * 1000
        latencies.append(ms)
        print(f"  '{q[:40]}...' → {ms:.0f} ms")

    if latencies:
        print(f"  Mean Gemini latency: {statistics.mean(latencies):.0f} ms")
        print(f"  Max Gemini latency:  {max(latencies):.0f} ms")
        return {"gemini_mean_ms": statistics.mean(latencies)}
    return None


# ---------------------------------------------------------------------------
# 5. Web Scraper Latency
# ---------------------------------------------------------------------------
def benchmark_web_scraper(runs=2):
    print("\n" + "="*60)
    print("BENCHMARK 5: Web Scraper (DuckDuckGo) Latency")
    print("="*60)

    from modules.web_scraper import search_duckduckgo
    latencies = []

    for q in WEB_SCRAPER_QUERIES[:runs]:
        t0 = time.perf_counter()
        result = search_duckduckgo(q)
        t1 = time.perf_counter()
        ms = (t1 - t0) * 1000
        latencies.append(ms)
        preview = result[:60] + "..." if len(result) > 60 else result
        print(f"  '{q}' → {ms:.0f} ms | '{preview}'")

    if latencies:
        print(f"  Mean scraper latency: {statistics.mean(latencies):.0f} ms")
        return {"scraper_mean_ms": statistics.mean(latencies)}
    return None


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def print_summary(parser_stats, concurrency_stats, routing_stats, gemini_stats, scraper_stats):
    print("\n" + "="*60)
    print("OMNIS BENCHMARK SUMMARY")
    print("="*60)
    print(f"  Local parser accuracy:       {parser_stats['accuracy_pct']:.1f}%")
    print(f"  Local parser latency (mean): {parser_stats['mean_ms']:.3f} ms")
    print(f"  Local parser latency (p95):  {parser_stats['p95_ms']:.3f} ms")
    print(f"  Routing throughput:          {concurrency_stats['throughput_ops_per_sec']:.0f} ops/sec ({concurrency_stats['thread_count']} threads)")
    print(f"  Local router hit rate:       {routing_stats['local_hit_rate_pct']:.1f}% of all commands")
    if gemini_stats:
        print(f"  Gemini fallback latency:     ~{gemini_stats['gemini_mean_ms']:.0f} ms avg")
    if scraper_stats:
        print(f"  Web scraper latency:         ~{scraper_stats['scraper_mean_ms']:.0f} ms avg")
    print("="*60)


if __name__ == "__main__":
    print("OMNIS AI Voice Assistant — Performance Benchmark")
    print(f"Python {sys.version.split()[0]} | Threads: {threading.active_count()} active at start")

    parser_stats = benchmark_local_parser(runs=200)
    concurrency_stats = benchmark_concurrency(num_threads=20, commands_per_thread=50)
    routing_stats = benchmark_routing_split()
    gemini_stats = benchmark_gemini(runs=3)
    scraper_stats = benchmark_web_scraper(runs=2)

    print_summary(parser_stats, concurrency_stats, routing_stats, gemini_stats, scraper_stats)
