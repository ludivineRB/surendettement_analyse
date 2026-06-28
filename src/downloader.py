import requests

from config import DOWNLOAD_DIR


def download(url: str):

    filename = url.split("/")[-1]

    output = DOWNLOAD_DIR / filename

    if output.exists():
        print(f"Already exists {filename}")
        return output

    r = requests.get(url, stream=True, timeout=600)

    r.raise_for_status()

    with open(output, "wb") as f:

        for chunk in r.iter_content(1024 * 1024):
            f.write(chunk)

    return output