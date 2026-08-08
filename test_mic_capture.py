import sounddevice as sd
import numpy as np
import time

print("--- Testing Interactive Microphone Array Capture ---")

# Look at default input device
default_input_idx = sd.default.device[0]
devices = sd.query_devices()
dev_name = devices[default_input_idx]["name"]
max_inputs = devices[default_input_idx]["max_input_channels"]
samplerate = int(devices[default_input_idx]["default_samplerate"])

print(f"[+] Default Microphone Device Index: {default_input_idx}")
print(f"[+] Device Name: {dev_name}")
print(f"[+] Hardware Input Channels: {max_inputs}")
print(f"[+] Default Sample Rate: {samplerate}")

print("\n[*] Starting 3-second recording. Please speak clearly into your mic array!")
audio_blocks = []

def callback(indata, frames, time_info, status):
    if status:
        print(f"[!] Stream status: {status}")
    audio_blocks.append(indata.copy())

try:
    # Open with channels=1
    with sd.InputStream(
        device=default_input_idx,
        channels=1,
        samplerate=16000,
        dtype="int16",
        callback=callback
    ):
        time.sleep(3.0)
        
    if not audio_blocks:
        print("[-] Error: No audio blocks captured at all!")
        exit(1)
        
    full_audio = np.concatenate(audio_blocks, axis=0).astype(float)
    rms = np.sqrt(np.mean(full_audio ** 2)) if full_audio.size > 0 else 0
    max_val = np.max(np.abs(full_audio)) if full_audio.size > 0 else 0
    
    print(f"\n[+] Capture finished.")
    print(f"  - Total samples captured: {len(full_audio)}")
    print(f"  - Average Volume (RMS): {rms:.2f}")
    print(f"  - Peak Amplitude Value: {max_val:.2f}")
    
    if rms < 5.0:
        print("\n❌ SILENCE DETECTED: The microphone is capturing absolute silence!")
        print("   This usually means:")
        print("   1. Your microphone is physically muted (check your headset or laptop mic switch).")
        print("   2. Windows Privacy Settings are blocking microphone access for Python.")
        print("   3. The Intel Smart Sound driver failed to mix the 4-channel microphone array down to 1-channel.")
    else:
        print("\n👉 SUCCESS: The microphone is capturing sound perfectly!")
        
except Exception as e:
    print(f"[-] Recording failed: {e}")
