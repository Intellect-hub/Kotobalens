
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QApplication


class SelectionOverlay(QWidget):

    # Sends the selected image to main.py
    image_selected = Signal(QImage)

    def __init__(self, screenshot, screen_geometry):
        super().__init__()

        self.start_point = QPoint()
        self.end_point = QPoint()
        self.selecting = False

        image = QImage(
            screenshot.bgra,
            screenshot.width,
            screenshot.height,
            screenshot.width * 4,
            QImage.Format.Format_ARGB32
        )

        self.background = QPixmap.fromImage(image.copy())

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(screen_geometry)

    def get_selection(self):
        rectangle = QRect(
            self.start_point,
            self.end_point
        ).normalized()

        scale_x = self.background.width() / self.width()
        scale_y = self.background.height() / self.height()

        return QRect(
            round(rectangle.x() * scale_x),
            round(rectangle.y() * scale_y),
            round(rectangle.width() * scale_x),
            round(rectangle.height() * scale_y)
        )

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.drawPixmap(self.rect(), self.background)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if self.selecting:
            rectangle = QRect(
                self.start_point,
                self.end_point
            ).normalized()

            selected_area = self.get_selection()

            painter.drawPixmap(
                rectangle,
                self.background,
                selected_area
            )

            painter.setPen(QPen(QColor("white"), 2))
            painter.drawRect(rectangle)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.position().toPoint()
            self.end_point = self.start_point
            self.selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.selecting:
            self.end_point = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.selecting
        ):
            self.end_point = event.position().toPoint()

            rectangle = self.get_selection()

            if rectangle.width() > 10 and rectangle.height() > 10:
                selected = self.background.copy(rectangle)
                self.image_selected.emit(selected.toImage())

            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            print("Selection cancelled.")
            self.close()
