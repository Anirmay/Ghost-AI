import sys
import os
import traceback

# Ensure current folder is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("[*] Starting PyQt6 Diagnostic Session...")

try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    print("[+] QApplication created successfully.")
    
    from ui.overlay import GhostOverlay
    print("[+] GhostOverlay class imported.")
    
    # Enable python exception printing for Qt event handlers
    sys.excepthook = lambda cls, err, tb: traceback.print_exception(cls, err, tb)
    
    print("[*] Instantiating GhostOverlay...")
    overlay = GhostOverlay()
    print("[+] GhostOverlay instantiated!")
    
    print("[*] Showing overlay (will trigger showEvent)...")
    overlay.show()
    print("[+] Overlay shown successfully!")
    
    # Run the event loop for 5 seconds so the user can verify the overlay visually
    print("[*] Running event loop for 5 seconds to let you see the overlay...")
    from PyQt6.QtCore import QTimer
    timer = QTimer()
    timer.timeout.connect(app.quit)
    timer.start(5000)
    app.exec()
    print("[+] Event loop finished!")
    
except Exception as e:
    print("[-] CRITICAL DIAGNOSTIC EXCEPTION CAUGHT:")
    traceback.print_exc()
    sys.exit(1)

print("[+] Diagnostic check completed successfully without crash.")
