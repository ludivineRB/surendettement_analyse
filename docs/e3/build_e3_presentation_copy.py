"""Build a review copy of the E3 presentation without changing the original."""

from __future__ import annotations

import copy
import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.lexers import PythonLexer, YamlLexer


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(
    "/home/utilisateur/Rédaction Certif/"
    "Support_soutenance_RNCP37827_Ludivine_Raby(1).odp"
)
OUTPUT = ROOT / "docs/e3/Support_soutenance_RNCP37827_E3_preuves.odp"

NS = {
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def code_image(code: str, lexer, title: str) -> Image.Image:
    formatter = ImageFormatter(
        font_name="DejaVu Sans Mono",
        font_size=20,
        line_numbers=True,
        style="monokai",
        image_pad=20,
    )
    rendered = Image.open(io.BytesIO(highlight(code, lexer, formatter))).convert("RGB")
    canvas = Image.new("RGB", (rendered.width, rendered.height + 54), "#18212b")
    canvas.paste(rendered, (0, 54))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 25)
    draw.text((20, 12), title, font=font, fill="#f4f7f8")
    return canvas


def composite(left: Image.Image, right: Image.Image) -> bytes:
    width = left.width + right.width + 20
    # Match the 31.367 × 15.288 cm image frame used by the presentation.
    # Padding prevents LibreOffice from stretching the code horizontally.
    height = round(width / (31.367 / 15.288))
    canvas = Image.new("RGB", (width, height), "#0f1720")
    canvas.paste(left, (0, (height - left.height) // 2))
    canvas.paste(right, (left.width + 20, (height - right.height) // 2))
    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join(paragraph.itertext()).strip()


def replace_paragraph(page: ET.Element, old: str, new: str) -> None:
    for paragraph in page.findall(".//text:p", NS):
        if paragraph_text(paragraph) != old:
            continue
        for child in list(paragraph):
            paragraph.remove(child)
        paragraph.text = new


def clear_repeated_note(page: ET.Element) -> None:
    for paragraph in page.findall(".//text:p", NS):
        if paragraph_text(paragraph).startswith(
            "« Cette diapositive distingue la validation de l’outil de mesure"
        ):
            for child in list(paragraph):
                paragraph.remove(child)
            paragraph.text = ""


def set_slide_image(page: ET.Element, href: str) -> None:
    image = page.find(".//draw:image", NS)
    if image is None:
        raise RuntimeError("La diapositive modèle ne contient aucune image.")
    image.set(f"{{{NS['xlink']}}}href", href)


def clone_proof_slide(template: ET.Element, name: str, title: str, subtitle: str, href: str) -> ET.Element:
    page = copy.deepcopy(template)
    page.set(f"{{{NS['draw']}}}name", name)
    replace_paragraph(page, "Une API REST contractuelle et protégée", title)
    replace_paragraph(
        page,
        "FastAPI orchestre les fonctions IA et renvoie une réponse structurée aux autres composants",
        subtitle,
    )
    replace_paragraph(page, "BLOC 1 • SYNTHÈSE", "BLOC 2 • E3")
    clear_repeated_note(page)
    set_slide_image(page, href)
    return page


def main() -> None:
    api_code = """app = FastAPI(title=\"Surendettement Business Assistant API\")

@app.get(\"/metrics/prometheus\", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    return prometheus.render() + render_evaluation_metrics()

@app.post(\"/v1/answers\", response_model=AnswerResponse)
def answer_question(
    request: AnswerRequest,
    engine: Engine = Depends(get_engine),
    _authenticated: None = Depends(require_internal_token),
) -> AnswerResponse:
    ..."""
    client_code = """class AssistantClient:
    def answer(self, question: str, *, mode=\"information\") -> dict:
        headers = {
            \"Accept\": \"application/json\",
            \"X-Internal-Token\": settings.ASSISTANT_INTERNAL_TOKEN,
        }
        try:
            response = self.session.post(
                f\"{self.base_url}/v1/answers\",
                json={\"question\": question, \"mode\": mode},
                timeout=self.timeout,
                headers=headers,
            )
            response.raise_for_status()
            return validate_answer(response.json())
        except requests.RequestException as exc:
            raise AssistantAPIError(
                \"L’assistant est temporairement indisponible.\"
            ) from exc"""
    monitoring_code = """@app.middleware(\"http\")
async def operational_metrics(request, call_next):
    started = monotonic()
    response = await call_next(request)
    labels = {
        \"method\": request.method,
        \"path\": request.url.path,
        \"status\": str(response.status_code),
    }
    prometheus.increment(\"assistant_http_requests_total\", **labels)
    prometheus.observe(
        \"assistant_http_request_duration_seconds\",
        monotonic() - started,
        **labels,
    )
    return response"""
    ci_code = """package-assistant:
  needs: validate
  steps:
    - name: Build versioned Assistant API image
      run: docker build --target assistant-api \\
        --tag surendettement-assistant:${{ github.sha }} .
    - name: Smoke test versioned image
      run: |
        docker run --detach --name assistant-smoke \\
          surendettement-assistant:${{ github.sha }}
        docker exec assistant-smoke python -c \\
          \"urllib.request.urlopen('http://localhost:8030/health')\"
    - name: Publish delivery artifact
      uses: actions/upload-artifact@v4"""

    proof_api = composite(
        code_image(api_code, PythonLexer(), "C9 — API FastAPI exposée"),
        code_image(client_code, PythonLexer(), "C10 — Intégration Django robuste"),
    )
    proof_ops = composite(
        code_image(monitoring_code, PythonLexer(), "C11 — Métriques du service IA"),
        code_image(ci_code, YamlLexer(), "C12–C13 — Tests, packaging et smoke test"),
    )

    with zipfile.ZipFile(SOURCE) as source_zip:
        content = ET.fromstring(source_zip.read("content.xml"))
        manifest = ET.fromstring(source_zip.read("META-INF/manifest.xml"))
        pages = content.findall(".//draw:page", NS)
        parent = next(node for node in content.iter() if pages[0] in list(node))

        for slide_number in range(24, 31):
            page = pages[slide_number - 1]
            replace_paragraph(page, "BLOC 1 • SYNTHÈSE", "BLOC 2 • E3")
            clear_repeated_note(page)

        template = pages[25]
        api_href = "Pictures/E3_preuve_code_api_integration.png"
        ops_href = "Pictures/E3_preuve_code_monitoring_ci.png"
        api_slide = clone_proof_slide(
            template,
            "E3 preuve code API et intégration",
            "Preuve code — API et intégration applicative",
            "Extraits ciblés : contrat REST, authentification, timeout et erreurs contrôlées",
            api_href,
        )
        ops_slide = clone_proof_slide(
            template,
            "E3 preuve code monitoring et livraison",
            "Preuve code — monitoring, tests et livraison",
            "Extraits ciblés : métriques Prometheus, image versionnée, health check et artifact",
            ops_href,
        )
        parent.insert(list(parent).index(pages[27]), api_slide)
        parent.insert(list(parent).index(pages[30]), ops_slide)

        root_manifest = manifest
        for href in (api_href, ops_href):
            entry = ET.SubElement(root_manifest, f"{{{NS['manifest']}}}file-entry")
            entry.set(f"{{{NS['manifest']}}}full-path", href)
            entry.set(f"{{{NS['manifest']}}}media-type", "image/png")

        content_bytes = ET.tostring(content, encoding="utf-8", xml_declaration=True)
        manifest_bytes = ET.tostring(manifest, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(OUTPUT, "w") as output_zip:
            for info in source_zip.infolist():
                if info.filename in {"content.xml", "META-INF/manifest.xml"}:
                    continue
                output_zip.writestr(info, source_zip.read(info.filename))
            output_zip.writestr("content.xml", content_bytes)
            output_zip.writestr("META-INF/manifest.xml", manifest_bytes)
            output_zip.writestr(api_href, proof_api)
            output_zip.writestr(ops_href, proof_ops)

    print(OUTPUT)


if __name__ == "__main__":
    main()
