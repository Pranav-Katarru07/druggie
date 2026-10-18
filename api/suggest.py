"""Vercel serverless version of server.py's POST /api/suggest.

Same prompt, model call and validation as the local server; settings come from the
Vercel project's environment variables (LLM_API_KEY, optionally LLM_BASE_URL and LLM_MODEL).
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server import handle_suggest  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        status, payload = handle_suggest(self.rfile.read(length))
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
