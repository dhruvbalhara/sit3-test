# SIT3 FastAPI Proxy

A tiny FastAPI service that forwards `GET /trigger` to a downstream URL defined by `SIT3_URL`.

## Run with Docker

```bash
docker build -t sit3-fastapi .
docker run --rm -p 8000:8000 \
  -e SIT3_URL="https://example.com" \
  sit3-fastapi
```

Optional headers can be provided as JSON:

```bash
docker run --rm -p 8000:8000 \
  -e SIT3_URL="https://example.com" \
  -e SIT3_HEADERS_JSON='{"Authorization":"Bearer token"}' \
  sit3-fastapi
```

## Run with Docker Compose

```bash
export SIT3_URL="https://example.com"
# Optional: export SIT3_HEADERS_JSON='{"Authorization":"Bearer token"}'
docker compose up --build
```

## Test connection to `SIT3_URL`

```bash
curl -i http://localhost:8000/trigger
```

## Health check

```bash
curl -i http://localhost:8000/health
```
