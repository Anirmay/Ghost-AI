import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sounddevice as sd
import numpy as np
import io
import wave
import time
import base64
import requests
from core.config import load_config

print("=== GEMINI REST AUDIO TRANSCRIPTION TEST (2.5 FLASH) ===")

config = load_config()
api_key = config.get("api_key", "").strip()

if not api_key:
    print("[-] Error: Gemini API Key is missing in config.json.")
    exit(1)

default_input_idx = sd.default.device[0]
devices = sd.query_devices()
dev_name = devices[default_input_idx]["name"]
samplerate = 44100

print(f"[+] Active Mic: {dev_name} (Index: {default_input_idx})")
print(f"[+] Samplerate: {samplerate}")

print("\n[*] RECORDING START: Speak clearly and say 'Hello Gemini' constantly now!")
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
        for i in range(4):
            print(f"  {4-i}s remaining...")
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
    
    # Base64 encode
    base64_audio = base64.b64encode(wav_data).decode('utf-8')
    
    print("\n[*] Sending inline WAV bytes to Gemini 2.0 Flash REST API...")
    
    model = "gemini-2.0-flash"
    url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "audio/wav",
                            "data": base64_audio
                        }
                    },
                    {
                        "text": "Transcribe this audio exactly. Do not add any formatting or extra notes, just return the exact spoken words. If there is no speech, return '[SILENCE]'."
                    }
                ]
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    
    print(f"\n[+] REST Response Code: {response.status_code}")
    
    if response.status_code == 200:
        res_json = response.json()
        candidates = res_json.get('candidates', [])
        if candidates:
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            if parts:
                text = parts[0].get('text', '')
                print(f"\n🎉 GEMINI REST SUCCESS! Transcribed Text: '{text.strip()}'")
            else:
                print("\n[-] Gemini REST returned empty parts (no speech detected).")
        else:
            print("\n[-] No candidates returned in REST response.")
    else:
        print(f"\n[-] Gemini REST request failed: {response.text}")
        
except Exception as e:
    print(f"\n[-] Gemini REST audio test failed: {e}")
