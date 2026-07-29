FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "psycopg[binary]==3.2.3"

COPY . .

FROM runtime AS api
EXPOSE 8020
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8020"]

FROM runtime AS streamlit
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
