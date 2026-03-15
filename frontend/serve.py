import http.server
import socketserver
import webbrowser
import os

PORT = 8080
os.chdir(os.path.dirname(os.path.abspath(__file__)))

handler = http.server.SimpleHTTPRequestHandler
handler.extensions_map.update({
    '.js':  'application/javascript',
    '.css': 'text/css',
    '.html':'text/html',
})

print(f"✅ Serving on http://localhost:{PORT}")
print("   Open Chrome and go to: http://localhost:8080/index.html")
print("   Press Ctrl+C to stop.\n")

webbrowser.open(f"http://localhost:{PORT}/index.html")

with socketserver.TCPServer(("", PORT), handler) as httpd:
    httpd.serve_forever()