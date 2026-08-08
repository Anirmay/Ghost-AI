import sounddevice as sd
import numpy as np
import time
import os
import sys

print("====================================================")
print("       REAL-TIME MICROPHONE LEVEL METER             ")
print("====================================================")
print(" This tool shows your live microphone volume level.  ")
print(" If your microphone is physically muted or blocked,  ")
print(" the bar will stay completely flat (0-1%).          ")
print("                                                    ")
print(" 1. SPEAK CONSTANTLY into your microphone.          ")
print(" 2. PRESS your keyboard Mic Mute key (e.g. F4)      ")
print("    or check your headset physical mute button.     ")
print(" 3. Watch the bar jump when you successfully unmute!")
print("                                                    ")
print(" Press Ctrl+C to exit this meter.                   ")
print("====================================================")
time.sleep(2.0)

default_input_idx = sd.default.device[0]
devices = sd.query_devices()
dev_name = devices[default_input_idx]["name"]
samplerate = 44100

print(f"[+] Active Mic: {dev_name} (Index: {default_input_idx})")
print("[*] Starting real-time meter...")
time.sleep(1.0)

def callback(indata, frames, time_info, status):
    # Calculate volume peak/RMS
    float_in = indata.astype(float)
    rms = np.sqrt(np.mean(float_in ** 2)) if float_in.size > 0 else 0.0
    if np.isnan(rms) or np.isinf(rms):
        rms = 0.0
        
    # Scale RMS to a percentage bar (speech rms usually peaks around 1000 - 3000)
    percentage = min(100.0, (rms / 2000.0) * 100.0)
    bar_length = int(percentage / 2)
    bar = "█" * bar_length + "-" * (50 - bar_length)
    
    # Print the level bar (carriage return to overwrite line)
    sys.stdout.write(f"\rLevel: [{bar}] {percentage:.1f}% (RMS: {rms:.0f})   ")
    sys.stdout.flush()

try:
    with sd.InputStream(
        device=default_input_idx,
        channels=1,
        samplerate=samplerate,
        dtype="int16",
        callback=callback
    ):
        # Keep running until user Ctrl+C's
        while True:
            time.sleep(0.1)
except KeyboardInterrupt:
    print("\n\n[+] Exited microphone level meter.")
except Exception as e:
    print(f"\n[-] Error running meter: {e}")
