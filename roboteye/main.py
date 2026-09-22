import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor, QFont

from ui.main_window import MainWindow
from ui import theme


def apply_cyberpunk_theme(app: QApplication):
    app.setStyle("Fusion")

    # Fuente monoespaciada estilo terminal para toda la app, con fallbacks
    # multiplataforma (Qt prueba cada familia en orden hasta encontrar una instalada)
    font = QFont()
    font.setFamilies(theme.MONO_FONT_FAMILIES)
    font.setPointSize(10)
    app.setFont(font)

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(theme.BG_BASE))
    palette.setColor(QPalette.WindowText, QColor(theme.TEXT_PRIMARY))
    palette.setColor(QPalette.Base, QColor(theme.BG_PANEL))
    palette.setColor(QPalette.AlternateBase, QColor(theme.BG_PANEL_ALT))
    palette.setColor(QPalette.ToolTipBase, QColor(theme.BG_PANEL))
    palette.setColor(QPalette.ToolTipText, QColor(theme.NEON_CYAN))
    palette.setColor(QPalette.Text, QColor(theme.TEXT_PRIMARY))
    palette.setColor(QPalette.Button, QColor(theme.BG_PANEL))
    palette.setColor(QPalette.ButtonText, QColor(theme.NEON_CYAN))
    palette.setColor(QPalette.Highlight, QColor(theme.NEON_MAGENTA))
    palette.setColor(QPalette.HighlightedText, QColor(theme.BG_VOID))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(theme.TEXT_DIM))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(theme.TEXT_DIM))
    palette.setColor(QPalette.Link, QColor(theme.NEON_CYAN))
    app.setPalette(palette)

    app.setStyleSheet(f"""
        QMainWindow, QWidget {{
            background-color: {theme.BG_BASE};
            color: {theme.TEXT_PRIMARY};
        }}

        QMenuBar {{
            background-color: {theme.BG_VOID};
            color: {theme.NEON_CYAN};
            border-bottom: 1px solid {theme.BORDER_BRIGHT};
            padding: 2px;
        }}
        QMenuBar::item {{
            padding: 4px 12px;
            background: transparent;
        }}
        QMenuBar::item:selected {{
            background-color: {theme.BG_PANEL_ALT};
            color: {theme.NEON_MAGENTA};
        }}
        QMenu {{
            background-color: {theme.BG_PANEL};
            color: {theme.TEXT_PRIMARY};
            border: 1px solid {theme.NEON_CYAN};
        }}
        QMenu::item {{
            padding: 6px 24px 6px 12px;
        }}
        QMenu::item:selected {{
            background-color: {theme.BG_PANEL_ALT};
            color: {theme.NEON_MAGENTA};
        }}
        QMenu::item:disabled {{
            color: {theme.TEXT_DIM};
        }}
        QMenu::separator {{
            height: 1px;
            background: {theme.BORDER_BRIGHT};
            margin: 4px 8px;
        }}

        QPushButton {{
            background-color: {theme.BG_PANEL};
            color: {theme.NEON_CYAN};
            border: 1px solid {theme.NEON_CYAN};
            border-radius: 2px;
            padding: 6px 14px;
        }}
        QPushButton:hover {{
            background-color: {theme.NEON_CYAN};
            color: {theme.BG_VOID};
        }}
        QPushButton:pressed {{
            background-color: {theme.NEON_MAGENTA};
            border-color: {theme.NEON_MAGENTA};
        }}

        QLineEdit, QTextEdit, QComboBox, QListWidget {{
            background-color: {theme.BG_PANEL};
            color: {theme.TEXT_PRIMARY};
            border: 1px solid {theme.BORDER_BRIGHT};
            border-radius: 2px;
            padding: 3px;
            selection-background-color: {theme.NEON_MAGENTA};
            selection-color: {theme.BG_VOID};
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border: 1px solid {theme.NEON_CYAN};
        }}
        QComboBox::drop-down {{
            border-left: 1px solid {theme.BORDER_BRIGHT};
            background-color: {theme.BG_PANEL};
        }}
        QComboBox::down-arrow {{
            width: 10px;
            height: 10px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {theme.BG_PANEL};
            color: {theme.TEXT_PRIMARY};
            selection-background-color: {theme.NEON_CYAN};
            selection-color: {theme.BG_VOID};
            border: 1px solid {theme.NEON_CYAN};
        }}

        QLabel {{
            color: {theme.TEXT_PRIMARY};
        }}

        QStatusBar {{
            background-color: {theme.BG_VOID};
            color: {theme.NEON_GREEN};
            border-top: 1px solid {theme.BORDER_BRIGHT};
        }}

        QScrollBar:vertical {{
            background: {theme.BG_BASE};
            width: 10px;
        }}
        QScrollBar::handle:vertical {{
            background: {theme.BORDER_BRIGHT};
            min-height: 24px;
            border-radius: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {theme.NEON_CYAN};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: {theme.BG_BASE};
        }}

        QScrollBar:horizontal {{
            background: {theme.BG_BASE};
            height: 10px;
        }}
        QScrollBar::handle:horizontal {{
            background: {theme.BORDER_BRIGHT};
            min-width: 24px;
            border-radius: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {theme.NEON_CYAN};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: {theme.BG_BASE};
        }}

        QGraphicsView {{
            border: none;
        }}
    """)


def main():
    app = QApplication(sys.argv)
    apply_cyberpunk_theme(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
