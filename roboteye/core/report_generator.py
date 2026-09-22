"""
Genera un informe legible (HTML o PDF) de una investigación: resumen,
desglose por tipo de entidad, y cada nodo con sus propiedades y
relaciones. Pensado para entregar a un cliente o archivar un hallazgo,
no para trabajar dentro de la app (para eso ya está el propio lienzo).

Separado en dos partes a propósito:
- `build_report_data()`: construye una estructura de datos plana, sin
  ninguna dependencia de formato de salida.
- `generate_html_report()` / `generate_pdf_report()`: renderizan esa
  misma estructura en cada formato -- si el día de mañana se quiere un
  tercer formato, no hace falta tocar la parte de recogida de datos.
"""
import html
from datetime import datetime
from typing import List, Dict, Any

from core.graph_model import GraphModel


def build_report_data(model: GraphModel) -> Dict[str, Any]:
    entities = model.all_entities()
    edges = model.edges()

    relations_by_source: Dict[str, List[Dict[str, str]]] = {}
    for source_id, target_id, data in edges:
        target = model.get_entity(target_id)
        if target is None:
            continue  # arista huérfana defensiva, no debería darse en un grafo sano
        relations_by_source.setdefault(source_id, []).append({
            "label": data.get("label", ""),
            "target_type": target.type,
            "target_value": target.value,
        })

    counts_by_type: Dict[str, int] = {}
    for e in entities:
        counts_by_type[e.type] = counts_by_type.get(e.type, 0) + 1

    entities_data = []
    for e in sorted(entities, key=lambda x: (x.type, x.value.lower())):
        entities_data.append({
            "type": e.type,
            "value": e.value,
            "properties": dict(e.properties),
            "relations": relations_by_source.get(e.id, []),
            "user_note": e.user_note,
        })

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_nodes": len(entities),
        "total_edges": len(edges),
        "counts_by_type": dict(sorted(counts_by_type.items())),
        "entities": entities_data,
    }


# ---------------------------------------------------------------- HTML --

_HTML_STYLE = """
body { font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; margin: 2em auto; max-width: 900px; line-height: 1.5; }
h1 { color: #0a2540; border-bottom: 3px solid #00b3ad; padding-bottom: 8px; }
h2 { color: #0a2540; margin-top: 2em; border-left: 5px solid #d6006e; padding-left: 10px; }
.meta { color: #64748b; font-size: 0.9em; margin-bottom: 1.5em; }
table.summary { border-collapse: collapse; margin: 1em 0; }
table.summary td, table.summary th { border: 1px solid #cfd8e3; padding: 6px 12px; text-align: left; }
table.summary th { background: #0a2540; color: white; }
.entity-card { border: 1px solid #cfd8e3; border-radius: 6px; padding: 12px 16px; margin: 12px 0; background: #f7f9fb; }
.entity-title { font-weight: bold; font-size: 1.05em; color: #0a2540; }
.entity-type-badge { display: inline-block; background: #00b3ad; color: white; font-size: 0.75em; padding: 2px 8px; border-radius: 10px; margin-left: 8px; }
.props { margin: 8px 0 0 0; font-size: 0.92em; }
.props div { margin: 2px 0; }
.prop-key { color: #b3005c; }
.relations { margin-top: 8px; font-size: 0.92em; }
.relations ul { margin: 4px 0; padding-left: 20px; }
.user-note { margin-top: 8px; padding: 6px 10px; background: #fff8e1; border-left: 3px solid #ffb300; font-size: 0.92em; }
"""


def generate_html_report(model: GraphModel, path: str) -> None:
    data = build_report_data(model)

    summary_rows = "".join(
        f"<tr><td>{html.escape(t)}</td><td>{n}</td></tr>"
        for t, n in data["counts_by_type"].items()
    )

    entity_blocks = []
    current_type = None
    for e in data["entities"]:
        if e["type"] != current_type:
            current_type = e["type"]
            entity_blocks.append(f"<h2>{html.escape(current_type)}</h2>")

        props_html = "".join(
            f'<div><span class="prop-key">{html.escape(str(k))}:</span> {html.escape(str(v))}</div>'
            for k, v in e["properties"].items()
        )
        rel_items = "".join(
            f'<li>{html.escape(r["label"])} &rarr; <strong>{html.escape(r["target_type"])}</strong>: '
            f'{html.escape(r["target_value"])}</li>'
            for r in e["relations"]
        )
        relations_html = f'<div class="relations"><strong>Conexiones:</strong><ul>{rel_items}</ul></div>' if rel_items else ""
        note_html = (
            f'<div class="user-note"><strong>📝 Nota:</strong> {html.escape(e["user_note"])}</div>'
            if e["user_note"] else ""
        )

        entity_blocks.append(f"""
<div class="entity-card">
  <span class="entity-title">{html.escape(e['value'])}</span>
  <span class="entity-type-badge">{html.escape(e['type'])}</span>
  <div class="props">{props_html}</div>
  {relations_html}
  {note_html}
</div>""")

    html_doc = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Informe RobotEye</title>
<style>{_HTML_STYLE}</style>
</head><body>
<h1>Informe de investigación &mdash; RobotEye</h1>
<p class="meta">Generado el {data['generated_at']} &mdash; {data['total_nodes']} entidades, {data['total_edges']} relaciones.</p>

<h2>Resumen por tipo</h2>
<table class="summary">
<tr><th>Tipo</th><th>Cantidad</th></tr>
{summary_rows}
</table>

{''.join(entity_blocks)}
</body></html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html_doc)


# ----------------------------------------------------------------- PDF --

def generate_pdf_report(model: GraphModel, path: str) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    data = build_report_data(model)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TituloRobotEye", parent=styles["Title"], textColor=colors.HexColor("#0a2540"))
    h2_style = ParagraphStyle("H2RobotEye", parent=styles["Heading2"], textColor=colors.HexColor("#0a2540"),
                               spaceBefore=14, spaceAfter=6)
    meta_style = ParagraphStyle("MetaRobotEye", parent=styles["Normal"], textColor=colors.HexColor("#64748b"))
    entity_title_style = ParagraphStyle("EntityTitle", parent=styles["Heading3"], textColor=colors.HexColor("#0a2540"))
    normal_style = styles["Normal"]

    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=20 * mm, bottomMargin=18 * mm)
    story = [
        Paragraph("Informe de investigación &mdash; RobotEye", title_style),
        Paragraph(
            f"Generado el {data['generated_at']} &mdash; {data['total_nodes']} entidades, "
            f"{data['total_edges']} relaciones.",
            meta_style,
        ),
        Spacer(1, 10 * mm),
        Paragraph("Resumen por tipo", h2_style),
    ]

    summary_table_data = [["Tipo", "Cantidad"]] + [[t, str(n)] for t, n in data["counts_by_type"].items()]
    summary_table = Table(summary_table_data, colWidths=[80 * mm, 30 * mm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0a2540")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfd8e3")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fb")]),
    ]))
    story.append(summary_table)

    current_type = None
    for e in data["entities"]:
        if e["type"] != current_type:
            current_type = e["type"]
            story.append(Paragraph(html.escape(current_type), h2_style))

        block = [Paragraph(f"<b>{html.escape(e['value'])}</b>", entity_title_style)]
        for k, v in e["properties"].items():
            block.append(Paragraph(f"<b>{html.escape(str(k))}:</b> {html.escape(str(v))}", normal_style))
        if e["relations"]:
            rel_text = "<br/>".join(
                f"&rarr; {html.escape(r['label'])} &rarr; <b>{html.escape(r['target_type'])}</b>: "
                f"{html.escape(r['target_value'])}"
                for r in e["relations"]
            )
            block.append(Paragraph(f"<b>Conexiones:</b><br/>{rel_text}", normal_style))
        if e["user_note"]:
            block.append(Paragraph(f"<b>📝 Nota:</b> {html.escape(e['user_note'])}", normal_style))
        block.append(Spacer(1, 4 * mm))
        story.append(KeepTogether(block))

    doc.build(story)
