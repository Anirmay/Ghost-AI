import time
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication
import uiautomation as auto
from pynput import mouse

class GlobalClickCopyWorker(QThread):
    """
    Background worker thread that listens for global mouse left-clicks on any outside application
    or webpage. When active, it extracts the article/paragraph text under the clicked point
    and copies it to the Windows Clipboard.
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
                if doc_txt and len(doc_txt) < 5000:
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
            parent = control.GetParentControl()
            if parent and parent.ControlTypeName in ["GroupControl", "TextControl", "EditControl", "DocumentControl"]:
                if parent.Name and len(parent.Name.strip()) > len(control.Name or ""):
                    return parent.Name.strip()
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
                    cb = QApplication.clipboard()
                    if cb:
                        cb.setText(text)
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
