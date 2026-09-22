from PySide6.QtWidgets import (QGraphicsItem, QGraphicsEllipseItem, QGraphicsTextItem,
                                QGraphicsSimpleTextItem, QGraphicsDropShadowEffect)
from PySide6.QtGui import QBrush, QColor, QPen, QFont
from PySide6.QtCore import Signal, QObject, QTimer

from core.entity_types import Entity
from ui import theme

NODE_RADIUS = 30

# Paleta neón por tipo de entidad -- cada tipo tiene su color de "glow" propio
NODE_COLORS = {
    "Domain": theme.NEON_CYAN,
    "IP": theme.NEON_GREEN,
    "Email": theme.NEON_AMBER,
    "Person": theme.NEON_MAGENTA,
    "ASN": theme.NEON_PURPLE,
    "Phone": "#00d9ff",
    "URL": theme.NEON_BLUE,
    "Organization": "#ff8c00",
    "Hash": "#6ee7ff",
    "Dork": theme.NEON_RED,
    "Breach": "#ff0044",
    "Username": "#00ffab",
    "Paste": "#ff5e3a",
    "Software": "#a3ff00",
    "MACAddress": "#ff6ec7",
    "EmailMessage": "#ffd700",
}


class NodeSignals(QObject):
    moved = Signal()
    selected_entity = Signal(object)  # Entity
    context_requested = Signal(object, object)  # entity, scene_pos


class NodeItem(QGraphicsEllipseItem):
    def __init__(self, entity: Entity):
        super().__init__(-NODE_RADIUS, -NODE_RADIUS, NODE_RADIUS * 2, NODE_RADIUS * 2)
        self.entity = entity
        self.signals = NodeSignals()
        self.edges = []  # lista de EdgeItem conectados

        neon_color = QColor(NODE_COLORS.get(entity.type, theme.NEON_CYAN))

        # Relleno oscuro "cristal neón": el color del tipo teñido a baja opacidad
        # sobre fondo oscuro, con un borde neón sólido -- en vez del círculo
        # plano sólido de antes.
        fill = QColor(neon_color)
        fill.setAlpha(55)
        self.setBrush(QBrush(fill))
        pen = QPen(neon_color, 2)
        self.setPen(pen)

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        # Glow neón alrededor del nodo, coloreado según el tipo de entidad
        glow = QGraphicsDropShadowEffect()
        glow.setColor(neon_color)
        glow.setBlurRadius(28)
        glow.setOffset(0, 0)
        self.setGraphicsEffect(glow)
        # Se guarda el estado "normal" del glow para poder revertir tras
        # un highlight() temporal de la búsqueda.
        self._highlight_original_radius = glow.blurRadius()
        self._highlight_original_color = QColor(neon_color)
        self._highlight_revert_timer = None

        # icono encima
        self.icon_item = QGraphicsSimpleTextItem(entity.icon, self)
        icon_font = QFont()
        icon_font.setFamilies(theme.EMOJI_FONT_FAMILIES)
        icon_font.setPointSize(16)
        self.icon_item.setFont(icon_font)
        icon_rect = self.icon_item.boundingRect()
        self.icon_item.setPos(-icon_rect.width() / 2, -icon_rect.height() / 2 - 4)

        # label debajo del nodo, monoespaciada estilo terminal
        self.label_item = QGraphicsTextItem(self._short_label(entity.value), self)
        self.label_item.setDefaultTextColor(QColor(theme.TEXT_PRIMARY))
        label_font = QFont()
        label_font.setFamilies(theme.MONO_FONT_FAMILIES)
        label_font.setPointSize(8)
        self.label_item.setFont(label_font)
        lbl_rect = self.label_item.boundingRect()
        self.label_item.setPos(-lbl_rect.width() / 2, NODE_RADIUS + 4)

    @staticmethod
    def _short_label(value: str, max_len: int = 22) -> str:
        return value if len(value) <= max_len else value[: max_len - 1] + "…"

    def add_edge(self, edge):
        self.edges.append(edge)

    def highlight(self, duration_ms: int = 1800):
        """Resalta el nodo temporalmente -- usado por la búsqueda del
        lienzo para que el resultado encontrado destaque un momento,
        aunque el usuario no sepa aún hacia dónde se ha centrado la
        vista. Agranda y aclara el glow existente, luego lo devuelve
        exactamente a como estaba (nunca dos highlights a la vez
        pisándose: el segundo cancela el timer del primero antes de
        empezar)."""
        glow = self.graphicsEffect()
        if glow is None:
            return
        if self._highlight_revert_timer is not None:
            self._highlight_revert_timer.stop()

        original_radius = self._highlight_original_radius
        original_color = self._highlight_original_color
        glow.setBlurRadius(60)
        glow.setColor(QColor("#ffffff"))

        def _revert():
            glow.setBlurRadius(original_radius)
            glow.setColor(original_color)
            self._highlight_revert_timer = None

        self._highlight_revert_timer = QTimer()
        self._highlight_revert_timer.setSingleShot(True)
        self._highlight_revert_timer.timeout.connect(_revert)
        self._highlight_revert_timer.start(duration_ms)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            for edge in self.edges:
                edge.update_position()
        elif change == QGraphicsItem.ItemPositionHasChanged:
            self.signals.moved.emit()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.signals.selected_entity.emit(self.entity)

    def contextMenuEvent(self, event):
        self.signals.context_requested.emit(self.entity, event.scenePos())
        event.accept()
