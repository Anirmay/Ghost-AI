import sounddevice as sd
import numpy as np
import io
import wave
import speech_recognition as sr
import time

print("--- Testing Live Speech Recognition ---")

default_input_idx = sd.default.device[0]
devices = sd.query_devices()
dev_name = devices[default_input_idx]["name"]
samplerate = 16000

print(f"[+] Using Default Microphone Device Index: {default_input_idx}")
print(f"[+] Device Name: {dev_name}")

print("\n[*] RECORDING START: Please speak a clear sentence now (e.g., 'Hello Ghost AI, testing 1 2 3')!")
audio_blocks = []

def callback(indata, frames, time_info, status):
    if status:
        print(f"[!] Stream status: {status}")
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
            print(f"Recording... {4-i}s remaining")
            time.sleep(1.0)
            
    if not audio_blocks:
        print("[-] Error: No audio blocks captured.")
        exit(1)
        
    full_audio = np.concatenate(audio_blocks, axis=0)
    
    # Calculate float RMS to avoid overflow
    float_audio = full_audio.astype(float)
    rms = np.sqrt(np.mean(float_audio ** 2)) if float_audio.size > 0 else 0
    max_val = np.max(np.abs(float_audio)) if float_audio.size > 0 else 0
    
    print(f"\n[+] Capture finished.")
    print(f"  - Total samples captured: {len(full_audio)}")
    print(f"  - Average Volume (RMS): {rms:.2f}")
    print(f"  - Peak Amplitude Value: {max_val:.2f}")
    
    # Save to in-memory WAV
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(samplerate)
        wav_file.writeframes(full_audio.tobytes())
    wav_io.seek(0)
    
    print("\n[*] Starting Speech Recognition via Google Web Speech...")
    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_io) as source:
        audio_data = recognizer.record(source)
        
    try:
        text = recognizer.recognize_google(audio_data)
        print(f"\n🎉 SUCCESS! Transcribed Text: '{text}'")
    except sr.UnknownValueError:
        print("\n❌ Google Speech Recognition could not understand the audio (sr.UnknownValueError).")
    except sr.RequestError as e:
        print(f"\n❌ Google Speech Recognition service error: {e}")
        
except Exception as e:
    print(f"[-] Test failed: {e}")
