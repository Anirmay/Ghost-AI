import speech_recognition as sr
import numpy as np
import wave
import io

def test_file(filepath, amplify_factor=1.0):
    print(f"\n[*] Transcribing '{filepath}' (amplify={amplify_factor}x)...")
    
    # Read wave file
    with wave.open(filepath, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        sample_rate = params.framerate
        
    audio_data = np.frombuffer(frames, dtype=np.int16).astype(float)
    
    # Amplify
    audio_data = audio_data * amplify_factor
    
    # Clip to valid 16-bit range
    audio_data = np.clip(audio_data, -32768, 32767).astype(np.int16)
    
    # Package into byte stream
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())
    wav_io.seek(0)
    
    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_io) as source:
        audio_data_sr = recognizer.record(source)
        
    try:
        text = recognizer.recognize_google(audio_data_sr)
        print(f"    -> SUCCESS: '{text}'")
        return True
    except sr.UnknownValueError:
        print("    -> ERROR: Could not recognize speech (UnknownValueError).")
        return False
    except sr.RequestError as e:
        print(f"    -> ERROR: Google Speech service error: {e}")
        return False

# Test different amplification factors on the captured 16k 1ch audio
test_file("scratch/test_mic_16k_1ch.wav", amplify_factor=1.0)
test_file("scratch/test_mic_16k_1ch.wav", amplify_factor=5.0)
test_file("scratch/test_mic_16k_1ch.wav", amplify_factor=15.0)
test_file("scratch/test_mic_16k_1ch.wav", amplify_factor=30.0)

# Test with automatic normalization (scale peak to 25000)
print("\n[*] Testing automatic peak normalization...")
with wave.open("scratch/test_mic_16k_1ch.wav", 'rb') as w:
    params = w.getparams()
    frames = w.readframes(params.nframes)
    sample_rate = params.framerate
    
audio_data = np.frombuffer(frames, dtype=np.int16).astype(float)
max_val = np.max(np.abs(audio_data))
if max_val > 0:
    norm_factor = 25000.0 / max_val
    print(f"    - Max value found: {max_val}. Normalization factor: {norm_factor:.2f}x")
    test_file("scratch/test_mic_16k_1ch.wav", amplify_factor=norm_factor)
else:
    print("    - File is completely silent.")
