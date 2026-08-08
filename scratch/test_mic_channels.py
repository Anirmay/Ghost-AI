import sounddevice as sd
import numpy as np
import io
import wave
import speech_recognition as sr
import time

print("--- DIAGNOSTIC: Testing Microphone configurations ---")

default_input_idx = sd.default.device[0]
device_info = sd.query_devices(default_input_idx)
dev_name = device_info["name"]
max_channels = device_info["max_input_channels"]
default_sr = int(device_info["default_samplerate"])

print(f"Device: {dev_name} (Index: {default_input_idx})")
print(f"Max Hardware Input Channels: {max_channels}")
print(f"Default Samplerate: {default_sr}")

def test_config(channels, samplerate):
    print(f"\n[*] Testing Config: channels={channels}, samplerate={samplerate}...")
    audio_blocks = []
    
    def callback(indata, frames, time_info, status):
        audio_blocks.append(indata.copy())
        
    try:
        with sd.InputStream(
            device=default_input_idx,
            channels=channels,
            samplerate=samplerate,
            dtype="int16",
            callback=callback
        ):
            time.sleep(2.0)
            
        full_audio = np.concatenate(audio_blocks, axis=0)
        # Convert to mono if multi-channel
        if channels > 1:
            mono_audio = np.mean(full_audio, axis=1)
        else:
            mono_audio = full_audio.flatten()
            
        float_audio = mono_audio.astype(float)
        rms = np.sqrt(np.mean(float_audio ** 2)) if float_audio.size > 0 else 0
        max_val = np.max(np.abs(float_audio)) if float_audio.size > 0 else 0
        print(f"    -> Captured {len(full_audio)} frames. Mono RMS: {rms:.2f}, Mono Peak: {max_val:.2f}")
        return mono_audio, rms
    except Exception as e:
        print(f"    -> Error with this config: {e}")
        return None, 0

# Run a few test configurations
configs = [
    (1, 16000),
    (1, 44100),
    (max_channels, default_sr),
]

for ch, sr_val in configs:
    test_config(ch, sr_val)
