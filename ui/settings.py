import os
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTextEdit, QPushButton, QSlider, QMessageBox, QTabWidget, QWidget
)
from PyQt6.QtCore import pyqtSignal, Qt

from core.config import load_config, save_config, load_memory, save_memory
from core.capture_guard import protect_window

class SettingsDialog(QDialog):
    """
    Settings panel containing API configuration, UI opacity/size parameters,
    and a direct text editor for the local knowledge base (memory.txt).
    Protected from screen shares.
    """
    config_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GhostAI Controller Panel")
        self.resize(550, 600)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
        self.config = load_config()
        self.init_ui()
        self.apply_theme()
        
        # Load active config data into UI
        self.load_values()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # Header title
        header = QLabel("👻 GHOSTAI SYSTEM SETTINGS", self)
        header.setObjectName("header_title")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)
        
        # Tabs for clean layout
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("tabs")
        
        # TAB 1: System Config
        config_tab = QWidget()
        config_layout = QVBoxLayout(config_tab)
        config_layout.setSpacing(12)
        config_layout.setContentsMargins(12, 12, 12, 12)
        
        # Gemini API Key Entry
        api_label = QLabel("Gemini API Key:", self)
        api_label.setObjectName("field_label")
        config_layout.addWidget(api_label)
        
        api_row = QHBoxLayout()
        self.api_input = QLineEdit(self)
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_input.setPlaceholderText("Enter your AI Studio API Key...")
        api_row.addWidget(self.api_input)
        
        self.reveal_btn = QPushButton("👁", self)
        self.reveal_btn.setFixedSize(30, 30)
        self.reveal_btn.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))
        self.reveal_btn.clicked.connect(self.toggle_api_visibility)
        api_row.addWidget(self.reveal_btn)
        config_layout.addLayout(api_row)
        
        # Help link
        link_label = QLabel(self)
        link_label.setText('<a href="https://aistudio.google.com/" style="color: #00f0ff; text-decoration: none;">🔗 Click here to get a free Gemini API Key from Google AI Studio</a>')
        link_label.setOpenExternalLinks(True)
        link_label.setObjectName("help_label")
        config_layout.addWidget(link_label)
        
        # Hotkey Configuration
        hotkey_label = QLabel("Voice Global Hotkey:", self)
        hotkey_label.setObjectName("field_label")
        config_layout.addWidget(hotkey_label)
        
        self.hotkey_input = QLineEdit(self)
        self.hotkey_input.setPlaceholderText("e.g. ctrl+shift+s")
        config_layout.addWidget(self.hotkey_input)
        
        hotkey_help = QLabel("Default is 'ctrl+shift+s'. Use lowercase '+' delimited keys.", self)
        hotkey_help.setObjectName("small_help")
        config_layout.addWidget(hotkey_help)
        
        # Real-time Opacity slider
        opacity_label = QLabel("Overlay Window Opacity:", self)
        opacity_label.setObjectName("field_label")
        config_layout.addWidget(opacity_label)
        
        opacity_row = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.opacity_slider.setMinimum(10)  # 10%
        self.opacity_slider.setMaximum(100) # 100%
        self.opacity_slider.setSingleStep(5)
        self.opacity_slider.valueChanged.connect(self.on_opacity_slide)
        opacity_row.addWidget(self.opacity_slider)
        
        self.opacity_val_lbl = QLabel("90%", self)
        self.opacity_val_lbl.setObjectName("slider_value")
        self.opacity_val_lbl.setFixedWidth(40)
        opacity_row.addWidget(self.opacity_val_lbl)
        config_layout.addLayout(opacity_row)
        
        config_layout.addStretch()
        self.tabs.addTab(config_tab, "⚙ General settings")
        
        # TAB 2: Memory / Knowledge Base Manager
        memory_tab = QWidget()
        memory_layout = QVBoxLayout(memory_tab)
        memory_layout.setSpacing(8)
        memory_layout.setContentsMargins(12, 12, 12, 12)
        
        mem_instructions = QLabel("Local Memory / Private Knowledge base:", self)
        mem_instructions.setObjectName("field_label")
        memory_layout.addWidget(mem_instructions)
        
        mem_desc = QLabel("Enter any private facts, notes, code snippets, or cheat sheets. The AI reads this file on every turn to answer questions correctly.", self)
        mem_desc.setWordWrap(True)
        mem_desc.setObjectName("small_help")
        memory_layout.addWidget(mem_desc)
        
        self.memory_editor = QTextEdit(self)
        self.memory_editor.setPlaceholderText("# Paste your notes here...")
        self.memory_editor.setAcceptRichText(False)
        self.memory_editor.setObjectName("memory_editor")
        memory_layout.addWidget(self.memory_editor)
        
        self.tabs.addTab(memory_tab, "💾 Memory Base Editor")
        main_layout.addWidget(self.tabs)
        
        # Bottom Actions row
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)
        
        self.save_btn = QPushButton("Save Config & Memory", self)
        self.save_btn.setObjectName("save_btn")
        self.save_btn.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))
        self.save_btn.clicked.connect(self.save_all)
        actions_layout.addWidget(self.save_btn)
        
        self.close_btn = QPushButton("Close", self)
        self.close_btn.setObjectName("close_btn")
        self.close_btn.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))
        self.close_btn.clicked.connect(self.reject)
        actions_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(actions_layout)

    def apply_theme(self):
        # Professional dark mode styling
        stylesheet = """
            QDialog {
                background-color: #111116;
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel#header_title {
                color: #00f0ff;
                font-size: 15px;
                font-weight: bold;
                letter-spacing: 2px;
                padding-bottom: 5px;
            }
            QLabel#field_label {
                color: #00f0ff;
                font-size: 12px;
                font-weight: bold;
            }
            QLabel#slider_value {
                color: #00ffcc;
                font-size: 12px;
                font-weight: bold;
            }
            QLabel#small_help {
                color: #94a3b8;
                font-size: 10px;
            }
            QLineEdit {
                background-color: #1e1e24;
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 6px;
                padding: 6px 10px;
                color: #ffffff;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #00f0ff;
            }
            QTextEdit#memory_editor {
                background-color: #1e1e24;
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 6px;
                padding: 10px;
                color: #f1f5f9;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }
            QTextEdit#memory_editor:focus {
                border: 1px solid #00f0ff;
            }
            QTabWidget::pane {
                border: 1px solid rgba(0, 240, 255, 0.15);
                border-radius: 8px;
                background-color: #16161c;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #111116;
                border: 1px solid rgba(0, 240, 255, 0.15);
                border-bottom-color: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 16px;
                color: #94a3b8;
                font-size: 11px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #16161c;
                color: #00f0ff;
                border-bottom: 2px solid #00f0ff;
            }
            QTabBar::tab:hover {
                color: #ffffff;
                background-color: rgba(0, 240, 255, 0.08);
            }
            QPushButton {
                background-color: #1e1e26;
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 6px;
                padding: 8px 16px;
                color: #cbd5e1;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(0, 240, 255, 0.15);
                border: 1px solid #00f0ff;
                color: #ffffff;
            }
            QPushButton#save_btn {
                background-color: rgba(0, 240, 255, 0.1);
                border: 1px solid #00f0ff;
                color: #00f0ff;
            }
            QPushButton#save_btn:hover {
                background-color: #00f0ff;
                color: #111116;
            }
            QSlider::groove:horizontal {
                border: 1px solid rgba(255, 255, 255, 0.1);
                height: 6px;
                background: #1e1e24;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #00f0ff;
                border: none;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #00ffcc;
            }
        """
        self.setStyleSheet(stylesheet)

    def load_values(self):
        """Loads configuration and memory text into GUI widgets."""
        self.api_input.setText(self.config.get("api_key", ""))
        self.hotkey_input.setText(self.config.get("hotkey", "ctrl+shift+s"))
        
        opacity_percent = int(self.config.get("opacity", 0.9) * 100)
        self.opacity_slider.setValue(opacity_percent)
        self.opacity_val_lbl.setText(f"{opacity_percent}%")
        
        # Load local memory base file text
        self.memory_editor.setPlainText(load_memory())

    def toggle_api_visibility(self):
        """Toggles the password masking for the API field."""
        if self.api_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.reveal_btn.setText("🙈")
        else:
            self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.reveal_btn.setText("👁")

    def on_opacity_slide(self, val):
        """Callback to update percentage text in real time."""
        self.opacity_val_lbl.setText(f"{val}%")
        # If overlay window parent exists, update its opacity dynamically
        if self.parent() and hasattr(self.parent(), "setWindowOpacity"):
            self.parent().setWindowOpacity(val / 100.0)

    def save_all(self):
        """Persists config fields and raw memory text to storage."""
        # 1. Update config model
        self.config["api_key"] = self.api_input.text().strip()
        self.config["hotkey"] = self.hotkey_input.text().strip().lower()
        self.config["opacity"] = self.opacity_slider.value() / 100.0
        
        # Save config
        if not save_config(self.config):
            QMessageBox.critical(self, "Error", "Failed to save configuration data.")
            return
            
        # 2. Save Memory Text
        memory_text = self.memory_editor.toPlainText()
        if not save_memory(memory_text):
            QMessageBox.critical(self, "Error", "Failed to save local memory base.")
            return

        # Emit update signal
        self.config_updated.emit()
        
        QMessageBox.information(self, "Success", "Configuration and Memory base updated successfully!")
        self.accept()

    def showEvent(self, event):
        super().showEvent(event)
        # Exclude settings panel from screen share captures too
        hwnd = int(self.winId())
        protect_window(hwnd)
