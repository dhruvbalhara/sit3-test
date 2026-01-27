import json
import os
from typing import Dict

import httpx
from fastapi import FastAPI, HTTPException, Request
from starlette.responses import Response

app = FastAPI()

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
}


def load_optional_headers() -> Dict[str, str]:
    raw_headers = os.getenv("SIT3_HEADERS_JSON")
    if not raw_headers:
        return {}

    try:
        parsed = json.loads(raw_headers)
    except json.JSONDecodeError as exc:
        raise ValueError("SIT3_HEADERS_JSON must be valid JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("SIT3_HEADERS_JSON must be a JSON object")

    return {str(key): str(value) for key, value in parsed.items()}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/trigger")
async def trigger(request: Request) -> Response:
    target_url = os.getenv("SIT3_URL")
    if not target_url:
        raise HTTPException(status_code=500, detail="SIT3_URL is not set")

    try:
        extra_headers = load_optional_headers()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    async with httpx.AsyncClient() as client:
        upstream_response = await client.get(
            target_url,
            params=dict(request.query_params),
            headers=extra_headers or None,
        )

    filtered_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=filtered_headers,
    )
