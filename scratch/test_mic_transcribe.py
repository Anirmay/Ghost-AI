import sounddevice as sd
import numpy as np
import io
import wave
import speech_recognition as sr
import time

print("=== SPEECH RECOGNITION DIAGNOSTIC ===")

devices = sd.query_devices()
default_input_idx = sd.default.device[0]
dev_name = devices[default_input_idx]["name"]
samplerate = 44100

print(f"[+] Active Mic: {dev_name} (Index: {default_input_idx})")
print(f"[+] Native Samplerate: {samplerate}")

print("\n[*] RECORDING START: Speak clearly into your mic for 4 seconds now!")
time.sleep(0.5)

audio_blocks = []

def callback(indata, frames, time_info, status):
    if status:
        print(f"[!] Status: {status}")
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
        
    full_audio = np.concatenate(audio_blocks, axis=0)
    float_audio = full_audio.astype(float)
    rms = np.sqrt(np.mean(float_audio ** 2)) if float_audio.size > 0 else 0
    max_val = np.max(np.abs(float_audio)) if float_audio.size > 0 else 0
    
    print(f"\n[+] Audio Captured:")
    print(f"  - Total samples: {len(full_audio)}")
    print(f"  - Raw RMS: {rms:.2f}")
    print(f"  - Raw Peak: {max_val:.2f}")
    
    # Apply automatic normalization
    norm_factor = 1.0
    if max_val > 50.0:
        norm_factor = min(40.0, 24000.0 / max_val)
        float_audio = float_audio * norm_factor
        
    normalized_audio = np.clip(float_audio, -32768, 32767).astype(np.int16)
    norm_rms = np.sqrt(np.mean(normalized_audio.astype(float) ** 2))
    norm_peak = np.max(np.abs(normalized_audio))
    
    print(f"  - Normalized Boost Factor: {norm_factor:.2f}x")
    print(f"  - Normalized RMS: {norm_rms:.2f}")
    print(f"  - Normalized Peak: {norm_peak:.2f}")
    
    # Save to wav byte stream
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(samplerate)
        wav_file.writeframes(normalized_audio.tobytes())
    wav_io.seek(0)
    
    print("\n[*] Sending to Google Web Speech API...")
    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_io) as source:
        audio_data = recognizer.record(source)
        
    try:
        text = recognizer.recognize_google(audio_data)
        print(f"\n[+] SUCCESS! Transcribed Text: '{text}'")
    except sr.UnknownValueError:
        print("\n[-] Google Speech Recognition could not understand the audio (UnknownValueError).")
        print("    This usually means the audio was silent, pure static, or heavily distorted.")
    except sr.RequestError as e:
        print(f"\n[-] Google Speech Recognition request failed: {e}")
        
except Exception as e:
    print(f"\n[-] Test failed: {e}")
