import math
import random
from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtCore import Signal
import networkx as nx

from core.graph_model import GraphModel
from core.entity_types import Entity
from ui.node_item import NodeItem
from ui.edge_item import EdgeItem


class GraphScene(QGraphicsScene):
    entity_selected = Signal(object)          # Entity
    context_requested = Signal(object, object)  # Entity, QPointF

    def __init__(self, model: GraphModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setSceneRect(-2000, -2000, 4000, 4000)
        self.node_items = {}  # entity.id -> NodeItem
        self.edge_keys = set()  # {(source_id, target_id)} ya dibujados, evita aristas duplicadas

    def clear_all(self):
        self.clear()
        self.node_items = {}
        self.edge_keys = set()

    def remove_entity_visual(self, entity_id: str):
        """Elimina el nodo y todas sus aristas conectadas (evita aristas huérfanas)."""
        node = self.node_items.pop(entity_id, None)
        if node is None:
            return
        for edge in list(node.edges):
            other = edge.target_node if edge.source_node is node else edge.source_node
            if edge in other.edges:
                other.edges.remove(edge)
            self.edge_keys.discard((edge.source_node.entity.id, edge.target_node.entity.id))
            if edge.scene() is self:
                self.removeItem(edge)
        node.edges.clear()
        if node.scene() is self:
            self.removeItem(node)

    def add_entity_visual(self, entity: Entity, pos=None):
        if entity.id in self.node_items:
            return self.node_items[entity.id]

        node = NodeItem(entity)
        if pos is None:
            saved_pos = self.model.get_position(entity.id)
            if saved_pos is not None:
                pos = saved_pos
            else:
                angle = random.uniform(0, 2 * math.pi)
                radius = random.uniform(50, 200)
                pos = (radius * math.cos(angle), radius * math.sin(angle))
        node.setPos(*pos)
        self.model.set_position(entity.id, pos[0], pos[1])
        node.signals.selected_entity.connect(self.entity_selected.emit)
        node.signals.context_requested.connect(self.context_requested.emit)
        node.signals.moved.connect(
            lambda entity_id=entity.id, n=node: self.model.set_position(entity_id, n.pos().x(), n.pos().y())
        )

        self.addItem(node)
        self.node_items[entity.id] = node
        return node

    def add_relation_visual(self, source_entity: Entity, target_entity: Entity, label: str = ""):
        key = (source_entity.id, target_entity.id)
        if key in self.edge_keys:
            return  # ya existe visualmente, evita aristas duplicadas al re-ejecutar una transform
        source_node = self.node_items.get(source_entity.id)
        target_node = self.node_items.get(target_entity.id)
        if not source_node or not target_node:
            return
        edge = EdgeItem(source_node, target_node, label)
        self.addItem(edge)  # label_item es hijo de edge, se añade automáticamente
        self.edge_keys.add(key)

    def add_transform_results(self, source_entity: Entity, results):
        """results: lista de (nueva_entidad, label_relacion). Añade al modelo y a la escena."""
        if self.model.get_entity(source_entity.id) is None:
            # La entidad origen ya no existe en este modelo: viene de un proyecto anterior
            # (transform en vuelo que terminó tras 'Nuevo proyecto'/cargar otro). La ignoramos
            # para no corromper el grafo actual con un nodo huérfano.
            return
        source_node = self.node_items.get(source_entity.id)
        base_x, base_y = (source_node.pos().x(), source_node.pos().y()) if source_node else (0, 0)

        n = len(results)
        for i, (new_entity, rel_label) in enumerate(results):
            new_id = self.model.add_entity(new_entity)
            real_entity = self.model.get_entity(new_id)
            self.model.add_relation(source_entity.id, new_id, rel_label)

            if new_id not in self.node_items:
                angle = (2 * math.pi / max(n, 1)) * i
                radius = 150
                pos = (base_x + radius * math.cos(angle), base_y + radius * math.sin(angle))
                self.add_entity_visual(real_entity, pos)

            self.add_relation_visual(source_entity, real_entity, rel_label)

    def apply_spring_layout(self, scale: float = 400.0):
        """Reorganiza todos los nodos con un layout de fuerzas (spring layout
        de networkx) en vez del posicionamiento circular aleatorio inicial.
        Mucho más legible en grafos con muchos nodos y relaciones cruzadas.
        Mover cada nodo dispara su signal 'moved', que ya persiste la nueva
        posición en el modelo automáticamente -- no hace falta guardarla aquí.
        """
        if self.model.graph.number_of_nodes() == 0:
            return
        # seed fija: mismo grafo -> mismo layout, resultado reproducible
        layout = nx.spring_layout(self.model.graph, scale=scale, seed=42)
        for entity_id, (x, y) in layout.items():
            node = self.node_items.get(entity_id)
            if node:
                node.setPos(float(x), float(y))
