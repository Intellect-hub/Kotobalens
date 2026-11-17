
from PySide6.QtCore import Qt, QRect, QSize, QPoint
from PySide6.QtWidgets import QLayout


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=8, spacing=5):
        super().__init__(parent)

        self.items = []
        self.setContentsMargins(
            margin, margin, margin, margin
        )
        self.setSpacing(spacing)

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        if 0 <= index < len(self.items):
            return self.items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.items):
            return self.items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.arrange(
            QRect(0, 0, width, 0),
            test_only=True
        )

    def setGeometry(self, rectangle):
        super().setGeometry(rectangle)
        self.arrange(rectangle, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()

        for item in self.items:
            size = size.expandedTo(item.minimumSize())

        margins = self.contentsMargins()

        size += QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom()
        )

        return size

    def arrange(self, rectangle, test_only=False):
        margins = self.contentsMargins()

        left = rectangle.x() + margins.left()
        top = rectangle.y() + margins.top()
        right = rectangle.right() - margins.right()

        x = left
        y = top
        row_height = 0

        for item in self.items:
            item_size = item.sizeHint()

            if (
                x + item_size.width() > right + 1
                and row_height > 0
            ):
                x = left
                y += row_height + self.spacing()
                row_height = 0

            if not test_only:
                item.setGeometry(
                    QRect(QPoint(x, y), item_size)
                )

            x += item_size.width() + self.spacing()
            row_height = max(
                row_height,
                item_size.height()
            )

        return (
            y + row_height - rectangle.y()
            + margins.bottom()
        )
