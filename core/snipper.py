import io
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

class ScreenSnipperOverlay(QtWidgets.QWidget):
    """
    Full-screen semi-transparent overlay widget that allows the user to click & drag
    a glowing selection box over any screen area (diagram, code snippet, math formula).
    Emits snippet_captured(bytes) when mouse button is released.
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
        self.setCursor(QtGui.QCursor(Qt.CursorShape.CrossCursor))
        
        self.start_point = QPoint()
        self.current_point = QPoint()
        self.is_selecting = False
        self.screen_pixmap = None

    def start_snipping(self):
        """Captures primary screen and opens the interactive snipper canvas."""
        screen = QtWidgets.QApplication.primaryScreen()
        if not screen:
            return
        
        # Grab whole screen screenshot
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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw full screen background screenshot
        if self.screen_pixmap:
            painter.drawPixmap(0, 0, self.screen_pixmap)

        # Dim tint over whole screen
        dim_color = QColor(0, 0, 0, 140)
        painter.fillRect(self.rect(), dim_color)

        if self.is_selecting and not self.start_point.isNull():
            rect = QRect(self.start_point, self.current_point).normalized()
            
            # Clear dark tint inside selection rectangle so image shines through bright & clear
            if self.screen_pixmap:
                painter.drawPixmap(rect, self.screen_pixmap, rect)

            # Draw glowing cyan selection border
            pen = QPen(QColor(0, 240, 255, 255), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Draw dimension dimensions tag box
            dim_text = f" {rect.width()} × {rect.height()} px "
            font = QFont("Consolas", 10, QFont.Weight.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(dim_text)
            th = fm.height()

            tag_rect = QRect(rect.left(), max(0, rect.top() - th - 6), tw + 8, th + 4)
            painter.fillRect(tag_rect, QColor(0, 240, 255, 220))
            painter.setPen(QColor(0, 0, 0))
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, dim_text)
