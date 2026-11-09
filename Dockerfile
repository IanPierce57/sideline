# The recipe for running Sideline online (Google Cloud Run builds this). Setup: hosting/README.md.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# New segments need the access code (set when it's deployed); at most 15 new segments a day,
# one at a time. Cloud Run sets PORT itself.
ENV HOST=0.0.0.0 PORT=8080 TZ=America/New_York PYTHONUNBUFFERED=1 \
    SIDELINE_DAILY_LIMIT=15 SIDELINE_MAX_AT_ONCE=1
CMD ["python", "server.py"]
