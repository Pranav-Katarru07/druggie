"""Vercel stand-in for server.py's POST /api/log.

Locally that endpoint prints the case on screen to the server's terminal; a deployed
function has no terminal to print to, so it just acknowledges the request.
"""
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(204)
        self.end_headers()
