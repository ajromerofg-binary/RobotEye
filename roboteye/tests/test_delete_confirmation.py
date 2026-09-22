"""
Tests de la confirmación antes de borrar un nodo (`MainWindow.delete_entity`)
y del conteo de conexiones que la hace posible (`GraphModel.degree`).
"""
from unittest.mock import patch
from PySide6.QtWidgets import QMessageBox
from core.entity_types import Entity
from core.graph_model import GraphModel


def test_degree_counts_both_directions():
    model = GraphModel()
    e1 = Entity(type="Domain", value="x.com")
    e2 = Entity(type="IP", value="1.2.3.4")
    e3 = Entity(type="Email", value="a@x.com")
    model.add_entity(e1)
    model.add_entity(e2)
    model.add_entity(e3)

    assert model.degree(e3.id) == 0  # aislado

    model.add_relation(e1.id, e2.id, "resuelve a")
    assert model.degree(e1.id) == 1  # origen de la relación
    assert model.degree(e2.id) == 1  # destino de la relación

    model.add_relation(e1.id, e3.id, "contacto")
    assert model.degree(e1.id) == 2  # ahora en dos relaciones


def test_degree_of_nonexistent_entity_is_zero():
    model = GraphModel()
    assert model.degree("id-que-no-existe") == 0


def test_delete_isolated_node_never_asks_for_confirmation(main_window):
    """Un nodo sin conexiones no tiene nada que perder salvo a sí mismo --
    no hace falta interrumpir con un diálogo para eso."""
    entity = Entity(type="Domain", value="aislado.com")
    main_window.model.add_entity(entity)
    main_window.scene.add_entity_visual(entity)

    with patch("ui.main_window.QMessageBox.question") as mocked:
        main_window.delete_entity(entity)
        assert not mocked.called

    assert main_window.model.get_entity(entity.id) is None


def test_delete_connected_node_asks_and_mentions_real_count(main_window):
    a = Entity(type="Domain", value="x.com")
    b = Entity(type="IP", value="1.2.3.4")
    main_window.model.add_entity(a)
    main_window.model.add_entity(b)
    main_window.scene.add_entity_visual(a)
    main_window.scene.add_entity_visual(b)
    main_window.model.add_relation(a.id, b.id, "resuelve a")
    main_window.scene.add_relation_visual(a, b, "resuelve a")

    with patch("ui.main_window.QMessageBox.question", return_value=QMessageBox.Yes) as mocked:
        main_window.delete_entity(a)
        texto_mostrado = mocked.call_args.args[2]

    assert "1 conexión" in texto_mostrado
    assert main_window.model.get_entity(a.id) is None  # se borró tras confirmar


def test_delete_connected_node_cancelled_keeps_the_node(main_window):
    a = Entity(type="Domain", value="y.com")
    b = Entity(type="IP", value="9.9.9.9")
    main_window.model.add_entity(a)
    main_window.model.add_entity(b)
    main_window.scene.add_entity_visual(a)
    main_window.scene.add_entity_visual(b)
    main_window.model.add_relation(a.id, b.id, "resuelve a")
    main_window.scene.add_relation_visual(a, b, "resuelve a")

    with patch("ui.main_window.QMessageBox.question", return_value=QMessageBox.No):
        main_window.delete_entity(a)

    assert main_window.model.get_entity(a.id) is not None
    assert main_window.scene.node_items.get(a.id) is not None  # tampoco desaparece visualmente


def test_delete_confirmation_default_button_is_no(main_window):
    """Que el botón por defecto sea 'No' es la parte importante de este
    diseño: un Enter accidental en el diálogo no debe borrar nada."""
    a = Entity(type="Domain", value="z.com")
    b = Entity(type="IP", value="1.1.1.1")
    main_window.model.add_entity(a)
    main_window.model.add_entity(b)
    main_window.scene.add_entity_visual(a)
    main_window.scene.add_entity_visual(b)
    main_window.model.add_relation(a.id, b.id, "r")
    main_window.scene.add_relation_visual(a, b, "r")

    with patch("ui.main_window.QMessageBox.question", return_value=QMessageBox.No) as mocked:
        main_window.delete_entity(a)
        default_button_arg = mocked.call_args.args[4]

    assert default_button_arg == QMessageBox.No


def test_delete_entity_confirmed_removes_orphan_edges(main_window):
    """El propio borrado (una vez confirmado) sigue limpiando las
    aristas conectadas, igual que antes de añadir la confirmación."""
    a = Entity(type="Domain", value="x.com")
    b = Entity(type="IP", value="1.2.3.4")
    main_window.model.add_entity(a)
    main_window.model.add_entity(b)
    main_window.scene.add_entity_visual(a)
    main_window.scene.add_entity_visual(b)
    main_window.model.add_relation(a.id, b.id, "r")
    main_window.scene.add_relation_visual(a, b, "r")

    main_window._delete_entity_confirmed(a)

    edges = [it for it in main_window.scene.items() if type(it).__name__ == "EdgeItem"]
    assert len(edges) == 0
