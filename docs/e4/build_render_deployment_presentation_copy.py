"""Add the demonstrated Render deployment to the cumulative E3/E4 support."""

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
    replace_paragraph,
    set_slide_image,
)


SOURCE = ROOT / "docs/e4/Support_soutenance_RNCP37827_E3_E4_preuves.odp"
OUTPUT = ROOT / "docs/e4/Support_soutenance_RNCP37827_E3_E4_Render.odp"
ASPECT = 31.367 / 15.288
WIDTH = 1770
HEIGHT = round(WIDTH / ASPECT)

NAVY = "#102c36"
TEAL = "#008c82"
MINT = "#d9f3ef"
PALE = "#f3f8f7"
GREY = "#557078"
WHITE = "#ffffff"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(name, size)


def rounded_card(draw: ImageDraw.ImageDraw, box, title: str, lines: list[str]) -> None:
    draw.rounded_rectangle(box, radius=22, fill=WHITE, outline="#c9dfdc", width=3)
    x1, y1, _, _ = box
    draw.text((x1 + 25, y1 + 20), title, fill=NAVY, font=font(28, True))
    for index, line in enumerate(lines):
        draw.text((x1 + 25, y1 + 68 + index * 35), line, fill=GREY, font=font(22))


def arrow(draw: ImageDraw.ImageDraw, start, end) -> None:
    draw.line((start, end), fill=TEAL, width=7)
    x, y = end
    draw.polygon([(x, y), (x - 15, y - 11), (x - 15, y + 11)], fill=TEAL)


def architecture_diagram() -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), PALE)
    draw = ImageDraw.Draw(image)
    services = [
        ("WEB DJANGO", ["Comptes, dashboard", "et assistants"]),
        ("API ANALYTIQUE", ["Scores, séries", "et facteurs"]),
        ("ASSISTANT API", ["RAG, génération", "et Text-to-SQL"]),
        ("STREAMLIT", ["Interface analytique", "complémentaire"]),
    ]
    card_width, gap = 385, 45
    for index, (title, lines) in enumerate(services):
        x = 45 + index * (card_width + gap)
        rounded_card(draw, (x, 65, x + card_width, 255), title, lines)

    rounded_card(
        draw,
        (525, 555, 1245, 785),
        "POSTGRESQL 16 — INSTANCE PARTAGÉE",
        ["Données analytiques + comptes + conversations", "Corpus RAG + audits SQL + rôle analytics_readonly"],
    )
    draw.rounded_rectangle((1360, 575, 1715, 750), radius=22, fill=MINT, outline=TEAL, width=3)
    draw.text((1400, 610), "OPENAI", fill=NAVY, font=font(30, True))
    draw.text((1400, 660), "Fournisseur externe", fill=GREY, font=font(22))

    for index in range(4):
        x = 45 + index * (card_width + gap) + card_width // 2
        draw.line((x, 255, x, 420), fill=TEAL, width=6)
        draw.line((x, 420, 885, 420), fill=TEAL, width=6)
    draw.line((885, 420, 885, 555), fill=TEAL, width=6)
    draw.polygon([(885, 555), (873, 536), (897, 536)], fill=TEAL)
    arrow(draw, (1235, 350), (1530, 575))
    draw.text((65, 460), "Blueprint Render • plan gratuit • région Frankfurt • HTTPS *.onrender.com", fill=NAVY, font=font(27, True))
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()


def restoration_diagram() -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), PALE)
    draw = ImageDraw.Draw(image)
    steps = [
        ("1", "Blueprint sync", "Création des services\net de PostgreSQL"),
        ("2", "Initialisation", "Migrations SQL/Django\net collectstatic"),
        ("3", "Restauration", "pg_restore du dump\nlocal complet"),
        ("4", "Sécurisation", "Rôle analytics_readonly\nsur les vues autorisées"),
        ("5", "Recette", "Health checks, Swagger\net parcours Django"),
    ]
    x_positions = [55, 395, 735, 1075, 1415]
    for index, (number, title, body) in enumerate(steps):
        x = x_positions[index]
        draw.ellipse((x, 85, x + 74, 159), fill=TEAL)
        draw.text((x + 25, 100), number, fill=WHITE, font=font(32, True))
        if index < len(steps) - 1:
            arrow(draw, (x + 78, 122), (x_positions[index + 1] - 22, 122))
        rounded_card(draw, (x - 20, 195, x + 285, 420), title, body.splitlines())

    draw.rounded_rectangle((120, 525, 1650, 790), radius=26, fill=MINT, outline=TEAL, width=3)
    draw.text((165, 560), "CONTRÔLES APRÈS RESTAURATION", fill=NAVY, font=font(30, True))
    checks = [
        "3 utilisateurs",
        "2 superusers",
        "11 543 observations",
        "4 090 scores",
        "1 763 documents",
        "61 chunks assistant",
    ]
    for index, label in enumerate(checks):
        column = index % 3
        row = index // 3
        x, y = 165 + column * 495, 625 + row * 62
        draw.text((x, y), "✓", fill=TEAL, font=font(29, True))
        draw.text((x + 43, y), label, fill=NAVY, font=font(25, True))
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()


def clone_slide(template: ET.Element, name: str, title: str, subtitle: str, href: str) -> ET.Element:
    page = copy.deepcopy(template)
    page.set(f"{{{NS['draw']}}}name", name)
    replace_paragraph(page, "Preuve code — réalisation de l’application", title)
    replace_paragraph(
        page,
        "Extraits ciblés : contrôle d’accès, validation des entrées et accessibilité",
        subtitle,
    )
    set_slide_image(page, href)
    return page


def main() -> None:
    blueprint_code = """services:
  - type: web
    name: surendettement-staging-api
    runtime: docker
    plan: free
    region: frankfurt
    dockerCommand: python -m src.render_start api
    healthCheckPath: /health/live
    envVars:
      - key: DATABASE_URL
        fromDatabase: &database_connection
          name: surendettement-staging-db
          property: connectionString
  - type: web
    name: surendettement-staging-assistant
    dockerCommand: python -m src.render_start assistant
    healthCheckPath: /health/ready
  - type: web
    name: surendettement-staging-web
    dockerCommand: python -m src.render_start django"""
    start_code = """if service == \"api\":
    print(apply_migrations(), flush=True)
    _exec(\"uvicorn\", \"app.main:app\", \"--host\", bind_host, \"--port\", port)
elif service == \"assistant\":
    _run(sys.executable, \"-m\", \"assistant_api.cli\", \"migrate\")
    _exec(\"uvicorn\", \"assistant_api.main:app\", \"--host\", bind_host, \"--port\", port)
elif service == \"django\":
    _run(sys.executable, \"web/manage.py\", \"migrate\", \"--noinput\")
    _run(sys.executable, \"web/manage.py\", \"collectstatic\", \"--noinput\")
    _exec(\"uvicorn\", \"web.config.asgi:application\", \"--host\", bind_host, \"--port\", port)"""
    proof_code = composite(
        code_image(blueprint_code, YamlLexer(), "Blueprint — services et variables liées"),
        code_image(start_code, PythonLexer(), "Démarrage — migrations, statiques et Uvicorn"),
    )

    assets = {
        "Pictures/E4_Render_architecture.png": architecture_diagram(),
        "Pictures/E4_Render_restoration.png": restoration_diagram(),
        "Pictures/E4_Render_code.png": proof_code,
    }
    with zipfile.ZipFile(SOURCE) as source_zip:
        content = ET.fromstring(source_zip.read("content.xml"))
        manifest = ET.fromstring(source_zip.read("META-INF/manifest.xml"))
        pages = content.findall(".//draw:page", NS)
        parent = next(node for node in content.iter() if pages[0] in list(node))
        template = pages[38]

        c19 = pages[41]
        replace_paragraph(c19, "C19 — LIVRAISON ET DÉMONSTRATION", "C19 — LIVRAISON ET DÉPLOIEMENT")
        replace_paragraph(
            c19,
            "Livraison GHCR définie et smoke-testée dans le workflow ; run réussi sur main encore à capturer. Aucun déploiement distant prouvé.",
            "Livraison GHCR versionnée, puis déploiement Render par Blueprint. Base restaurée et services validés sur l’environnement distant.",
        )
        replace_paragraph(
            c19,
            "Le POC couvre le besoin de bout en bout et produit des preuves ; la production reste une étape distincte.",
            "Le staging Render couvre le parcours de bout en bout ; la haute disponibilité et l’exploitation de production restent hors périmètre du plan gratuit.",
        )

        slides = [
            clone_slide(
                template,
                "E4 déploiement Render architecture",
                "Déploiement Render — architecture du Blueprint",
                "Quatre services Docker reliés à PostgreSQL 16 et au fournisseur IA",
                "Pictures/E4_Render_architecture.png",
            ),
            clone_slide(
                template,
                "E4 déploiement Render restauration",
                "Déploiement Render — restauration et recette",
                "La base locale complète est restaurée, sécurisée puis contrôlée sur le staging",
                "Pictures/E4_Render_restoration.png",
            ),
            clone_slide(
                template,
                "E4 déploiement Render code",
                "Preuve code — Blueprint et démarrage Render",
                "Configuration versionnée sur tentative_deploiement : services, migrations et health checks",
                "Pictures/E4_Render_code.png",
            ),
        ]
        insertion = list(parent).index(pages[42])
        for offset, slide in enumerate(slides):
            parent.insert(insertion + offset, slide)

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
