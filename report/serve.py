"""The report with working undo buttons, on localhost only.

    python -m report.serve runs/ab-llm [port]
"""
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from agent.tools import undo_change
from job.workspace import Workspace
from report.build import render, write_report


def make_handler(path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = render(Workspace(path), live=True).encode()
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path == "/undo":
                form = parse_qs(self.rfile.read(int(self.headers["content-length"])).decode())
                ws = Workspace(path)
                undo_change(ws, form["change_id"][0], "undone from the report", by="human")
                write_report(ws)
            self.send_response(303)
            self.send_header("location", "/")
            self.send_header("content-length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    return Handler


def main():
    path = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    server = HTTPServer(("127.0.0.1", port), make_handler(path))
    print(f"http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
