import ctypes
import numpy as np
import sounddevice as sd
import soundcard as sc
import io
import wave
import speech_recognition as sr
import queue
import threading
from PyQt6.QtCore import QThread, pyqtSignal


# ─────────────────────────────────────────────────────────────────────────────
#  Device Discovery
# ─────────────────────────────────────────────────────────────────────────────

def find_audio_devices():
    """
    Discovers the best devices for capturing:
      1. Your voice   → physical microphone via sounddevice
      2. System audio → WASAPI loopback via soundcard (captures ALL app audio:
                        YouTube, Zoom, Teams, VLC, etc. regardless of headphone state)

    Returns:
        mic_idx     (int|None)  : sounddevice index for the microphone
        sc_loopback (sc.Microphone|None) : soundcard loopback object for system audio
    """
    # ── Microphone (sounddevice default) ─────────────────────────────────────
    mic_idx = None
    try:
        mic_idx = sd.default.device[0]
        devices = sd.query_devices()
        print(f"[+] Microphone: index {mic_idx} = {devices[mic_idx].get('name')}")
    except Exception as e:
        print(f"[-] Default microphone lookup failed: {e}")
        mic_idx = None

    # ── System Audio Loopback (soundcard WASAPI) ──────────────────────────────
    # KEY: We use sc.default_speaker() to find whichever output Windows is
    # currently routing audio through — this automatically follows:
    #   • Headphones when plugged in   → Headphone (Realtek® Audio)
    #   • Speakers when no headphones  → Speaker (Realtek® Audio)
    sc_loopback = None
    try:
        # Get the currently active Windows audio output
        default_spk = sc.default_speaker()
        print(f"[+] Active audio output: {default_spk.name}")

        # Find its matching loopback capture device
        all_loopbacks = sc.all_microphones(include_loopback=True)
        all_speaker_names = {s.name for s in sc.all_speakers()}
        loopback_devices = [m for m in all_loopbacks if m.name in all_speaker_names]

        # Match by name to the default speaker — this is the one Windows plays audio through
        matched = next((m for m in loopback_devices if m.name == default_spk.name), None)

        if matched:
            sc_loopback = matched
            print(f"[+] System Audio Loopback -> {sc_loopback.name} (matched default output)")
        elif loopback_devices:
            # Fallback: use first available loopback speaker
            sc_loopback = loopback_devices[0]
            print(f"[+] System Audio Loopback -> {sc_loopback.name} (fallback, could not match default)")
        else:
            print("[-] No loopback speaker devices found.")
    except Exception as e:
        print(f"[-] Soundcard loopback discovery failed: {e}")
        sc_loopback = None

    return mic_idx, sc_loopback


# ─────────────────────────────────────────────────────────────────────────────
#  Shared audio helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fit_block(block, size):
    """Pad or trim a 1-D numpy array to exactly `size` samples."""
    block = np.asarray(block).flatten()
    if len(block) < size:
        return np.pad(block, (0, size - len(block)))
    return block[:size]


def _safe_rms(arr):
    """Returns RMS of a float array as a safe finite Python float."""
    arr = np.asarray(arr, dtype=np.float64)
    if arr.size == 0:
        return 0.0
    val = float(np.sqrt(np.mean(arr ** 2)))
    return val if np.isfinite(val) else 0.0


def _normalize_audio(audio_int16):
    """
    Peak-normalise int16 audio to ~73% of full scale (target peak = 24 000).
    Boost is capped at 40× so pure silence / noise floors are not amplified.
    """
    float_audio = audio_int16.astype(np.float64)
    max_val = np.max(np.abs(float_audio))
    if max_val > 50.0:
        norm_factor = min(40.0, 24000.0 / max_val)
        float_audio = float_audio * norm_factor
        print(f"[+] Audio normalised: {norm_factor:.2f}×")
    return np.clip(float_audio, -32768, 32767).astype(np.int16)


def _loopback_capture_thread(sc_mic, samplerate, block_size, loopback_q, stop_event):
    """
    Background thread that continuously reads from a soundcard loopback mic.
    Converts float32 frames → int16 mono and posts to loopback_q.
    Stops when stop_event is set.

    Note: Windows requires COM to be initialised on every thread that uses WASAPI.
    We call CoInitialize / CoUninitialize explicitly here.
    """
    # Initialise Windows COM for this thread (required by soundcard/WASAPI)
    ctypes.windll.ole32.CoInitialize(None)
    try:
        with sc_mic.recorder(samplerate=samplerate, channels=1, blocksize=block_size) as recorder:
            print(f"[+] Soundcard loopback thread started: {sc_mic.name}")
            while not stop_event.is_set():
                # record() blocks for one blocksize worth of audio
                data = recorder.record(numframes=block_size)  # shape (block_size, channels)
                mono_float = data[:, 0] if data.ndim > 1 else data.flatten()
                # Convert float32 [-1,1] to int16 scale
                mono_int16 = np.clip(mono_float * 32767, -32768, 32767).astype(np.int16)
                loopback_q.put(mono_int16)
    except Exception as e:
        print(f"[-] Loopback capture thread error: {e}")
    finally:
        ctypes.windll.ole32.CoUninitialize()


# ─────────────────────────────────────────────────────────────────────────────
#  Push-to-Talk Worker
# ─────────────────────────────────────────────────────────────────────────────

class SpeechWorker(QThread):
    """
    Push-to-Talk (PTT) recording worker.

    Simultaneously captures:
      • Your microphone (sounddevice)
      • All system audio – YouTube, apps, calls (soundcard WASAPI loopback)

    Mixes both streams, normalises amplitude, and transcribes via Google STT.
    """
    started        = pyqtSignal()
    volume_changed = pyqtSignal(float)  # Normalised 0.0 – 1.0 for UI animation
    finished       = pyqtSignal(str)    # Final transcription text
    error          = pyqtSignal(str)    # Error message string

    def __init__(self, sample_rate=44100):
        super().__init__()
        self.sample_rate = sample_rate
        self._is_recording = False
        self.audio_blocks = []

    def stop_recording(self):
        """Stop recording and trigger transcription."""
        self._is_recording = False

    def run(self):
        self._is_recording = True
        self.audio_blocks = []
        self.started.emit()

        block_size = 1024
        mic_q      = queue.Queue()
        loopback_q = queue.Queue()
        stop_event = threading.Event()

        # Discover devices
        mic_idx, sc_loopback = find_audio_devices()

        # ── Mic callback (sounddevice) ──────────────────────────────────────
        def mic_callback(indata, frames, time_info, status):
            if not self._is_recording:
                return
            if status:
                print(f"[!] Mic status: {status}")
            mono = np.mean(indata, axis=1) if indata.ndim > 1 else indata.flatten()
            mic_q.put(mono)

        opened_dual = False
        loopback_thread = None

        if mic_idx is not None and sc_loopback is not None:
            try:
                # Start soundcard loopback reader in a background thread
                loopback_thread = threading.Thread(
                    target=_loopback_capture_thread,
                    args=(sc_loopback, self.sample_rate, block_size, loopback_q, stop_event),
                    daemon=True
                )
                loopback_thread.start()

                # Open mic stream
                with sd.InputStream(
                    device=mic_idx,
                    channels=1,
                    samplerate=self.sample_rate,
                    blocksize=block_size,
                    dtype='int16',
                    callback=mic_callback
                ):
                    opened_dual = True
                    print("[+] PTT Dual-Stream (Mic + System Audio) ready.")
                    while self._is_recording:
                        while not mic_q.empty() or not loopback_q.empty():
                            mic_block  = mic_q.get()  if not mic_q.empty()      else np.zeros(block_size, dtype=np.float64)
                            loop_block = loopback_q.get() if not loopback_q.empty() else np.zeros(block_size, dtype=np.float64)

                            mic_block  = _fit_block(mic_block,  block_size).astype(np.float64)
                            loop_block = _fit_block(loop_block, block_size).astype(np.float64)

                            # Mix: voice + system audio
                            mixed = mic_block + (loop_block * 1.2)
                            mixed = np.clip(mixed, -32768, 32767).astype(np.int16)
                            self.audio_blocks.append(mixed)

                            # Drive volume indicator from the louder signal
                            rms = _safe_rms(np.maximum(np.abs(mic_block), np.abs(loop_block)))
                            self.volume_changed.emit(min(1.0, rms / 1500.0))

                        self.msleep(20)

            except Exception as e:
                print(f"[-] PTT Dual-Stream failed: {e}. Falling back to mic only…")
                opened_dual = False
            finally:
                stop_event.set()

        if not opened_dual:
            stop_event.set()  # ensure loopback thread stops
            # ── Mic-only fallback ───────────────────────────────────────────
            print(f"[*] PTT Mic-Only (device={mic_idx})")

            def callback(indata, frames, time, status):
                if status:
                    print(f"[!] Mic status: {status}")
                if self._is_recording:
                    self.audio_blocks.append(indata.copy())
                    rms = _safe_rms(indata.astype(np.float64))
                    self.volume_changed.emit(min(1.0, rms / 1500.0))

            try:
                with sd.InputStream(
                    device=mic_idx,
                    samplerate=self.sample_rate,
                    channels=1,
                    blocksize=block_size,
                    dtype='int16',
                    callback=callback
                ):
                    while self._is_recording:
                        self.msleep(50)
            except Exception as e:
                self.error.emit(f"Microphone access error: {str(e)}")
                return

        # ── Transcribe ──────────────────────────────────────────────────────
        if not self.audio_blocks:
            self.error.emit("No voice data detected.")
            return

        print("[+] Capture stopped. Transcribing…")
        try:
            full_audio = np.concatenate(self.audio_blocks, axis=0)
            if full_audio.ndim > 1:
                full_audio = full_audio[:, 0]
            full_audio = full_audio.astype(np.int16)

            duration = len(full_audio) / self.sample_rate
            if duration < 0.5:
                self.error.emit("Recording too short. Please speak clearly.")
                return

            full_audio = _normalize_audio(full_audio)

            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(full_audio.tobytes())
            wav_io.seek(0)

            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_io) as source:
                audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            self.finished.emit(text)

        except sr.UnknownValueError:
            self.error.emit("Could not recognize your voice. Please try again.")
        except sr.RequestError as e:
            self.error.emit(f"Google speech server error: {e}")
        except Exception as e:
            self.error.emit(f"Audio processing error: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
#  Auto-Pilot (continuous VAD) Worker
# ─────────────────────────────────────────────────────────────────────────────

class AutoPilotSpeechWorker(QThread):
    """
    Continuous Meeting Auto-Pilot Speech Worker.

    Captures system audio + microphone simultaneously using WASAPI loopback.
    VAD detects speech in EITHER the mic OR the system audio stream, so it
    correctly transcribes:
      • Your voice through the microphone
      • Audio from YouTube, Zoom, Teams, any app playing through speakers/headphones

    Automatically slices and transcribes each sentence when silence is detected.
    """
    started         = pyqtSignal()
    volume_changed  = pyqtSignal(float)
    phrase_completed = pyqtSignal(str)
    status_changed  = pyqtSignal(str, str)   # (status_text, color_hex)
    error           = pyqtSignal(str)

    def __init__(self, sample_rate=44100, silence_seconds=1.5, speech_threshold=800):
        super().__init__()
        self.sample_rate      = sample_rate
        self.silence_seconds  = silence_seconds
        self.speech_threshold = speech_threshold   # RMS amplitude to trigger VAD
        self._is_running      = False
        self._transcription_threads = []  # Keep refs — prevents GC of running threads

        self.chunks_per_second   = self.sample_rate / 1024.0
        self.silent_chunks_limit = int(self.chunks_per_second * self.silence_seconds)

        # NOTE: Device discovery is intentionally deferred to run() so that
        # it always reflects the current audio state (headphones in/out) at
        # the moment Auto-Pilot is actually started.
        self.mic_device_index  = None
        self.sc_loopback       = None


    def stop(self):
        self._is_running = False

    def run(self):
        self._is_running = True
        self.started.emit()
        self.status_changed.emit("Auto-Pilot ACTIVE • Listening…", "#00ffcc")

        # Re-discover devices every time Auto-Pilot starts so we always
        # capture from whichever output is currently active (speakers / headphones)
        self.mic_device_index, self.sc_loopback = find_audio_devices()

        audio_blocks  = []
        has_spoken    = False
        silent_chunks = 0
        block_size    = 1024

        mic_q      = queue.Queue()
        loopback_q = queue.Queue()
        stop_event = threading.Event()

        def mic_callback(indata, frames, time_info, status):
            if not self._is_running:
                return
            if status:
                print(f"[!] Mic status: {status}")
            mono = np.mean(indata, axis=1) if indata.ndim > 1 else indata.flatten()
            mic_q.put(mono)

        opened_dual   = False
        loopback_thread = None

        if self.mic_device_index is not None and self.sc_loopback is not None:
            try:
                loopback_thread = threading.Thread(
                    target=_loopback_capture_thread,
                    args=(self.sc_loopback, self.sample_rate, block_size, loopback_q, stop_event),
                    daemon=True
                )
                loopback_thread.start()

                with sd.InputStream(
                    device=self.mic_device_index,
                    channels=1,
                    samplerate=self.sample_rate,
                    blocksize=block_size,
                    dtype='int16',
                    callback=mic_callback
                ):
                    opened_dual = True
                    print("[+] AutoPilot Dual-Stream (Mic + System Audio) ready.")

                    while self._is_running:
                        while not mic_q.empty() or not loopback_q.empty():
                            mic_block  = mic_q.get()  if not mic_q.empty()      else np.zeros(block_size, dtype=np.float64)
                            loop_block = loopback_q.get() if not loopback_q.empty() else np.zeros(block_size, dtype=np.float64)

                            mic_block  = _fit_block(mic_block,  block_size).astype(np.float64)
                            loop_block = _fit_block(loop_block, block_size).astype(np.float64)

                            # Mix
                            mixed = mic_block + (loop_block * 1.2)
                            mixed = np.clip(mixed, -32768, 32767)
                            audio_blocks.append(mixed.astype(np.int16))

                            # VAD: trigger on whichever stream is louder
                            mic_rms  = _safe_rms(mic_block)
                            loop_rms = _safe_rms(loop_block)
                            active_rms = max(mic_rms, loop_rms)

                            # Volume indicator
                            self.volume_changed.emit(min(1.0, float(active_rms) / 1500.0))

                            # VAD logic
                            if active_rms > self.speech_threshold:
                                if not has_spoken:
                                    has_spoken = True
                                    self.status_changed.emit("Hearing conversation…", "#00ffaa")
                                silent_chunks = 0
                            else:
                                if has_spoken:
                                    silent_chunks += 1
                                    if silent_chunks >= self.silent_chunks_limit:
                                        self.status_changed.emit("Processing speech…", "#ffaa00")
                                        phrase_blocks = list(audio_blocks)
                                        audio_blocks.clear()
                                        has_spoken    = False
                                        silent_chunks = 0
                                        self.transcribe_phrase_async(phrase_blocks)

                        self.msleep(20)

            except Exception as e:
                print(f"[-] AutoPilot Dual-Stream failed: {e}. Falling back to mic only…")
                opened_dual = False
            finally:
                stop_event.set()

        if not opened_dual:
            stop_event.set()
            # ── Mic-only AutoPilot fallback ─────────────────────────────────
            try:
                print(f"[*] AutoPilot Mic-Only (device={self.mic_device_index})")

                def callback(indata, frames, time, status):
                    if not self._is_running:
                        return
                    if status:
                        print(f"[!] Mic status: {status}")
                    mono = np.mean(indata, axis=1) if indata.ndim > 1 else indata.flatten()
                    mic_q.put(mono)

                with sd.InputStream(
                    device=self.mic_device_index,
                    samplerate=self.sample_rate,
                    channels=1,
                    blocksize=block_size,
                    dtype='int16',
                    callback=callback
                ):
                    print("[+] AutoPilot Mic-Only initialized.")
                    while self._is_running:
                        while not mic_q.empty():
                            mic_block = _fit_block(mic_q.get(), block_size)
                            float_mic = mic_block.astype(np.float64)
                            audio_blocks.append(mic_block.astype(np.int16))

                            mic_rms = _safe_rms(float_mic)
                            self.volume_changed.emit(min(1.0, float(mic_rms) / 1500.0))

                            if mic_rms > self.speech_threshold:
                                if not has_spoken:
                                    has_spoken = True
                                    self.status_changed.emit("Hearing conversation…", "#00ffaa")
                                silent_chunks = 0
                            else:
                                if has_spoken:
                                    silent_chunks += 1
                                    if silent_chunks >= self.silent_chunks_limit:
                                        self.status_changed.emit("Processing speech…", "#ffaa00")
                                        phrase_blocks = list(audio_blocks)
                                        audio_blocks.clear()
                                        has_spoken    = False
                                        silent_chunks = 0
                                        self.transcribe_phrase_async(phrase_blocks)

                        self.msleep(20)

            except Exception as e:
                self.error.emit(f"Audio recording failed: {str(e)}")
                self.status_changed.emit("Auto-Pilot Error", "#ff5555")
                return

        self.status_changed.emit("Auto-Pilot Off", "#00ffcc")

    def transcribe_phrase_async(self, phrase_blocks):
        """Spawns a parentless QThread to transcribe a completed audio phrase.

        IMPORTANT: TranscriptionThread must NOT use parent=self here.
        This method is called from inside run() which executes in the worker
        thread. PyQt6 forbids creating QObject children from a thread that
        is different from the parent's home thread — doing so prints:
          'QObject: Cannot create children for a parent that is in a different thread'
        and silently fails to create the thread, so phrase_completed is never emitted.
        Fix: no parent + store reference in _transcription_threads list to prevent GC.
        """
        class TranscriptionThread(QThread):
            completed = pyqtSignal(str)

            def __init__(self, blocks, sample_rate):
                super().__init__()          # NO parent — this is the critical fix
                self.blocks      = blocks
                self.sample_rate = sample_rate

            def run(self):
                try:
                    full_audio = np.concatenate(self.blocks, axis=0)
                    if full_audio.ndim > 1:
                        full_audio = full_audio[:, 0]
                    full_audio = _normalize_audio(full_audio.astype(np.int16))

                    wav_io = io.BytesIO()
                    with wave.open(wav_io, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(self.sample_rate)
                        wf.writeframes(full_audio.tobytes())
                    wav_io.seek(0)

                    recognizer = sr.Recognizer()
                    with sr.AudioFile(wav_io) as source:
                        audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(audio_data)
                    self.completed.emit(text)
                except Exception:
                    pass  # Ignore noise-only / silence segments

        t = TranscriptionThread(phrase_blocks, self.sample_rate)
        self._transcription_threads.append(t)

        def _cleanup():
            if t in self._transcription_threads:
                self._transcription_threads.remove(t)

        t.completed.connect(self.phrase_completed.emit)
        t.finished.connect(_cleanup)
        t.start()

