"""
Regresiones de la capa de UI (`ui/main_window.py`, `ui/graph_scene.py`):
los bugs históricos encontrados durante el desarrollo, convertidos en
tests permanentes para que nunca vuelvan a colarse sin darse cuenta.
"""
from unittest.mock import patch
from core.entity_types import Entity, VALID_TYPES
from core.graph_model import GraphModel
from ui.graph_scene import GraphScene
from transforms import TRANSFORM_REGISTRY


def test_duplicate_entity_via_dialog_does_not_create_ghost_node(main_window):
    """Bug histórico ('nodo fantasma'): añadir la misma entidad dos veces
    por el diálogo debía reusar el nodo existente, no crear un segundo
    nodo visual desincronizado del modelo."""
    import ui.main_window as mw
    mw.QInputDialog.getText = staticmethod(lambda *a, **k: ("dup.com", True))
    main_window.type_combo.setCurrentText("Domain")
    main_window.add_entity_dialog()
    main_window.add_entity_dialog()
    assert len(main_window.model.all_entities()) == 1
    assert len(main_window.scene.node_items) == 1


def test_removing_entity_removes_orphan_edges():
    """Bug histórico: al borrar un nodo, las aristas conectadas a él
    debían desaparecer también -- si no, quedaban aristas "huérfanas"
    apuntando a un nodo que ya no existe."""
    model = GraphModel()
    scene = GraphScene(model)
    e1 = Entity(type="Domain", value="x.com")
    e2 = Entity(type="IP", value="1.2.3.4")
    model.add_entity(e1)
    model.add_entity(e2)
    scene.add_entity_visual(e1)
    scene.add_entity_visual(e2)
    model.add_relation(e1.id, e2.id, "resuelve a")
    scene.add_relation_visual(e1, e2, "resuelve a")

    scene.remove_entity_visual(e1.id)
    model.remove_entity(e1.id)

    edges = [it for it in scene.items() if type(it).__name__ == "EdgeItem"]
    assert len(edges) == 0


def test_repeated_transform_does_not_duplicate_edges():
    """Bug histórico: ejecutar la misma transform dos veces sobre el
    mismo nodo (ej. tras recargar resultados) duplicaba la arista visual."""
    model = GraphModel()
    scene = GraphScene(model)
    e = Entity(type="Domain", value="y.com")
    model.add_entity(e)
    scene.add_entity_visual(e)

    fake_results = [(Entity(type="IP", value="9.9.9.9"), "resuelve a")]
    scene.add_transform_results(e, fake_results)
    scene.add_transform_results(e, fake_results)

    edges = [it for it in scene.items() if type(it).__name__ == "EdgeItem"]
    assert len(edges) == 1


def test_new_project_clears_in_flight_transform_leak(main_window):
    """Bug histórico: una transform lanzada en un proyecto que terminaba
    DESPUÉS de haber abierto/creado un proyecto nuevo contaminaba el
    proyecto nuevo con sus resultados."""
    old_entity = Entity(type="Domain", value="viejo.com")
    main_window.model.add_entity(old_entity)
    main_window.scene.add_entity_visual(old_entity)

    main_window.new_project()
    main_window.on_transform_ok([(Entity(type="IP", value="1.1.1.1"), "r")], old_entity)

    assert len(main_window.model.all_entities()) == 0


def test_sqlite_and_json_hold_all_entity_types_simultaneously(tmp_path):
    model = GraphModel()
    for t in VALID_TYPES:
        model.add_entity(Entity(type=t, value=f"v_{t}"))

    json_path = tmp_path / "p.json"
    db_path = tmp_path / "p.db"
    model.save_json(str(json_path))
    model.save_sqlite(str(db_path))

    from_json = GraphModel()
    from_json.load_json(str(json_path))
    from_sqlite = GraphModel()
    from_sqlite.load_sqlite(str(db_path))

    assert len(from_json.all_entities()) == len(VALID_TYPES)
    assert len(from_sqlite.all_entities()) == len(VALID_TYPES)


# ------------------------------------------------------- Consentimiento --

class _FakeButton:
    def __init__(self, label):
        self.label = label


class _FakeMessageBoxCancel:
    """Simula el diálogo de confirmación con el usuario pulsando Cancelar."""
    Warning = "w"
    AcceptRole = "a"
    RejectRole = "r"

    def __init__(self, parent=None):
        self._buttons = []

    def setIcon(self, *a):
        pass

    def setWindowTitle(self, *a):
        pass

    def setText(self, *a):
        pass

    def setDefaultButton(self, *a):
        pass

    def addButton(self, label, role):
        b = _FakeButton(label)
        self._buttons.append(b)
        return b

    def buttons(self):
        return self._buttons

    def exec(self):
        pass

    def clickedButton(self):
        return self._buttons[1]  # el segundo botón añadido es "Cancelar"


def test_every_active_transform_requires_explicit_consent(main_window):
    """Las transforms activas (requires_consent=True) NUNCA deben
    ejecutarse si el usuario pulsa Cancelar en el diálogo -- probado
    contra TODAS las transforms activas existentes, no solo una."""
    import ui.main_window as mw

    activas = [t for t in TRANSFORM_REGISTRY if t.requires_consent]
    assert len(activas) >= 1, "Debería haber al menos una transform activa registrada"

    for transform in activas:
        entity = Entity(type=transform.input_types[0], value="test")
        main_window.model.add_entity(entity)
        main_window.scene.add_entity_visual(entity)
        with patch.object(mw, "QMessageBox", _FakeMessageBoxCancel):
            with patch.object(main_window, "run_transform") as mocked_run:
                main_window.run_transform_with_consent(transform, entity)
                assert not mocked_run.called, f"{transform.name} se ejecutó pese a cancelar"


def test_run_all_passive_never_includes_active_transforms(main_window):
    """'Ejecutar todas' debe excluir SIEMPRE las transforms activas, sin
    excepción -- es el invariante de seguridad central de esa función."""
    domain = Entity(type="Domain", value="ejemplo.com")
    main_window.model.add_entity(domain)
    main_window.scene.add_entity_visual(domain)

    with patch.object(main_window, "run_transform") as mocked_run:
        main_window.run_all_passive_transforms(domain)
        llamadas = [call.args[0] for call in mocked_run.call_args_list]
        assert all(not t.requires_consent for t in llamadas)
        assert len(llamadas) > 0  # de verdad se ejecutó algo


def test_run_all_passive_staggers_ddg_transforms(main_window):
    """Bug real encontrado y corregido en esta misma ronda: `QTimer` se
    usaba en run_all_passive_transforms para escalonar las transforms
    marcadas `uses_ddg = True`, pero nunca se importaba -- crasheaba con
    NameError en cuanto 'Ejecutar todas' tocaba un Domain de verdad. Este
    test comprueba, con tiempos reales (no solo que no crashee), que las
    transforms sin DDG se lanzan al instante y las de DDG se escalonan."""
    from PySide6.QtCore import QEventLoop, QTimer
    from transforms import TRANSFORM_REGISTRY

    domain = Entity(type="Domain", value="ejemplo.com")
    main_window.model.add_entity(domain)
    main_window.scene.add_entity_visual(domain)

    aplicables = [t for t in TRANSFORM_REGISTRY if t.applies_to(domain) and not t.requires_consent]
    con_ddg = [t for t in aplicables if t.uses_ddg]
    sin_ddg = [t for t in aplicables if not t.uses_ddg]
    assert con_ddg, "Este test necesita que Domain tenga al menos una transform con uses_ddg=True"

    llamadas = []
    with patch.object(main_window, "run_transform", side_effect=lambda t, e: llamadas.append(t)):
        main_window.run_all_passive_transforms(domain)
        assert len(llamadas) == len(sin_ddg), "Las transforms SIN DDG deben lanzarse de inmediato"

        loop = QEventLoop()
        QTimer.singleShot(len(con_ddg) * main_window.DDG_STAGGER_MS + 500, loop.quit)
        loop.exec()

    assert len(llamadas) == len(aplicables), "Tras esperar, las de DDG también deben haberse lanzado"


def test_run_all_passive_button_threshold():
    """El botón 'Ejecutar todas' solo debería tener sentido con más de
    una transform pasiva aplicable -- con una sola no aporta nada sobre
    clicarla directamente."""
    for entity_type in ("Hash", "Breach", "Paste"):
        entity = Entity(type=entity_type, value="test")
        pasivas = [t for t in TRANSFORM_REGISTRY if t.applies_to(entity) and not t.requires_consent]
        assert len(pasivas) <= 1, f"{entity_type} tiene {len(pasivas)} pasivas, revisar si el botón debe aparecer"
