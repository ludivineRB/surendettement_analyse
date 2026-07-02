# Surendettement Data Pipeline

Production-oriented Python pipeline to discover, download, clean, and store Banque de France over-indebtedness datasets.

## Project Structure

```text
project_root/
├── data/
│   ├── raw/
│   ├── processed/
│   └── external/
├── src/
│   ├── scraper/
│   │   ├── spider.py
│   │   ├── parser.py
│   │   └── downloader.py
│   ├── processing/
│   │   ├── clean.py
│   │   ├── transform.py
│   │   └── validation.py
│   ├── storage/
│   │   ├── database.py
│   │   └── models.py
│   └── utils/
│       ├── logger.py
│       └── config.py
├── notebooks/
├── tests/
├── requirements.txt
└── README.md
```

## Modules Overview

- `src/scraper/spider.py`: Recursively crawls Banque de France pages with domain + keyword filtering.
- `src/scraper/parser.py`: Extracts links and metadata (`year`, `region`, `dataset_type`).
- `src/scraper/downloader.py`: Downloads discovered files to `data/raw/` with naming convention:
  - `bdf_<year>_<type>.<ext>`
- `src/processing/*`: Cleaning, transformation, and basic validation helpers.
- `src/storage/*`: SQLAlchemy schema + persistence helpers (SQLite by default, PostgreSQL-ready via `DATABASE_URL`).
- `src/utils/*`: Runtime config and structured logging setup.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Environment variables:

- `BDF_BASE_URL` default: `https://www.banque-france.fr/fr`
- `BDF_ALLOWED_DOMAINS` default: `banque-france.fr,www.banque-france.fr`
- `BDF_KEYWORDS` default: `surendettement,statistiques,typologie,series annuelles,séries annuelles`
- `BDF_FILE_EXTENSIONS` default: `.xlsx,.csv,.pdf`
- `BDF_START_URLS` optional CSV list of seed pages (if invalid, crawler falls back to `BDF_BASE_URL`)
- `BDF_MAX_DEPTH` default: `3`
- `BDF_MAX_PAGES` default: `500`
- `DATABASE_URL` default: `sqlite:///data/processed/surendettement.db`

## Run Full Pipeline

Single command for end-to-end ingestion:

```bash
.venv/bin/python -m src.pipeline
```

What it does in order:

1. Crawl Banque de France pages
2. Discover downloadable XLSX/CSV/PDF files
3. Download files into `data/raw/`
4. Parse and normalize into unified schema
5. Export unified CSV to `data/processed/surendettement_unified.csv`
6. Load rows into SQLite table `surendettement_data`

Useful options:

```bash
# Process only first 20 discovered files
.venv/bin/python -m src.pipeline --max-files 20

# Re-process existing files in data/raw without crawling/downloading
.venv/bin/python -m src.pipeline --skip-crawl

# Resume mode (default): process only files not yet ingested in DB
.venv/bin/python -m src.pipeline --skip-crawl --max-files 200

# Force full reprocessing (including already ingested source_file names)
.venv/bin/python -m src.pipeline --skip-crawl --reprocess-all

# Enable debug logs
.venv/bin/python -m src.pipeline --log-level DEBUG
```

Default SQLite database file:

- `data/processed/surendettement.db`

Note:
- Invalid/corrupted PDFs are skipped with a warning and no longer stop the pipeline.

Switch to PostgreSQL (example):

```bash
export DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/surendettement"
.venv/bin/python -m src.pipeline --skip-crawl
```

## Quick Start: Scraper Discovery + Download

```python
from src.utils.logger import configure_logging
from src.scraper.spider import BanqueFranceSpider
from src.scraper.downloader import FileDownloader

configure_logging("INFO")

spider = BanqueFranceSpider()
result = spider.crawl()
print(f"Pages crawled: {len(result.pages)}")
print(f"Files found: {len(result.files)}")

downloader = FileDownloader()
downloaded = downloader.download_all(result.files)
print(f"Files downloaded: {len(downloaded)}")
```

## Testing

```bash
.venv/bin/python -m pytest -q
```

## Dashboard Streamlit

Le projet contient une première application Streamlit pour explorer les données de surendettement et les indicateurs macro-économiques par année et par département.

### Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Lancement

```bash
streamlit run app.py
```

### Configuration de l'API

Par défaut, le dashboard tente de lire l'API locale :

```text
http://127.0.0.1:8000/api/data/joined
```

Pour utiliser une autre URL, créer un fichier `.env` local :

```bash
SURENDETTEMENT_API_URL=http://127.0.0.1:8000/api/data/joined
SURENDETTEMENT_API_TIMEOUT=8
```

Si l'API ne répond pas, l'application utilise les fichiers locaux de `data/processed/`. Si ces fichiers sont absents, elle affiche un jeu de démonstration.

### Ajouter de nouvelles données macro-économiques

Ajouter ou remplacer un fichier au format CSV compatible avec :

- `reference_year`
- `departement_code`
- `departement_name`
- `indicator_code`
- `indicator_name`
- `value`

Le chemin utilisé par défaut est `data/processed/statinfo_departements_bi_curated.csv`. Les codes départements sont normalisés automatiquement pour fiabiliser la jointure avec les données de surendettement.
