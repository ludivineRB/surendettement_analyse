import re
import requests
from bs4 import BeautifulSoup

PAGE_URL = "https://www.insee.fr/fr/statistiques/5359146"

html = requests.get(PAGE_URL, timeout=60).text
soup = BeautifulSoup(html, "html.parser")

downloads = []

for a in soup.find_all("a", href=True):
    href = a["href"]

    if any(ext in href.lower() for ext in [".zip", ".csv", ".xlsx"]):
        if href.startswith("/"):
            href = "https://www.insee.fr" + href

        downloads.append(href)

for url in sorted(set(downloads)):
    print(url)