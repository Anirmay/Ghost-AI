# 👻 GhostAI — Invisible Desktop Assistant & Stealth Meeting Copilot

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![UI Framework](https://img.shields.io/badge/UI-PyQt6-brightgreen.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![AI Engine](https://img.shields.io/badge/AI-Google%20Gemini-orange.svg)](https://ai.google.dev/)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://microsoft.com/windows)

**GhostAI** is an invisible, ultra-fast desktop overlay assistant engineered for stealth, rapid answer retrieval, and real-time meeting/interview support. Built with Python, PyQt6, and the Google Gemini API, it provides instant answers without interrupting your workflow.

---

## ✨ Features

- 👻 **Stealth Screen Overlay**: Sleek, floating semi-transparent UI overlay with adjustable opacity and custom dark neon themes.
- 🛡️ **Anti-Screen Capture Guard**: Integrates Windows Native API (`SetWindowDisplayAffinity` `WDA_EXCLUDEFROMCAPTURE`) so the overlay remains completely invisible during screen shares (Zoom, Microsoft Teams, Google Meet, Discord, OBS, or screenshots).
- ⚡ **Ultra-Fast Answer Engine**: Dynamically cascades across Gemini flash models (`gemini-flash-latest`, `gemini-3.6-flash`, `gemini-2.0-flash`) for sub-second, direct answers with zero fluff.
- 🎙️ **Real-Time Voice & Interview Copilot**: Live microphone audio capture with speech recognition for hands-free query answering during meetings, interviews, or coding sessions.
- 💾 **Local Knowledge Base (`memory.txt`)**: Reads a local knowledge base file on every query to personalize answers with your custom facts, resume details, or code cheat sheets.
- ⚙️ **Global Hotkey & Tray Control**: Quick toggling via global hotkey (`Ctrl + Shift + S`) and system tray integration.

---

## 🛠️ Project Structure

```
GhostAI/
├── main.py                    # Application entry point & Qt event loop
├── config.json                # User settings (API key, hotkey, opacity, window geometry)
├── memory.txt                 # Local private knowledge base / memory storage
├── requirements.txt           # Project Python dependencies
├── GhostAI.spec               # PyInstaller build specification
├── GhostAI.bat                # Windows quick launcher batch script
├── icon.ico                   # Application icon
├── core/                      # Core backend logic
│   ├── ai.py                  # Gemini API client, model cascading & response parsing
│   ├── capture_guard.py       # Windows API screen capture protection hook
│   ├── config.py              # Configuration & memory file managers
│   ├── hotkey.py              # Windows global hotkey listener
│   └── speech.py              # Speech recognition & audio stream processing
└── ui/                        # User Interface components
    ├── overlay.py             # Main PyQt6 floating stealth window
    └── settings.py            # Settings dialog & memory editor panel
```

---

## 🚀 Getting Started

### Prerequisites

- **Windows OS** (Windows 10/11 recommended)
- **Python 3.10+**
- **Google Gemini API Key** (Get a free key from [Google AI Studio](https://aistudio.google.com/))

### Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/Anirmay/Ghost-AI.git
   cd Ghost-AI
   ```

2. **Set Up Virtual Environment**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## 💻 Running the App

### Option 1: Run with Python
```powershell
.\.venv\Scripts\python.exe main.py
```

### Option 2: Run Launcher Batch File
Double-click `GhostAI.bat` or run:
```cmd
GhostAI.bat
```

---

## 📦 Building Standalone Executable (`GhostAI.exe`)

You can compile **GhostAI** into a single-file executable (`GhostAI.exe`) with PyInstaller:

1. Install PyInstaller in your environment:
   ```bash
   pip install pyinstaller
   ```

2. Run PyInstaller with `GhostAI.spec`:
   ```bash
   pyinstaller GhostAI.spec --noconfirm
   ```

3. Find the standalone `GhostAI.exe` file in the `dist/` directory!

---

## ⚙️ Configuration & Controls

| Action / Setting | Description / Default |
| :--- | :--- |
| **Global Voice Hotkey** | Press `Ctrl + Shift + S` to trigger voice query listening |
| **Settings Panel** | Click the **⚙ (Gear)** icon on the overlay or tray to open Settings |
| **API Key Entry** | Paste your Gemini API Key in Settings |
| **Opacity Slider** | Adjust window transparency in real time (10% to 100%) |
| **Memory Editor** | Edit `memory.txt` directly from the Settings dialog |

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
