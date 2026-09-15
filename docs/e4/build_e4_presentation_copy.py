"""Add E4 code evidence to the previously enriched E3 presentation."""

from __future__ import annotations

import copy
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pygments.lexers import HtmlDjangoLexer, PythonLexer, YamlLexer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from docs.e3.build_e3_presentation_copy import (
    NS,
    clear_repeated_note,
    code_image,
    composite,
    replace_paragraph,
    set_slide_image,
)


SOURCE = ROOT / "docs/e3/Support_soutenance_RNCP37827_E3_preuves.odp"
OUTPUT = ROOT / "docs/e4/Support_soutenance_RNCP37827_E3_E4_preuves.odp"


def clone_proof_slide(
    template: ET.Element,
    *,
    name: str,
    title: str,
    subtitle: str,
    href: str,
) -> ET.Element:
    page = copy.deepcopy(template)
    page.set(f"{{{NS['draw']}}}name", name)
    replace_paragraph(page, "Preuve code — API et intégration applicative", title)
    replace_paragraph(
        page,
        "Extraits ciblés : contrat REST, authentification, timeout et erreurs contrôlées",
        subtitle,
    )
    replace_paragraph(page, "BLOC 2 • E3", "BLOC 3 • E4")
    clear_repeated_note(page)
    set_slide_image(page, href)
    return page


def main() -> None:
    dashboard_code = """@login_required
@permission_required(\"accounts.view_dashboard\", raise_exception=True)
def dashboard(request):
    client = AnalyticsClient()
    context = {
        \"score\": None,
        \"series\": [],
        \"region_ranking\": [],
        \"analytics_error\": None,
    }
    form = DashboardFilterForm(request.GET or defaults, ...)
    if not form.is_valid():
        return render(request, \"dashboard/index.html\", context)
    filters = form.cleaned_data
    context[\"series\"] = client.get_series(...)[\"series\"]
    return render(request, \"dashboard/index.html\", context)"""
    accessibility_code = """{% if analytics_error %}
  <div class=\"alert\" role=\"alert\">
    <strong>Impossible de récupérer les données.</strong>
    {{ analytics_error }}
  </div>
{% endif %}

<div class=\"map-controls\" aria-label=\"Paramètres de la carte\">
  <label for=\"map-level\">Niveau géographique</label>
  <select id=\"map-level\">...</select>
</div>
<div class=\"map-status\" role=\"status\" aria-live=\"polite\"></div>
<svg role=\"img\" aria-labelledby=\"france-map-title france-map-desc\">
  <title id=\"france-map-title\">Carte territoriale de France</title>
  <desc id=\"france-map-desc\">Sélectionnez un territoire...</desc>
</svg>"""
    ci_code = """- name: Validation
  run: sh docker/run_ci.sh

# docker/run_ci.sh
python -m ruff check app assistant_api src web tests
python -m pip_audit -r requirements.txt
docker compose --profile ci -f docker/compose.yaml build \\
  api assistant-api django ci
docker compose --profile ci -f docker/compose.yaml run --rm \\
  ci python -m pytest -q tests app/tests \\
  --junitxml=app/reports/ci/pytest.xml \\
  --cov-report=xml:app/reports/ci/coverage.xml
CONFIRM_LOCAL_MIGRATION=yes sh docker/test_postgres_migration.sh"""
    delivery_code = """deliver-application:
  needs: [validate, package-assistant]
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
  permissions:
    contents: read
    packages: write
  env:
    API_IMAGE: ghcr.io/ludivinerb/surendettement-api:${{ github.sha }}
    DJANGO_IMAGE: ghcr.io/ludivinerb/surendettement-django:${{ github.sha }}
    ASSISTANT_IMAGE: ghcr.io/ludivinerb/surendettement-assistant:${{ github.sha }}
  steps:
    - name: Smoke test delivery images
      run: wait_for_health delivery-api http://localhost:8020/health/live
    - name: Publish versioned application images
      run: |
        docker push \"$API_IMAGE\"
        docker push \"$DJANGO_IMAGE\"
        docker push \"$ASSISTANT_IMAGE\""""

    proof_app = composite(
        code_image(dashboard_code, PythonLexer(), "C14–C17 — Parcours protégé et données validées"),
        code_image(accessibility_code, HtmlDjangoLexer(), "C14–C17 — Accessibilité de l’interface"),
    )
    proof_delivery = composite(
        code_image(ci_code, PythonLexer(), "C18 — Contrôles et tests automatisés"),
        code_image(delivery_code, YamlLexer(), "C19 — Livraison des trois images au SHA"),
    )

    with zipfile.ZipFile(SOURCE) as source_zip:
        content = ET.fromstring(source_zip.read("content.xml"))
        manifest = ET.fromstring(source_zip.read("META-INF/manifest.xml"))
        pages = content.findall(".//draw:page", NS)
        parent = next(node for node in content.iter() if pages[0] in list(node))
        template = pages[27]  # Existing E3 code-proof slide.

        app_href = "Pictures/E4_preuve_code_application.png"
        delivery_href = "Pictures/E4_preuve_code_ci_livraison.png"
        app_slide = clone_proof_slide(
            template,
            name="E4 preuve code application",
            title="Preuve code — réalisation de l’application",
            subtitle="Extraits ciblés : contrôle d’accès, validation des entrées et accessibilité",
            href=app_href,
        )
        delivery_slide = clone_proof_slide(
            template,
            name="E4 preuve code intégration et livraison continues",
            title="Preuve code — intégration et livraison continues",
            subtitle="Extraits ciblés : qualité, tests, images versionnées, smoke tests et GHCR",
            href=delivery_href,
        )

        # Insert after C17, then after C19. Element lookup remains stable after insertion.
        parent.insert(list(parent).index(pages[38]), app_slide)
        parent.insert(list(parent).index(pages[41]), delivery_slide)

        for href in (app_href, delivery_href):
            entry = ET.SubElement(manifest, f"{{{NS['manifest']}}}file-entry")
            entry.set(f"{{{NS['manifest']}}}full-path", href)
            entry.set(f"{{{NS['manifest']}}}media-type", "image/png")

        with zipfile.ZipFile(OUTPUT, "w") as output_zip:
            for info in source_zip.infolist():
                if info.filename in {"content.xml", "META-INF/manifest.xml"}:
                    continue
                output_zip.writestr(info, source_zip.read(info.filename))
            output_zip.writestr(
                "content.xml",
                ET.tostring(content, encoding="utf-8", xml_declaration=True),
            )
            output_zip.writestr(
                "META-INF/manifest.xml",
                ET.tostring(manifest, encoding="utf-8", xml_declaration=True),
            )
            output_zip.writestr(app_href, proof_app)
            output_zip.writestr(delivery_href, proof_delivery)

    print(OUTPUT)


if __name__ == "__main__":
    main()
