"""Capability discovery and a bounded loopback proxy that keeps the real key out of workers."""
from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
import urllib.error
import urllib.request


class ProviderError(RuntimeError):
    pass


def api_base_url():
    return os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")


def endpoint(base_url, suffix):
    return base_url.rstrip("/") + "/" + suffix.lstrip("/")


def discover_models(api_key, base_url=None, timeout=20):
    if not api_key:
        raise ProviderError("DeepSeek credential is missing")
    request = urllib.request.Request(
        endpoint(base_url or api_base_url(), "models"),
        headers={"Authorization": "Bearer " + api_key, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"DeepSeek model discovery failed with HTTP {exc.code}") from None
    except Exception as exc:
        raise ProviderError(f"DeepSeek model discovery failed: {type(exc).__name__}") from None
    models = sorted({item["id"] for item in payload.get("data", []) if isinstance(item, dict) and isinstance(item.get("id"), str)})
    if not models:
        raise ProviderError("DeepSeek returned no usable model identifiers")
    return models


def select_models(models):
    available = set(models)
    flash = next((name for name in ("deepseek-flash", "deepseek-v4-flash") if name in available), None)
    pro = next((name for name in ("deepseek-v4-pro", "deepseek-pro") if name in available), None)
    if not flash:
        raise ProviderError("No supported DeepSeek Flash model is currently available")
    return {"flash": flash, "pro": pro}


def capabilities_path(runtime_directory):
    return Path(runtime_directory) / "capabilities.json"


def save_capabilities(runtime_directory, models, base_url=None):
    path = capabilities_path(runtime_directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"checked_at": time.time(), "base_url": (base_url or api_base_url()).rstrip("/"), "models": list(models), "selected": select_models(models)}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return value


def load_capabilities(runtime_directory, max_age_seconds=86400, base_url=None):
    path = capabilities_path(runtime_directory)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(value["checked_at"]) > max_age_seconds:
            return None
        if value.get("base_url") != (base_url or api_base_url()).rstrip("/"):
            return None
        select_models(value["models"])
        return value
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, ProviderError):
        return None


class BoundedCredentialProxy:
    """Forward one assigned model through a request-count/token bounded loopback endpoint."""

    def __init__(self, api_key, model, *, base_url=None, max_requests=24, max_tokens=8192, timeout=360, protocol="openai"):
        if not api_key:
            raise ProviderError("DeepSeek credential is missing")
        self._api_key = api_key
        self.model = model
        self.protocol = protocol
        if protocol == "anthropic":
            self.upstream = endpoint(base_url or (api_base_url() + "/anthropic"), "v1/messages")
        else:
            self.upstream = endpoint(base_url or api_base_url(), "chat/completions")
        self.max_requests = max_requests
        self.max_tokens = max_tokens
        self.timeout = timeout
        raw_token = secrets.token_urlsafe(32)
        self.token = "sk-ant-api03-" + raw_token if protocol == "anthropic" else raw_token
        self.path_token = secrets.token_urlsafe(24) if protocol == "anthropic" else None
        self.requests = 0
        self.forwarded_requests = 0
        self.errors = 0
        self.rate_limited = False
        self.last_error_code = None
        self.last_error_kind = None
        self.observed_model = None
        self.rejected_requests = 0
        self.last_rejected_path = None
        self.last_auth_kind = None
        self.last_auth_length = None
        self._lock = threading.Lock()
        self._server = None
        self._thread = None

    def __enter__(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *args):
                pass

            def send_bytes(self, status, body, content_type="application/json"):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def authorized(self):
                supplied = self.headers.get("Authorization", "")
                if hmac.compare_digest(supplied, "Bearer " + owner.token):
                    return True
                supplied_key = self.headers.get("x-api-key", "")
                return hmac.compare_digest(supplied_key, owner.token)

            def do_GET(self):
                allowed = (f"/{owner.path_token}/models", f"/{owner.path_token}/v1/models") if owner.protocol == "anthropic" else ("/models", "/v1/models")
                if self.path.split("?", 1)[0] not in allowed or (owner.protocol != "anthropic" and not self.authorized()):
                    owner.record_rejection(self)
                    self.send_bytes(403, b'{"error":"forbidden"}')
                    return
                body = json.dumps({"object": "list", "data": [{"id": owner.model, "object": "model", "owned_by": "deepseek"}]}).encode()
                self.send_bytes(200, body)

            def do_POST(self):
                allowed = (f"/{owner.path_token}/messages", f"/{owner.path_token}/v1/messages") if owner.protocol == "anthropic" else ("/chat/completions", "/v1/chat/completions")
                path_only = self.path.split("?", 1)[0]
                if path_only not in allowed or (owner.protocol != "anthropic" and not self.authorized()):
                    owner.record_rejection(self)
                    self.send_bytes(403, b'{"error":"forbidden"}')
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 8 * 1024 * 1024:
                        raise ValueError()
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        raise ValueError()
                except (ValueError, TypeError, json.JSONDecodeError):
                    self.send_bytes(400, b'{"error":"invalid request"}')
                    return
                with owner._lock:
                    if owner.rate_limited:
                        self.send_bytes(429, b'{"error":"upstream rate limit; retry later"}')
                        return
                    if owner.requests >= owner.max_requests:
                        self.send_bytes(429, b'{"error":"router request limit reached"}')
                        return
                    owner.requests += 1
                payload["model"] = owner.model
                owner.observed_model = owner.model
                requested = payload.get("max_tokens", owner.max_tokens)
                payload["max_tokens"] = min(requested, owner.max_tokens) if isinstance(requested, int) and requested > 0 else owner.max_tokens
                data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                headers = {"Content-Type": "application/json", "Accept": self.headers.get("Accept", "application/json")}
                if owner.protocol == "anthropic":
                    headers.update({"x-api-key": owner._api_key, "anthropic-version": "2023-06-01"})
                else:
                    headers["Authorization"] = "Bearer " + owner._api_key
                request = urllib.request.Request(
                    owner.upstream,
                    data=data,
                    headers=headers,
                    method="POST",
                )
                try:
                    with owner._lock:
                        owner.forwarded_requests += 1
                    with urllib.request.urlopen(request, timeout=owner.timeout) as response:
                        self.send_response(response.status)
                        self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        while True:
                            chunk = response.read(65536)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            self.wfile.flush()
                except urllib.error.HTTPError as exc:
                    with owner._lock:
                        owner.errors += 1
                        owner.last_error_code = exc.code
                        if exc.code == 429:
                            owner.rate_limited = True
                    self.send_bytes(exc.code, exc.read(65536), exc.headers.get("Content-Type", "application/json"))
                except Exception:
                    with owner._lock:
                        owner.errors += 1
                        owner.last_error_kind = "upstream_transport"
                    self.send_bytes(502, b'{"error":"provider connection failed"}')

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="deepseek-credential-proxy", daemon=True)
        self._thread.start()
        return self

    @property
    def base_url(self):
        suffix = "/" + self.path_token if self.protocol == "anthropic" else "/v1"
        return f"http://127.0.0.1:{self._server.server_port}{suffix}"

    @property
    def request_count(self):
        return self.forwarded_requests

    @property
    def error_count(self):
        return self.errors

    @property
    def error_code(self):
        return self.last_error_code

    @property
    def error_kind(self):
        return self.last_error_kind

    @property
    def received_count(self):
        return self.requests

    @property
    def model_seen(self):
        return self.observed_model

    def record_rejection(self, handler):
        with self._lock:
            self.rejected_requests += 1
            self.last_rejected_path = handler.path.split("?", 1)[0]
            if handler.headers.get("x-api-key"):
                self.last_auth_kind = "x-api-key"
                self.last_auth_length = len(handler.headers.get("x-api-key", ""))
            elif handler.headers.get("Authorization"):
                self.last_auth_kind = "authorization"
                self.last_auth_length = len(handler.headers.get("Authorization", ""))
            else:
                self.last_auth_kind = "none"
                self.last_auth_length = 0

    def __exit__(self, *_args):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=5)
        self._api_key = ""
