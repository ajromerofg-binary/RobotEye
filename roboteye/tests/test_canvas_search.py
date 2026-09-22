"""
Tests de la búsqueda dentro del lienzo (`MainWindow._find_matching_entities`,
`MainWindow.search_next`) y del resaltado temporal de nodo (`NodeItem.highlight`).
"""
from core.entity_types import Entity


def _populate(main_window):
    entidades = [
        Entity(type="Domain", value="acmecorp.com"),
        Entity(type="Domain", value="acme-staging.com"),
        Entity(type="IP", value="8.8.8.8"),
        Entity(type="IP", value="1.1.1.1"),
        Entity(type="Email", value="ana@acmecorp.com"),
    ]
    for e in entidades:
        main_window.model.add_entity(e)
        main_window.scene.add_entity_visual(e)
    return entidades


def test_search_by_substring_matches_across_types(main_window):
    _populate(main_window)
    resultados = main_window._find_matching_entities("acme")
    assert len(resultados) == 3  # 2 dominios + 1 email, todos contienen "acme"


def test_search_by_exact_type_name_filters_by_type(main_window):
    _populate(main_window)
    resultados = main_window._find_matching_entities("IP")
    assert len(resultados) == 2
    assert all(e.type == "IP" for e in resultados)


def test_search_type_filter_is_case_insensitive(main_window):
    _populate(main_window)
    resultados = main_window._find_matching_entities("domain")
    assert len(resultados) == 2
    assert all(e.type == "Domain" for e in resultados)


def test_search_substring_is_case_insensitive(main_window):
    _populate(main_window)
    resultados = main_window._find_matching_entities("ACME")
    assert len(resultados) == 3


def test_search_no_results(main_window):
    _populate(main_window)
    assert main_window._find_matching_entities("noexiste123") == []


def test_search_empty_query_returns_nothing(main_window):
    _populate(main_window)
    assert main_window._find_matching_entities("   ") == []


def test_search_next_cycles_through_results_and_wraps(main_window):
    _populate(main_window)
    main_window.search_box.setText("IP")

    main_window.search_next()
    assert main_window._search_index == 0
    primer_mensaje = main_window.statusBar().currentMessage()
    assert "Resultado 1 de 2" in primer_mensaje

    main_window.search_next()
    assert main_window._search_index == 1
    assert "Resultado 2 de 2" in main_window.statusBar().currentMessage()

    main_window.search_next()  # debe volver al principio (ciclo)
    assert main_window._search_index == 0


def test_search_next_selects_and_highlights_the_found_node(main_window):
    entidades = _populate(main_window)
    acme_domain = next(e for e in entidades if e.value == "acmecorp.com")
    otra_entidad = next(e for e in entidades if e.value == "8.8.8.8")

    main_window.search_box.setText("acmecorp.com")
    main_window.search_next()

    node_encontrado = main_window.scene.node_items[acme_domain.id]
    node_otro = main_window.scene.node_items[otra_entidad.id]

    assert node_encontrado.isSelected() is True
    assert node_otro.isSelected() is False
    assert node_encontrado.graphicsEffect().blurRadius() == 60  # resaltado activo


def test_search_next_empty_query_shows_message_without_crashing(main_window):
    _populate(main_window)
    main_window.search_box.setText("")
    main_window.search_next()
    assert "Escribe algo" in main_window.statusBar().currentMessage()


def test_search_next_no_results_shows_message(main_window):
    _populate(main_window)
    main_window.search_box.setText("noexiste123")
    main_window.search_next()
    assert "Sin resultados" in main_window.statusBar().currentMessage()


def test_node_highlight_reverts_after_timeout(qapp):
    from PySide6.QtCore import QEventLoop, QTimer
    from ui.node_item import NodeItem

    node = NodeItem(Entity(type="Domain", value="x.com"))
    glow = node.graphicsEffect()
    original_radius = glow.blurRadius()

    node.highlight(duration_ms=200)
    assert glow.blurRadius() == 60

    loop = QEventLoop()
    QTimer.singleShot(400, loop.quit)
    loop.exec()

    assert glow.blurRadius() == original_radius


def test_node_highlight_second_call_cancels_first_timer_correctly(qapp):
    """El segundo highlight() debe cancelar el timer del primero -- si no,
    el nodo se apaga a mitad del segundo highlight en vez de mantenerse
    resaltado hasta el final de este último."""
    from PySide6.QtCore import QEventLoop, QTimer
    from ui.node_item import NodeItem

    node = NodeItem(Entity(type="Domain", value="x.com"))
    glow = node.graphicsEffect()

    node.highlight(duration_ms=300)  # dispararía en t=300ms si no se cancela
    loop1 = QEventLoop()
    QTimer.singleShot(100, loop1.quit)
    loop1.exec()  # t=100ms
    node.highlight(duration_ms=300)  # cancela el anterior; dispara en t=100+300=400ms

    loop2 = QEventLoop()
    QTimer.singleShot(250, loop2.quit)
    loop2.exec()  # t=350ms: pasado el t=300 original, antes del t=400 del segundo
    assert glow.blurRadius() == 60, "el primer timer no se canceló correctamente"

    loop3 = QEventLoop()
    QTimer.singleShot(100, loop3.quit)
    loop3.exec()  # t=450ms: pasado el t=400 del segundo
    assert glow.blurRadius() == 28
