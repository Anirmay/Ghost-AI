import speech_recognition as sr
import numpy as np
import wave
import io

def test_file_44k(filepath, norm_to_peak=True):
    print(f"\n[*] Transcribing '{filepath}'...")
    
    with wave.open(filepath, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        sample_rate = params.framerate
        
    audio_data = np.frombuffer(frames, dtype=np.int16).astype(float)
    
    if norm_to_peak:
        max_val = np.max(np.abs(audio_data))
        if max_val > 50.0:
            norm_factor = min(40.0, 24000.0 / max_val)
            print(f"    - Programmatic boost: {norm_factor:.2f}x")
            audio_data = audio_data * norm_factor
            
    audio_data = np.clip(audio_data, -32768, 32767).astype(np.int16)
    
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

# Test the 44k recording
test_file_44k("scratch/test_mic_44k_1ch.wav")
