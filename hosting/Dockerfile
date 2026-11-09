# Sideline on Hugging Face Spaces (a free Docker Space). Copy this file into the Space as
# "Dockerfile". It pulls the code from GitHub every time the Space builds, so the Space
# never needs its own copy of the code. Setup steps: hosting/README.md.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face runs every Space as user 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user

# The latest commit on GitHub. When it changes, everything below is rebuilt with the new code.
ADD https://api.github.com/repos/IanPierce57/sideline/commits/main /tmp/latest-commit.json
RUN git clone --depth 1 https://github.com/IanPierce57/sideline.git app
WORKDIR /home/user/app
RUN pip install --no-cache-dir --user -r requirements.txt

# New segments need the access code (a Space secret); at most 15 new segments a day, one at a time.
ENV HOST=0.0.0.0 PORT=7860 TZ=America/New_York PYTHONUNBUFFERED=1 \
    SIDELINE_DAILY_LIMIT=15 SIDELINE_MAX_AT_ONCE=1
EXPOSE 7860
CMD ["python", "server.py"]
