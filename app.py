"""Morning Signal: a private, dependency-free local news reader."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent
APP_ID = "morning-signal"
INSTANCE_ID = hashlib.sha256(str(ROOT).lower().encode()).hexdigest()[:16]
MAX_BODY = 32_768


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, engine):
        self.engine = engine
        self.stopping = threading.Event()
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server: LocalServer
    protocol_version = "HTTP/1.1"

    def log_message(self, message, *args):
        logging.info("http %s %s", self.client_address[0], message % args)

    def _trusted_host(self):
        host = self.headers.get("Host", "")
        port = self.server.server_address[1]
        return host in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _trusted_write(self):
        if not self._trusted_host():
            return False
        origin = self.headers.get("Origin")
        port = self.server.server_address[1]
        if origin and origin not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}:
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            return False
        return self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() == "application/json"

    def _send(self, status, data, mime="application/json; charset=utf-8"):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if not self._trusted_host():
            return self._send(403, {"error": "Open Morning Signal using its local address."})
        path = urlsplit(self.path).path
        if path == "/api/health":
            return self._send(200, {"app": APP_ID, "instance": INSTANCE_ID, "version": "1.0.0"})
        if path == "/api/state":
            try:
                return self._send(200, self.server.engine.snapshot())
            except Exception:
                logging.exception("Could not load reader state")
                return self._send(500, {"error": "Could not load your stories. See data/app.log for details."})
        static_paths = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/index.html": ("index.html", "text/html; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/static/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/favicon.svg": ("favicon.svg", "image/svg+xml"),
        }
        entry = static_paths.get(path)
        if entry:
            file_path = ROOT / "static" / entry[0]
            if file_path.is_file():
                return self._send(200, file_path.read_bytes(), entry[1])
        return self._send(404, {"error": "This page does not exist."})

    def do_POST(self):
        if not self._trusted_write():
            self.close_connection = True
            return self._send(403, {"error": "This action must come from your local Morning Signal page."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0 or size > MAX_BODY:
                self.close_connection = True
                return self._send(413, {"error": "The request is too large."})
            payload = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("Expected a settings object.")
            path = urlsplit(self.path).path
            if path == "/api/refresh":
                return self._send(200, self.server.engine.start_refresh())
            if path == "/api/settings":
                return self._send(200, {"settings": self.server.engine.update_settings(payload)})
            if path == "/api/story":
                story_id = payload.get("id")
                if not isinstance(story_id, str) or not story_id or len(story_id) > 160:
                    raise ValueError("Choose a valid story.")
                if "saved" in payload and isinstance(payload["saved"], bool):
                    result = self.server.engine.toggle_saved(story_id, payload["saved"])
                elif "read" in payload and isinstance(payload["read"], bool):
                    result = self.server.engine.mark_read(story_id, payload["read"])
                else:
                    raise ValueError("Choose whether to save or mark the story read.")
                return self._send(200, {"story": result})
            if path == "/api/shutdown":
                self._send(200, {"stopped": True})
                self.server.stopping.set()
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self._send(404, {"error": "This action does not exist."})
        except (ValueError, TypeError, KeyError) as error:
            self._send(400, {"error": str(error)[:200] or "Check your request and try again."})
        except Exception:
            logging.exception("Could not complete reader action")
            self._send(500, {"error": "Could not complete that action. See data/app.log for details."})


def running_instance(port):
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.4) as response:
            data = json.loads(response.read(2048))
            return isinstance(data, dict) and data.get("app") == APP_ID and data.get("instance") == INSTANCE_ID
    except (URLError, OSError, ValueError):
        return False


def auto_refresh(server):
    """Refresh when stale, including once on startup, without blocking the UI."""
    from datetime import datetime, timezone

    while not server.stopping.is_set():
        try:
            state = server.engine.snapshot()
            refresh = state.get("refresh", {})
            last = refresh.get("finished_at") or refresh.get("last_success_at")
            interval = max(5, int(state.get("settings", {}).get("refresh_minutes", 60))) * 60
            age = float("inf")
            if last:
                stamp = datetime.fromisoformat(last.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - stamp).total_seconds()
            if age >= interval and not refresh.get("running"):
                server.engine.start_refresh()
        except Exception:
            logging.exception("Scheduled refresh failed")
        server.stopping.wait(30)


def main():
    parser = argparse.ArgumentParser(description="Your free local morning digest")
    parser.add_argument("--open", action="store_true", help="Open the reader in your default browser")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-refresh", action="store_true", help="Open cached stories without fetching feeds")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65525:
        parser.error("Choose a port between 1024 and 65525.")
    args.data_dir.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[RotatingFileHandler(args.data_dir / "app.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")])
    from news_engine import NewsEngine

    # Reopening the launcher reuses this folder's existing reader.
    for port in range(args.port, args.port + 10):
        if running_instance(port):
            if args.open:
                webbrowser.open(f"http://127.0.0.1:{port}")
            print(f"Morning Signal is already running: http://127.0.0.1:{port}", flush=True)
            return
    engine = NewsEngine(args.data_dir, ROOT / "sources.json")
    server = None
    for port in range(args.port, args.port + 10):
        try:
            server = LocalServer(("127.0.0.1", port), engine)
            break
        except OSError:
            continue
    if server is None:
        raise RuntimeError("Could not open a local port. Try python app.py --open --port 8875")
    url = f"http://127.0.0.1:{server.server_address[1]}"
    logging.info("Morning Signal started at %s", url)
    print(f"Morning Signal: {url}", flush=True)
    if not args.no_refresh:
        threading.Thread(target=auto_refresh, args=(server,), daemon=True).start()
    if args.open:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        server.stopping.set()
        server.server_close()
        logging.info("Morning Signal stopped")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Morning Signal could not start")
        raise
