from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsTextItem
from PySide6.QtGui import QPen, QColor, QFont
from PySide6.QtCore import Qt

from ui import theme


class EdgeItem(QGraphicsLineItem):
    def __init__(self, source_node, target_node, label: str = ""):
        super().__init__()
        self.source_node = source_node
        self.target_node = target_node
        edge_color = QColor(theme.NEON_CYAN)
        edge_color.setAlpha(110)  # línea neón atenuada, no compite con los nodos
        self.setPen(QPen(edge_color, 1.5, Qt.SolidLine))
        self.setZValue(-1)

        self.label_item = QGraphicsTextItem(label, self)
        self.label_item.setDefaultTextColor(QColor(theme.TEXT_DIM))
        label_font = QFont()
        label_font.setFamilies(theme.MONO_FONT_FAMILIES)
        label_font.setPointSize(7)
        self.label_item.setFont(label_font)

        source_node.add_edge(self)
        target_node.add_edge(self)
        self.update_position()

    def update_position(self):
        p1 = self.source_node.scenePos()
        p2 = self.target_node.scenePos()
        self.setLine(p1.x(), p1.y(), p2.x(), p2.y())
        mid_x = (p1.x() + p2.x()) / 2
        mid_y = (p1.y() + p2.y()) / 2
        self.label_item.setPos(mid_x, mid_y)
