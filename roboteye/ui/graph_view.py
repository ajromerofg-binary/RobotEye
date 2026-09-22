from PySide6.QtWidgets import QGraphicsView
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QRadialGradient
from PySide6.QtCore import Qt

from ui import theme

GRID_SPACING = 40  # separación en px de la rejilla, a escala 1:1


class GraphView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._zoom = 1.0
        self.setBackgroundBrush(QBrush(QColor(theme.BG_VOID)))

    def drawBackground(self, painter, rect):
        """Fondo tipo Tron: negro-azulado con una rejilla tenue y un halo
        radial sutil en el centro de la escena, en vez del blanco por defecto."""
        painter.fillRect(rect, QColor(theme.BG_VOID))

        # Halo radial muy suave centrado en el origen de la escena, para dar
        # sensación de profundidad sin distraer del grafo
        gradient = QRadialGradient(0, 0, 900)
        glow = QColor(theme.NEON_CYAN)
        glow.setAlpha(14)
        gradient.setColorAt(0.0, glow)
        transparent = QColor(theme.BG_VOID)
        transparent.setAlpha(0)
        gradient.setColorAt(1.0, transparent)
        painter.fillRect(rect, QBrush(gradient))

        # Rejilla tenue
        pen = QPen(QColor(theme.GRID_LINE))
        pen.setWidth(0)  # 0 = línea de 1px independiente del zoom
        painter.setPen(pen)

        left = int(rect.left()) - (int(rect.left()) % GRID_SPACING)
        top = int(rect.top()) - (int(rect.top()) % GRID_SPACING)

        x = left
        while x < rect.right():
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += GRID_SPACING

        y = top
        while y < rect.bottom():
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += GRID_SPACING

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        new_zoom = self._zoom * factor
        if 0.15 <= new_zoom <= 4.0:
            self._zoom = new_zoom
            self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            fake_event = event
            super().mousePressEvent(fake_event)
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.setDragMode(QGraphicsView.RubberBandDrag)
