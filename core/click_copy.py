import time
import ctypes
from ctypes import wintypes
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication
import uiautomation as auto
from pynput import mouse

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]

def set_windows_clipboard(text: str) -> bool:
    """Sets text directly into the OS Windows System Clipboard (Thread-safe across all threads)."""
    if not text:
        return False
    try:
        user32.OpenClipboard(None)
        user32.EmptyClipboard()
        text_bytes = text.encode('utf-16-le') + b'\x00\x00'
        h_mem = kernel32.GlobalAlloc(0x0042, len(text_bytes)) # GHND
        if not h_mem:
            user32.CloseClipboard()
            return False
        p_mem = kernel32.GlobalLock(h_mem)
        if p_mem:
            ctypes.memmove(p_mem, text_bytes, len(text_bytes))
            kernel32.GlobalUnlock(h_mem)
            user32.SetClipboardData(13, h_mem) # CF_UNICODETEXT = 13
        user32.CloseClipboard()
        return True
    except Exception as e:
        try:
            user32.CloseClipboard()
        except Exception:
            pass
        return False

class GlobalClickCopyWorker(QThread):
    """
    Background worker thread that listens for global mouse left-clicks on any outside application
    or webpage. When active, it extracts the article/paragraph text under the clicked point
    and copies it directly to the Windows System Clipboard.
    """
    text_copied = pyqtSignal(str)

    def __init__(self, overlay_hwnd=None):
        super().__init__()
        self.overlay_hwnd = overlay_hwnd
        self.running = False
        self.listener = None

    def start_listening(self):
        self.running = True
        if not self.isRunning():
            self.start()

    def stop_listening(self):
        self.running = False
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None
        self.quit()

    def extract_element_text(self, control) -> str:
        if not control:
            return ""

        # Avoid capturing full Desktop background window
        if control.ControlTypeName == "PaneControl" and control.Name == "Desktop 1":
            return ""

        # 1. Try Document / TextPattern
        try:
            txt_pat = control.GetTextPattern()
            if txt_pat:
                sel = txt_pat.GetSelection()
                if sel:
                    txt = "".join([s.GetText(-1) for s in sel]).strip()
                    if txt:
                        return txt
                doc_txt = txt_pat.DocumentRange.GetText(-1).strip()
                if doc_txt and len(doc_txt) < 10000:
                    return doc_txt
        except Exception:
            pass

        # 2. Try ValuePattern (for input fields/text areas)
        try:
            val_pat = control.GetValuePattern()
            if val_pat and val_pat.Value:
                txt = val_pat.Value.strip()
                if txt:
                    return txt
        except Exception:
            pass

        # 3. Try LegacyIAccessiblePattern
        try:
            leg_pat = control.GetLegacyIAccessiblePattern()
            if leg_pat:
                if leg_pat.Value:
                    txt = leg_pat.Value.strip()
                    if txt:
                        return txt
                if leg_pat.Name:
                    txt = leg_pat.Name.strip()
                    if txt:
                        return txt
        except Exception:
            pass

        # 4. Try Name property
        if control.Name:
            txt = control.Name.strip()
            if txt:
                return txt

        # 5. Parent container fallback for webpage article/paragraph nodes
        try:
            curr = control
            for _ in range(3):
                parent = curr.GetParentControl()
                if not parent:
                    break
                if parent.Name and len(parent.Name.strip()) > 3:
                    return parent.Name.strip()
                curr = parent
        except Exception:
            pass

        return ""

    def on_click(self, x, y, button, pressed):
        if not self.running:
            return

        if pressed and button == mouse.Button.left:
            try:
                # Check control under cursor
                ctrl = auto.ControlFromPoint(x, y)
                if not ctrl:
                    return

                # Ignore clicks inside GhostAI window itself
                if self.overlay_hwnd and hasattr(ctrl, "NativeWindowHandle"):
                    if ctrl.NativeWindowHandle == self.overlay_hwnd:
                        return

                text = self.extract_element_text(ctrl)
                if text and len(text) >= 2:
                    # Set native OS system clipboard directly from background thread
                    set_windows_clipboard(text)
                    self.text_copied.emit(text)
            except Exception:
                pass

    def run(self):
        try:
            with mouse.Listener(on_click=self.on_click) as listener:
                self.listener = listener
                while self.running:
                    time.sleep(0.1)
                listener.stop()
        except Exception:
            pass
