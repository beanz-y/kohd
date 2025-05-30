# kohd_translator/gui/kohd_canvas.py
from PyQt6.QtWidgets import QWidget # type: ignore
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont # type: ignore
from PyQt6.QtCore import Qt, QRectF # type: ignore

from kohd_core.kohd_rules import NODE_POSITIONS, NODE_LAYOUT # Import NODE_LAYOUT as well for names

class KohdCanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(350, 350)  # Give it a decent default size
        self.node_radius = 20  # Radius for drawing nodes
        self.font_size = 10

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fill background (optional)
        painter.fillRect(self.rect(), QColor(Qt.GlobalColor.white))

        # Pen for node outlines
        pen = QPen(QColor(Qt.GlobalColor.black))
        pen.setWidth(2)
        painter.setPen(pen)

        # Brush for node fill
        brush = QBrush(QColor(Qt.GlobalColor.lightGray)) # Default fill
        painter.setBrush(brush)
        
        # Font for node names
        font = QFont()
        font.setPointSize(self.font_size)
        painter.setFont(font)

        for node_name, (cx, cy) in NODE_POSITIONS.items():
            # Draw the node circle
            rect = QRectF(
                cx - self.node_radius, 
                cy - self.node_radius,
                2 * self.node_radius, 
                2 * self.node_radius
            )
            painter.drawEllipse(rect)

            # Draw the node name text (e.g., "ABC") inside the circle
            painter.setPen(QColor(Qt.GlobalColor.black)) # Ensure text is black
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, node_name)
            
            painter.setPen(pen) # Reset pen for next node outline
            painter.setBrush(brush) # Reset brush

        painter.end()