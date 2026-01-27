import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

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

LOG_PATH_ENV = "SIT3_LOG_PATH"
DEFAULT_LOG_PATH = os.path.join("logs", "trigger.log")


def get_log_path() -> str:
    return os.getenv(LOG_PATH_ENV, DEFAULT_LOG_PATH)


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("sit3.trigger")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    log_path = get_log_path()
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream_handler)

    logger.propagate = False
    return logger


LOGGER = setup_logger()


def current_timestamp() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def serialize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    return {str(key): str(value) for key, value in headers.items()}


def build_request_context(request: Request) -> Dict[str, Any]:
    return {
        "timestamp": current_timestamp(),
        "method": request.method,
        "path": request.url.path,
        "query_params": {key: value for key, value in request.query_params.items()},
        "request_headers": serialize_headers(request.headers),
    }


def log_json_event(
    logger: logging.Logger,
    payload: Dict[str, Any],
    level: int = logging.INFO,
) -> None:
    logger.log(level, json.dumps(payload, default=str))


def log_trigger_error(
    logger: logging.Logger,
    request_context: Dict[str, Any],
    target_url: str | None,
    status_code: int,
    error: Exception,
    error_message: str,
) -> None:
    payload = {
        **request_context,
        "event": "trigger_error",
        "target_url": target_url,
        "status_code": status_code,
        "error_type": type(error).__name__,
        "error_message": error_message,
    }
    log_json_event(logger, payload, logging.ERROR)


def log_trigger_success(
    logger: logging.Logger,
    request_context: Dict[str, Any],
    target_url: str,
    upstream_response: httpx.Response,
) -> None:
    payload = {
        **request_context,
        "event": "trigger_request",
        "target_url": target_url,
        "upstream_status": upstream_response.status_code,
        "upstream_headers": serialize_headers(upstream_response.headers),
    }
    log_json_event(logger, payload)


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
    request_context = build_request_context(request)
    target_url = os.getenv("SIT3_URL")
    if not target_url:
        error = HTTPException(status_code=500, detail="SIT3_URL is not set")
        log_trigger_error(
            LOGGER,
            request_context,
            target_url,
            error.status_code,
            error,
            str(error.detail),
        )
        raise error

    try:
        extra_headers = load_optional_headers()
    except ValueError as exc:
        error = HTTPException(status_code=500, detail=str(exc))
        log_trigger_error(
            LOGGER,
            request_context,
            target_url,
            error.status_code,
            exc,
            str(exc),
        )
        raise error from exc

    try:
        async with httpx.AsyncClient() as client:
            upstream_response = await client.get(
                target_url,
                params=dict(request.query_params),
                headers=extra_headers or None,
            )
    except httpx.HTTPError as exc:
        error = HTTPException(status_code=502, detail="Upstream request failed")
        log_trigger_error(
            LOGGER,
            request_context,
            target_url,
            error.status_code,
            exc,
            str(exc),
        )
        raise error from exc

    filtered_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    log_trigger_success(LOGGER, request_context, target_url, upstream_response)

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=filtered_headers,
    )
