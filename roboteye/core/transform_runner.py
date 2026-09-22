"""
Ejecuta una transform en un hilo aparte (QThread) para que la UI
no se congele durante las peticiones de red, y emite una señal
con los resultados cuando termina.
"""
from PySide6.QtCore import QThread, Signal
from core.entity_types import Entity
from core.transform_base import Transform


class TransformWorker(QThread):
    finished_ok = Signal(list, object)   # (resultados, entidad_origen)
    finished_error = Signal(str, object)  # (mensaje_error, entidad_origen)

    def __init__(self, transform: Transform, entity: Entity, parent=None):
        super().__init__(parent)
        self.transform = transform
        self.entity = entity

    def run(self):
        try:
            results = self.transform.run(self.entity)
            self.finished_ok.emit(results, self.entity)
        except Exception as e:
            self.finished_error.emit(str(e), self.entity)
