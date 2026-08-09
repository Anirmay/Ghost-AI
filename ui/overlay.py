import re
import ctypes
from ctypes import wintypes
import traceback
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextBrowser, QSlider, QFrame, QSizeGrip
)
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QBrush, QPen

from core.capture_guard import protect_window
from core.config import load_config, save_config
from core.click_copy import GlobalClickCopyWorker

# Windows native global hotkey API bindings
user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL

def markdown_to_html(md_text: str) -> str:
    """
    Highly performant, lightweight regex Markdown-to-HTML engine
    specifically customized for PyQt6's QTextBrowser styling capabilities.
    """
    if not md_text:
        return ""
        
    # 1. Escape HTML special characters to prevent rendering injection
    html = md_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # 2. Format block code (```lang ... ```)
    def replace_code_block(match):
        code = match.group(1).strip()
        return (
            '<div style="background-color: rgba(10, 10, 15, 0.95); '
            'border: 1px solid rgba(0, 255, 230, 0.25); '
            'border-radius: 6px; padding: 10px; margin: 8px 0px; '
            'font-family: \'Consolas\', \'Courier New\', monospace; '
            'font-size: 11px; color: #00ffaa; white-space: pre-wrap; line-height: 1.4;">'
            f'{code}</div>'
        )
    html = re.sub(r'```(?:[a-zA-Z0-9_-]+)?\n(.*?)\n```', replace_code_block, html, flags=re.DOTALL)
    
    # 3. Format inline code (`code`)
    html = re.sub(
        r'`(.*?)`', 
        r'<span style="background-color: rgba(0, 255, 230, 0.12); '
        r'font-family: \'Consolas\', monospace; padding: 2px 5px; '
        r'border-radius: 4px; color: #ff007f;">\1</span>', 
        html
    )
    
    # 4. Format blockquotes (> text)
    def replace_blockquote(match):
        text = match.group(1).strip()
        return (
            '<div style="border-left: 3px solid #00f0ff; '
            'padding-left: 10px; margin: 8px 0px; color: #94a3b8; '
            f'font-style: italic;">{text}</div>'
        )
    html = re.sub(r'^&gt;\s*(.*?)$', replace_blockquote, html, flags=re.MULTILINE)
    
    # 5. Format headers (# Header)
    html = re.sub(r'^###\s*(.*?)$', r'<h3 style="color: #00f0ff; margin-top: 10px; margin-bottom: 4px; font-weight: bold;">\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^##\s*(.*?)$', r'<h2 style="color: #00f0ff; margin-top: 12px; margin-bottom: 6px; font-weight: bold; border-bottom: 1px solid rgba(0, 240, 255, 0.15); padding-bottom: 2px;">\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^#\s*(.*?)$', r'<h1 style="color: #00f0ff; margin-top: 14px; margin-bottom: 8px; font-weight: bold; border-bottom: 1px solid rgba(0, 240, 255, 0.3); padding-bottom: 4px;">\1</h1>', html, flags=re.MULTILINE)
    
    # 6. Format bold (**text**)
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong style="color: #ffffff; font-weight: bold;">\1</strong>', html)
    
    # 7. Format italic (*text*)
    html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
    
    # 8. Format bullet point lists (- list item)
    html = re.sub(r'^\s*[-*]\s*(.*?)$', r'<li style="color: #cbd5e1; margin-left: 12px; margin-bottom: 3px;">\1</li>', html, flags=re.MULTILINE)
    
    # 9. Format line breaks
    html = html.replace("\n", "<br>")
    
    # Clean up double linebreaks inside code blocks and list items
    html = re.sub(r'(<div.*?>)<br>', r'\1', html)
    html = re.sub(r'<br>(</div>)', r'\1', html)
    html = re.sub(r'<li>(.*?)</li><br>', r'<li>\1</li>', html)
    
    return html


class PulsingMicButton(QPushButton):
    """
    A custom button designed with advanced, responsive vectors.
    Breathes light cyan when idle, flashes hot magenta dynamically matching 
    incoming speech decibels when recording.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 60)
        self.volume = 0.0  # Normalized mic volume input: 0.0 to 1.0
        self.is_recording = False
        
        # Micro-animation parameters
        self.pulse_val = 0.0
        self.pulse_dir = 1
        
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(30)  # ~33 frames per second for organic motion

        self.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))

    def set_recording(self, recording: bool):
        self.is_recording = recording
        self.update()

    def set_volume(self, volume: float):
        import math
        if math.isnan(volume) or math.isinf(volume):
            self.volume = 0.0
        else:
            self.volume = max(0.0, min(1.0, volume))
        self.update()

    def update_animation(self):
        if not self.is_recording:
            # Idle smooth breathing cycle
            self.pulse_val += 0.025 * self.pulse_dir
            if self.pulse_val >= 1.0:
                self.pulse_val = 1.0
                self.pulse_dir = -1
            elif self.pulse_val <= 0.0:
                self.pulse_val = 0.0
                self.pulse_dir = 1
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        cx, cy = w / 2, h / 2
        
        # Calculate dynamic radii based on mic levels/breathing states
        if self.is_recording:
            outer_r = 22 + (self.volume * 22)
            inner_r = 17
            glow_col = QColor(255, 0, 110, int(160 - (self.volume * 60)))
            core_col = QColor(255, 0, 110)
        else:
            outer_r = 20 + (self.pulse_val * 6)
            inner_r = 15
            glow_col = QColor(0, 240, 255, int(70 + (self.pulse_val * 80)))
            core_col = QColor(0, 190, 255)
            
        # Draw outer breathing radial halo glow
        radial_grad = QRadialGradient(cx, cy, outer_r)
        radial_grad.setColorAt(0.0, glow_col)
        radial_grad.setColorAt(0.65, QColor(glow_col.red(), glow_col.green(), glow_col.blue(), int(glow_col.alpha() * 0.35)))
        radial_grad.setColorAt(1.0, QColor(glow_col.red(), glow_col.green(), glow_col.blue(), 0))
        
        painter.setBrush(QBrush(radial_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(cx - outer_r), int(cy - outer_r), int(outer_r * 2), int(outer_r * 2))
        
        # Draw solid high-intensity core
        painter.setBrush(QBrush(core_col))
        painter.drawEllipse(int(cx - inner_r), int(cy - inner_r), int(inner_r * 2), int(inner_r * 2))
        
        # Draw dynamic structural white ring border
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen_col = QColor(255, 255, 255, 220) if self.is_recording else QColor(0, 255, 230, 220)
        painter.setPen(QPen(pen_col, 2))
        painter.drawEllipse(int(cx - inner_r), int(cy - inner_r), int(inner_r * 2), int(inner_r * 2))
        
        # Draw minimalist Vector microphone icon inside the button
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        # Mic Capsule
        painter.drawRoundedRect(int(cx - 3), int(cy - 8), 6, 12, 3, 3)
        # Stand Horseshoe Arc
        painter.drawArc(int(cx - 7), int(cy - 3), 14, 11, 180 * 16, 180 * 16)
        # Stand Stem & Base
        painter.drawLine(int(cx), int(cy + 8), int(cx), int(cy + 11))
        painter.drawLine(int(cx - 4), int(cy + 11), int(cx + 4), int(cy + 11))


class ElegantSizeGrip(QSizeGrip):
    """Custom size grip that draws a modern glowing cyan corner indicator.
    Cursor is forced to ArrowCursor — QSizeGrip normally overrides this
    internally so we reset it in enterEvent and mouseMoveEvent."""

    def _reset_cursor(self):
        self.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))

    def enterEvent(self, event):
        super().enterEvent(event)
        self._reset_cursor()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self._reset_cursor()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        pen = QPen(QColor(0, 240, 255, 180), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        # Draw 3 diagonal lines of decreasing length towards the corner
        painter.drawLine(w - 12, h - 2, w - 2, h - 12)
        painter.drawLine(w - 8,  h - 2, w - 2, h - 8)
        painter.drawLine(w - 4,  h - 2, w - 2, h - 4)





class GhostOverlay(QWidget):
    """
    Main Floating Desktop Overlay. Incorporates frameless controls,
    Windows display affinity, drag handling, and markdown text rendering.
    """
    settings_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    mic_clicked = pyqtSignal()
    autopilot_clicked = pyqtSignal()
    interview_clicked = pyqtSignal()
    text_submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_position = QPoint()
        
        # Window attributes for complete custom design
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # Load user configuration
        self.config = load_config()
        
        # UI Elements setup
        self.init_ui()
        self.apply_theme()
        
        # Window positioning
        self.resize(self.config.get("width", 450), self.config.get("height", 400))
        self.move(self.config.get("x", 100), self.config.get("y", 100))
        self.setWindowOpacity(self.config.get("opacity", 0.9))
        self.set_click_through(self.config.get("click_through", False))
        self.set_click_copy(self.config.get("click_copy", False))

    def init_ui(self):
        # Base container widget to allow rounded border styling
        self.base_widget = QWidget(self)
        self.base_widget.setObjectName("base_widget")
        
        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.base_widget)
        
        container_layout = QVBoxLayout(self.base_widget)
        container_layout.setContentsMargins(12, 8, 12, 12)
        container_layout.setSpacing(8)
        
        # 1. Custom Title Bar Layout
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)
        
        # Logo / Glow indicator
        self.logo_label = QLabel("👻", self)
        self.logo_label.setStyleSheet("font-size: 15px;")
        header_layout.addWidget(self.logo_label)
        
        # Drag title label
        self.title_label = QLabel("GHOST AI", self)
        self.title_label.setObjectName("title_label")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        # 🎤 Interview Mode Button
        self.interview_btn = QPushButton("🎤", self)
        self.interview_btn.setFixedSize(24, 24)
        self.interview_btn.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))
        self.interview_btn.setObjectName("interview_btn")
        self.interview_btn.clicked.connect(self.interview_clicked.emit)
        header_layout.addWidget(self.interview_btn)

        # 🧠 Auto-Pilot Mode Toggle Button
        self.autopilot_btn = QPushButton("🧠", self)
        self.autopilot_btn.setFixedSize(24, 24)
        self.autopilot_btn.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))
        self.autopilot_btn.clicked.connect(self.toggle_autopilot_requested)
        header_layout.addWidget(self.autopilot_btn)
        
        # 📋 Click-to-Copy Toggle Button
        self.click_copy_btn = QPushButton("📋", self)
        self.click_copy_btn.setFixedSize(24, 24)
        self.click_copy_btn.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))
        self.click_copy_btn.setObjectName("click_copy_btn")
        self.click_copy_btn.setToolTip("Toggle Click-to-Copy Feature")
        self.click_copy_btn.clicked.connect(self.toggle_click_copy)
        header_layout.addWidget(self.click_copy_btn)

        # Click-Through Toggle Button
        self.lock_btn = QPushButton("🔓", self)
        self.lock_btn.setFixedSize(24, 24)
        self.lock_btn.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))
        self.lock_btn.clicked.connect(self.toggle_click_through)
        header_layout.addWidget(self.lock_btn)
        
        # Clear/Sweep Text Button
        self.clear_btn = QPushButton("🧹", self)
        self.clear_btn.setFixedSize(24, 24)
        self.clear_btn.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))
        self.clear_btn.clicked.connect(self.clear_requested.emit)
        header_layout.addWidget(self.clear_btn)
        
        # Settings Gear Button
        self.settings_btn = QPushButton("⚙", self)
        self.settings_btn.setFixedSize(24, 24)
        self.settings_btn.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        header_layout.addWidget(self.settings_btn)
        
        # Minimize button
        self.minimize_btn = QPushButton("—", self)
        self.minimize_btn.setFixedSize(24, 24)
        self.minimize_btn.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))
        self.minimize_btn.clicked.connect(self.hide)
        header_layout.addWidget(self.minimize_btn)
        
        container_layout.addLayout(header_layout)
        
        # 2. Border divider
        self.divider = QFrame(self)
        self.divider.setFrameShape(QFrame.Shape.HLine)
        self.divider.setFrameShadow(QFrame.Shadow.Sunken)
        self.divider.setObjectName("divider")
        container_layout.addWidget(self.divider)
        
        # 3. Output Text Display
        self.text_browser = QTextBrowser(self)
        self.text_browser.setObjectName("text_browser")
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setHtml(
            "<div style='color: #888899; text-align: center; margin-top: 50px;'>"
            "🚀 <b>GhostAI Stealthed Copilot</b><br><br>"
            "Press the **Global Hotkey** <font color='#00ffcc'><b>Ctrl + Shift + S</b></font> "
            "or click the microphone below to start talking.<br><br>"
            "All answers will stream here invisibly to screen shares!"
            "</div>"
        )
        container_layout.addWidget(self.text_browser)
        
        # 4. Input status indicator (e.g. "Hearing...", "Generating...")
        self.status_label = QLabel("", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setObjectName("status_label")
        container_layout.addWidget(self.status_label)
        
        # 5. Write box & Voice Button side-by-side Layout
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(6)
        
        # Cyberpunk Styled Write Box
        self.input_field = QtWidgets.QLineEdit(self)
        self.input_field.setObjectName("input_field")
        self.input_field.setPlaceholderText("Type a message and press Enter...")
        self.input_field.setFixedHeight(36)
        self.input_field.returnPressed.connect(self.on_input_submitted)
        footer_layout.addWidget(self.input_field)
        
        # Compact, high-tech voice button positioned to the side
        self.mic_btn = PulsingMicButton(self)
        self.mic_btn.setFixedSize(36, 36)
        self.mic_btn.clicked.connect(self.mic_clicked.emit)
        footer_layout.addWidget(self.mic_btn)
        
        # Sleek, functional Size Grip — uses ElegantSizeGrip subclass so the
        # cursor stays as ArrowCursor even during resize (QSizeGrip overrides internally)
        self.sizegrip = ElegantSizeGrip(self)
        self.sizegrip.setFixedSize(14, 14)
        self.sizegrip.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))
        footer_layout.addWidget(self.sizegrip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        
        container_layout.addLayout(footer_layout)

    def apply_theme(self):
        # Stunning Cyberpunk Glassmorphic stylesheet
        stylesheet = """
            QWidget#base_widget {
                background-color: rgba(14, 14, 20, 0.88);
                border: 1px solid rgba(0, 240, 255, 0.35);
                border-radius: 12px;
            }
            QLabel#title_label {
                color: #00f0ff;
                font-family: 'Outfit', 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
                font-size: 11px;
                letter-spacing: 2px;
            }
            QFrame#divider {
                background-color: rgba(0, 240, 255, 0.12);
                max-height: 1px;
                border: none;
            }
            QTextBrowser {
                background-color: transparent;
                border: none;
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                line-height: 1.5;
            }
            QLabel#status_label {
                color: #00ffcc;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }
            /* Clean Minimal Scrollbar */
            QScrollBar:vertical {
                border: none;
                background: rgba(0, 0, 0, 0);
                width: 6px;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 255, 230, 0.2);
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 255, 230, 0.5);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            /* Flat buttons in Title Bar */
            QPushButton {
                background-color: transparent;
                color: #e2e8f0;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(0, 240, 255, 0.15);
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: rgba(0, 240, 255, 0.3);
            }
            /* High-tech glassmorphic write box styling */
            QLineEdit#input_field {
                background-color: rgba(30, 30, 40, 0.60);
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 6px;
                padding: 6px 10px;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }
            QLineEdit#input_field:focus {
                border: 1px solid #00f0ff;
                background-color: rgba(30, 30, 40, 0.90);
            }
        """
        self.setStyleSheet(stylesheet)

    # ------------------ Draggable Frameless Window Handlers ------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is on title bar/logo area (top 35px) to allow dragging
            if event.position().y() < 35:
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
            
    def mouseReleaseEvent(self, event):
        self.drag_position = QPoint()
        # Update memory state (will be saved to disk on closeEvent)
        self.config["x"] = self.x()
        self.config["y"] = self.y()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Update memory state (will be saved to disk on closeEvent)
        self.config["width"] = self.width()
        self.config["height"] = self.height()

    # ------------------ Stealth Exclude Display Affinity & Native Hotkeys ------------------
    def showEvent(self, event):
        try:
            print("[*] showEvent triggered inside GhostOverlay!")
            super().showEvent(event)
            print("[+] super().showEvent(event) completed successfully.")
            
            hwnd = int(self.winId())
            print(f"[*] Window handle acquired: {hwnd}")
            
            # Apply display protection from screen shares (Stealth Mode)
            protected = protect_window(hwnd)
            print(f"[*] protect_window result: {protected}")
        except Exception as e:
            print(f"[-] Error in overlay showEvent initialization: {e}")
            traceback.print_exc() if "traceback" in globals() else None

    def closeEvent(self, event):
        # Defer disk writes: Save final window geometry cleanly on exit
        try:
            self.config["x"] = self.x()
            self.config["y"] = self.y()
            self.config["width"] = self.width()
            self.config["height"] = self.height()
            save_config(self.config)
            print("[+] Configuration successfully saved on close.")
        except Exception as e:
            print(f"[-] Failed to save configuration on close: {e}")
            
        super().closeEvent(event)



    # ------------------ Interactive Features ------------------
    def set_status(self, text: str, color_hex: str = "#00ffcc"):
        """Displays status message below the display browser."""
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color_hex}; font-family: 'Consolas', monospace; font-size: 11px;")

    def on_text_copied(self, copied_text: str):
        """Displays a brief status notification when text is clicked & copied from any webpage or box to clipboard."""
        if copied_text:
            cb = QtWidgets.QApplication.clipboard()
            if cb:
                cb.setText(copied_text)
        preview = copied_text[:28] + "..." if len(copied_text) > 28 else copied_text
        self.set_status(f"📋 Copied: \"{preview}\"", "#00ffcc")
        QTimer.singleShot(2500, lambda: self.set_status(
            "📋 GLOBAL CLICK-COPY: ON" if self.config.get("click_copy", False) else ("STEALTH: Interactive" if not self.config.get("click_through", False) else "STEALTH: Click-through ACTIVE"), 
            "#00ffcc"
        ))

    def is_point_inside(self, x: int, y: int) -> bool:
        """Returns True if global screen point (x, y) falls inside the GhostOverlay window bounds."""
        g_pos = self.mapToGlobal(QPoint(0, 0))
        w = self.width()
        h = self.height()
        return (g_pos.x() <= x <= g_pos.x() + w and g_pos.y() <= y <= g_pos.y() + h)

    def set_click_copy(self, active: bool):
        """Toggles the global background click-to-copy feature on or off."""
        self.config["click_copy"] = active
        save_config(self.config)

        if active:
            if not getattr(self, "global_copy_worker", None):
                hwnd = int(self.winId()) if self.winId() else None
                self.global_copy_worker = GlobalClickCopyWorker(
                    overlay_hwnd=hwnd, 
                    is_inside_callback=self.is_point_inside
                )
                self.global_copy_worker.text_copied.connect(self.on_text_copied)
            self.global_copy_worker.start_listening()

            if hasattr(self, "click_copy_btn"):
                self.click_copy_btn.setStyleSheet(
                    "color: #00ffcc; font-weight: bold; "
                    "background-color: rgba(0, 240, 255, 0.25); "
                    "border: 1px solid #00f0ff; border-radius: 4px;"
                )
                self.set_status("📋 GLOBAL CLICK-COPY: ON", "#00ffcc")
        else:
            if getattr(self, "global_copy_worker", None):
                self.global_copy_worker.stop_listening()

            if hasattr(self, "click_copy_btn"):
                self.click_copy_btn.setStyleSheet("")
                self.set_status("📋 GLOBAL CLICK-COPY: OFF", "#94a3b8")

    def toggle_click_copy(self):
        """Toggles click-to-copy state."""
        current = self.config.get("click_copy", False)
        self.set_click_copy(not current)

    def set_click_through(self, active: bool):
        """Toggles the window click-through state (WA_TransparentForMouseEvents)."""
        self.config["click_through"] = active
        save_config(self.config)
        
        if active:
            # Enable click-through
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.lock_btn.setText("🔒")
            # Add glowing transparent effect to background
            self.base_widget.setStyleSheet(
                "QWidget#base_widget { background-color: rgba(14, 14, 20, 0.5); "
                "border: 1px solid rgba(0, 240, 255, 0.15); border-radius: 12px; }"
            )
            # Give short notification
            self.set_status("STEALTH: Click-through ACTIVE", "#ff5555")
        else:
            # Disable click-through (interactive)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.lock_btn.setText("🔓")
            self.base_widget.setStyleSheet("")
            self.set_status("STEALTH: Interactive", "#00ffcc")

    def toggle_click_through(self):
        """Utility function called by buttons or key events."""
        self.set_click_through(not self.config.get("click_through", False))

    def on_input_submitted(self):
        """Handles user text input when Enter is pressed in the write box."""
        text = self.input_field.text().strip()
        if text:
            self.input_field.clear()
            self.text_submitted.emit(text)

    def add_chat_message(self, role: str, text: str):
        """Adds a chat message to the history and refreshes the display."""
        if not hasattr(self, "chat_history"):
            self.chat_history = []
        
        # Check if it's the first message and clear introductory welcome screen
        if not hasattr(self, "_chat_started") or not self._chat_started:
            self._chat_started = True
            self.chat_history = []
            
        self.chat_history.append({"role": role, "text": text})
        self.refresh_chat_display()

    def refresh_chat_display(self):
        """Renders the complete list of conversation messages as elegant bubbles."""
        if not hasattr(self, "chat_history"):
            return
            
        html = ""
        for msg in self.chat_history:
            role = msg["role"]
            text = msg["text"]
            
            if role == "user":
                # Slate blue chat bubble, aligned right, rounded corners
                html += (
                    '<div style="display: block; text-align: right; margin: 10px 0px;">'
                    '<span style="display: inline-block; background-color: #1e3a8a; color: #ffffff; '
                    'padding: 8px 12px; border-radius: 12px 12px 2px 12px; max-width: 80%; '
                    f'text-align: left; font-size: 13px; line-height: 1.4; font-family: \'Segoe UI\', Arial;">{text}</span>'
                    '</div>'
                )
            else:
                # Cyan accent bar left-aligned response bubble
                formatted_ai = markdown_to_html(text)
                html += (
                    '<div style="display: block; text-align: left; margin: 14px 0px; '
                    'padding-left: 8px; border-left: 2px solid rgba(0, 240, 255, 0.45);">'
                    f'<div style="color: #e2e8f0; font-size: 13px; line-height: 1.5; font-family: \'Segoe UI\', Arial;">{formatted_ai}</div>'
                    '</div>'
                )
                
        self.text_browser.setHtml(html)
        
        # Debounced scrolling: Wait for HTML to render, then auto-scroll to bottom
        QtCore.QTimer.singleShot(50, lambda: self.text_browser.verticalScrollBar().setValue(
            self.text_browser.verticalScrollBar().maximum()
        ))

    def update_answer(self, markdown_text: str):
        """Appends the AI answer to the chat history and updates bubble UI."""
        self.add_chat_message("ai", markdown_text)

    def toggle_autopilot_requested(self):
        """Emits the autopilot click signal."""
        self.autopilot_clicked.emit()

    def set_autopilot_active(self, active: bool):
        """Updates the overlay UI style to reflect if Auto-Pilot Mode is running."""
        if active:
            # Active (Continuous listening) - glow brain emerald green
            self.autopilot_btn.setText("🤖")
            self.autopilot_btn.setStyleSheet("color: #00ffaa; font-weight: bold; background-color: rgba(0, 255, 170, 0.15);")
            self.set_status("AUTO-PILOT ACTIVE", "#00ffaa")
            # Set a subtle emerald green border glow on base widget
            self.base_widget.setStyleSheet(
                "QWidget#base_widget { background-color: rgba(14, 14, 20, 0.90); "
                "border: 1px solid rgba(0, 255, 170, 0.45); border-radius: 12px; }"
            )
        else:
            # Inactive - revert brain to standard look
            self.autopilot_btn.setText("🧠")
            self.autopilot_btn.setStyleSheet("")
            self.set_status("AUTO-PILOT OFF", "#00f0ff")
            self.base_widget.setStyleSheet("")

    def set_interview_active(self, active: bool):
        """Updates the overlay UI to reflect if Interview Mode is live."""
        if active:
            # Pulsing red LIVE indicator on the mic button
            self.interview_btn.setText("🔴")
            self.interview_btn.setStyleSheet(
                "color: #ff4466; font-weight: bold; "
                "background-color: rgba(255, 60, 80, 0.18); "
                "border: 1px solid rgba(255, 60, 80, 0.50); border-radius: 4px;"
            )
            self.set_status("🔴 Interview Mode • Listening...", "#ff4466")
            # Hot red border glow on the overlay frame
            self.base_widget.setStyleSheet(
                "QWidget#base_widget { background-color: rgba(14, 14, 20, 0.92); "
                "border: 1px solid rgba(255, 60, 80, 0.50); border-radius: 12px; }"
            )
        else:
            # Revert to normal mic icon
            self.interview_btn.setText("🎤")
            self.interview_btn.setStyleSheet("")
            self.set_status("INTERVIEW MODE OFF", "#00f0ff")
            self.base_widget.setStyleSheet("")
