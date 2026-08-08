import sounddevice as sd
import numpy as np
import time

print("=== AUTOMATED MICROPHONE AUDIT DIAGNOSTIC ===")
print("Please SPEAK CONSTANTLY and CLEARLY into your microphone while this test runs!")
time.sleep(2.0)

devices = sd.query_devices()
input_devices = []

for idx, dev in enumerate(devices):
    if dev.get("max_input_channels", 0) > 0:
        input_devices.append((idx, dev.get("name"), dev.get("hostapi")))

host_apis = sd.query_hostapis()

def test_device(idx, name, api_idx):
    api_name = host_apis[api_idx].get("name")
    print(f"\n[*] Testing Device {idx}: '{name}' ({api_name})...")
    audio_blocks = []
    
    def callback(indata, frames, time_info, status):
        audio_blocks.append(indata.copy())
        
    try:
        # Open with 1 channel, native samplerate of the device if possible, or 44100
        device_info = sd.query_devices(idx)
        native_sr = int(device_info.get("default_samplerate", 44100))
        
        with sd.InputStream(
            device=idx,
            channels=1,
            samplerate=native_sr,
            dtype="int16",
            callback=callback
        ):
            time.sleep(2.0)
            
        full_audio = np.concatenate(audio_blocks, axis=0).flatten()
        float_audio = full_audio.astype(float)
        rms = np.sqrt(np.mean(float_audio ** 2)) if float_audio.size > 0 else 0
        max_val = np.max(np.abs(float_audio)) if float_audio.size > 0 else 0
        
        print(f"    -> SUCCESS: Captured {len(full_audio)} frames. RMS: {rms:.2f}, Peak: {max_val:.2f}")
        return rms, max_val
    except Exception as e:
        print(f"    -> FAILED to open: {e}")
        return 0, 0

results = []
for idx, name, api_idx in input_devices:
    # Skip loopback devices to focus purely on active microphones
    name_lower = name.lower()
    if "loopback" in name_lower or "stereo mix" in name_lower or "what u hear" in name_lower:
        continue
    rms, peak = test_device(idx, name, api_idx)
    if rms > 1.0:
        results.append((idx, name, rms, peak))

print("\n=== AUDIT SUMMARY ===")
print("Candidates with captured signal:")
results_sorted = sorted(results, key=lambda x: x[2], reverse=True)
for idx, name, rms, peak in results_sorted:
    print(f"  - Device {idx}: '{name}' | RMS: {rms:.2f} | Peak: {peak:.2f}")
    
if results_sorted:
    best_idx = results_sorted[0][0]
    best_name = results_sorted[0][1]
    best_rms = results_sorted[0][2]
    print(f"\n[+] Recommended best device index: {best_idx} ('{best_name}') with RMS: {best_rms:.2f}")
else:
    print("\n[!] WARNING: No input device captured any signal. Please check physical connection, hardware mute switches, or Windows privacy settings.")
