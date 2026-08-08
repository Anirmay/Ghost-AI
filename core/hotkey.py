import ctypes
from ctypes import wintypes
from PyQt6 import QtCore

# Declare Windows native API bindings
user32 = ctypes.WinDLL("user32", use_last_error=True)

user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL

user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL

user32.PeekMessageW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.PeekMessageW.restype = wintypes.BOOL

user32.TranslateMessage.argtypes = [ctypes.c_void_p]
user32.TranslateMessage.restype = wintypes.BOOL

user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.restype = ctypes.c_void_p

class HotkeyWorker(QtCore.QThread):
    """
    Background worker thread that runs a dedicated Win32 message loop.
    Registers global hotkeys safely without triggering PyQt6 event loop conflicts,
    and emits PyQt6 signals when hotkeys are pressed.
    """
    mic_triggered = QtCore.pyqtSignal()
    stealth_triggered = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = False

    def stop(self):
        """Gracefully shuts down the message pump loop."""
        self._is_running = False

    def run(self):
        self._is_running = True
        
        # Register hotkeys on this thread context (HWND = NULL)
        # IDs: 1 = Ctrl+Shift+S (0x53), 2 = Ctrl+Shift+C (0x43)
        # Modifiers: MOD_CONTROL (0x0002) | MOD_SHIFT (0x0004) = 0x0006
        res1 = user32.RegisterHotKey(None, 1, 0x0002 | 0x0004, 0x53)
        res2 = user32.RegisterHotKey(None, 2, 0x0002 | 0x0004, 0x43)
        
        print(f"[+] Native Hotkey Thread started.")
        print(f"[+] Thread registered Ctrl+Shift+S: {res1}")
        print(f"[+] Thread registered Ctrl+Shift+C: {res2}")
        
        import time
        last_mic_time = 0.0
        last_stealth_time = 0.0
        debounce_interval = 0.8  # 800ms debounce window
        
        msg = wintypes.MSG()
        while self._is_running:
            # PM_REMOVE = 0x0001
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0x0001):
                if msg.message == 0x0312:  # WM_HOTKEY
                    hotkey_id = msg.wParam
                    current_time = time.time()
                    if hotkey_id == 1:
                        if current_time - last_mic_time > debounce_interval:
                            last_mic_time = current_time
                            self.mic_triggered.emit()
                    elif hotkey_id == 2:
                        if current_time - last_stealth_time > debounce_interval:
                            last_stealth_time = current_time
                            self.stealth_triggered.emit()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                self.msleep(10)  # Avoid 100% CPU utilization
                
        # Unregister hotkeys thread-safely before thread exits
        user32.UnregisterHotKey(None, 1)
        user32.UnregisterHotKey(None, 2)
        print("[+] Native Hotkey Thread stopped.")
