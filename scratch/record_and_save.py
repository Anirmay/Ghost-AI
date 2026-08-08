import sounddevice as sd
import numpy as np
import wave
import time
import os

print("--- Recording test file ---")

default_input_idx = sd.default.device[0]
device_info = sd.query_devices(default_input_idx)
dev_name = device_info["name"]
default_sr = int(device_info["default_samplerate"])
max_channels = device_info["max_input_channels"]

print(f"Device: {dev_name} (Index: {default_input_idx})")
print(f"Default Samplerate: {default_sr}, Max Channels: {max_channels}")

def record_file(filename, channels=1, samplerate=16000):
    print(f"\n[*] Recording to {filename} with channels={channels}, samplerate={samplerate}...")
    print(">>> PLEASE SPEAK CLEARLY NOW <<<")
    audio_blocks = []
    
    def callback(indata, frames, time_info, status):
        if status:
            print(f"[!] Status: {status}")
        audio_blocks.append(indata.copy())
        
    try:
        with sd.InputStream(
            device=default_input_idx,
            channels=channels,
            samplerate=samplerate,
            dtype="int16",
            callback=callback
        ):
            for i in range(4):
                print(f"  {4-i}s remaining...")
                time.sleep(1.0)
                
        full_audio = np.concatenate(audio_blocks, axis=0)
        # Convert to mono for RMS analysis and saving
        if channels > 1:
            mono_audio = np.mean(full_audio, axis=1)
        else:
            mono_audio = full_audio.flatten()
            
        float_audio = mono_audio.astype(float)
        rms = np.sqrt(np.mean(float_audio ** 2)) if float_audio.size > 0 else 0
        max_val = np.max(np.abs(float_audio)) if float_audio.size > 0 else 0
        print(f"    -> Captured {len(full_audio)} frames.")
        print(f"    -> Mono RMS: {rms:.2f}, Mono Peak: {max_val:.2f}")
        
        # Save as standard WAV
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(samplerate)
            wav_file.writeframes(mono_audio.astype(np.int16).tobytes())
            
        print(f"    -> Saved to {filename}")
        
    except Exception as e:
        print(f"    -> Failed to record: {e}")

# Record standard 16000 Hz, channels=1
record_file("scratch/test_mic_16k_1ch.wav", channels=1, samplerate=16000)
# Record standard 44100 Hz, channels=1
record_file("scratch/test_mic_44k_1ch.wav", channels=1, samplerate=44100)
# Record native channels, native rate
record_file("scratch/test_mic_native.wav", channels=max_channels, samplerate=default_sr)
