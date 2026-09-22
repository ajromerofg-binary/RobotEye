"""
Paleta de colores y constantes de estilo "hacker cyberpunk" para RobotEye.
Punto único de verdad: todo lo demás en ui/ importa de aquí en vez de
repetir valores hex sueltos.
"""

# Fondos
BG_VOID = "#05070d"       # negro-azulado casi puro, el vacío detrás de todo
BG_BASE = "#0a0e17"       # fondo principal de ventanas/paneles
BG_PANEL = "#0d1420"      # paneles ligeramente más claros (inputs, cajas)
BG_PANEL_ALT = "#111a2b"  # hover / selección sutil

# Bordes y líneas
BORDER = "#1c2a3f"
BORDER_BRIGHT = "#2a3f5c"
GRID_LINE = "#0f1d2e"     # rejilla del canvas, muy tenue

# Acentos neón
NEON_CYAN = "#00fff2"
NEON_MAGENTA = "#ff2fd0"
NEON_GREEN = "#39ff88"
NEON_AMBER = "#ffb300"
NEON_PURPLE = "#b967ff"
NEON_RED = "#ff2b4e"
NEON_BLUE = "#2f9bff"

# Texto
TEXT_PRIMARY = "#d6faff"
TEXT_DIM = "#5c7a99"
TEXT_BRIGHT = "#ffffff"

# Tipografía monoespaciada estilo terminal, con fallbacks multiplataforma
MONO_FONT_FAMILIES = ["JetBrains Mono", "Cascadia Code", "Consolas",
                       "Fira Code", "Courier New", "monospace"]
EMOJI_FONT_FAMILIES = ["Segoe UI Emoji", "Noto Color Emoji", "Apple Color Emoji"]
