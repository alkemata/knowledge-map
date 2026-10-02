#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1] / "frontend" / "dist"


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        clean = path.split("?", 1)[0].split("#", 1)[0]
        requested = ROOT / clean.lstrip("/")
        if requested.is_file():
            return str(requested)
        return str(ROOT / "index.html")

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; frame-src https://www.youtube-nocookie.com "
            "https://player.vimeo.com; frame-ancestors 'none'; base-uri 'self'",
        )
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print(format % args, flush=True)


os.chdir(ROOT)
ThreadingHTTPServer(("172.17.0.1", 18080), Handler).serve_forever()
