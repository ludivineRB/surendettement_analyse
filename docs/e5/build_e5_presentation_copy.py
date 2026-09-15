"""Correct and enrich E5 in the cumulative RNCP presentation."""

from __future__ import annotations

import copy
import io
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont
from pygments.lexers import PythonLexer, YamlLexer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from docs.e3.build_e3_presentation_copy import (  # noqa: E402
    NS,
    code_image,
    composite,
    paragraph_text,
    replace_paragraph,
    set_slide_image,
)


SOURCE = ROOT / "docs/e4/Support_soutenance_RNCP37827_E3_E4_Render.odp"
OUTPUT = ROOT / "docs/e5/Support_soutenance_RNCP37827_E3_E4_E5.odp"
WIDTH = 1770
HEIGHT = round(WIDTH / (31.367 / 15.288))
NAVY, TEAL, MINT, PALE, GREY, WHITE = (
    "#102c36", "#008c82", "#d9f3ef", "#f3f8f7", "#557078", "#ffffff"
)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)


def card(draw: ImageDraw.ImageDraw, box, title: str, lines: list[str], accent: bool = False) -> None:
    fill = MINT if accent else WHITE
    draw.rounded_rectangle(box, radius=22, fill=fill, outline=TEAL if accent else "#c9dfdc", width=3)
    x1, y1, _, _ = box
    draw.text((x1 + 24, y1 + 20), title, fill=NAVY, font=font(27, True))
    for index, line in enumerate(lines):
        draw.text((x1 + 24, y1 + 67 + 34 * index), line, fill=GREY, font=font(21))


def arrow(draw: ImageDraw.ImageDraw, start, end) -> None:
    draw.line((start, end), fill=TEAL, width=7)
    x, y = end
    draw.polygon([(x, y), (x - 17, y - 11), (x - 17, y + 11)], fill=TEAL)


def save_image(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def monitoring_diagram() -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), PALE)
    draw = ImageDraw.Draw(image)
    card(draw, (55, 80, 430, 290), "SERVICES", ["API analytique", "Assistant API", "Django", "PostgreSQL"])
    card(draw, (555, 80, 960, 290), "PROMETHEUS", ["Scrape toutes les 15 s", "Métriques HTTP et IA", "Évaluation RAG / SQL"], True)
    card(draw, (1090, 45, 1505, 220), "GRAFANA", ["7 panneaux", "métriques + logs"])
    card(draw, (1090, 270, 1505, 445), "ALERTMANAGER", ["groupement", "FIRING / RESOLVED"])
    arrow(draw, (430, 180), (555, 180))
    arrow(draw, (960, 150), (1090, 130))
    arrow(draw, (960, 220), (1090, 350))

    card(draw, (55, 555, 430, 750), "LOGS JSON", ["request_id", "method, path, status", "sans corps ni secret"])
    card(draw, (555, 555, 960, 750), "PROMTAIL + LOKI", ["collecte Docker", "rétention 360 h", "recherche par request_id"], True)
    card(draw, (1090, 555, 1505, 750), "GRAFANA EXPLORE", ["corrélation métrique/log", "diagnostic de l’incident"])
    arrow(draw, (430, 650), (555, 650))
    arrow(draw, (960, 650), (1090, 650))
    draw.text((85, 825), "C20 : détecter → alerter → diagnostiquer → corriger → vérifier le retour au nominal", fill=NAVY, font=font(28, True))
    return save_image(image)


def incident_diagram() -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), PALE)
    draw = ImageDraw.Draw(image)
    steps = [
        ("1 · DÉFAUT", ["Une seule génération", "SQL refusé ou vide", "arrêt du parcours"]),
        ("2 · DIAGNOSTIC", ["Validateur correct", "contexte incomplet", "aucune réparation"]),
        ("3 · CORRECTION", ["Motif transmis", "deux essais maximum", "garde-fous inchangés"]),
        ("4 · VALIDATION", ["2 tests ciblés", "44 tests du lot", "retour nominal"]),
    ]
    positions = [(45, 190, 405, 480), (475, 190, 835, 480), (905, 190, 1265, 480), (1335, 190, 1695, 480)]
    for index, ((title, lines), box) in enumerate(zip(steps, positions)):
        card(draw, box, title, lines, accent=index in {2, 3})
        if index < 3:
            arrow(draw, (box[2] + 5, 335), (positions[index + 1][0] - 10, 335))
    draw.rounded_rectangle((160, 610, 1610, 790), radius=24, fill=WHITE, outline="#c9dfdc", width=3)
    draw.text((205, 645), "PRINCIPE DE SÉCURITÉ CONSERVÉ", fill=NAVY, font=font(29, True))
    draw.text((205, 705), "Le modèle propose ; SQLGlot valide ; PostgreSQL exécute en lecture seule.", fill=GREY, font=font(27))
    return save_image(image)


def clone_slide(template: ET.Element, name: str, title: str, subtitle: str, href: str) -> ET.Element:
    page = copy.deepcopy(template)
    page.set(f"{{{NS['draw']}}}name", name)
    replace_paragraph(page, "Preuve code — réalisation de l’application", title)
    replace_paragraph(
        page,
        "Extraits ciblés : contrôle d’accès, validation des entrées et accessibilité",
        subtitle,
    )
    replace_paragraph(page, "BLOC 3 • E4", "BLOC 3 • E5")
    set_slide_image(page, href)
    return page


def set_status_badge(page: ET.Element, label: str, status: str) -> None:
    svg = "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
    shapes = list(page)
    label_shape = next(shape for shape in shapes if label in "".join(shape.itertext()))
    label_y = float(label_shape.get(f"{{{svg}}}y", "0cm")[:-2])
    label_x = float(label_shape.get(f"{{{svg}}}x", "0cm")[:-2])
    candidates = []
    for shape in shapes:
        text = "".join(shape.itertext()).strip()
        raw_y = shape.get(f"{{{svg}}}y")
        if text not in {"PARTIEL", "DÉMONTRÉ"} or not raw_y:
            continue
        shape_x = float(shape.get(f"{{{svg}}}x")[:-2])
        if abs(float(raw_y[:-2]) - label_y) < 0.6 and shape_x > label_x:
            candidates.append(shape)
    target = min(candidates, key=lambda shape: float(shape.get(f"{{{svg}}}x")[:-2]))
    paragraph = target.find(".//text:p", NS)
    for child in list(paragraph):
        paragraph.remove(child)
    paragraph.text = status


def remove_duplicated_threshold_layers(page: ET.Element) -> None:
    children = list(page)
    # The slide contains the same 43-shape content layer three times.
    for child in children[48:134]:
        page.remove(child)


def main() -> None:
    prometheus_code = """global:
  scrape_interval: 15s
scrape_configs:
  - job_name: assistant
    metrics_path: /metrics/prometheus
    static_configs:
      - targets: [\"assistant-api:8030\"]

# alerts.yml
- alert: SqlRejectionRateHigh
  expr: >-
    sum(rate(assistant_sql_executions_total{status=\"rejected\"}[15m]))
    / clamp_min(sum(rate(assistant_sql_executions_total[15m])), 0.001) > 0.25
  for: 15m
  labels: {severity: warning}"""
    metrics_code = """@app.get(\"/metrics/prometheus\", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    return prometheus.render() + render_evaluation_metrics()

labels = {
    \"method\": request.method,
    \"path\": request.url.path,
    \"status\": str(status),
}
prometheus.increment(\"assistant_http_requests_total\", **labels)
prometheus.observe(
    \"assistant_http_request_duration_seconds\",
    duration_ms / 1000,
    **labels,
)"""
    correction_code = """rejection_reason = None
for attempt in range(2):
    sql = generate_sql_candidate(
        question,
        generator,
        rejected_sql=sql or None,
        rejection_reason=rejection_reason,
    )
    try:
        execution = execute_readonly_sql(
            sql, engine=readonly_engine or get_readonly_engine()
        )
        if attempt == 0 and not execution.rows:
            rejection_reason = \"empty_result\"
            continue
        break
    except (SQLValidationError, ProgrammingError) as exc:
        if attempt == 1:
            raise
        rejection_reason = (
            exc.code if isinstance(exc, SQLValidationError)
            else \"invalid_postgresql\"
        )"""
    tests_code = """def test_invalid_generated_sql_is_corrected_once(...):
    generator.generate.side_effect = [forbidden_sql, corrected_sql]
    result = run_text_to_sql(...)
    assert result.sql_execution.rows == [{\"score\": 42}]
    assert generator.generate.call_count == 2
    assert \"table_forbidden\" in correction

def test_empty_result_is_retried_once(...):
    execute.side_effect = [empty_result, empty_result]
    result = run_text_to_sql(...)
    assert result.sql_execution.rows == []
    assert generator.generate.call_count == 2
    assert \"empty_result\" in user_prompt"""
    c20_code = composite(
        code_image(prometheus_code, YamlLexer(), "C20 — Collecte et seuil SQL"),
        code_image(metrics_code, PythonLexer(), "C20 — Endpoint et instrumentation"),
    )
    c21_code = composite(
        code_image(correction_code, PythonLexer(), "C21 — Réparation bornée à deux essais"),
        code_image(tests_code, PythonLexer(), "C21 — Tests de non-régression"),
    )
    assets = {
        "Pictures/E5_monitoring_architecture.png": monitoring_diagram(),
        "Pictures/E5_monitoring_code.png": c20_code,
        "Pictures/E5_incident_sequence.png": incident_diagram(),
        "Pictures/E5_incident_code.png": c21_code,
    }

    with zipfile.ZipFile(SOURCE) as source_zip:
        content = ET.fromstring(source_zip.read("content.xml"))
        manifest = ET.fromstring(source_zip.read("META-INF/manifest.xml"))
        pages = content.findall(".//draw:page", NS)
        parent = next(node for node in content.iter() if pages[0] in list(node))
        template = pages[38]

        replace_paragraph(
            pages[46],
            "Transition vers Livrer une application observable et maintenable.",
            "Dernière épreuve : démontrer la surveillance, le diagnostic et le retour au nominal.",
        )
        set_status_badge(pages[47], "Installation locale", "DÉMONTRÉ")
        set_status_badge(pages[47], "Documentation accessible", "DÉMONTRÉ")
        set_status_badge(pages[47], "Solution versionnée dans Git", "DÉMONTRÉ")
        remove_duplicated_threshold_layers(pages[49])
        replace_paragraph(
            pages[52],
            "À CAPTURER",
            "À AJOUTER : CAPTURE FIRING + RETOUR AU NOMINAL",
        )
        replace_paragraph(
            pages[53],
            "C21 — RÉCIT DE L’INCIDENT",
            "C21 — DÉFAUT TECHNIQUE IDENTIFIÉ ET REPRODUIT",
        )
        replace_paragraph(pages[53], "Symptôme observé", "Comportement reproduit")
        replace_paragraph(
            pages[53],
            "L’utilisateur pouvait recevoir une erreur ou une réponse vide alors qu’une correction restait possible.",
            "Impact potentiel : erreur ou réponse vide ; aucun utilisateur réellement touché n’est quantifié.",
        )

        monitoring_arch = clone_slide(
            template,
            "E5 architecture monitoring",
            "C20 — De la collecte au diagnostic",
            "Deux chaînes corrélées : métriques Prometheus et journaux Loki",
            "Pictures/E5_monitoring_architecture.png",
        )
        monitoring_proof = clone_slide(
            template,
            "E5 preuve code monitoring",
            "C20 — Preuve code du monitoring",
            "Endpoint Assistant, collecte Prometheus et seuil Text-to-SQL",
            "Pictures/E5_monitoring_code.png",
        )
        incident_arch = clone_slide(
            template,
            "E5 séquence incident",
            "C21 — Du défaut au retour nominal",
            "Diagnostic, correction bornée et validation sans assouplir la sécurité",
            "Pictures/E5_incident_sequence.png",
        )
        incident_proof = clone_slide(
            template,
            "E5 preuve code incident",
            "C21 — Preuve code de la correction",
            "Une seconde tentative au maximum et deux tests de non-régression",
            "Pictures/E5_incident_code.png",
        )

        # C20 proofs after tooling; C21 proofs between the narrative and resolution.
        first_insert = list(parent).index(pages[49])
        parent.insert(first_insert, monitoring_arch)
        parent.insert(first_insert + 1, monitoring_proof)
        second_insert = list(parent).index(pages[54])
        parent.insert(second_insert, incident_arch)
        parent.insert(second_insert + 1, incident_proof)

        for href in assets:
            entry = ET.SubElement(manifest, f"{{{NS['manifest']}}}file-entry")
            entry.set(f"{{{NS['manifest']}}}full-path", href)
            entry.set(f"{{{NS['manifest']}}}media-type", "image/png")

        with zipfile.ZipFile(OUTPUT, "w") as output_zip:
            for info in source_zip.infolist():
                if info.filename in {"content.xml", "META-INF/manifest.xml"}:
                    continue
                output_zip.writestr(info, source_zip.read(info.filename))
            output_zip.writestr("content.xml", ET.tostring(content, encoding="utf-8", xml_declaration=True))
            output_zip.writestr("META-INF/manifest.xml", ET.tostring(manifest, encoding="utf-8", xml_declaration=True))
            for href, payload in assets.items():
                output_zip.writestr(href, payload)
    print(OUTPUT)


if __name__ == "__main__":
    main()
