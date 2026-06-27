
import subprocess
import numpy as np
import speech_recognition as sr
from openwakeword.model import Model
from ai.ai_response import handle_command
from rich.console import Console

console = Console()
recognizer = sr.Recognizer()

console.print("[bold yellow]Initializing offline Wake-Word Engine (openwakeword)...[/bold yellow]")
try:
    import openwakeword
    import os
    # Get all pre-trained models
    paths = openwakeword.get_pretrained_model_paths()
    # Find Hey Jarvis model specifically
    jarvis_paths = [p for p in paths if "hey_jarvis" in p]
    if jarvis_paths:
        oww_model = Model(wakeword_model_paths=jarvis_paths)
        model_key = os.path.splitext(os.path.basename(jarvis_paths[0]))[0]
        console.print(f"[bold green]Offline Wake-Word Engine loaded successfully (Model: {model_key})![/bold green]")
    else:
        raise FileNotFoundError("Could not find hey_jarvis model in pre-trained resources.")
except Exception as e:
    console.print(f"[bold red]Failed to load wake word engine: {e}. Falling back.[/bold red]")
    oww_model = None
    model_key = None

def detect_wake_word():
    console.print("\n[bold cyan]● OMNIX is active. Say 'Hey Jarvis' to wake me...[/bold cyan]")

    if oww_model is None:
        console.print("[bold yellow]⚠ Wake word engine unavailable. Running in always-listening mode.[/bold yellow]")
        listen_for_command()
        return

    # Spawn pw-record to capture audio natively via PipeWire
    # --format=s16: 16-bit signed PCM
    # --rate=16000: 16kHz sample rate (expected by openwakeword)
    # --channels=1: Mono
    # --latency=100ms: Low delay
    # -: Write raw bytes to stdout
    proc = subprocess.Popen(
        ["pw-record", "--format=s16", "--rate=16000", "--channels=1", "--latency=100ms", "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )
    
    try:
        while True:
            # openwakeword processes chunks of 1280 samples (2560 bytes for s16)
            raw_chunk = proc.stdout.read(2560)
            if len(raw_chunk) < 2560:
                break
                
            audio_frame = np.frombuffer(raw_chunk, dtype=np.int16)
            
            if oww_model:
                prediction = oww_model.predict(audio_frame)
                
                # Check if Hey Jarvis score is above threshold (0.5)
                if prediction.get(model_key, 0.0) > 0.5:
                    console.print("[bold green]✔ Wake word detected![/bold green]")
                    # Terminate the wake word loop record process
                    proc.terminate()
                    proc.wait()
                    
                    # Open a new stream to listen for the actual command
                    listen_for_command()
                    break
    except Exception as e:
        print(f"Error in wake-word detection loop: {e}")
    finally:
        try:
            proc.terminate()
        except:
            pass

def listen_for_command():
    console.print("[bold purple]🎤 Awaiting command... Speak now.[/bold purple]")
    
    # Spawn a clean pw-record process for command capture
    proc = subprocess.Popen(
        ["pw-record", "--format=s16", "--rate=16000", "--channels=1", "--latency=100ms", "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )
    
    recorded_bytes = bytearray()
    
    # Custom high-performance RMS-based Voice Activity Detector (VAD)
    silence_threshold = 300.0  # RMS threshold for silence detection
    chunk_duration = 1280 / 16000.0  # ~0.08 seconds per 1280 samples chunk
    max_duration = 7.0  # Max 7 seconds of recording
    silence_timeout = 1.6  # Stop after 1.6 seconds of continuous silence
    
    started_speaking = False
    silence_time = 0.0
    total_time = 0.0
    
    try:
        while total_time < max_duration:
            chunk = proc.stdout.read(2560)
            if len(chunk) < 2560:
                break
                
            recorded_bytes.extend(chunk)
            audio_frame = np.frombuffer(chunk, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_frame.astype(np.float32) ** 2))
            
            total_time += chunk_duration
            
            # Simple volume-based speech detector
            if rms > silence_threshold:
                if not started_speaking:
                    started_speaking = True
                silence_time = 0.0
            else:
                if started_speaking:
                    silence_time += chunk_duration
                    if silence_time >= silence_timeout:
                        break
                        
    except Exception as e:
        console.print(f"[bold red]Audio capture error: {e}[/bold red]")
    finally:
        try:
            proc.terminate()
            proc.wait()
        except:
            pass
            
    # Transcribe captured audio via SpeechRecognition
    if recorded_bytes:
        console.print("[bold yellow]⚡ Processing speech...[/bold yellow]")
        try:
            audio_data = sr.AudioData(bytes(recorded_bytes), 16000, 2)
            command = recognizer.recognize_google(audio_data)
            handle_command(command)
        except sr.UnknownValueError:
            console.print("[bold red]⚠ Speech could not be understood.[/bold red]")
        except sr.RequestError as e:
            console.print(f"[bold red]⚠ Speech recognition service request failed: {e}[/bold red]")
        except Exception as e:
            console.print(f"[bold red]⚠ Speech transcription error: {e}[/bold red]")

