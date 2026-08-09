import io
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen
from core.capture_guard import protect_window

class ScreenSnipperOverlay(QtWidgets.QWidget):
    """
    Stealth Screen Region Snipper with Capture-Protected Selection Box.
    - Applies WDA_EXCLUDEFROMCAPTURE so selection box is visible ONLY to you on your monitor,
      and completely invisible on Zoom, Teams, Meet, Discord screen shares & recordings.
    - Screen remains 100% natural (no screen dimming/tint).
    - Mouse cursor stays as standard ArrowCursor (no crosshair/plus pointer).
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

    def showEvent(self, event):
        """Applies Windows Display Affinity protection to keep selection box hidden on screen shares."""
        super().showEvent(event)
        protect_window(int(self.winId()))

    def start_snipping(self):
        """Captures primary screen and opens the protected snipper canvas."""
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
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.current_point = event.pos()
            self.update()

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
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Seamless background screen screenshot
        if self.screen_pixmap:
            painter.drawPixmap(0, 0, self.screen_pixmap)

        # 2. Draw glowing cyan selection box (Visible ONLY to user via WDA_EXCLUDEFROMCAPTURE)
        if self.is_selecting and not self.start_point.isNull():
            rect = QRect(self.start_point, self.current_point).normalized()
            pen = QPen(QColor(0, 240, 255, 230), 1.5, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)
