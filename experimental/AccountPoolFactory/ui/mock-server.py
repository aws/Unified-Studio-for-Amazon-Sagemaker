#!/usr/bin/env python3
"""
Dev server for Account Pool Factory UI.

Two modes:
  python3 mock-server.py          # mock mode — fake data, no AWS calls
  python3 mock-server.py --live   # live mode — real AWS credentials injected

Hot reload: browser auto-reloads when any .html/.js/.css file changes.
            server auto-restarts when any .py file changes.

Then open:
    http://localhost:8080/pool-console/
    http://localhost:8080/project-creator/
"""

import http.server
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse

PORT = 8080
UI_DIR = os.path.dirname(os.path.abspath(__file__))
MOCK_DIR = os.path.join(UI_DIR, "mock")
LIVE_MODE = "--live" in sys.argv

# ── Hot reload ────────────────────────────────────────────────────────────────
# SSE clients waiting for reload signal
_sse_clients = []
_sse_lock = threading.Lock()
_reload_flag = threading.Event()

def _watch_files():
    """Background thread: watch UI files for changes."""
    mtimes = {}

    def scan():
        changed_py = False
        changed_ui = False
        for root, dirs, files in os.walk(UI_DIR):
            # Skip hidden dirs and __pycache__
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            for fname in files:
                if not any(fname.endswith(ext) for ext in ('.html', '.js', '.css', '.py', '.svg')):
                    continue
                path = os.path.join(root, fname)
                try:
                    mtime = os.stat(path).st_mtime
                except OSError:
                    continue
                if path in mtimes and mtimes[path] != mtime:
                    print(f"  🔄 Changed: {os.path.relpath(path, UI_DIR)}")
                    if fname.endswith('.py'):
                        changed_py = True
                    else:
                        changed_ui = True
                mtimes[path] = mtime
        return changed_py, changed_ui

    # Initial scan to populate mtimes
    scan()

    while True:
        time.sleep(0.5)
        changed_py, changed_ui = scan()
        if changed_py:
            print("  🔁 Python file changed — restarting server...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        if changed_ui:
            _reload_flag.set()
            with _sse_lock:
                for q in list(_sse_clients):
                    try:
                        q.set()
                    except Exception:
                        pass
            _reload_flag.clear()

threading.Thread(target=_watch_files, daemon=True).start()

sys.path.insert(0, MOCK_DIR)
import api as mock_api
if LIVE_MODE:
    import live_api

MIME = {
    ".html": "text/html",
    ".js":   "application/javascript",
    ".css":  "text/css",
    ".json": "application/json",
    ".png":  "image/png",
    ".ico":  "image/x-icon",
}

# ── Live config ───────────────────────────────────────────────────────────────

_live_cfg = None

def get_live_config():
    global _live_cfg
    if _live_cfg:
        return _live_cfg

    print("  🔑 Reading AWS credentials from environment...")

    # Verify credentials work
    try:
        identity = json.loads(subprocess.check_output(
            ["aws", "sts", "get-caller-identity", "--output", "json"],
            stderr=subprocess.DEVNULL
        ))
        account_id = identity["Account"]
    except Exception as e:
        print(f"  ❌ No valid AWS credentials: {e}")
        print("     Run: eval $(isengardcli credentials amirbo+3@amazon.com)")
        sys.exit(1)

    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")
    domain_id = ""
    portal_url = ""
    identity_store_id = ""
    org_admin_account_id = ""

    # Read 02-domain-account/config.yaml
    config_path = os.path.join(UI_DIR, "..", "02-domain-account/config.yaml")
    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            region = cfg.get("region", region)
            domain_id = cfg.get("domain_id", "")
            org_admin_account_id = cfg.get("org_admin_account_id", "")
            if not domain_id:
                domain_name = cfg.get("domain_name", "")
                if domain_name:
                    out = subprocess.check_output([
                        "aws", "datazone", "list-domains",
                        "--region", region,
                        "--query", f"items[?name=='{domain_name}'].id",
                        "--output", "text"
                    ], stderr=subprocess.DEVNULL).decode().strip()
                    domain_id = out.split()[0] if out else ""
        except Exception as e:
            print(f"  ⚠️  02-domain-account/config.yaml: {e}")

    # Get portal URL
    if domain_id:
        try:
            info = json.loads(subprocess.check_output([
                "aws", "datazone", "get-domain",
                "--identifier", domain_id,
                "--region", region, "--output", "json"
            ], stderr=subprocess.DEVNULL))
            portal_url = info.get("portalUrl", "")
        except Exception:
            pass

    # Get IDC identity store ID
    try:
        idc = json.loads(subprocess.check_output([
            "aws", "sso-admin", "list-instances",
            "--region", region, "--output", "json"
        ], stderr=subprocess.DEVNULL))
        instances = idc.get("Instances", [])
        if instances:
            identity_store_id = instances[0].get("IdentityStoreId", "")
    except Exception:
        pass

    _live_cfg = {
        "region": region,
        "domainId": domain_id,
        "portalUrl": portal_url,
        "dynamoTable": "AccountPoolFactory-AccountState",
        "accountId": account_id,
        "orgAdminAccountId": org_admin_account_id,
        "identityStoreId": identity_store_id,
        "accessKeyId": os.environ.get("AWS_ACCESS_KEY_ID", ""),
        "secretAccessKey": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        "sessionToken": os.environ.get("AWS_SESSION_TOKEN", ""),
    }

    print(f"  ✅ Account:  {account_id}")
    print(f"     Region:  {region}")
    print(f"     Domain:  {domain_id or '(not found — set domain_id in 02-domain-account/config.yaml)'}")
    print(f"     IDC:     {identity_store_id or '(not found)'}")
    return _live_cfg


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        status = args[0] if args else ""
        print(f"  {self.command:6} {self.path[:80]} → {status}")

    def send_json(self, status, data):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_js(self, text):
        body = text.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path):
        ext = os.path.splitext(path)[1]
        mime = MIME.get(ext, "text/plain")
        try:
            with open(path, "rb") as f:
                body = f.read()
            # Inject hot reload script into HTML files
            if ext == ".html":
                snippet = b"""<script>
(function(){
  const es = new EventSource('/__reload__');
  es.onmessage = () => location.reload();
  es.onerror = () => setTimeout(() => location.reload(), 1000);
})();
</script>"""
                body = body.replace(b"</body>", snippet + b"</body>")
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            try:
                return json.loads(self.rfile.read(length))
            except Exception:
                return {}
        return {}

    def handle_request(self, method):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Hot reload SSE endpoint
        if path == "/__reload__":
            evt = threading.Event()
            with _sse_lock:
                _sse_clients.append(evt)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                while True:
                    if evt.wait(timeout=25):
                        self.wfile.write(b"data: reload\n\n")
                        self.wfile.flush()
                        evt.clear()
                    else:
                        # Keepalive ping
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except Exception:
                pass
            finally:
                with _sse_lock:
                    try:
                        _sse_clients.remove(evt)
                    except ValueError:
                        pass
            return

        # CORS preflight
        if method == "OPTIONS":
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers",
                "Content-Type, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token, X-Amz-User-Agent")
            self.end_headers()
            return

        # config.js
        if path == "/config.js":
            if LIVE_MODE:
                c = get_live_config()
                self.send_js(f"""export const CONFIG = {{
  MOCK: false,
  API_URL: "http://localhost:{PORT}/api",
  region: "{c['region']}",
  domainId: "{c['domainId']}",
  portalUrl: "{c['portalUrl']}",
  dynamoTable: "{c['dynamoTable']}",
  identityStoreId: "{c['identityStoreId']}",
}};""")
            else:
                self.send_js(
                    f'export const CONFIG = {{ MOCK: true, API_URL: "http://localhost:{PORT}/api",'
                    f' portalUrl: "https://dzd-4h7jbz76qckoh5.sagemaker.us-east-2.on.aws",'
                    f' PORTAL_URL: "https://dzd-4h7jbz76qckoh5.sagemaker.us-east-2.on.aws" }};'
                )
            return

        # auth.js — no-op (live mode uses credentials from config.js directly)
        if path == "/auth.js":
            self.send_js(
                'export const Auth = { isAuthenticated: () => true, login: () => {}, logout: () => {} };'
            )
            return

        # API routes — mock or live
        if path.startswith("/api/"):
            full_path = path + ("?" + parsed.query if parsed.query else "")
            body = self.read_body() if method in ("POST", "PUT") else None
            if LIVE_MODE:
                try:
                    status, data = live_api.handle(method, full_path, body, get_live_config())
                except Exception as e:
                    import traceback
                    print(f"  ❌ Live API error: {e}")
                    traceback.print_exc()
                    status, data = 500, {"error": str(e)}
            else:
                status, data = mock_api.handle(method, full_path, body)
            self.send_json(status, data)
            return

        # Root redirect
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/pool-console/")
            self.end_headers()
            return

        if path.endswith("/"):
            path += "index.html"

        self.send_file(os.path.join(UI_DIR, path.lstrip("/")))

    def do_GET(self):     self.handle_request("GET")
    def do_POST(self):    self.handle_request("POST")
    def do_PUT(self):     self.handle_request("PUT")
    def do_DELETE(self):  self.handle_request("DELETE")
    def do_OPTIONS(self): self.handle_request("OPTIONS")


if __name__ == "__main__":
    import socketserver
    class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    mode_label = "LIVE (real AWS)" if LIVE_MODE else "MOCK (fake data)"
    print(f"Account Pool Factory UI — {mode_label}")
    print("=" * 44)
    if LIVE_MODE:
        get_live_config()  # validate early, print info
    print(f"  Pool Console    : http://localhost:{PORT}/pool-console/")
    print(f"  Project Creator : http://localhost:{PORT}/project-creator/")
    print(f"  Press Ctrl+C to stop")
    print()
    server = ThreadedServer(("", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
