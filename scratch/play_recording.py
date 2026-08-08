import sounddevice as sd
import numpy as np
import wave
import time

print("=== AUDIO PLAYBACK DIAGNOSTIC ===")

filepath = "scratch/test_mic_native.wav"
print(f"[*] Loading '{filepath}'...")

try:
    with wave.open(filepath, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        sample_rate = params.framerate
        channels = params.nchannels
        
    audio_data = np.frombuffer(frames, dtype=np.int16)
    print(f"[+] Loaded: channels={channels}, samplerate={sample_rate}, frames={len(audio_data)}")
    
    # Analyze the volume
    float_audio = audio_data.astype(float)
    rms = np.sqrt(np.mean(float_audio ** 2)) if float_audio.size > 0 else 0
    max_val = np.max(np.abs(float_audio)) if float_audio.size > 0 else 0
    print(f"    - Audio RMS: {rms:.2f}, Peak: {max_val:.2f}")
    
    # Play back the recorded sound!
    print("\n[*] PLAYING BACK: Please listen carefully to your PC headphones/speakers now!")
    sd.play(audio_data, sample_rate)
    sd.wait()
    print("[+] Playback finished!")
    
    if rms < 5.0:
        print("\n[!] DIAGNOSIS: The audio is completely silent.")
        print("    Please check if your microphone is physically muted or disabled in Windows.")
    elif rms < 100.0:
        print("\n[!] DIAGNOSIS: The audio is extremely quiet.")
        print("    Your microphone boost or volume is likely set very low in Windows Sound Control Panel.")
    else:
        print("\n[+] DIAGNOSIS: The audio has healthy volume levels.")
        print("    If you heard your voice clearly, then the microphone is working perfectly!")
        
except Exception as e:
    print(f"\n[-] Playback failed: {e}")
