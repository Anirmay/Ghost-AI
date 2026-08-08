import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sounddevice as sd
import numpy as np
import io
import wave
import time
import google.generativeai as genai
from core.config import load_config

print("=== GEMINI MULTIMODAL AUDIO TRANSCRIPTION TEST ===")

config = load_config()
api_key = config.get("api_key")

if not api_key:
    print("[-] Error: Gemini API Key is missing in config.json.")
    exit(1)

genai.configure(api_key=api_key)

default_input_idx = sd.default.device[0]
devices = sd.query_devices()
dev_name = devices[default_input_idx]["name"]
samplerate = 44100

print(f"[+] Active Mic: {dev_name} (Index: {default_input_idx})")
print(f"[+] Samplerate: {samplerate}")

print("\n[*] RECORDING START: Speak clearly and say 'Hello Gemini' now!")
time.sleep(0.5)

audio_blocks = []

def callback(indata, frames, time_info, status):
    audio_blocks.append(indata.copy())

try:
    with sd.InputStream(
        device=default_input_idx,
        channels=1,
        samplerate=samplerate,
        dtype="int16",
        callback=callback
    ):
        for i in range(3):
            print(f"  {3-i}s remaining...")
            time.sleep(1.0)
            
    if not audio_blocks:
        print("[-] Error: No audio captured.")
        exit(1)
        
    full_audio = np.concatenate(audio_blocks, axis=0).flatten()
    float_audio = full_audio.astype(float)
    max_val = np.max(np.abs(float_audio))
    
    # Normalize
    if max_val > 50.0:
        float_audio = float_audio * (24000.0 / max_val)
    normalized_audio = np.clip(float_audio, -32768, 32767).astype(np.int16)
    
    # Create WAV in memory
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(samplerate)
        wav_file.writeframes(normalized_audio.tobytes())
    wav_data = wav_io.getvalue()
    
    print("\n[*] Sending inline WAV bytes to Gemini 1.5 Flash...")
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    response = model.generate_content([
        {
            "mime_type": "audio/wav",
            "data": wav_data
        },
        "Transcribe this audio exactly. Do not add any formatting or extra notes, just the transcribed text."
    ])
    
    print(f"\n🎉 GEMINI SUCCESS! Transcribed Text: '{response.text.strip()}'")
    
except Exception as e:
    print(f"\n[-] Gemini audio test failed: {e}")
