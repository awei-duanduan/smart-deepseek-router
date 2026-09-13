"""Short-lived loopback-only password form; no request/body logging."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import time
import urllib.error
import urllib.request
from credentials import save_key, runtime_dir
from provider_proxy import api_base_url, endpoint, save_capabilities

PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DeepSeek local setup</title>
<style>body{margin:0;background:#f4f6fa;color:#17243b;font:16px/1.7 system-ui,sans-serif}main{max-width:540px;margin:8vh auto;padding:36px;background:white;border:1px solid #dde3ed;border-radius:20px}h1{font-size:26px;margin-top:0}small,p{color:#53627a}input{box-sizing:border-box;width:100%;padding:14px;border:1px solid #a8b8cf;border-radius:8px;font-size:16px}button{margin-top:20px;padding:13px 22px;border:0;border-radius:8px;background:#244fd1;color:white;font-size:16px;cursor:pointer}#status{white-space:pre-wrap;margin-top:20px}a{color:#244fd1}</style>
<main><small>SMART DEEPSEEK ROUTER · LOCAL ONLY</small><h1>Configure a DeepSeek API key</h1><p>Enter an official DeepSeek API key. It stays on this Windows account.</p>
<form id="form"><label for="key">API key</label><input id="key" name="key" type="password" autocomplete="off" required maxlength="4096" placeholder="Enter it here; never paste it into chat"><button id="save">Encrypt, save, and verify</button></form>
<div id="status" role="status"></div><p><small>Windows DPAPI encrypts the key for the current user. Verification requests only the provider model list and sends no repository code.</small></p><p><a href="https://platform.deepseek.com/api_keys" target="_blank" rel="noreferrer">Create a DeepSeek API key</a></p></main>
<script>document.getElementById('form').onsubmit=async e=>{e.preventDefault();const k=document.getElementById('key'),b=document.getElementById('save'),s=document.getElementById('status');b.disabled=true;s.textContent='Saving and verifying…';try{let r=await fetch(location.pathname,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k.value})});k.value='';let d=await r.json();s.textContent=d.message;if(d.saved){document.getElementById('form').hidden=true;}}catch(e){s.textContent='The local setup page has closed. Ask Codex to open it again.';}finally{b.disabled=false;}};</script></html>'''


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--state", required=True, help="Non-secret status JSON for the configuring task")
    args = p.parse_args()
    if os.name != "nt":
        p.error("Local encrypted storage uses Windows DPAPI. Set DEEPSEEK_API_KEY in your secure environment on this platform.")
    state_path = Path(args.state).resolve()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    state = {"saved": False, "authenticated": False, "started_at": time.time()}

    def persist():
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(state_path)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, code, data, kind="application/json; charset=utf-8"):
            payload = data.encode("utf-8") if isinstance(data, str) else json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def valid(self):
            return self.path == "/" + token and self.headers.get("Host") == host

        def do_GET(self):
            self.respond(200, PAGE, "text/html; charset=utf-8") if self.valid() else self.respond(404, {"message": "Page not found."})

        def do_POST(self):
            if not self.valid() or self.headers.get("Origin") != "http://" + host or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.respond(403, {"message": "Use the local setup page."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise ValueError()
                key = json.loads(self.rfile.read(length)).get("key", "").strip()
                if not 8 <= len(key) <= 4096 or any(c.isspace() for c in key):
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                self.respond(400, {"message": "Enter a complete API key."})
                return
            try:
                request = urllib.request.Request(endpoint(api_base_url(), "models"), headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
                with urllib.request.urlopen(request, timeout=20) as response:
                    data = json.load(response)
                models = [m["id"] for m in data.get("data", []) if isinstance(m, dict) and isinstance(m.get("id"), str)]
                authenticated = True
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    self.respond(400, {"message": "DeepSeek rejected this key. Check it and try again; it was not saved."})
                    return
                authenticated, models = False, []
            except Exception:
                authenticated, models = False, []
            try:
                save_key(key)
                if authenticated:
                    save_capabilities(runtime_dir(), models)
            except Exception:
                self.respond(500, {"message": "Windows encryption failed. The key was not written to the status log."})
                return
            key = ""
            state.update(saved=True, authenticated=authenticated, models=models, saved_at=time.time())
            persist()
            message = "Encrypted and saved. DeepSeek authentication succeeded; return to Codex." if authenticated else "Encrypted and saved, but online verification could not finish. Return to Codex and run doctor --online."
            self.respond(200, {"saved": True, "message": message})

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 1
    host = "127.0.0.1:" + str(server.server_port)
    state["url"] = "http://" + host + "/" + token
    persist()
    try:
        while not state["saved"] and time.time() - state["started_at"] < 1200:
            server.handle_request()
    finally:
        server.server_close()
        state["server_closed"] = True
        persist()


if __name__ == "__main__":
    main()
