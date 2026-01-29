# SIT3 Flask Proxy

A tiny Flask service that forwards `GET /trigger` to a downstream URL defined by `SIT3_URL`.

## Run locally

```bash
export SIT3_URL="https://example.com"
python run.py
```

Optional headers can be provided as JSON:

```bash
export SIT3_HEADERS_JSON='{"Authorization":"Bearer token"}'
python run.py
```

You can also use `flask run`:

```bash
export FLASK_APP=run.py
export FLASK_RUN_PORT=8000
flask run --host 0.0.0.0
```

## Run with Docker

```bash
docker build -t sit3-flask .
docker run --rm -p 8000:8000 \
  -e SIT3_URL="https://example.com" \
  -e SIT3_LOG_PATH="logs/trigger.log" \
  sit3-flask
```

Optional headers can be provided as JSON:

```bash
docker run --rm -p 8000:8000 \
  -e SIT3_URL="https://example.com" \
  -e SIT3_LOG_PATH="logs/trigger.log" \
  -e SIT3_HEADERS_JSON='{"Authorization":"Bearer token"}' \
  sit3-flask
```

## Run with Docker Compose

```bash
export SIT3_URL="https://example.com"
# Optional: export SIT3_HEADERS_JSON='{"Authorization":"Bearer token"}'
docker compose up --build
```

## Logging

Set `SIT3_LOG_PATH` to control the log file location (default: `logs/trigger.log`).
`/trigger` requests emit JSON logs to this file and the console. Log entries
include timestamp, request method/path, query params, headers, target URL,
upstream status/headers/body, and error details when failures occur.

## Test connection to `SIT3_URL`

```bash
curl -i http://localhost:8000/trigger
```

## Health check

```bash
curl -i http://localhost:8000/health
```
