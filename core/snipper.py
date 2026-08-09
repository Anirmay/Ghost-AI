import io
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QPainter

class ScreenSnipperOverlay(QtWidgets.QWidget):
    """
    100% Stealth Screen Region Snipper.
    - No screen dimming / dark tint
    - Mouse cursor stays as standard ArrowCursor (no plus/crosshair)
    - No selection rectangle outline or animation
    Runs completely invisibly in the background. Emits snippet_captured(bytes) on mouse release.
    """
    snippet_captured = pyqtSignal(bytes)
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(QtGui.QCursor(Qt.CursorShape.ArrowCursor))
        
        self.start_point = QPoint()
        self.current_point = QPoint()
        self.is_selecting = False
        self.screen_pixmap = None

    def start_snipping(self):
        """Captures primary screen and opens the invisible stealth snipper canvas."""
        screen = QtWidgets.QApplication.primaryScreen()
        if not screen:
            self.cancelled.emit()
            return
        
        # Grab whole screen screenshot at the moment snipping starts
        self.screen_pixmap = screen.grabWindow(0)
        self.setGeometry(screen.geometry())
        self.start_point = QPoint()
        self.current_point = QPoint()
        self.is_selecting = False
        self.show()
        self.activateWindow()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.pos()
            self.current_point = event.pos()
            self.is_selecting = True

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.current_point = event.pos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.current_point = event.pos()
            self.hide()

            selection_rect = QRect(self.start_point, self.current_point).normalized()
            if selection_rect.width() >= 10 and selection_rect.height() >= 10:
                if self.screen_pixmap:
                    cropped_pixmap = self.screen_pixmap.copy(selection_rect)
                    buffer = QtCore.QBuffer()
                    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
                    cropped_pixmap.save(buffer, "PNG")
                    img_bytes = bytes(buffer.data())
                    buffer.close()
                    if img_bytes:
                        self.snippet_captured.emit(img_bytes)
                    else:
                        self.cancelled.emit()
                else:
                    self.cancelled.emit()
            else:
                self.cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        # 100% Invisible stealth rendering — draws captured screen background seamlessly
        painter = QPainter(self)
        if self.screen_pixmap:
            painter.drawPixmap(0, 0, self.screen_pixmap)
