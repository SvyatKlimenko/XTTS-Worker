#!/usr/bin/env python3
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PORT = int(os.environ.get("PROXY_PORT", os.environ.get("PORT", "8888")))
TARGET = os.environ.get("PROXY_TARGET", "http://127.0.0.1:8889").rstrip("/")
TIMEOUT = int(os.environ.get("PROXY_TIMEOUT", "300"))


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stdout.write("[proxy] " + fmt % args + "\n")
        sys.stdout.flush()

    def do_GET(self):
        if self.path == "/ping":
            self._send_text(200, "ok")
            return
        self._proxy("GET", self.path)

    def do_POST(self):
        self._proxy("POST", self.path)

    def do_PUT(self):
        self._proxy("PUT", self.path)

    def do_DELETE(self):
        self._proxy("DELETE", self.path)

    def _proxy(self, method, path):
        body = None
        if method in {"POST", "PUT"}:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else None

        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"host", "content-length", "connection"}
        }
        url = TARGET + path
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = resp.read()
                self.send_response(resp.status)
                for key, value in resp.headers.items():
                    if key.lower() not in {"connection", "transfer-encoding"}:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as exc:
            data = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:
            data = f"Proxy error: {exc}".encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    def _send_text(self, status, text):
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    print(f"[proxy] Listening on 0.0.0.0:{PORT}, target={TARGET}", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), ProxyHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
