import sys
import os

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# Import modules
from core.config import load_config, save_config, load_memory
from core.speech import SpeechWorker, AutoPilotSpeechWorker
from core.ai import GeminiClient
from core.hotkey import HotkeyWorker
from ui.overlay import GhostOverlay
from ui.settings import SettingsDialog

class AIWorker(QThread):
    """Background worker thread to request content from Gemini without freezing the UI."""
    finished = pyqtSignal(str)

    def __init__(self, client: GeminiClient, question: str):
        super().__init__()
        self.client = client
        self.question = question

    def run(self):
        answer = self.client.ask(self.question)
        self.finished.emit(answer)


class AIImageWorker(QThread):
    """Background worker to request multimodal vision content from Gemini for image snippets."""
    finished = pyqtSignal(str)

    def __init__(self, client: GeminiClient, image_bytes: bytes, prompt: str = ""):
        super().__init__()
        self.client = client
        self.image_bytes = image_bytes
        self.prompt = prompt

    def run(self):
        answer = self.client.ask_image(self.image_bytes, self.prompt)
        self.finished.emit(answer)


class AutoPilotAIWorker(QThread):
    """Background worker to request content from Gemini in Auto-Pilot mode."""
    finished = pyqtSignal(str)

    def __init__(self, client: GeminiClient, question: str):
        super().__init__()
        self.client = client
        self.question = question

    def run(self):
        answer = self.client.ask_autopilot(self.question)
        self.finished.emit(answer)


class InterviewAIWorker(QThread):
    """Background AI worker for Interview Mode — always answers, never ignores.
    
    NOTE: Kept in a list (not single variable) to prevent Python GC from
    destroying running threads when the next phrase triggers a new worker.
    """
    finished = pyqtSignal(str)

    def __init__(self, client: GeminiClient, question: str):
        super().__init__()
        self.client = client
        self.question = question

    def run(self):
        # Always emit finished — even on unhandled exception — so the UI
        # never gets stuck in "Generating answer..." forever.
        try:
            answer = self.client.ask_interview(self.question)
        except Exception as e:
            answer = f"❌ **Interview AI Error:**\n\n{str(e)}"
        self.finished.emit(answer)


class GhostApp(QObject):
    """Main application coordinator managing overlay UI, hotkeys, workers, and settings."""
    
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.ai_client = GeminiClient()
        
        # 1. Initialize main overlay and settings dialog
        self.overlay = GhostOverlay()
        self.settings_dialog = SettingsDialog(self.overlay)
        
        # Initialize screen region snipper overlay
        from core.snipper import ScreenSnipperOverlay
        self.snipper_overlay = ScreenSnipperOverlay()
        self.snipper_overlay.snippet_captured.connect(self.on_snippet_captured)

        # Connect settings & overlay signals
        self.settings_dialog.config_updated.connect(self.on_config_updated)
        self.overlay.settings_requested.connect(self.show_settings)
        self.overlay.clear_requested.connect(self.clear_assistant)
        self.overlay.mic_clicked.connect(self.toggle_voice_capture)
        self.overlay.autopilot_clicked.connect(self.toggle_autopilot)
        self.overlay.interview_clicked.connect(self.toggle_interview_mode)
        self.overlay.snip_clicked.connect(self.trigger_screen_snip)
        self.overlay.text_submitted.connect(self.on_text_submitted)

        # 2. Setup background native global hotkey thread worker
        self.hotkey_worker = HotkeyWorker()
        self.hotkey_worker.mic_triggered.connect(self.toggle_voice_capture)
        self.hotkey_worker.stealth_triggered.connect(self.overlay.toggle_click_through)
        self.hotkey_worker.snip_triggered.connect(self.trigger_screen_snip)
        self.hotkey_worker.start()

        # 2. Setup background worker threads
        self.speech_worker = None
        self.autopilot_worker = None
        self.interview_worker = None
        self.ai_worker = None
        self.autopilot_ai_worker = None
        self._interview_ai_workers = []   # LIST — prevents GC of running workers
        self._interview_active = False
        
        # 3. System Tray configuration
        self.setup_tray_icon()
        
        # Show overlay
        self.overlay.show()
        
        # Set initial status
        self.overlay.set_status("GhostAI Ready • Press Ctrl+Shift+S", "#00ffcc")

    def setup_tray_icon(self):
        """Creates an elegant programmatic tray icon and contextual menu."""
        self.tray_icon = QSystemTrayIcon(self)
        
        # Draw high-res glowing cyan orb for the tray
        pixmap = QtGui.QPixmap(64, 64)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        
        # Glowing body
        grad = QtGui.QRadialGradient(32, 32, 28)
        grad.setColorAt(0.0, QtGui.QColor(0, 240, 255, 255))
        grad.setColorAt(0.7, QtGui.QColor(0, 160, 255, 200))
        grad.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
        painter.setBrush(QtGui.QBrush(grad))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 56, 56)
        painter.end()
        
        self.tray_icon.setIcon(QtGui.QIcon(pixmap))
        self.tray_icon.setToolTip("GhostAI Stealth Assistant")
        
        # Create Tray Menu
        tray_menu = QMenu()
        
        show_action = tray_menu.addAction("Show Assistant")
        show_action.triggered.connect(self.overlay.show)
        
        hide_action = tray_menu.addAction("Hide Assistant")
        hide_action.triggered.connect(self.overlay.hide)
        
        tray_menu.addSeparator()
        
        click_action = tray_menu.addAction("Toggle Click-Through")
        click_action.triggered.connect(self.overlay.toggle_click_through)
        
        clear_action = tray_menu.addAction("Clear Screen")
        clear_action.triggered.connect(self.clear_assistant)
        
        settings_action = tray_menu.addAction("Settings & Memory")
        settings_action.triggered.connect(self.show_settings)
        
        tray_menu.addSeparator()
        
        exit_action = tray_menu.addAction("Exit GhostAI")
        exit_action.triggered.connect(self.quit_app)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        # Double clicking the tray icon shows/hides the overlay
        self.tray_icon.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.overlay.isVisible():
                self.overlay.hide()
            else:
                self.overlay.show()
                self.overlay.activateWindow()

    def show_settings(self):
        """Displays the settings dialog."""
        # Unmask settings dialog, it has capture protection enabled internally
        self.settings_dialog.load_values()
        self.settings_dialog.show()
        self.settings_dialog.activateWindow()

    def on_config_updated(self):
        """Triggered when settings are successfully saved."""
        self.config = load_config()
        
        # Update overlay parameters dynamically
        self.overlay.setWindowOpacity(self.config.get("opacity", 0.9))

    def on_text_submitted(self, text):
        """Triggered when the user types a message manually and presses Enter."""
        # 1. Add user message bubble to UI
        self.overlay.add_chat_message("user", text)
        
        # 2. Trigger background Gemini query
        self.overlay.set_status("Generating answer...", "#00ffcc")
        self.ai_worker = AIWorker(self.ai_client, text)
        self.ai_worker.finished.connect(self.on_ai_answered)
        self.ai_worker.start()

    def toggle_autopilot(self):
        """Toggles continuous Meeting Auto-Pilot Mode."""
        if self.autopilot_worker and self.autopilot_worker.isRunning():
            # Stop Auto-Pilot
            self.overlay.set_status("Auto-Pilot Stopping...", "#ffaa00")
            self.autopilot_worker.stop()
            self.overlay.set_autopilot_active(False)
            self.overlay.mic_btn.set_recording(False)
            self.overlay.mic_btn.set_volume(0.0)
        else:
            # Stop standard recording if active
            if self.speech_worker and self.speech_worker.isRunning():
                self.speech_worker.stop_recording()
                
            # Start Auto-Pilot continuous listening
            self.autopilot_worker = AutoPilotSpeechWorker()
            self.autopilot_worker.started.connect(self.on_autopilot_started)
            self.autopilot_worker.volume_changed.connect(self.overlay.mic_btn.set_volume)
            self.autopilot_worker.phrase_completed.connect(self.on_autopilot_phrase)
            self.autopilot_worker.status_changed.connect(self.overlay.set_status)
            self.autopilot_worker.error.connect(self.on_autopilot_error)
            self.autopilot_worker.start()
            
            self.overlay.set_autopilot_active(True)

    def on_autopilot_started(self):
        self.overlay.mic_btn.set_recording(True)

    def on_autopilot_phrase(self, text):
        """Processes a continuous speech phrase automatically."""
        # 1. Add user transcription bubble to chat display
        self.overlay.add_chat_message("user", text)
        self.overlay.set_status("Analyzing question...", "#00ffaa")
        
        # 2. Spawn non-blocking background Gemini analyzer
        self.autopilot_ai_worker = AutoPilotAIWorker(self.ai_client, text)
        self.autopilot_ai_worker.finished.connect(lambda ans: self.on_autopilot_ai_answered(ans, text))
        self.autopilot_ai_worker.start()

    def on_autopilot_ai_answered(self, answer, text):
        """Processes the copilot analysis from Gemini."""
        if answer.strip() == "[IGNORE]":
            # Just ignore general chatter, remove the last user bubble to keep the overlay clean!
            if hasattr(self.overlay, "chat_history") and self.overlay.chat_history:
                if self.overlay.chat_history[-1]["text"] == text:
                    self.overlay.chat_history.pop()
                    self.overlay.refresh_chat_display()
            self.overlay.set_status("Auto-Pilot Listening...", "#00ffcc")
            return
            
        # Display valid answer as AI bubble
        self.overlay.set_status("Answer Generated!", "#00ffcc")
        self.overlay.add_chat_message("ai", answer)

    def on_autopilot_error(self, err_msg):
        self.overlay.mic_btn.set_recording(False)
        self.overlay.mic_btn.set_volume(0.0)
        self.overlay.set_autopilot_active(False)
        self.overlay.set_status("Auto-Pilot Error", "#ff5555")

    def toggle_interview_mode(self):
        """
        Toggles fully hands-free Interview Mode.
        - Starts continuous listening (mic + system audio via WASAPI loopback)
        - Auto-detects each spoken phrase via VAD silence detection
        - Sends every phrase to AI (no filtering — always answers)
        - Immediately resumes listening after each answer
        - Click again to stop
        """
        if self._interview_active:
            # ── STOP interview mode ─────────────────────────────────────────
            self._interview_active = False
            if self.interview_worker and self.interview_worker.isRunning():
                self.interview_worker.stop()
                self.interview_worker = None
            self.overlay.set_interview_active(False)
            self.overlay.mic_btn.set_recording(False)
            self.overlay.mic_btn.set_volume(0.0)
        else:
            # ── START interview mode ────────────────────────────────────────
            # Stop any other modes that may be running
            if self.speech_worker and self.speech_worker.isRunning():
                self.speech_worker.stop_recording()
            if self.autopilot_worker and self.autopilot_worker.isRunning():
                self.autopilot_worker.stop()
                self.overlay.set_autopilot_active(False)

            self._interview_active = True

            # Use AutoPilotSpeechWorker with more sensitive VAD settings
            # Lower threshold = catches quieter interviewer voice from speakers
            # Shorter silence = faster response
            self.interview_worker = AutoPilotSpeechWorker(
                sample_rate=44100,
                silence_seconds=1.0,      # 1 second silence = end of phrase
                speech_threshold=500      # Lower than default 800 — more sensitive
            )
            self.interview_worker.started.connect(self.on_interview_started)
            self.interview_worker.volume_changed.connect(self.overlay.mic_btn.set_volume)
            self.interview_worker.phrase_completed.connect(self.on_interview_phrase)
            self.interview_worker.status_changed.connect(self._on_interview_status)
            self.interview_worker.error.connect(self.on_interview_error)
            self.interview_worker.start()

            self.overlay.set_interview_active(True)

    def on_interview_started(self):
        self.overlay.mic_btn.set_recording(True)
        self.overlay.set_status("Interview Mode • Listening...", "#ff4466")

    def _on_interview_status(self, text, color):
        """Relay interview worker status — only update display for meaningful states."""
        if not self._interview_active:
            return
        if "Listening" in text or "ACTIVE" in text or "Off" in text:
            self.overlay.set_status("🔴 Interview Mode • Listening...", "#ff4466")
        elif "Hearing" in text:
            self.overlay.set_status("🔴 Interview Mode • Hearing speech...", "#ffaa44")
        elif "Processing" in text:
            # Audio chunk sent to transcription — show a neutral status.
            # IMPORTANT: do NOT say "Generating answer" here — the AI has not been
            # called yet. If transcription silently fails (noise/STT error), the
            # status must reset itself back to Listening automatically.
            self.overlay.set_status("🔴 Interview Mode • Transcribing...", "#aaaaff")
            # Auto-reset to Listening after 6 s in case transcription fails silently
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(
                6000,
                lambda: self.overlay.set_status("🔴 Interview Mode • Listening...", "#ff4466")
                        if self._interview_active else None
            )

    def on_interview_phrase(self, text):
        """Called when transcription succeeds — AI is now actually invoked."""
        if not self._interview_active:
            return

        # Show the transcribed question immediately
        self.overlay.add_chat_message("user", text)
        # NOW it's correct to say "Generating answer" — AI is about to be called
        self.overlay.set_status("🔴 Interview Mode • Generating answer...", "#ffaa44")

        # Create worker and add to list BEFORE starting — prevents GC if
        # a second phrase arrives before this one finishes.
        worker = InterviewAIWorker(self.ai_client, text)
        self._interview_ai_workers.append(worker)
        worker.finished.connect(
            lambda answer, w=worker: self._on_interview_ai_done(answer, w)
        )
        worker.start()

    def _on_interview_ai_done(self, answer, worker):
        """Called when any InterviewAIWorker finishes. Cleans up worker list."""
        # Remove from tracking list so it can be GC'd now that it's done
        if worker in self._interview_ai_workers:
            self._interview_ai_workers.remove(worker)
        self.on_interview_ai_answered(answer)

    def on_interview_ai_answered(self, answer):
        """Displays interview answer and immediately resumes listening."""
        if not self._interview_active:
            return
        self.overlay.add_chat_message("ai", answer)
        self.overlay.set_status("🔴 Interview Mode • Listening...", "#ff4466")

    def on_interview_error(self, err_msg):
        self._interview_active = False
        self.overlay.mic_btn.set_recording(False)
        self.overlay.mic_btn.set_volume(0.0)
        self.overlay.set_interview_active(False)
        self.overlay.set_status("Interview Mode Error", "#ff5555")

    def toggle_voice_capture(self):
        """Toggles the microphone recording thread."""
        # If AI is generating, do not capture voice
        if self.ai_worker and self.ai_worker.isRunning():
            return

        if self.speech_worker and self.speech_worker.isRunning():
            # Stop recording (will trigger transcription)
            self.overlay.set_status("Thinking...", "#ffaa00")
            self.speech_worker.stop_recording()
        else:
            # Start recording
            self.speech_worker = SpeechWorker()
            self.speech_worker.started.connect(self.on_speech_started)
            self.speech_worker.volume_changed.connect(self.overlay.mic_btn.set_volume)
            self.speech_worker.finished.connect(self.on_speech_transcribed)
            self.speech_worker.error.connect(self.on_speech_error)
            self.speech_worker.start()

    def on_speech_started(self):
        self.overlay.mic_btn.set_recording(True)
        self.overlay.set_status("Hearing... Speak now!", "#00ffcc")

    def on_speech_error(self, err_msg):
        self.overlay.mic_btn.set_recording(False)
        self.overlay.mic_btn.set_volume(0.0)
        self.overlay.set_status("Error", "#ff5555")
        
        # Display the error text in the overlay
        self.overlay.text_browser.setHtml(
            f"<div style='color: #ff5555; text-align: center; margin-top: 50px;'>"
            f"⚠️ <b>Recording Error!</b><br><br>"
            f"{err_msg}"
            f"</div>"
        )

    def on_speech_transcribed(self, text):
        self.overlay.mic_btn.set_recording(False)
        self.overlay.mic_btn.set_volume(0.0)
        self.overlay.set_status("Transcribed", "#00ffcc")
        
        # Add voice transcription as a user bubble
        self.overlay.add_chat_message("user", text)
        
        # Trigger background Gemini query
        self.overlay.set_status("Generating answer...", "#00ffcc")
        self.ai_worker = AIWorker(self.ai_client, text)
        self.ai_worker.finished.connect(self.on_ai_answered)
        self.ai_worker.start()

    def on_ai_answered(self, answer):
        self.overlay.set_status("Completed", "#00ffcc")
        self.overlay.add_chat_message("ai", answer)

    def trigger_screen_snip(self):
        """Launches the interactive screen region snipper canvas."""
        self.overlay.set_status("📸 Drag rectangle to snip screen area...", "#00ffcc")
        self.snipper_overlay.start_snipping()

    def on_snippet_captured(self, img_bytes: bytes):
        """Triggered when a screen region snippet selection is completed."""
        if not img_bytes:
            return

        self.overlay.add_chat_message("user", "📸 *[Screen Snippet Captured]*")
        self.overlay.set_status("Analyzing Image Snippet...", "#00ffcc")
        self.image_ai_worker = AIImageWorker(self.ai_client, img_bytes)
        self.image_ai_worker.finished.connect(self.on_ai_answered)
        self.image_ai_worker.start()

    def clear_assistant(self):
        """Wipes current overlay text and rolling history."""
        self.ai_client.clear_history()
        if hasattr(self.overlay, "chat_history"):
            self.overlay.chat_history = []
        self.overlay._chat_started = False
        self.overlay.text_browser.setHtml(
            "<div style='color: #888899; text-align: center; margin-top: 50px;'>"
            "🧹 <b>Screen & History Cleared!</b><br><br>"
            "Context reset successfully. Ready for new questions."
            "</div>"
        )
        self.overlay.set_status("GhostAI Cleared", "#00ffcc")

    def quit_app(self):
        """Wipes hotkeys and gracefully exits."""
        self.tray_icon.hide()
        if hasattr(self, "hotkey_worker") and self.hotkey_worker:
            self.hotkey_worker.stop()
            self.hotkey_worker.wait() # Wait for thread exit
        QApplication.quit()


def main():
    # Fix high DPI display scaling on modern Windows resolutions
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) # Keep running in tray if overlay hidden
    
    # Initialize Core Application
    ghost_app = GhostApp()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
