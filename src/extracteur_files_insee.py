from __future__ import annotations

import os
import re
import zipfile
import requests
import pandas as pd

from io import BytesIO
from bs4 import BeautifulSoup
from tqdm import tqdm

BASE_DIR = "data/insee_raw"
OUTPUT_FILE = "data/insee_macro_departements_2010_2025.csv"

os.makedirs(BASE_DIR, exist_ok=True)


# =========================================================
# 1. LISTE DES DATASETS OFFICIELS (POPULATION EXEMPLE)
# =========================================================

INSEE_DATASETS = {
    "population": "https://www.insee.fr/fr/statistiques/series/population",
    "logement": "https://www.insee.fr/fr/statistiques/series/logement",
    "emploi": "https://www.insee.fr/fr/statistiques/series/emploi",
    "revenus": "https://www.insee.fr/fr/statistiques/series/revenus",
    "entreprises": "https://www.insee.fr/fr/statistiques/series/entreprises",
}


# =========================================================
# 2. SCRAP PAGE -> ZIP/XLSX LINKS
# =========================================================

def extract_download_links(url: str):
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if any(ext in href for ext in ["zip", "xlsx", "csv"]):
            if href.startswith("/"):
                href = "https://www.insee.fr" + href
            links.append(href)

    return list(set(links))


# =========================================================
# 3. DOWNLOAD FILE
# =========================================================

def download_file(url: str, out_path: str):
    if os.path.exists(out_path):
        return out_path

    r = requests.get(url, timeout=60)
    r.raise_for_status()

    with open(out_path, "wb") as f:
        f.write(r.content)

    return out_path


# =========================================================
# 4. READ EXCEL / ZIP
# =========================================================

def read_insee_file(path: str):
    dfs = []

    if path.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            for file in z.namelist():
                if file.endswith(".xlsx") or file.endswith(".csv"):
                    with z.open(file) as f:
                        if file.endswith(".csv"):
                            df = pd.read_csv(f, sep=";", low_memory=False)
                        else:
                            df = pd.read_excel(f)
                        dfs.append(df)

    elif path.endswith(".xlsx"):
        dfs.append(pd.read_excel(path))

    elif path.endswith(".csv"):
        dfs.append(pd.read_csv(path, sep=";", low_memory=False))

    return dfs


# =========================================================
# 5. NORMALISATION DEPARTEMENT
# =========================================================

def standardize(df: pd.DataFrame, year: int, source: str):

    df = df.copy()

    # heuristique colonnes INSEE
    dept_col = None
    value_col = None
    var_col = None

    for c in df.columns:
        if "DEP" in c.upper() or "DEPART" in c.upper():
            dept_col = c
        if "VALEUR" in c.upper() or "VALUE" in c.upper():
            value_col = c
        if "LIB" in c.upper() or "TYPE" in c.upper():
            var_col = c

    if not dept_col or not value_col:
        return None

    out = pd.DataFrame()

    out["departement"] = df[dept_col].astype(str)
    out["value"] = pd.to_numeric(df[value_col], errors="coerce")

    out["variable"] = df[var_col] if var_col else "unknown"

    out["year"] = year
    out["source"] = source

    return out


# =========================================================
# 6. PIPELINE PRINCIPAL
# =========================================================

def build_dataset():

    all_data = []

    for theme, url in INSEE_DATASETS.items():

        print(f"\n🔎 Theme: {theme}")

        links = extract_download_links(url)

        for link in tqdm(links):

            try:
                filename = os.path.join(BASE_DIR, link.split("/")[-1])

                download_file(link, filename)

                dfs = read_insee_file(filename)

                # extraction année depuis nom fichier
                year_match = re.findall(r"(20\d{2})", filename)
                year = int(year_match[0]) if year_match else None

                for df in dfs:

                    cleaned = standardize(df, year, theme)

                    if cleaned is not None:
                        all_data.append(cleaned)

            except Exception as e:
                print(f"❌ error {link} -> {e}")

    final = pd.concat(all_data, ignore_index=True)

    final.to_csv(OUTPUT_FILE, index=False)

    print("\n✅ Dataset created:", OUTPUT_FILE)


# =========================================================
# 7. RUN
# =========================================================

if __name__ == "__main__":
    build_dataset()