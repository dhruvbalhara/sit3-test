# SIT3 FastAPI Proxy

A tiny FastAPI service that forwards `GET /trigger` to a downstream URL defined by `SIT3_URL`.

## Run with Docker

```bash
docker build -t sit3-fastapi .
docker run --rm -p 8000:8000 \
  -e SIT3_URL="https://example.com" \
  -e SIT3_LOG_PATH="logs/trigger.log" \
  sit3-fastapi
```

Optional headers can be provided as JSON:

```bash
docker run --rm -p 8000:8000 \
  -e SIT3_URL="https://example.com" \
  -e SIT3_LOG_PATH="logs/trigger.log" \
  -e SIT3_HEADERS_JSON='{"Authorization":"Bearer token"}' \
  sit3-fastapi
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
upstream status/headers, and error details when failures occur.

## Test connection to `SIT3_URL`

```bash
curl -i http://localhost:8000/trigger
```

## Health check

```bash
curl -i http://localhost:8000/health
```
