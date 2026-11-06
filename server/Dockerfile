# Preview image. Build from the repository root:
#   docker build -f server/Dockerfile -t hablaia-voice-preview .
# Do not publish this image and do not point a production name at it.
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends libopus0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY server/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt
COPY server/hablaia_server /app/hablaia_server
COPY config /app/config

ENV PYTHONPATH=/app
USER nobody
EXPOSE 8787
CMD ["python", "-m", "hablaia_server"]
