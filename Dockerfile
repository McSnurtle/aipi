FROM python:3.10

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# For caching apparently
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt --upgrade --verbose

COPY src ./src

EXPOSE 8000

CMD sh -c ': "${DB_ADDR:?DB_ADDR is required}" && : "${DB_PASS:?DB_ROOT_PASS is required}" && exec uvicorn src.main:app --host 0.0.0.0 --port 8000'