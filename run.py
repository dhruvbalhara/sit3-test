import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

import httpx
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

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


def build_request_context(flask_request) -> Dict[str, Any]:
    return {
        "timestamp": current_timestamp(),
        "method": flask_request.method,
        "path": flask_request.path,
        "query_params": flask_request.args.to_dict(flat=True),
        "request_headers": serialize_headers(flask_request.headers),
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
    upstream_headers: Dict[str, str] | None = None,
    upstream_body: str | None = None,
) -> None:
    payload = {
        **request_context,
        "event": "trigger_error",
        "target_url": target_url,
        "status_code": status_code,
        "error_type": type(error).__name__,
        "error_message": error_message,
    }
    if upstream_headers is not None:
        payload["upstream_headers"] = upstream_headers
    if upstream_body is not None:
        payload["upstream_body"] = upstream_body
    log_json_event(logger, payload, logging.ERROR)


def log_trigger_success(
    logger: logging.Logger,
    request_context: Dict[str, Any],
    target_url: str,
    upstream_response: httpx.Response,
    upstream_body: str | None = None,
) -> None:
    payload = {
        **request_context,
        "event": "trigger_request",
        "target_url": target_url,
        "upstream_status": upstream_response.status_code,
        "upstream_headers": serialize_headers(upstream_response.headers),
    }
    if upstream_body is not None:
        payload["upstream_body"] = upstream_body
    log_json_event(logger, payload)


def truncate_text(value: str, limit: int = 500) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def get_upstream_body(response: httpx.Response) -> str:
    try:
        return response.text
    except Exception:
        try:
            return response.content.decode("utf-8", errors="replace")
        except Exception:
            return ""


def build_upstream_error_message(response: httpx.Response) -> str:
    message = f"Upstream responded with status {response.status_code}"
    body_text = get_upstream_body(response).strip()

    if body_text:
        message = f"{message}: {truncate_text(body_text)}"

    return message


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
def health() -> Response:
    return jsonify(status="ok")


@app.get("/trigger")
def trigger() -> Response:
    request_context = build_request_context(request)
    target_url = os.getenv("SIT3_URL")
    if not target_url:
        error = RuntimeError("SIT3_URL is not set")
        log_trigger_error(
            LOGGER,
            request_context,
            target_url,
            500,
            error,
            str(error),
        )
        return jsonify(detail=str(error)), 500

    try:
        extra_headers = load_optional_headers()
    except ValueError as exc:
        log_trigger_error(
            LOGGER,
            request_context,
            target_url,
            500,
            exc,
            str(exc),
        )
        return jsonify(detail=str(exc)), 500

    try:
        with httpx.Client() as client:
            upstream_response = client.get(
                target_url,
                params=request.args.to_dict(flat=True),
                headers=extra_headers or None,
            )
    except httpx.HTTPError as exc:
        log_trigger_error(
            LOGGER,
            request_context,
            target_url,
            502,
            exc,
            str(exc),
        )
        return jsonify(detail="Upstream request failed"), 502

    filtered_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    upstream_body = get_upstream_body(upstream_response)
    upstream_headers = serialize_headers(upstream_response.headers)

    if upstream_response.status_code >= 400:
        error = RuntimeError("Upstream returned error status")
        log_trigger_error(
            LOGGER,
            request_context,
            target_url,
            upstream_response.status_code,
            error,
            build_upstream_error_message(upstream_response),
            upstream_headers,
            upstream_body,
        )
    else:
        log_trigger_success(
            LOGGER,
            request_context,
            target_url,
            upstream_response,
            upstream_body,
        )

    return Response(
        upstream_response.content,
        status=upstream_response.status_code,
        headers=filtered_headers,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
