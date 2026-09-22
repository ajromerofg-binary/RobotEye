"""
Modelo de datos puro del grafo (sin dependencias de Qt).
Usa networkx por debajo para la lógica de nodos/aristas,
y expone una API sencilla para que la UI y las transforms lo consuman.
"""
import json
import sqlite3
from typing import List, Optional
import networkx as nx

from core.entity_types import Entity


class GraphModel:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.positions = {}  # entity_id -> (x, y), posición en el canvas visual

    # ---------- Posiciones (estado visual, persistido junto al grafo) ----------
    def set_position(self, entity_id: str, x: float, y: float):
        self.positions[entity_id] = (x, y)

    def get_position(self, entity_id: str):
        return self.positions.get(entity_id)  # None si nunca se ha posicionado

    # ---------- Nodos ----------
    def add_entity(self, entity: Entity) -> str:
        """Añade una entidad si no existe ya una igual (mismo type+value)."""
        existing = self.find_entity(entity.type, entity.value)
        if existing:
            return existing.id
        self.graph.add_node(entity.id, entity=entity)
        return entity.id

    def find_entity(self, type_: str, value: str) -> Optional[Entity]:
        for _, data in self.graph.nodes(data=True):
            e: Entity = data["entity"]
            if e.type == type_ and e.value == value:
                return e
        return None

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        data = self.graph.nodes.get(entity_id)
        return data["entity"] if data else None

    def remove_entity(self, entity_id: str):
        if self.graph.has_node(entity_id):
            self.graph.remove_node(entity_id)
        self.positions.pop(entity_id, None)

    def all_entities(self) -> List[Entity]:
        return [data["entity"] for _, data in self.graph.nodes(data=True)]

    # ---------- Aristas ----------
    def add_relation(self, source_id: str, target_id: str, label: str = ""):
        if not self.graph.has_edge(source_id, target_id):
            self.graph.add_edge(source_id, target_id, label=label)

    def neighbors(self, entity_id: str) -> List[Entity]:
        return [self.get_entity(n) for n in self.graph.successors(entity_id)]

    def degree(self, entity_id: str) -> int:
        """Número total de conexiones que tocan esta entidad, contando
        tanto las que salen de ella como las que le llegan -- usado para
        avisar con un número concreto antes de un borrado irreversible,
        en vez de un aviso genérico igual para un nodo aislado que para
        uno con horas de investigación colgando de él."""
        if entity_id not in self.graph:
            return 0
        return self.graph.degree(entity_id)

    def edges(self):
        return list(self.graph.edges(data=True))

    # ---------- Persistencia ----------
    def to_dict(self) -> dict:
        nodes = []
        for nid, data in self.graph.nodes(data=True):
            e: Entity = data["entity"]
            nodes.append({
                "id": e.id, "type": e.type, "value": e.value,
                "properties": e.properties, "user_note": e.user_note,
            })
        edges = [{"source": s, "target": t, "label": d.get("label", "")}
                  for s, t, d in self.graph.edges(data=True)]
        positions = {eid: list(pos) for eid, pos in self.positions.items()}
        return {"nodes": nodes, "edges": edges, "positions": positions}

    def from_dict(self, data: dict):
        self.graph.clear()
        self.positions = {}
        for n in data.get("nodes", []):
            e = Entity(type=n["type"], value=n["value"],
                        properties=n.get("properties", {}), id=n["id"],
                        user_note=n.get("user_note", ""))  # "" si el proyecto es de antes de este campo
            self.graph.add_node(e.id, entity=e)
        for e in data.get("edges", []):
            self.add_relation(e["source"], e["target"], e.get("label", ""))
        for eid, pos in data.get("positions", {}).items():
            if self.graph.has_node(eid) and len(pos) == 2:
                self.positions[eid] = (pos[0], pos[1])

    def save_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def load_json(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            self.from_dict(json.load(f))

    def save_sqlite(self, path: str):
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS nodes")
        cur.execute("DROP TABLE IF EXISTS edges")
        cur.execute("DROP TABLE IF EXISTS positions")
        cur.execute("""CREATE TABLE nodes (
            id TEXT PRIMARY KEY, type TEXT, value TEXT, properties TEXT, user_note TEXT)""")
        cur.execute("""CREATE TABLE edges (
            source TEXT, target TEXT, label TEXT)""")
        cur.execute("""CREATE TABLE positions (
            id TEXT PRIMARY KEY, x REAL, y REAL)""")
        for e in self.all_entities():
            cur.execute("INSERT INTO nodes VALUES (?, ?, ?, ?, ?)",
                        (e.id, e.type, e.value, json.dumps(e.properties), e.user_note))
        for s, t, d in self.edges():
            cur.execute("INSERT INTO edges VALUES (?, ?, ?)",
                        (s, t, d.get("label", "")))
        for eid, (x, y) in self.positions.items():
            cur.execute("INSERT INTO positions VALUES (?, ?, ?)", (eid, x, y))
        conn.commit()
        conn.close()

    def load_sqlite(self, path: str):
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        self.graph.clear()
        self.positions = {}
        # La columna user_note puede no existir si el fichero es de una
        # versión anterior de RobotEye (antes de que se pudieran guardar
        # notas manuales) -- se recupera sin ella en ese caso, con "" por
        # defecto, en vez de fallar al cargar un proyecto antiguo.
        try:
            rows = cur.execute("SELECT id, type, value, properties, user_note FROM nodes").fetchall()
            has_user_note = True
        except sqlite3.OperationalError:
            rows = cur.execute("SELECT id, type, value, properties FROM nodes").fetchall()
            has_user_note = False
        for row in rows:
            if has_user_note:
                id_, type_, value, props, user_note = row
            else:
                id_, type_, value, props = row
                user_note = ""
            e = Entity(type=type_, value=value, properties=json.loads(props), id=id_, user_note=user_note or "")
            self.graph.add_node(e.id, entity=e)
        for source, target, label in cur.execute("SELECT source, target, label FROM edges"):
            self.add_relation(source, target, label)
        # La tabla positions puede no existir si el fichero es de una versión
        # anterior de RobotEye (antes de que se guardaran posiciones).
        try:
            for eid, x, y in cur.execute("SELECT id, x, y FROM positions"):
                if self.graph.has_node(eid):
                    self.positions[eid] = (x, y)
        except sqlite3.OperationalError:
            pass
        conn.close()
