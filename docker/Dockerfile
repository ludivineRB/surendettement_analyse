FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY requirements.txt .
COPY web/requirements.txt web-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r web-requirements.txt \
    && pip install --no-cache-dir "psycopg[binary]==3.2.3"

COPY app ./app
COPY assistant_api ./assistant_api
COPY web ./web
COPY src ./src
COPY config ./config
COPY tests ./tests
COPY models ./models
COPY app.py .

# Runtime and migration inputs only. Raw sources, local virtual environments,
# notebooks, caches, and unrelated processed datasets stay outside the image.
COPY data/metadata ./data/metadata
COPY data/processed/surendettement.db ./data/processed/surendettement.db
COPY data/processed/analytics ./data/processed/analytics
COPY data/processed/surendettement_unified.csv ./data/processed/surendettement_unified.csv
COPY data/processed/statinfo_departements_bi_curated.csv ./data/processed/statinfo_departements_bi_curated.csv

FROM runtime AS api
EXPOSE 8020
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8020"]

FROM python:3.12-slim AS assistant-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY assistant_api/requirements.txt assistant-requirements.txt
RUN pip install --no-cache-dir -r assistant-requirements.txt

COPY assistant_api ./assistant_api

FROM assistant-runtime AS assistant-api
EXPOSE 8030
CMD ["uvicorn", "assistant_api.main:app", "--host", "0.0.0.0", "--port", "8030"]

FROM runtime AS streamlit
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]

FROM runtime AS django
EXPOSE 8000
CMD ["python", "web/manage.py", "runserver", "0.0.0.0:8000"]
