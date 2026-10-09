"""
Local preview server for AirScribe Web Virtual Whiteboard.
Serves the web/ directory and opens the browser automatically.
"""

import os
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = int(os.environ.get("PORT", 8000))
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class CustomHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)


def main():
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, CustomHandler)
    url = f"http://localhost:{PORT}/"
    print("\n=======================================================")
    print("      AirScribe Web Virtual Whiteboard Server          ")
    print("=======================================================")
    print(f" Serving files from: {WEB_DIR}")
    print(f" URL: {url}")
    print(f" Listening on: 0.0.0.0:{PORT}")
    print(" Press Ctrl+C in this terminal to stop.")
    print("=======================================================\n")

    # Only auto-open browser in local desktop environments
    if "RENDER" not in os.environ and "PORT" not in os.environ:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[AirScribe] Web server stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
