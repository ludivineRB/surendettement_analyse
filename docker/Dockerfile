FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY requirements.txt .
COPY pyproject.toml .
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
COPY benchmark ./benchmark
COPY models ./models
COPY app.py .

FROM runtime AS api
EXPOSE 8020
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8020"]

FROM runtime AS ci
COPY requirements-ci.txt requirements-ci.txt
COPY assistant_api/requirements.txt assistant-requirements.txt
RUN pip install --no-cache-dir -r requirements-ci.txt \
    && pip install --no-cache-dir -r assistant-requirements.txt
CMD ["python", "-m", "pytest", "-q"]

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
