"""
Configuración compartida de la suite de tests.

- `qapp`: una única QApplication por proceso de test (Qt no permite más de
  una instancia viva a la vez -- de ámbito "session" para reutilizarla en
  todos los tests en vez de crear/destruir una por test).
- `QT_QPA_PLATFORM=offscreen`: se fija ANTES de importar nada de PySide6,
  para poder correr la suite en un entorno sin pantalla (CI, terminal
  remota) sin necesidad de un servidor gráfico real.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def main_window(qapp):
    """Una MainWindow nueva y limpia para cada test que la necesite."""
    from ui.main_window import MainWindow
    return MainWindow()


@pytest.fixture
def graph_model():
    from core.graph_model import GraphModel
    return GraphModel()


@pytest.fixture
def graph_scene(graph_model, qapp):
    from ui.graph_scene import GraphScene
    return GraphScene(graph_model)
