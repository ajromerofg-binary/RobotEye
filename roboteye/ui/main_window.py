from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QMenu, QInputDialog, QFileDialog, QMessageBox,
    QStatusBar, QTextEdit, QComboBox, QPushButton,
    QDialog, QPlainTextEdit, QCheckBox, QDialogButtonBox,
    QLineEdit
)
from PySide6.QtGui import QAction, QCursor
from PySide6.QtCore import QTimer
from datetime import datetime

from core.graph_model import GraphModel
from core.entity_types import Entity, VALID_TYPES, guess_entity_type
from core.transform_runner import TransformWorker
from transforms import TRANSFORM_REGISTRY
from ui.graph_scene import GraphScene
from ui.graph_view import GraphView
from ui import theme


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RobotEye — Sr.Robot Labs")
        self.resize(1300, 800)

        self.model = GraphModel()
        self.scene = GraphScene(self.model)
        self.view = GraphView(self.scene)

        self.scene.entity_selected.connect(self.show_entity_details)
        self.scene.context_requested.connect(self.show_context_menu)

        self._build_ui()
        self._build_menu()
        self._workers = []  # referencias vivas a QThreads en curso
        self._selected_entity_id = None
        self._last_search_query = None
        self._search_results = []
        self._search_index = -1
        self._activity_log = []  # [{"timestamp": ..., "message": ...}, ...] -- rastro estructurado y exportable, además de lo que ya se ve en el LOG

    # ---------- UI ----------
    def _build_ui(self):
        central = QWidget()
        layout = QHBoxLayout(central)

        layout.addWidget(self.view, stretch=4)

        side = QWidget()
        side_layout = QVBoxLayout(side)

        side_layout.addWidget(self._section_header("BUSCAR", theme.NEON_GREEN))
        search_row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("valor, o un tipo exacto (ej. IP)...")
        self.search_box.returnPressed.connect(self.search_next)
        search_row.addWidget(self.search_box)
        search_btn = QPushButton("↓")
        search_btn.setToolTip("Ir al siguiente resultado (o pulsa Intro en la caja)")
        search_btn.setMaximumWidth(32)
        search_btn.clicked.connect(self.search_next)
        search_row.addWidget(search_btn)
        side_layout.addLayout(search_row)

        side_layout.addWidget(self._section_header("DETALLES", theme.NEON_CYAN))
        self.detail_box = QTextEdit()
        self.detail_box.setReadOnly(True)
        self.detail_box.setStyleSheet(f"""
            QTextEdit {{
                background-color: {theme.BG_VOID};
                color: {theme.TEXT_PRIMARY};
                border: 1px solid {theme.NEON_CYAN};
            }}
        """)
        side_layout.addWidget(self.detail_box, stretch=2)

        side_layout.addWidget(self._section_header("NOTAS", theme.NEON_AMBER))
        self.notes_box = QPlainTextEdit()
        self.notes_box.setPlaceholderText("Selecciona un nodo y escribe tu propio criterio aquí: "
                                           "confirmado a mano, falso positivo, pendiente de verificar...")
        self.notes_box.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {theme.BG_VOID};
                color: {theme.TEXT_PRIMARY};
                border: 1px solid {theme.NEON_AMBER};
            }}
        """)
        side_layout.addWidget(self.notes_box, stretch=1)
        save_note_btn = QPushButton("💾 Guardar nota")
        save_note_btn.clicked.connect(self.save_note)
        side_layout.addWidget(save_note_btn)

        side_layout.addWidget(self._section_header("AÑADIR ENTIDAD", theme.NEON_MAGENTA))
        self.type_combo = QComboBox()
        self.type_combo.addItems(VALID_TYPES)
        side_layout.addWidget(self.type_combo)
        add_btn = QPushButton("+ AÑADIR")
        add_btn.clicked.connect(self.add_entity_dialog)
        side_layout.addWidget(add_btn)

        side_layout.addWidget(self._section_header("LOG", theme.NEON_GREEN))
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet(f"""
            QTextEdit {{
                background-color: {theme.BG_VOID};
                color: {theme.NEON_GREEN};
                border: 1px solid {theme.NEON_GREEN};
            }}
        """)
        side_layout.addWidget(self.log_box, stretch=3)

        side.setMaximumWidth(320)
        layout.addWidget(side, stretch=1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

    @staticmethod
    def _section_header(text: str, color: str) -> QLabel:
        """Cabecera de sección estilo consola: '[ TEXTO ]' en el color de acento
        de esa sección, para dar jerarquía visual sin salir del tema oscuro."""
        label = QLabel(f"[ {text} ]")
        label.setStyleSheet(f"color: {color}; font-weight: bold; padding-top: 6px;")
        return label

    def _build_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("&Proyecto")
        new_action = QAction("Nuevo", self)
        new_action.triggered.connect(self.new_project)
        file_menu.addAction(new_action)

        save_action = QAction("Guardar como JSON...", self)
        save_action.triggered.connect(self.save_json)
        file_menu.addAction(save_action)

        load_action = QAction("Abrir JSON...", self)
        load_action.triggered.connect(self.load_json)
        file_menu.addAction(load_action)

        save_db_action = QAction("Guardar como SQLite...", self)
        save_db_action.triggered.connect(self.save_sqlite)
        file_menu.addAction(save_db_action)

        load_db_action = QAction("Abrir SQLite...", self)
        load_db_action.triggered.connect(self.load_sqlite)
        file_menu.addAction(load_db_action)

        file_menu.addSeparator()
        import_bulk_action = QAction("Importar lista...", self)
        import_bulk_action.triggered.connect(self.import_bulk_dialog)
        file_menu.addAction(import_bulk_action)

        file_menu.addSeparator()
        export_html_action = QAction("Exportar informe (HTML)...", self)
        export_html_action.triggered.connect(self.export_html_report)
        file_menu.addAction(export_html_action)

        export_pdf_action = QAction("Exportar informe (PDF)...", self)
        export_pdf_action.triggered.connect(self.export_pdf_report)
        file_menu.addAction(export_pdf_action)

        export_log_action = QAction("Exportar registro de actividad...", self)
        export_log_action.triggered.connect(self.export_activity_log)
        file_menu.addAction(export_log_action)

        file_menu.addSeparator()
        import_eml_action = QAction("Analizar email sospechoso (.eml)...", self)
        import_eml_action.triggered.connect(self.import_eml_dialog)
        file_menu.addAction(import_eml_action)

        view_menu = menu.addMenu("&Vista")
        organize_action = QAction("Auto-organizar (layout de fuerzas)", self)
        organize_action.triggered.connect(self.auto_organize)
        view_menu.addAction(organize_action)

    def auto_organize(self):
        self.scene.apply_spring_layout()
        self.log("Grafo reorganizado con layout de fuerzas.")

    # ---------- Acciones de proyecto ----------
    def new_project(self):
        self.model = GraphModel()
        self.scene = GraphScene(self.model)
        self.scene.entity_selected.connect(self.show_entity_details)
        self.scene.context_requested.connect(self.show_context_menu)
        self.view.setScene(self.scene)
        self._selected_entity_id = None
        self.detail_box.clear()
        self.log("Nuevo proyecto creado.")

    def save_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Guardar proyecto", "", "JSON (*.json)")
        if path:
            self.model.save_json(path)
            self.log(f"Proyecto guardado en {path}")

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", "", "JSON (*.json)")
        if path:
            self.model.load_json(path)
            self._rebuild_scene_from_model()
            self.log(f"Proyecto cargado desde {path}")

    def save_sqlite(self):
        path, _ = QFileDialog.getSaveFileName(self, "Guardar proyecto", "", "SQLite (*.db)")
        if path:
            self.model.save_sqlite(path)
            self.log(f"Proyecto guardado en {path}")

    def load_sqlite(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", "", "SQLite (*.db)")
        if path:
            self.model.load_sqlite(path)
            self._rebuild_scene_from_model()
            self.log(f"Proyecto cargado desde {path}")

    def export_html_report(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar informe HTML", "informe_roboteye.html", "HTML (*.html)")
        if not path:
            return
        try:
            from core.report_generator import generate_html_report
            generate_html_report(self.model, path)
            self.log(f"Informe HTML exportado en {path}")
        except Exception as ex:
            self.log(f"Error al exportar el informe HTML: {ex}")

    def export_pdf_report(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar informe PDF", "informe_roboteye.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            from core.report_generator import generate_pdf_report
            generate_pdf_report(self.model, path)
            self.log(f"Informe PDF exportado en {path}")
        except Exception as ex:
            self.log(f"Error al exportar el informe PDF: {ex}")

    def import_eml_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Analizar email sospechoso", "", "Correo (*.eml)")
        if not path:
            return
        try:
            from core.email_analyzer import analyze_eml, populate_graph_from_analysis
            analysis = analyze_eml(path)
            email_msg_entity = populate_graph_from_analysis(self.model, self.scene, analysis)
        except Exception as ex:
            self.log(f"Error al analizar el correo: {ex}")
            return

        n_indicadores = len(analysis["spoofing_indicators"])
        if n_indicadores:
            self.log(
                f"Correo analizado: '{email_msg_entity.value}' -- {n_indicadores} "
                f"indicador(es) de posible suplantación encontrados. Revisa el panel "
                f"de detalles del nodo para más información."
            )
        else:
            self.log(
                f"Correo analizado: '{email_msg_entity.value}' -- sin indicadores "
                f"automáticos de suplantación (revisa igualmente el contenido a mano)."
            )

    def _rebuild_scene_from_model(self):
        self.scene.clear_all()
        for entity in self.model.all_entities():
            self.scene.add_entity_visual(entity)
        for source, target, data in self.model.edges():
            src_e = self.model.get_entity(source)
            tgt_e = self.model.get_entity(target)
            self.scene.add_relation_visual(src_e, tgt_e, data.get("label", ""))

    # ---------- Entidades ----------
    def add_entity_dialog(self):
        type_ = self.type_combo.currentText()
        value, ok = QInputDialog.getText(self, f"Nueva entidad ({type_})", "Valor:")
        if ok and value.strip():
            was_duplicate = self.model.find_entity(type_, value.strip()) is not None
            entity_id = self.model.add_entity(Entity(type=type_, value=value.strip()))
            real_entity = self.model.get_entity(entity_id)  # siempre la instancia que vive en el grafo
            self.scene.add_entity_visual(real_entity)
            if was_duplicate:
                self.log(f"'{value.strip()}' ya existía como {type_}, no se duplica.")
            else:
                self.log(f"Entidad añadida: {type_} = {value.strip()}")

    def import_bulk_dialog(self):
        """Importación masiva: pega una lista de valores (uno por línea) y
        los añade todos de golpe, reusando exactamente el mismo camino de
        deduplicación que add_entity_dialog() (uno por uno, en bucle) --
        nada nuevo que pueda desincronizar modelo y escena."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Importar lista de entidades")
        dialog.resize(480, 420)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Tipo por defecto (se usa si no se autodetecta):"))
        type_combo = QComboBox()
        type_combo.addItems(VALID_TYPES)
        layout.addWidget(type_combo)

        autodetect_checkbox = QCheckBox(
            "Autodetectar tipo cuando sea evidente (Email, URL, IP, Domain)"
        )
        autodetect_checkbox.setChecked(True)
        layout.addWidget(autodetect_checkbox)

        layout.addWidget(QLabel("Pega los valores, uno por línea:"))
        text_edit = QPlainTextEdit()
        text_edit.setPlaceholderText("ejemplo.com\notro-dominio.com\nana@ejemplo.com\n8.8.8.8\n...")
        layout.addWidget(text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        default_type = type_combo.currentText()
        autodetect = autodetect_checkbox.isChecked()
        lines = [line.strip() for line in text_edit.toPlainText().splitlines()]
        lines = [line for line in lines if line]

        if not lines:
            self.log("Importación: no se pegó ningún valor.")
            return

        added, duplicates = self._import_lines(lines, default_type, autodetect)
        self.log(
            f"Importación completa: {added} entidad(es) nueva(s) añadida(s), "
            f"{duplicates} ya existían y no se duplicaron ({len(lines)} línea(s) procesadas en total)."
        )

    def _import_lines(self, lines, default_type: str, autodetect: bool):
        """Lógica pura de la importación masiva, separada del diálogo para
        poder testearla sin simular la interfaz gráfica. Devuelve
        (añadidas, duplicadas)."""
        added, duplicates = 0, 0
        for value in lines:
            entity_type = default_type
            if autodetect:
                detected = guess_entity_type(value)
                if detected:
                    entity_type = detected

            was_duplicate = self.model.find_entity(entity_type, value) is not None
            entity_id = self.model.add_entity(Entity(type=entity_type, value=value))
            real_entity = self.model.get_entity(entity_id)
            self.scene.add_entity_visual(real_entity)

            if was_duplicate:
                duplicates += 1
            else:
                added += 1
        return added, duplicates

    def _find_matching_entities(self, query: str):
        """Lógica pura de la búsqueda, separada de la interfaz para poder
        testearla sin simular clics ni centrar la vista. Dos modos en la
        misma caja: si el texto coincide EXACTAMENTE (sin importar
        mayúsculas) con un tipo de entidad válido, se interpreta como
        filtro por tipo (ej. escribir "IP" recorre todos los nodos IP,
        uno tras otro); si no, se busca como subcadena dentro del valor
        de cualquier entidad, sin importar mayúsculas."""
        query = query.strip()
        if not query:
            return []
        query_lower = query.lower()
        type_match = next((t for t in VALID_TYPES if t.lower() == query_lower), None)
        if type_match:
            return [e for e in self.model.all_entities() if e.type == type_match]
        return [e for e in self.model.all_entities() if query_lower in e.value.lower()]

    def search_next(self):
        """Busca (o avanza al siguiente resultado de la misma búsqueda ya
        en curso) y centra la vista sobre el nodo encontrado,
        resaltándolo un momento."""
        query = self.search_box.text()
        if not query.strip():
            self.statusBar().showMessage("Escribe algo para buscar.", 3000)
            return

        if query != self._last_search_query:
            self._last_search_query = query
            self._search_results = self._find_matching_entities(query)
            self._search_index = -1

        if not self._search_results:
            self.statusBar().showMessage(f"Sin resultados para '{query.strip()}'.", 3000)
            return

        self._search_index = (self._search_index + 1) % len(self._search_results)
        entity = self._search_results[self._search_index]

        node = self.scene.node_items.get(entity.id)
        if node is None:
            # La entidad ya no existe visualmente (se borró entre búsquedas) --
            # se salta sin más, no es un fallo del que avisar con alarma.
            return
        self.view.centerOn(node)
        node.highlight()
        self.scene.clearSelection()
        node.setSelected(True)

        self.statusBar().showMessage(
            f"Resultado {self._search_index + 1} de {len(self._search_results)}: "
            f"{entity.type} = {entity.value}"
        )

    def show_entity_details(self, entity: Entity):
        self._selected_entity_id = entity.id
        lines = [
            f'<span style="color:{theme.TEXT_DIM}">Tipo:</span> '
            f'<span style="color:{theme.NEON_CYAN}">{entity.type}</span>',
            f'<span style="color:{theme.TEXT_DIM}">Valor:</span> '
            f'<span style="color:{theme.TEXT_BRIGHT}">{entity.value}</span>',
            "",
        ]
        for k, v in entity.properties.items():
            lines.append(
                f'<span style="color:{theme.NEON_MAGENTA}">{k}:</span> '
                f'<span style="color:{theme.TEXT_PRIMARY}">{v}</span>'
            )
        self.detail_box.setHtml("<br>".join(lines))
        self.notes_box.setPlainText(entity.user_note)

    def save_note(self):
        """Guarda el texto de la caja de notas en la entidad actualmente
        seleccionada -- explícito con un botón (y no automático al
        escribir) para no arriesgar guardar a mitad de frase sobre la
        entidad equivocada si el usuario cambia de selección mientras
        escribe."""
        if self._selected_entity_id is None:
            self.log("⚠ No hay ningún nodo seleccionado -- selecciona uno antes de guardar una nota.")
            return
        entity = self.model.get_entity(self._selected_entity_id)
        if entity is None:
            self.log("⚠ El nodo seleccionado ya no existe (se borró) -- la nota no se ha guardado.")
            return
        entity.user_note = self.notes_box.toPlainText()
        self.log(f"Nota guardada en '{entity.value}'.")

    # ---------- Menú contextual / transforms ----------
    def show_context_menu(self, entity: Entity, scene_pos):
        menu = QMenu(self)
        applicable = [t for t in TRANSFORM_REGISTRY if t.applies_to(entity)]
        passive = [t for t in applicable if not t.requires_consent]
        active = [t for t in applicable if t.requires_consent]

        if not applicable:
            menu.addAction("(sin transforms para este tipo)").setEnabled(False)
        else:
            # Atajo "ejecutar todas de golpe", inspirado en el icono >> de
            # Maltego ("Run all in this Set"): lanza todas las transforms
            # PASIVAS aplicables a la vez -- nunca las activas, eso
            # rompería el sentido de pedir consentimiento por acción.
            if len(passive) > 1:
                run_all_action = QAction(f"▶▶ Ejecutar todas ({len(passive)})", self)
                run_all_action.triggered.connect(
                    lambda checked=False, e=entity: self.run_all_passive_transforms(e)
                )
                menu.addAction(run_all_action)
                menu.addSeparator()

            for transform in passive:
                action = QAction(f"▶ {transform.name}", self)
                action.triggered.connect(
                    lambda checked=False, t=transform, e=entity: self.run_transform_with_consent(t, e)
                )
                menu.addAction(action)

            # Apartado aparte: transforms que tocan el objetivo directamente
            # (no un tercero). Separadas visualmente y con confirmación
            # explícita antes de ejecutarse -- ver run_transform_with_consent().
            # Deliberadamente NUNCA se incluyen en "Ejecutar todas": cada una
            # exige su propia confirmación consciente, una por una.
            if active:
                menu.addSeparator()
                header = QAction("⚠ Reconocimiento activo (toca el objetivo)", self)
                header.setEnabled(False)
                menu.addAction(header)
                for transform in active:
                    action = QAction(f"▶ {transform.name}", self)
                    action.triggered.connect(
                        lambda checked=False, t=transform, e=entity: self.run_transform_with_consent(t, e)
                    )
                    menu.addAction(action)

        menu.addSeparator()
        delete_action = QAction("🗑 Eliminar entidad", self)
        delete_action.triggered.connect(lambda: self.delete_entity(entity))
        menu.addAction(delete_action)

        menu.exec(QCursor.pos())

    # Milisegundos entre el lanzamiento de cada transform que consulta
    # DuckDuckGo dentro de "Ejecutar todas" -- un disparo simultáneo de
    # varias búsquedas es precisamente el patrón que dispara el bloqueo
    # por detección de anomalías de DDG (ver
    # dorking_transforms.py::is_ddg_blocked). Las demás transforms (DNS,
    # APIs oficiales...) no tienen este problema y siguen lanzándose de
    # golpe, sin ningún retraso.
    DDG_STAGGER_MS = 700

    def run_all_passive_transforms(self, entity: Entity):
        """Lanza de golpe todas las transforms pasivas aplicables a esta
        entidad -- cada una crea su propio TransformWorker (QThread), así
        que corren en paralelo de forma natural, igual que Maltego muestra
        el progreso conjunto de varias transforms lanzadas a la vez. Las
        transforms activas (requires_consent) nunca se incluyen aquí.

        Excepción: las transforms marcadas `uses_ddg = True` se escalonan
        en el tiempo (ver DDG_STAGGER_MS) en vez de lanzarse en el mismo
        instante -- mitiga, no elimina del todo, el riesgo de bloqueo por
        anomalías de DuckDuckGo si se han lanzado ya otras búsquedas hace
        poco en la misma sesión."""
        applicable_passive = [
            t for t in TRANSFORM_REGISTRY
            if t.applies_to(entity) and not t.requires_consent
        ]
        applicable_active = [
            t for t in TRANSFORM_REGISTRY
            if t.applies_to(entity) and t.requires_consent
        ]
        self.log(f"Ejecutando {len(applicable_passive)} transform(s) pasivas sobre '{entity.value}'...")

        ddg_delay_slots = 0
        for transform in applicable_passive:
            if transform.uses_ddg:
                delay_ms = ddg_delay_slots * self.DDG_STAGGER_MS
                ddg_delay_slots += 1
                QTimer.singleShot(delay_ms, lambda t=transform, e=entity: self.run_transform(t, e))
            else:
                self.run_transform(transform, entity)

        if applicable_active:
            nombres = ", ".join(t.name for t in applicable_active)
            self.log(
                f"({len(applicable_active)} transform(s) de reconocimiento activo disponibles "
                f"para '{entity.value}' no se han ejecutado -- lánzalas manualmente si las necesitas: {nombres})"
            )

    def delete_entity(self, entity: Entity):
        """Pide confirmación antes de borrar si el nodo tiene alguna
        conexión -- un nodo aislado no necesita el mismo aviso que uno
        con horas de investigación colgando de él, y el borrado es
        irreversible (no hay deshacer)."""
        n_conexiones = self.model.degree(entity.id)
        if n_conexiones > 0:
            respuesta = QMessageBox.question(
                self,
                "Confirmar eliminación",
                f"'{entity.value}' tiene {n_conexiones} conexión(es). Al eliminarlo, "
                f"esas conexiones desaparecerán también, y esta acción no se puede "
                f"deshacer.\n\n¿Seguro que quieres continuar?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,  # por defecto NO -- un Enter accidental no debe borrar nada
            )
            if respuesta != QMessageBox.Yes:
                self.log(f"Eliminación cancelada: '{entity.value}' se conserva.")
                return

        self._delete_entity_confirmed(entity)

    def _delete_entity_confirmed(self, entity: Entity):
        """Lógica real de borrado, separada de la confirmación para poder
        testearla sin simular clics en un QMessageBox."""
        self.scene.remove_entity_visual(entity.id)  # también limpia sus aristas conectadas
        self.model.remove_entity(entity.id)
        self.log(f"Entidad eliminada: {entity.value}")

    def run_transform_with_consent(self, transform, entity: Entity):
        """Punto de entrada único desde el menú contextual: si la transform
        toca directamente al objetivo (requires_consent), exige una
        confirmación explícita y bloqueante antes de lanzarla. Si el usuario
        no confirma, la transform NUNCA se ejecuta."""
        if transform.requires_consent:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Confirmación requerida: reconocimiento activo")
            box.setText(
                f"'{transform.name}' va a enviar tráfico directamente a "
                f"'{entity.value}' -- no a un tercero, como hace el resto de "
                f"transforms de RobotEye.\n\n"
                "Confirma que tienes autorización expresa para hacer pruebas "
                "sobre este objetivo (es tuyo, es un laboratorio/CTF con "
                "permiso, o tienes autorización explícita del propietario)."
            )
            yes_button = box.addButton("Sí, tengo autorización", QMessageBox.AcceptRole)
            box.addButton("Cancelar", QMessageBox.RejectRole)
            box.setDefaultButton(box.buttons()[-1])  # el botón por defecto es Cancelar, no el de riesgo
            box.exec()
            if box.clickedButton() is not yes_button:
                self.log(f"Cancelado: '{transform.name}' requiere confirmación de autorización y no se dio.")
                return
            self.log(f"Autorización confirmada por el usuario para '{transform.name}' sobre {entity.value}.")

        self.run_transform(transform, entity)

    def run_transform(self, transform, entity: Entity):
        self.log(f"Ejecutando '{transform.name}' sobre {entity.value}...")
        self.statusBar().showMessage(f"Ejecutando {transform.name}...")

        worker = TransformWorker(transform, entity)
        worker.finished_ok.connect(self.on_transform_ok)
        worker.finished_error.connect(self.on_transform_error)
        worker.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        self._workers.append(worker)
        worker.start()

    def on_transform_ok(self, results, source_entity):
        self.scene.add_transform_results(source_entity, results)
        self.log(f"'{source_entity.value}': {len(results)} resultado(s) nuevo(s).")
        self.statusBar().showMessage("Listo.", 3000)
        # Si la transform modificó propiedades de la entidad actualmente mostrada
        # (ej. WHOIS añade registrar/fechas al propio dominio), refrescamos el panel.
        if source_entity.id == self._selected_entity_id:
            refreshed = self.model.get_entity(source_entity.id)
            if refreshed:
                self.show_entity_details(refreshed)

    def on_transform_error(self, error_msg, source_entity):
        self.log(f"⚠ Error en transform sobre {source_entity.value}: {error_msg}")
        self.statusBar().showMessage("Error en transform.", 5000)

    # ---------- Utilidades ----------
    def log(self, msg: str):
        # Estilo consola: prompt '>' en verde, errores (⚠) resaltados en rojo
        is_error = msg.strip().startswith("⚠")
        color = theme.NEON_RED if is_error else theme.NEON_GREEN
        prompt_color = theme.TEXT_DIM if is_error else theme.NEON_GREEN
        self.log_box.append(f'<span style="color:{prompt_color}">&gt;</span> '
                             f'<span style="color:{color}">{msg}</span>')
        # Además del texto visual de arriba, se guarda una entrada
        # estructurada (con fecha/hora real) -- es lo que hace posible
        # exportar un registro de actividad de verdad, en vez de que todo
        # se pierda al cerrar la app.
        self._activity_log.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": msg,
        })

    def _format_activity_log(self) -> str:
        """Lógica pura de formateo, separada de la exportación a fichero
        para poder testearla sin simular un diálogo de guardado."""
        if not self._activity_log:
            return "(sin actividad registrada en esta sesión)\n"
        return "\n".join(f"[{e['timestamp']}] {e['message']}" for e in self._activity_log) + "\n"

    def export_activity_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar registro de actividad", "registro_roboteye.txt", "Texto (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._format_activity_log())
            self.log(f"Registro de actividad exportado en {path} ({len(self._activity_log)} entrada(s)).")
        except Exception as ex:
            self.log(f"⚠ Error al exportar el registro de actividad: {ex}")
